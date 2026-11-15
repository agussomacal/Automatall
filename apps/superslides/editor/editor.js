// ============================================================
// editor/editor.js — The editor manager (FINAL version).
// Changes vs the earlier draft:
//  - listens for 'slide-content-changed' (full re-render) and
//    'slide-thumbnail-changed' (thumbnail only) events dispatched
//    by element modules, so elements never import this file.
//  - renderToolbarButtons() no longer wipes static toolbar content.
// ============================================================

import { state, markDirty } from '../core/state.js';
import { ElementRegistry } from '../core/registry.js';
import {
    applyCommonBoxStyles,
    getGridSvgDataUri,
    updateDimensionsCSS,
    syncSlideSizeSelect,
    syncGridSizeSelect,
    escapeHtml,
} from '../core/render.js';
import { startDragOrResize, updateResizeCursor, gridSteps } from '../core/geometry.js';
import { saveAndExitTextEditing } from '../elements/text/text.js';

// ---------- Toolbar (built from the registry) ----------

export function renderToolbarButtons() {
    const container = document.querySelector('.editor-toolbar');
    if (!container) return;
    // Remove only previously generated buttons, keep static controls.
    container.querySelectorAll('[data-role="add-element"]').forEach(n => n.remove());

    const anchor = container.querySelector('button:not([data-role])');
    ElementRegistry.types().forEach(def => {
        const btn = document.createElement('button');
        btn.className = 'toolbar-btn';
        btn.setAttribute('data-role', 'add-element');
        btn.onclick = () => addElement(def.type);
        btn.innerHTML = `<span>${def.icon}</span> ${escapeHtml(def.label)}`;
        container.insertBefore(btn, anchor);
    });
}

// ---------- Element lifecycle ----------

export function addElement(type) {
    const slide = state.slides[state.currentSlideIndex];
    if (!slide) return;

    const def = ElementRegistry.get(type);
    if (!def) {
        console.error(`No element registered for type '${type}'`);
        return;
    }

    const stagger = slide.elements.length * 30;
    const el = {
        ...def.defaults({}),
        x: 200 + stagger,
        y: 200 + stagger,
    };

    slide.elements.push(el);
    state.selectedElementIndex = slide.elements.length - 1;
    markDirty();
    renderEditor();
}

function updateProp(propName, value) {
    const slide = state.slides[state.currentSlideIndex];
    if (state.selectedElementIndex === null || !slide) return;
    const el = slide.elements[state.selectedElementIndex];

    if (['x', 'y', 'width', 'height', 'fontSize', 'borderWidth'].includes(propName)) {
        el[propName] = Number(value);
    } else {
        el[propName] = value;
    }

    markDirty();
    renderCanvas();
    updateThumbnailLive();
}
window.updateProp = updateProp;

// ---------- Thumbnails ----------

function buildThumbElement(el) {
    const thumbEl = document.createElement('div');
    const def = ElementRegistry.get(el.type);
    thumbEl.className = `thumb-element ${def ? def.className : 'element-shape'}`;
    thumbEl.style.left = `${el.x}px`;
    thumbEl.style.top = `${el.y}px`;
    thumbEl.style.width = `${el.width}px`;
    thumbEl.style.height = `${el.height}px`;
    applyCommonBoxStyles(thumbEl, el);

    if (def) {
        def.renderDom(thumbEl, el, { context: 'thumb', elIndex: -1 });
    }
    return thumbEl;
}

export function updateThumbnailLive() {
    const activeContainer = document.querySelectorAll('.thumb-container')[state.currentSlideIndex];
    if (!activeContainer) return;
    const scaler = activeContainer.querySelector('.thumb-canvas-scaler');
    if (!scaler) return;

    scaler.innerHTML = '';
    state.slides[state.currentSlideIndex].elements.forEach(el => {
        scaler.appendChild(buildThumbElement(el));
    });
}

// ---------- Canvas ----------

