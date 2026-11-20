// ============================================================
// core/clipboard.js — Keyboard shortcuts for slide navigation,
// multi-selection, arrow movement, cut/copy/paste, deletion,
// and undo/redo.
// ============================================================

import {
    state,
    markDirty,
    flashSaveIndicator,
    getSelectedElementIndices,
    setSelectedElementIndices,
    getSelectedSlideIndices,
    setSelectedSlideIndices,
    undo,
    redo,
} from './state.js';
import {
    renderEditor,
    deleteSelectedElements,
    deleteSelectedSlides,
    extendSlideSelectionByArrow,
    navigateSlideByArrow,
    moveSelectedElementsByArrow,
} from '../editor/editor.js';
import {
    syncSlideSizeSelect,
    syncGridSizeSelect,
    updateDimensionsCSS,
} from './render.js';

const PASTE_OFFSET_PX = 40;

function isTypingTarget(activeEl) {
    return activeEl && (
        activeEl.contentEditable === 'true'
        || activeEl.tagName === 'INPUT'
        || activeEl.tagName === 'TEXTAREA'
    );
}

function syncUiAfterHistoryChange() {
    document.body.classList.toggle('dark-mode', state.isDarkMode);
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.innerHTML = state.isDarkMode ? '<span>☀️</span> Day Mode' : '<span>🌙</span> Night Mode';
    }
    syncSlideSizeSelect();
    syncGridSizeSelect();
    updateDimensionsCSS();
    renderEditor();
}

function copySelectionToClipboard() {
    const slide = state.slides[state.currentSlideIndex];
    const selectedElIndices = getSelectedElementIndices();

    if (selectedElIndices.length > 0 && slide) {
        const copiedEls = selectedElIndices
            .map(idx => slide.elements[idx])
            .filter(Boolean)
            .map(el => JSON.parse(JSON.stringify(el)));
        if (copiedEls.length > 0) {
            state.elementClipboard = copiedEls;
            state.slideClipboard = null;
            return { kind: 'elements', count: copiedEls.length };
        }
        return null;
    }

    const selectedSlideIdxList = getSelectedSlideIndices();
    if (selectedSlideIdxList.length > 0) {
        const copiedSlides = selectedSlideIdxList
            .map(idx => state.slides[idx])
            .filter(Boolean)
            .map(s => JSON.parse(JSON.stringify(s)));
        if (copiedSlides.length > 0) {
            state.slideClipboard = copiedSlides;
            state.elementClipboard = null;
            return { kind: 'slides', count: copiedSlides.length };
        }
    }

    return null;
}

