// ============================================================
// core/render.js — FINAL version. Changes vs the draft:
//  - markDirty imported statically (no dynamic-import hack).
//  - markDirtyAndRender uses the bound callback synchronously.
//  - removed the bogus _noopPlaceholder export.
// ============================================================

import { state, markDirty } from './state.js';

// ---------- Markdown + KaTeX ----------

export function renderMarkdownAndKatex(element, rawText) {
    let html = rawText || '';
    if (window.marked && typeof window.marked.parse === 'function') {
        try {
            html = window.marked.parse(rawText || '', { breaks: true, gfm: true });
        } catch (e) {
            console.error('Markdown parsing error:', e);
        }
    }
    element.innerHTML = html;
    if (window.renderMathInElement) {
        try {
            renderMathInElement(element, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\(', right: '\\)', display: false },
                    { left: '\\[', right: '\\]', display: true },
                ],
                macros: state.projectMacros,
                throwOnError: false,
            });
        } catch (e) {
            console.error('KaTeX rendering error:', e);
        }
    }
}

export function renderMarkdownAndKatexToString(el) {
    const tempDiv = document.createElement('div');
    renderMarkdownAndKatex(tempDiv, el.content);
    return tempDiv.innerHTML;
}

export function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// ---------- Alignment: single source of truth ----------

export function getHAlign(el) {
    return el.textAlign || 'center';
}

export function getVJustify(el) {
    switch (el.verticalAlign || 'center') {
        case 'top': return 'flex-start';
        case 'bottom': return 'flex-end';
        default: return 'center';
    }
}

export function textElementSharedStyle(el) {
    return `font-size:${el.fontSize}px; font-family:${el.fontFamily}; color:${el.fontColor};`
        + `display:flex; flex-direction:column;`
        + `justify-content:${getVJustify(el)};`
        + `text-align:${getHAlign(el)};`;
}

export function textElementClass(el) {
    return `element-text align-${getHAlign(el)}`;
}

export function applyAlignmentStyles(domEl, el) {
    domEl.style.textAlign = getHAlign(el);

    domEl.classList.remove('align-left', 'align-center', 'align-right');
    domEl.classList.add('align-' + getHAlign(el));

    domEl.style.display = 'flex';
    domEl.style.flexDirection = 'column';
    domEl.style.justifyContent = getVJustify(el);
}

// ---------- Common element box styles ----------

export function commonGeometryStyle(el) {
    return `position: absolute; left:${el.x}px; top:${el.y}px; width:${el.width}px; height:${el.height}px;`
        + `background-color:${el.bg};`
        + `border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol};`
        + `box-sizing: border-box;`;
}

export function applyCommonBoxStyles(domEl, el) {
    domEl.style.left = `${el.x}px`;
    domEl.style.top = `${el.y}px`;
    domEl.style.width = `${el.width}px`;
    domEl.style.height = `${el.height}px`;
    domEl.style.backgroundColor = el.bg;
    domEl.style.borderColor = el.borderCol;
    domEl.style.borderWidth = `${el.borderWidth}px`;
    domEl.style.borderStyle = el.borderStyle;
}

// ---------- Grid + dimensions ----------

export function getGridSvgDataUri(width, height, gridSize, isDarkMode) {
    if (!gridSize || gridSize <= 0) return 'none';
    const cols = Math.max(1, Math.round(width / gridSize));
    const rows = Math.max(1, Math.round(height / gridSize));
    const stepX = width / cols;
    const stepY = height / rows;
    const dotRadius = Math.max(1.5, Math.min(4, Math.min(stepX, stepY) * 0.08));
    const dotColor = isDarkMode ? '#94a3b8' : '#64748b';

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">`;
    for (let x = 0; x <= width + 0.1; x += stepX) {
        for (let y = 0; y <= height + 0.1; y += stepY) {
            svg += `<circle cx="${x}" cy="${y}" r="${dotRadius}" fill="${dotColor}"/>`;
        }
    }
    svg += `</svg>`;
    return `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
}

export function updateDimensionsCSS() {
    document.documentElement.style.setProperty('--slide-width', `${state.slideWidth}px`);
    document.documentElement.style.setProperty('--slide-height', `${state.slideHeight}px`);
}

export function syncSlideSizeSelect() {
    const sel = document.getElementById('global-slide-size');
    if (!sel) return;
    const key = `${state.slideWidth}x${state.slideHeight}`;
    sel.value = ['1920x1080', '960x540', '1280x960'].includes(key) ? key : 'custom';
}

export function syncGridSizeSelect() {
    const sel = document.getElementById('grid-size-select');
    if (sel) sel.value = state.gridSize;
}

// Late-bound render callback to avoid a circular static import
// with editor/editor.js. main.js binds it at startup.
let _renderAfterSettingsChange = () => {};
export function bindMarkDirtyAndRender(fn) {
    _renderAfterSettingsChange = fn;
}

export function changeSlideSizePreset(val) {
    if (val === '1920x1080') {
        state.slideWidth = 1920; state.slideHeight = 1080;
    } else if (val === '960x540') {
        state.slideWidth = 960; state.slideHeight = 540;
    } else if (val === '1280x960') {
        state.slideWidth = 1280; state.slideHeight = 960;
    } else if (val === 'custom') {
        const w = prompt('Enter slide width in pixels:', state.slideWidth);
        const h = prompt('Enter slide height in pixels:', state.slideHeight);
        if (w && h && !isNaN(w) && !isNaN(h)) {
            state.slideWidth = parseInt(w);
            state.slideHeight = parseInt(h);
        } else {
            syncSlideSizeSelect();
            return;
        }
    }
    updateDimensionsCSS();
    markDirty();
    _renderAfterSettingsChange();
}

export function changeGridSize(val) {
    state.gridSize = parseInt(val, 10);
    markDirty();
    _renderAfterSettingsChange();
}