function renderCanvas() {
    const canvas = document.getElementById('slide-canvas');
    canvas.innerHTML = '';

    const { stepX, stepY } = gridSteps();

    if (state.gridSize > 0) {
        canvas.style.backgroundImage = getGridSvgDataUri(state.slideWidth, state.slideHeight, state.gridSize, state.isDarkMode);
        canvas.style.backgroundSize = '100% 100%';
        canvas.style.backgroundPosition = '0px 0px';
        canvas.style.width = `${state.slideWidth}px`;
        canvas.style.height = `${state.slideHeight}px`;
    } else {
        canvas.style.backgroundImage = 'none';
    }

    const slide = state.slides[state.currentSlideIndex];
    if (!slide) return;

    slide.elements.forEach((el, elIndex) => {
        const def = ElementRegistry.get(el.type);
        const domEl = document.createElement('div');
        domEl.className = `canvas-element ${def ? def.className : 'element-shape'}`;
        if (state.selectedElementIndex === elIndex) {
            domEl.classList.add('selected');
        }

        applyCommonBoxStyles(domEl, el);

        if (def) {
            def.renderDom(domEl, el, { context: 'canvas', elIndex });
        }

        domEl.onmousemove = (e) => {
            if (domEl.classList.contains('editing-mode')) return;
            updateResizeCursor(domEl, el, e);
        };

        domEl.onmousedown = (e) => {
            if (domEl.classList.contains('editing-mode')) return;
            if (state.selectedElementIndex !== elIndex) {
                state.selectedElementIndex = elIndex;
                renderCanvas();
                renderPropertiesPanel();
                return;
            }

            startDragOrResize(domEl, el, e, {
                onGeometryChanged() {
                    const xInput = document.getElementById('prop-x');
                    const yInput = document.getElementById('prop-y');
                    if (xInput) xInput.value = Math.round(el.x);
                    if (yInput) yInput.value = Math.round(el.y);
                },
                onFinish(hasDragged, isResizing) {
                    if (hasDragged) markDirty();
                    renderPropertiesPanel();
                    if (hasDragged && !isResizing) {
                        renderEditor();
                    }
                },
            });
            e.stopPropagation();
        };

        canvas.appendChild(domEl);
    });
}

// Canvas background click deselects.
document.getElementById('slide-canvas').addEventListener('click', (e) => {
    if (e.target.id === 'slide-canvas') {
        state.selectedElementIndex = null;
        renderCanvas();
        renderPropertiesPanel();
    }
});

// Clicking outside an editing text box commits it.
window.addEventListener('click', (e) => {
    const editingEl = document.querySelector('.canvas-element.editing-mode');
    if (editingEl && !editingEl.contains(e.target)) {
        const slide = state.slides[state.currentSlideIndex];
        if (slide && slide.elements[state.selectedElementIndex]) {
            saveAndExitTextEditing(editingEl, slide.elements[state.selectedElementIndex]);
        }
    }
});

// ---------- Element-module notifications (no import cycles) ----------
// 'slide-content-changed': content/props changed materially — full re-render.
// 'slide-thumbnail-changed': lightweight change — thumbnail only.
document.addEventListener('slide-content-changed', () => {
    renderCanvas();
    renderPropertiesPanel();
    updateThumbnailLive();
});
document.addEventListener('slide-thumbnail-changed', () => {
    updateThumbnailLive();
});

// ---------- Properties panel ----------