export function initKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
        const activeEl = document.activeElement;
        if (isTypingTarget(activeEl)) return;

        const slide = state.slides[state.currentSlideIndex];
        const hasCtrlOrCmd = e.ctrlKey || e.metaKey;

        // 0a. Ctrl/Cmd + Shift + Z (or Ctrl/Cmd + Y) — Redo
        if (hasCtrlOrCmd && !e.altKey && ((e.shiftKey && e.key.toLowerCase() === 'z') || (!e.shiftKey && e.key.toLowerCase() === 'y'))) {
            if (redo()) {
                syncUiAfterHistoryChange();
                e.preventDefault();
            }
            return;
        }

        // 0b. Ctrl/Cmd + Z (without Shift) — Undo
        if (hasCtrlOrCmd && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'z') {
            if (undo()) {
                syncUiAfterHistoryChange();
                e.preventDefault();
            }
            return;
        }

        // 0c. Shift + ArrowUp / ArrowDown — extend multi-selection across slides
        if (e.shiftKey && !hasCtrlOrCmd && !e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
            const delta = e.key === 'ArrowUp' ? -1 : 1;
            if (extendSlideSelectionByArrow(delta)) {
                e.preventDefault();
            }
            return;
        }

        // 0d. Plain Arrow keys — move selected object(s) if any are selected, otherwise navigate slides
        if (!hasCtrlOrCmd && !e.shiftKey && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            if (getSelectedElementIndices().length > 0) {
                if (moveSelectedElementsByArrow(e.key, e.altKey)) {
                    e.preventDefault();
                }
                return;
            }
            if (!e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
                const delta = (e.key === 'ArrowUp' || e.key === 'ArrowLeft') ? -1 : 1;
                if (navigateSlideByArrow(delta)) {
                    e.preventDefault();
                }
            }
            return;
        }

        // 1. Delete / Backspace — delete selected object(s), or selected slide(s) if no object is active
        if (e.key === 'Delete' || e.key === 'Backspace') {
            if (getSelectedElementIndices().length > 0) {
                if (deleteSelectedElements()) {
                    e.preventDefault();
                }
                return;
            }
            if (deleteSelectedSlides()) {
                e.preventDefault();
            }
            return;
        }

        // 2. Ctrl/Cmd + X — cut selected element(s) or selected slide(s) into clipboard
        if (hasCtrlOrCmd && e.key.toLowerCase() === 'x') {
            const copied = copySelectionToClipboard();
            if (!copied) return;

            if (copied.kind === 'elements') {
                deleteSelectedElements(false);
                flashSaveIndicator(copied.count > 1 ? `${copied.count} objects cut ✓` : 'Object cut ✓');
                e.preventDefault();
                return;
            }

            if (copied.kind === 'slides') {
                deleteSelectedSlides(false);
                flashSaveIndicator(copied.count > 1 ? `${copied.count} slides cut ✓` : 'Slide cut ✓');
                e.preventDefault();
            }
            return;
        }

        // 3. Ctrl/Cmd + C — copy selected element(s), or selected slide(s) if no element is active
        if (hasCtrlOrCmd && e.key.toLowerCase() === 'c') {
            const copied = copySelectionToClipboard();
            if (!copied) return;

            if (copied.kind === 'elements') {
                flashSaveIndicator(copied.count > 1 ? `${copied.count} objects copied ✓` : 'Object copied ✓');
            } else if (copied.kind === 'slides') {
                flashSaveIndicator(copied.count > 1 ? `${copied.count} slides copied ✓` : 'Slide copied ✓');
            }
            e.preventDefault();
            return;
        }

        // 4. Ctrl/Cmd + V — paste copied element(s) or copied slide(s)
        if (hasCtrlOrCmd && e.key.toLowerCase() === 'v') {
            if (Array.isArray(state.elementClipboard) && state.elementClipboard.length > 0 && slide) {
                const pastedIndices = [];
                state.elementClipboard.forEach(templateEl => {
                    const newEl = JSON.parse(JSON.stringify(templateEl));
                    newEl.x += PASTE_OFFSET_PX;
                    newEl.y += PASTE_OFFSET_PX;
                    slide.elements.push(newEl);
                    pastedIndices.push(slide.elements.length - 1);
                });
                setSelectedElementIndices(pastedIndices, pastedIndices[pastedIndices.length - 1]);
                markDirty();
                renderEditor();
                flashSaveIndicator(pastedIndices.length > 1 ? `${pastedIndices.length} objects pasted ✓` : 'Object pasted ✓');
                e.preventDefault();
                return;
            }

            if (Array.isArray(state.slideClipboard) && state.slideClipboard.length > 0) {
                const insertAfter = Math.max(0, Math.min(state.currentSlideIndex, state.slides.length - 1));
                const pastedSlideIndices = [];
                let maxId = state.slides.reduce((m, s) => Math.max(m, Number(s.id) || 0), 0);

                state.slideClipboard.forEach((templateSlide, offset) => {
                    maxId += 1;
                    const newSlide = JSON.parse(JSON.stringify(templateSlide));
                    newSlide.id = maxId;
                    newSlide.title = `${templateSlide.title || 'Slide'} (Copy)`;
                    const targetIdx = insertAfter + 1 + offset;
                    state.slides.splice(targetIdx, 0, newSlide);
                    pastedSlideIndices.push(targetIdx);
                });

                state.currentSlideIndex = pastedSlideIndices[0];
                setSelectedSlideIndices(pastedSlideIndices);
                setSelectedElementIndices([], null);
                markDirty();
                renderEditor();
                flashSaveIndicator(pastedSlideIndices.length > 1 ? `${pastedSlideIndices.length} slides pasted ✓` : 'Slide pasted ✓');
                e.preventDefault();
            }
        }
    });
}