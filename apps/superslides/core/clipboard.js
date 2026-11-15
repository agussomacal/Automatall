// ============================================================
// core/clipboard.js — FINAL version. Paste offset inlined here
// (was previously importing pasteOffset from geometry.js).
// ============================================================

import { state, markDirty, flashSaveIndicator } from './state.js';
import { renderEditor } from '../editor/editor.js';

const PASTE_OFFSET_PX = 40;

function isTypingTarget(activeEl) {
    return activeEl && (
        activeEl.contentEditable === 'true'
        || activeEl.tagName === 'INPUT'
        || activeEl.tagName === 'TEXTAREA'
    );
}

export function initKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
        const activeEl = document.activeElement;
        if (isTypingTarget(activeEl)) return;

        const slide = state.slides[state.currentSlideIndex];

        // 1. Delete / Backspace — remove selected element
        if (e.key === 'Delete' || e.key === 'Backspace') {
            if (state.selectedElementIndex !== null && slide
                && slide.elements[state.selectedElementIndex]) {
                slide.elements.splice(state.selectedElementIndex, 1);
                state.selectedElementIndex = null;
                markDirty();
                renderEditor();
                e.preventDefault();
            }
        }

        // 2. Ctrl/Cmd + C — copy element, or whole slide if none selected
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
            if (state.selectedElementIndex !== null) {
                if (slide && slide.elements[state.selectedElementIndex]) {
                    state.elementClipboard = JSON.parse(JSON.stringify(slide.elements[state.selectedElementIndex]));
                    state.slideClipboard = null;
                    e.preventDefault();
                }
            } else if (slide) {
                state.slideClipboard = JSON.parse(JSON.stringify(slide));
                state.elementClipboard = null;
                flashSaveIndicator('Slide copied ✓');
                e.preventDefault();
            }
        }

        // 3. Ctrl/Cmd + V — paste element or slide
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
            if (state.elementClipboard && slide) {
                const newEl = JSON.parse(JSON.stringify(state.elementClipboard));
                newEl.x += PASTE_OFFSET_PX;
                newEl.y += PASTE_OFFSET_PX;
                slide.elements.push(newEl);
                state.selectedElementIndex = slide.elements.length - 1;
                markDirty();
                renderEditor();
                e.preventDefault();
            } else if (state.slideClipboard) {
                const newSlide = JSON.parse(JSON.stringify(state.slideClipboard));
                newSlide.id = state.slides.length + 1;
                newSlide.title = `${state.slideClipboard.title} (Copy)`;
                state.slides.splice(state.currentSlideIndex + 1, 0, newSlide);
                state.currentSlideIndex++;
                state.selectedElementIndex = null;
                markDirty();
                renderEditor();
                flashSaveIndicator('Slide pasted ✓');
                e.preventDefault();
            }
        }
    });
}