function renderPropertiesPanel() {
    const panelBody = document.getElementById('properties-body');
    const slide = state.slides[state.currentSlideIndex];

    if (state.selectedElementIndex === null || !slide || !slide.elements[state.selectedElementIndex]) {
        panelBody.innerHTML = `<div class="no-selection">Select an object on the canvas to inspect and customize its properties.</div>`;
        return;
    }

    const el = slide.elements[state.selectedElementIndex];
    const def = ElementRegistry.get(el.type);
    const typeLabel = def ? def.label.replace(/^Add\s+/i, '') : el.type;

    let html = `
        <div class="prop-group">
            <label>Object Type</label>
            <input type="text" class="prop-control" value="${escapeHtml(typeLabel)}" disabled style="opacity: 0.6;">
        </div>
        <div class="prop-row">
            <div class="prop-group">
                <label>X Position</label>
                <input type="number" id="prop-x" class="prop-control" value="${Math.round(el.x)}" oninput="updateProp('x', this.value)">
            </div>
            <div class="prop-group">
                <label>Y Position</label>
                <input type="number" id="prop-y" class="prop-control" value="${Math.round(el.y)}" oninput="updateProp('y', this.value)">
            </div>
        </div>
        <div class="prop-row">
            <div class="prop-group">
                <label>Width</label>
                <input type="number" class="prop-control" value="${Math.round(el.width)}" oninput="updateProp('width', this.value)">
            </div>
            <div class="prop-group">
                <label>Height</label>
                <input type="number" class="prop-control" value="${Math.round(el.height)}" oninput="updateProp('height', this.value)">
            </div>
        </div>
    `;

    if (def) {
        html += def.properties(el, state.selectedElementIndex);
    }

    html += `
        <div style="border-top: 1px solid var(--border-color); padding-top: 12px; margin-top: 4px;"></div>
        <div class="prop-group">
            <label>Background Color</label>
            <input type="color" class="prop-control" value="${el.bg === 'transparent' ? '#ffffff' : el.bg}" style="height: 34px; padding: 2px;" oninput="updateProp('bg', this.value)">
        </div>
        <div class="prop-row">
            <div class="prop-group">
                <label>Border Color</label>
                <input type="color" class="prop-control" value="${el.borderCol === 'transparent' ? '#000000' : el.borderCol}" style="height: 34px; padding: 2px;" oninput="updateProp('borderCol', this.value)">
            </div>
            <div class="prop-group">
                <label>Border Width (px)</label>
                <input type="number" class="prop-control" min="0" max="20" value="${el.borderWidth}" oninput="updateProp('borderWidth', this.value)">
            </div>
        </div>
        <div class="prop-group">
            <label>Border Style</label>
            <select class="prop-control" onchange="updateProp('borderStyle', this.value)">
                <option value="solid" ${el.borderStyle === 'solid' ? 'selected' : ''}>Solid</option>
                <option value="dashed" ${el.borderStyle === 'dashed' ? 'selected' : ''}>Dashed</option>
                <option value="dotted" ${el.borderStyle === 'dotted' ? 'selected' : ''}>Dotted</option>
                <option value="none" ${el.borderStyle === 'none' ? 'selected' : ''}>None</option>
            </select>
        </div>
    `;

    panelBody.innerHTML = html;
}

// ---------- Editor frame ----------

export function renderEditor() {
    updateDimensionsCSS();
    syncGridSizeSelect();
    syncSlideSizeSelect();
    renderToolbarButtons();

    const thumbList = document.getElementById('slides-thumb-list');
    thumbList.innerHTML = '';

    state.slides.forEach((slide, idx) => {
        const container = document.createElement('div');
        container.className = `thumb-container ${idx === state.currentSlideIndex ? 'active' : ''}`;
        container.onclick = () => selectSlide(idx);

        const labelRow = document.createElement('div');
        labelRow.className = 'thumb-label-row';
        labelRow.innerHTML = `<span>${escapeHtml(slide.title)}</span><span>${idx + 1}</span>`;

        const thumb = document.createElement('div');
        thumb.className = 'slide-thumb';

        const scaler = document.createElement('div');
        scaler.className = 'thumb-canvas-scaler';

        slide.elements.forEach(el => {
            scaler.appendChild(buildThumbElement(el));
        });

        thumb.appendChild(scaler);
        container.appendChild(labelRow);
        container.appendChild(thumb);
        thumbList.appendChild(container);
    });

    const addThumb = document.createElement('div');
    addThumb.className = 'slide-thumb-add';
    addThumb.onclick = () => addSlide();
    addThumb.innerHTML = `
        <span style="font-size: 16px; font-weight: bold;">+</span>
        <span>Add Slide</span>`;
    thumbList.appendChild(addThumb);

    renderCanvas();
    renderPropertiesPanel();
}

// ---------- Slide operations ----------

export function addSlide() {
    const newSlideId = state.slides.length + 1;
    state.slides.push({ id: newSlideId, title: `Slide ${newSlideId}`, elements: [] });
    state.currentSlideIndex = state.slides.length - 1;
    state.selectedElementIndex = null;
    markDirty();
    renderEditor();
}

export function selectSlide(index) {
    state.currentSlideIndex = index;
    state.selectedElementIndex = null;
    renderEditor();
}
