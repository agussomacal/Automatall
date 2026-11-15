// ============================================================
// core/geometry.js — FINAL version. Same behavior as the draft;
// removed the unused pasteOffset/PASTE_OFFSET_PX export (paste
// offset lives in core/clipboard.js) so the API surface is clean.
// ============================================================

import { state } from './state.js';

const EDGE_THRESHOLD = 12;   // px inside the element that acts as resize handle
const MIN_WIDTH = 50;
const MIN_HEIGHT = 40;
const DRAG_START_PX = 2;     // movement before a click counts as a drag

export function snapToGridPoint(val, step) {
    if (!state.gridSize || state.gridSize <= 0) return val;
    return Math.round(val / step) * step;
}

/** Compute stepX/stepY accounting for grid rounding. */
export function gridSteps() {
    if (state.gridSize > 0) {
        const cols = Math.max(1, Math.round(state.slideWidth / state.gridSize));
        const rows = Math.max(1, Math.round(state.slideHeight / state.gridSize));
        return { stepX: state.slideWidth / cols, stepY: state.slideHeight / rows };
    }
    return { stepX: 1, stepY: 1 };
}

function computeScale(domEl, el) {
    return domEl.getBoundingClientRect().width / (el.width || 1) || 0.5;
}

/** Cursor feedback while hovering near edges of an element. */
export function updateResizeCursor(domEl, el, mouseEvent) {
    const rect = domEl.getBoundingClientRect();
    const scale = computeScale(domEl, el);
    const localX = (mouseEvent.clientX - rect.left) / scale;
    const localY = (mouseEvent.clientY - rect.top) / scale;

    const isLeft = localX < EDGE_THRESHOLD;
    const isRight = localX > (el.width - EDGE_THRESHOLD);
    const isTop = localY < EDGE_THRESHOLD;
    const isBottom = localY > (el.height - EDGE_THRESHOLD);

    if (isTop && isLeft) domEl.style.cursor = 'nwse-resize';
    else if (isTop && isRight) domEl.style.cursor = 'nesw-resize';
    else if (isBottom && isLeft) domEl.style.cursor = 'nesw-resize';
    else if (isBottom && isRight) domEl.style.cursor = 'nwse-resize';
    else if (isLeft || isRight) domEl.style.cursor = 'ew-resize';
    else if (isTop || isBottom) domEl.style.cursor = 'ns-resize';
    else domEl.style.cursor = 'move';
}

/** Full drag/resize interaction for one element. */
export function startDragOrResize(domEl, el, e, callbacks) {
    const scale = computeScale(domEl, el);
    const { stepX, stepY } = gridSteps();

    const startX = e.clientX;
    const startY = e.clientY;
    const orig = { x: el.x, y: el.y, w: el.width, h: el.height };
    let hasDragged = false;

    const rect = domEl.getBoundingClientRect();
    const localX = (e.clientX - rect.left) / scale;
    const localY = (e.clientY - rect.top) / scale;
    const isLeft = localX < EDGE_THRESHOLD;
    const isRight = localX > (el.width - EDGE_THRESHOLD);
    const isTop = localY < EDGE_THRESHOLD;
    const isBottom = localY > (el.height - EDGE_THRESHOLD);
    const isResizing = isLeft || isRight || isTop || isBottom;

    function applyGeometry(newX, newY, newW, newH, useSnap) {
        if (useSnap) {
            newX = snapToGridPoint(newX, stepX);
            newY = snapToGridPoint(newY, stepY);
            newW = snapToGridPoint(newW, stepX);
            newH = snapToGridPoint(newH, stepY);
        }
        el.x = newX; el.y = newY; el.width = newW; el.height = newH;
        domEl.style.left = `${el.x}px`;
        domEl.style.top = `${el.y}px`;
        domEl.style.width = `${el.width}px`;
        domEl.style.height = `${el.height}px`;
    }

    function onMouseMove(moveEvent) {
        const dx = (moveEvent.clientX - startX) / scale;
        const dy = (moveEvent.clientY - startY) / scale;
        if (Math.abs(dx) > DRAG_START_PX || Math.abs(dy) > DRAG_START_PX) hasDragged = true;

        const freeform = moveEvent.altKey;

        if (!isResizing && hasDragged) {
            applyGeometry(orig.x + dx, orig.y + dy, orig.w, orig.h, !freeform);
            domEl.style.cursor = 'grabbing';
            callbacks.onGeometryChanged();
        } else if (isResizing) {
            let newW = orig.w, newH = orig.h, newX = orig.x, newY = orig.y;

            if (isRight) newW = Math.max(MIN_WIDTH, orig.w + dx);
            if (isBottom) newH = Math.max(MIN_HEIGHT, orig.h + dy);
            if (isLeft) {
                const candidate = orig.w - dx;
                if (candidate > MIN_WIDTH) { newW = candidate; newX = orig.x + dx; }
            }
            if (isTop) {
                const candidate = orig.h - dy;
                if (candidate > MIN_HEIGHT) { newH = candidate; newY = orig.y + dy; }
            }

            applyGeometry(newX, newY, newW, newH, !freeform);
            callbacks.onGeometryChanged();
        }
    }

    function onMouseUp() {
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
        domEl.style.cursor = '';
        callbacks.onFinish(hasDragged, isResizing);
    }

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
}
