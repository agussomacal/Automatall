// ============================================================
// editor/editor.js — The editor manager.
// Supports single & multi-selection for both slides and elements,
// group dragging & arrow-key nudging, cut/copy/paste, and deletion.
// ============================================================

import {
    state,
    markDirty,
    flashSaveIndicator,
    getSelectedElementIndices,
    setSelectedElementIndices,
    getSelectedSlideIndices,
    setSelectedSlideIndices,
} from '../core/state.js';
import { ElementRegistry } from '../core/registry.js';
import {
    applyCommonBoxStyles,
    getGridSvgDataUri,
    updateDimensionsCSS,
    syncSlideSizeSelect,
    syncGridSizeSelect,
    escapeHtml,
} from '../core/render.js';
import { startDragOrResize, updateResizeCursor, gridSteps, snapToGridPoint } from '../core/geometry.js';
import { saveAndExitTextEditing } from '../elements/text/text.js';

// ---------- Toolbar (built from the registry) ----------

export function renderToolbarButtons() {
    const container = document.querySelector('.editor-toolbar');
    if (!container) return;
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
    setSelectedElementIndices([slide.elements.length - 1], slide.elements.length - 1);
    setSelectedSlideIndices([state.currentSlideIndex]);
    markDirty();
    renderEditor();
}

function updateProp(propName, value) {
    const slide = state.slides[state.currentSlideIndex];
    const indices = getSelectedElementIndices();
    if (indices.length === 0 || !slide) return;

    const numericProps = ['x', 'y', 'width', 'height', 'fontSize', 'borderWidth'];
    const parsedVal = numericProps.includes(propName) ? Number(value) : value;

    const primaryIdx = (state.selectedElementIndex !== null && indices.includes(state.selectedElementIndex))
        ? state.selectedElementIndex
        : indices[0];
    const primaryEl = slide.elements[primaryIdx];
    const prevVal = primaryEl ? primaryEl[propName] : undefined;

    if (propName === 'x' || propName === 'y') {
        const delta = Number(parsedVal) - Number(prevVal);
        indices.forEach(idx => {
            if (slide.elements[idx]) {
                slide.elements[idx][propName] = Number(slide.elements[idx][propName]) + delta;
            }
        });
    } else {
        indices.forEach(idx => {
            if (slide.elements[idx]) {
                slide.elements[idx][propName] = parsedVal;
            }
        });
    }

    markDirty();
    renderCanvas();
    updateThumbnailLive();
}
window.updateProp = updateProp;

export function moveSelectedElementsByArrow(key, altKey = false) {
    const slide = state.slides[state.currentSlideIndex];
    const indices = getSelectedElementIndices();
    if (!slide || indices.length === 0) return false;

    const { stepX, stepY } = gridSteps();
    const baseStepX = altKey ? 1 : (state.gridSize > 0 ? stepX : 10);
    const baseStepY = altKey ? 1 : (state.gridSize > 0 ? stepY : 10);

    let dx = 0;
    let dy = 0;
    if (key === 'ArrowLeft') dx = -baseStepX;
    else if (key === 'ArrowRight') dx = baseStepX;
    else if (key === 'ArrowUp') dy = -baseStepY;
    else if (key === 'ArrowDown') dy = baseStepY;
    else return false;

    indices.forEach(idx => {
        const el = slide.elements[idx];
        if (!el) return;
        let nextX = el.x + dx;
        let nextY = el.y + dy;
        if (!altKey && state.gridSize > 0) {
            nextX = snapToGridPoint(nextX, stepX);
            nextY = snapToGridPoint(nextY, stepY);
        }
        el.x = nextX;
        el.y = nextY;
    });

    markDirty();
    renderCanvas();
    renderPropertiesPanel();
    updateThumbnailLive();
    return true;
}

export function deleteSelectedElements(showFlash = false) {
    const slide = state.slides[state.currentSlideIndex];
    const indices = getSelectedElementIndices();
    if (!slide || indices.length === 0) return false;

    const toRemove = new Set(indices);
    slide.elements = slide.elements.filter((_, idx) => !toRemove.has(idx));
    setSelectedElementIndices([], null);
    markDirty();
    renderEditor();
    if (showFlash) {
        flashSaveIndicator(indices.length > 1 ? `${indices.length} objects removed ✓` : 'Object removed ✓');
    }
    return true;
}

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

    gridSteps();

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

    const selectedSet = new Set(getSelectedElementIndices());
    const renderedItems = [];

    slide.elements.forEach((el, elIndex) => {
        const def = ElementRegistry.get(el.type);
        const domEl = document.createElement('div');
        domEl.className = `canvas-element ${def ? def.className : 'element-shape'}`;
        if (selectedSet.has(elIndex)) {
            domEl.classList.add('selected');
        }

        applyCommonBoxStyles(domEl, el);

        if (def) {
            def.renderDom(domEl, el, { context: 'canvas', elIndex });
        }

        renderedItems.push({ el, domEl, elIndex });

        domEl.onmousemove = (e) => {
            if (domEl.classList.contains('editing-mode')) return;
            updateResizeCursor(domEl, el, e);
        };

        domEl.onmousedown = (e) => {
            if (domEl.classList.contains('editing-mode')) return;
            e.stopPropagation();

            const multiToggle = e.ctrlKey || e.metaKey;
            let currentSelected = getSelectedElementIndices();

            if (multiToggle) {
                if (currentSelected.includes(elIndex)) {
                    currentSelected = currentSelected.filter(i => i !== elIndex);
                    const nextPrimary = currentSelected.length > 0 ? currentSelected[currentSelected.length - 1] : null;
                    setSelectedElementIndices(currentSelected, nextPrimary);
                } else {
                    setSelectedElementIndices([...currentSelected, elIndex], elIndex);
                }
                renderCanvas();
                renderPropertiesPanel();
                return;
            }

            if (!currentSelected.includes(elIndex)) {
                setSelectedElementIndices([elIndex], elIndex);
                renderCanvas();
                renderPropertiesPanel();
                const freshDom = canvas.children[elIndex];
                if (!freshDom) return;
                startDragOrResize(freshDom, el, e, {
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
                return;
            }

            state.selectedElementIndex = elIndex;
            const groupItems = renderedItems
                .filter(item => getSelectedElementIndices().includes(item.elIndex))
                .map(item => ({ el: item.el, domEl: item.domEl }));

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
            }, groupItems);
        };

        canvas.appendChild(domEl);
    });
}

// Canvas background click clears element selection so slide is active.
document.getElementById('slide-canvas').addEventListener('click', (e) => {
    if (e.target.id === 'slide-canvas') {
        setSelectedElementIndices([], null);
        setSelectedSlideIndices([state.currentSlideIndex]);
        renderCanvas();
        renderPropertiesPanel();
        updateSlideThumbSelectionUI();
    }
});

// Clicking outside an editing text box commits it.
window.addEventListener('click', (e) => {
    const editingEl = document.querySelector('.canvas-element.editing-mode');
    if (editingEl && !editingEl.contains(e.target)) {
        const slide = state.slides[state.currentSlideIndex];
        if (slide && state.selectedElementIndex !== null && slide.elements[state.selectedElementIndex]) {
            saveAndExitTextEditing(editingEl, slide.elements[state.selectedElementIndex]);
        }
    }
});

// ---------- Element-module notifications (no import cycles) ----------
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
    const selectedIndices = getSelectedElementIndices();

    if (selectedIndices.length === 0 || !slide) {
        panelBody.innerHTML = `<div class="no-selection">Select an object on the canvas to inspect and customize its properties.</div>`;
        return;
    }

    if (selectedIndices.length > 1) {
        const firstEl = slide.elements[selectedIndices[0]];
        panelBody.innerHTML = `
            <div class="prop-group">
                <label>Selection</label>
                <input type="text" class="prop-control" value="${selectedIndices.length} objects selected" disabled style="opacity: 0.7;">
            </div>
            <p style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">
                Drag or use <strong>Arrow keys</strong> to move all ${selectedIndices.length} objects together, <strong>Ctrl+X / Ctrl+C / Ctrl+V</strong> to cut/copy/paste, or <strong>Delete</strong> to remove.
            </p>
            <div style="border-top: 1px solid var(--border-color); padding-top: 12px; margin-top: 4px;"></div>
            <div class="prop-group">
                <label>Background Color (All Selected)</label>
                <input type="color" class="prop-control" value="${firstEl.bg === 'transparent' ? '#ffffff' : firstEl.bg}" style="height: 34px; padding: 2px;" oninput="updateProp('bg', this.value)">
            </div>
            <div class="prop-row">
                <div class="prop-group">
                    <label>Border Color</label>
                    <input type="color" class="prop-control" value="${firstEl.borderCol === 'transparent' ? '#000000' : firstEl.borderCol}" style="height: 34px; padding: 2px;" oninput="updateProp('borderCol', this.value)">
                </div>
                <div class="prop-group">
                    <label>Border Width</label>
                    <input type="number" class="prop-control" min="0" max="20" value="${firstEl.borderWidth}" oninput="updateProp('borderWidth', this.value)">
                </div>
            </div>
        `;
        return;
    }

    const activeIdx = selectedIndices[0];
    const el = slide.elements[activeIdx];
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
        html += def.properties(el, activeIdx);
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

// ---------- Thumbnails & Slide selection ----------

function updateSlideThumbSelectionUI() {
    const selectedSet = new Set(getSelectedSlideIndices());
    document.querySelectorAll('.thumb-container').forEach((container, idx) => {
        container.classList.toggle('active', idx === state.currentSlideIndex);
        container.classList.toggle('selected', selectedSet.has(idx));
    });
}

export function renderEditor() {
    updateDimensionsCSS();
    syncGridSizeSelect();
    syncSlideSizeSelect();
    renderToolbarButtons();

    const thumbList = document.getElementById('slides-thumb-list');
    thumbList.innerHTML = '';

    const selectedSlideSet = new Set(getSelectedSlideIndices());

    state.slides.forEach((slide, idx) => {
        const container = document.createElement('div');
        container.className = `thumb-container ${idx === state.currentSlideIndex ? 'active' : ''} ${selectedSlideSet.has(idx) ? 'selected' : ''}`;
        container.onclick = (e) => {
            if (e.ctrlKey || e.metaKey) {
                toggleSlideSelection(idx);
            } else {
                selectSlide(idx);
            }
        };

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
    const newIdx = state.slides.length - 1;
    state.currentSlideIndex = newIdx;
    setSelectedSlideIndices([newIdx]);
    setSelectedElementIndices([], null);
    markDirty();
    renderEditor();
}

export function selectSlide(index) {
    if (index < 0 || index >= state.slides.length) return;
    state.currentSlideIndex = index;
    setSelectedSlideIndices([index]);
    setSelectedElementIndices([], null);
    renderEditor();
}

export function toggleSlideSelection(index) {
    if (index < 0 || index >= state.slides.length) return;
    let current = getSelectedSlideIndices();
    if (current.includes(index)) {
        if (current.length > 1) {
            current = current.filter(i => i !== index);
            setSelectedSlideIndices(current);
            if (state.currentSlideIndex === index) {
                state.currentSlideIndex = current[0];
            }
        }
    } else {
        setSelectedSlideIndices([...current, index]);
        state.currentSlideIndex = index;
    }
    setSelectedElementIndices([], null);
    renderEditor();
}

export function extendSlideSelectionByArrow(delta) {
    if (!Array.isArray(state.slides) || state.slides.length === 0) return false;
    const currentIdx = Math.max(0, Math.min(state.currentSlideIndex, state.slides.length - 1));
    const nextIdx = Math.max(0, Math.min(state.slides.length - 1, currentIdx + delta));

    const existing = getSelectedSlideIndices();
    const merged = [...new Set([...existing, currentIdx, nextIdx])].sort((a, b) => a - b);

    state.currentSlideIndex = nextIdx;
    setSelectedSlideIndices(merged);
    setSelectedElementIndices([], null);
    renderEditor();
    return true;
}

export function deleteSelectedSlides(showFlash = true) {
    // Only allowed when no element on the current slide is active/selected
    if (getSelectedElementIndices().length > 0) return false;

    const toDelete = getSelectedSlideIndices();
    if (toDelete.length === 0 || state.slides.length === 0) return false;

    const removeSet = new Set(toDelete);
    const remaining = state.slides.filter((_, idx) => !removeSet.has(idx));

    if (remaining.length === 0) {
        state.slides = [{ id: 1, title: 'Slide 1', elements: [] }];
        state.currentSlideIndex = 0;
        setSelectedSlideIndices([0]);
    } else {
        state.slides = remaining;
        const firstDeleted = Math.min(...toDelete);
        state.currentSlideIndex = Math.max(0, Math.min(firstDeleted, state.slides.length - 1));
        setSelectedSlideIndices([state.currentSlideIndex]);
    }

    setSelectedElementIndices([], null);
    markDirty();
    renderEditor();
    if (showFlash) {
        flashSaveIndicator(toDelete.length > 1 ? `${toDelete.length} slides deleted ✓` : 'Slide deleted ✓');
    }
    return true;
}