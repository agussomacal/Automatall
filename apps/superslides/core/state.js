// ============================================================
// core/state.js — Application state + persistence + macros +
// undo/redo history. No DOM manipulation here except the save indicator.
// ============================================================

export const AUTOSAVE_INTERVAL_MS = 5000;
export const PROJECT_SCHEMA_VERSION = 1;
export const MAX_HISTORY_ENTRIES = 100;

export const DEFAULT_TEX_MACROS = `\\usepackage{amssymb}
\\usepackage{amsfonts}
\\newcommand{\\R}{\\mathbb{R}}
\\newcommand{\\N}{\\mathbb{N}}
\\newcommand{\\eps}{\\varepsilon}
\\newcommand{\\vec}[1]{\\mathbf{#1}}`;

export const state = {
    slides: [],
    currentSlideIndex: 0,
    selectedSlideIndices: [0],
    selectedElementIndex: null,
    selectedElementIndices: [],
    slideWidth: 1920,
    slideHeight: 1080,
    gridSize: 20,
    isDarkMode: false,

    elementClipboard: null, // Array of cloned element objects
    slideClipboard: null,   // Array of cloned slide objects

    undoStack: [],
    redoStack: [],
    _isApplyingHistory: false,
    _historyAnchorSnapshot: '',

    rawTexMacros: DEFAULT_TEX_MACROS,
    projectMacros: {},

    projectPath: null,
    projectFolder: null,
    projectName: '',

    isDirty: false,
    lastSnapshot: '',
    recents: [],
};

/** Returns the pywebview API object or null in browser preview. */
export function pyApi() {
    return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
}

export function currentSlide() {
    return state.slides[state.currentSlideIndex] || null;
}

export function getSelectedElementIndices() {
    const slide = currentSlide();
    if (!slide) return [];
    const valid = (state.selectedElementIndices || [])
        .filter(idx => Number.isInteger(idx) && idx >= 0 && idx < slide.elements.length);
    if (valid.length > 0) return [...new Set(valid)].sort((a, b) => a - b);
    if (state.selectedElementIndex !== null && slide.elements[state.selectedElementIndex]) {
        return [state.selectedElementIndex];
    }
    return [];
}

export function setSelectedElementIndices(indices, primaryIndex = null) {
    const slide = currentSlide();
    const maxLen = slide ? slide.elements.length : 0;
    const cleaned = [...new Set(
        (indices || []).filter(idx => Number.isInteger(idx) && idx >= 0 && idx < maxLen)
    )].sort((a, b) => a - b);

    state.selectedElementIndices = cleaned;
    if (cleaned.length === 0) {
        state.selectedElementIndex = null;
    } else if (primaryIndex !== null && cleaned.includes(primaryIndex)) {
        state.selectedElementIndex = primaryIndex;
    } else {
        state.selectedElementIndex = cleaned[cleaned.length - 1];
    }
}

export function getSelectedSlideIndices() {
    const valid = (state.selectedSlideIndices || [])
        .filter(idx => Number.isInteger(idx) && idx >= 0 && idx < state.slides.length);
    if (valid.length > 0) return [...new Set(valid)].sort((a, b) => a - b);
    if (state.slides[state.currentSlideIndex]) return [state.currentSlideIndex];
    return [];
}

export function setSelectedSlideIndices(indices) {
    const cleaned = [...new Set(
        (indices || []).filter(idx => Number.isInteger(idx) && idx >= 0 && idx < state.slides.length)
    )].sort((a, b) => a - b);
    state.selectedSlideIndices = cleaned.length > 0
        ? cleaned
        : (state.slides.length > 0 ? [Math.max(0, Math.min(state.currentSlideIndex, state.slides.length - 1))] : []);
}

export function selectedElement() {
    const slide = currentSlide();
    const indices = getSelectedElementIndices();
    if (!slide || indices.length === 0) return null;
    const idx = (state.selectedElementIndex !== null && indices.includes(state.selectedElementIndex))
        ? state.selectedElementIndex
        : indices[indices.length - 1];
    return slide.elements[idx] || null;
}

// ---------- Undo / Redo history ----------

function buildHistoryEntry() {
    return {
        snapshot: currentSnapshot(),
        currentSlideIndex: state.currentSlideIndex,
        selectedSlideIndices: [...getSelectedSlideIndices()],
        selectedElementIndex: state.selectedElementIndex,
        selectedElementIndices: [...getSelectedElementIndices()],
    };
}

export function resetHistory() {
    state.undoStack = [];
    state.redoStack = [];
    state._isApplyingHistory = false;
    state._historyAnchorSnapshot = currentSnapshot();
}

export function recordUndoCheckpoint() {
    if (state._isApplyingHistory) return;
    const currentSnap = currentSnapshot();
    if (!state._historyAnchorSnapshot) {
        state._historyAnchorSnapshot = currentSnap;
    }
    if (currentSnap === state._historyAnchorSnapshot) return;

    const prevEntry = {
        snapshot: state._historyAnchorSnapshot,
        currentSlideIndex: state.currentSlideIndex,
        selectedSlideIndices: [...getSelectedSlideIndices()],
        selectedElementIndex: state.selectedElementIndex,
        selectedElementIndices: [...getSelectedElementIndices()],
    };

    state.undoStack.push(prevEntry);
    if (state.undoStack.length > MAX_HISTORY_ENTRIES) {
        state.undoStack.shift();
    }
    state.redoStack = [];
    state._historyAnchorSnapshot = currentSnap;
}

function applyHistoryEntry(entry) {
    if (!entry) return false;
    state._isApplyingHistory = true;
    try {
        const parsed = JSON.parse(entry.snapshot);
        state.slides = parsed.slides || [];
        state.slideWidth = parsed.slideWidth || 1920;
        state.slideHeight = parsed.slideHeight || 1080;
        state.gridSize = parsed.gridSize !== undefined ? parsed.gridSize : 20;
        state.isDarkMode = !!parsed.isDarkMode;
        if (typeof parsed.rawTexMacros === 'string') {
            state.rawTexMacros = parsed.rawTexMacros;
            state.projectMacros = parseTexMacros(state.rawTexMacros);
        }

        if (state.slides.length === 0) {
            state.currentSlideIndex = 0;
            state.selectedSlideIndices = [];
            state.selectedElementIndex = null;
            state.selectedElementIndices = [];
        } else {
            const clampedSlideIdx = Math.max(0, Math.min(entry.currentSlideIndex ?? 0, state.slides.length - 1));
            state.currentSlideIndex = clampedSlideIdx;

            const validSlides = (entry.selectedSlideIndices || [])
                .filter(i => Number.isInteger(i) && i >= 0 && i < state.slides.length);
            state.selectedSlideIndices = validSlides.length > 0 ? [...new Set(validSlides)].sort((a, b) => a - b) : [clampedSlideIdx];

            const slide = state.slides[clampedSlideIdx];
            const elCount = slide && Array.isArray(slide.elements) ? slide.elements.length : 0;
            const validEls = (entry.selectedElementIndices || [])
                .filter(i => Number.isInteger(i) && i >= 0 && i < elCount);
            state.selectedElementIndices = [...new Set(validEls)].sort((a, b) => a - b);

            if (Number.isInteger(entry.selectedElementIndex) && state.selectedElementIndices.includes(entry.selectedElementIndex)) {
                state.selectedElementIndex = entry.selectedElementIndex;
            } else {
                state.selectedElementIndex = state.selectedElementIndices.length > 0
                    ? state.selectedElementIndices[state.selectedElementIndices.length - 1]
                    : null;
            }
        }

        state._historyAnchorSnapshot = entry.snapshot;
        state.isDirty = currentSnapshot() !== state.lastSnapshot;
        return true;
    } finally {
        state._isApplyingHistory = false;
    }
}

export function canUndo() {
    return state.undoStack.length > 0;
}

export function canRedo() {
    return state.redoStack.length > 0;
}

export function undo() {
    if (!canUndo()) return false;
    const currentEntry = buildHistoryEntry();
    const targetEntry = state.undoStack.pop();
    state.redoStack.push(currentEntry);
    const applied = applyHistoryEntry(targetEntry);
    if (applied) {
        flashSaveIndicator('Undo ✓');
    }
    return applied;
}

export function redo() {
    if (!canRedo()) return false;
    const currentEntry = buildHistoryEntry();
    const targetEntry = state.redoStack.pop();
    state.undoStack.push(currentEntry);
    const applied = applyHistoryEntry(targetEntry);
    if (applied) {
        flashSaveIndicator('Redo ✓');
    }
    return applied;
}

// ---------- LaTeX macros ----------

export function parseTexMacros(texText) {
    const macros = {};
    const lines = (texText || '').split('\n');
    for (let line of lines) {
        line = line.trim();
        if (!line || line.startsWith('%') || line.startsWith('\\usepackage')) continue;

        const ncMatch = line.match(/\\newcommand\{\s*(\\[a-zA-Z]+)\s*\}(?:\[(\d+)\])?\s*\{([\s\S]*)\}/);
        if (ncMatch) {
            macros[ncMatch[1]] = ncMatch[3].trim();
            continue;
        }
        const defMatch = line.match(/\\def\s*(\\[a-zA-Z]+)\s*\{([\s\S]*)\}/);
        if (defMatch) {
            macros[defMatch[1]] = defMatch[2].trim();
        }
    }
    return macros;
}

export function resetMacros() {
    state.rawTexMacros = DEFAULT_TEX_MACROS;
    state.projectMacros = parseTexMacros(state.rawTexMacros);
}

// ---------- Dirty tracking / autosave ----------

export function markDirty() {
    state.isDirty = true;
    recordUndoCheckpoint();
}

export function currentSnapshot() {
    return JSON.stringify({
        slideWidth: state.slideWidth,
        slideHeight: state.slideHeight,
        gridSize: state.gridSize,
        isDarkMode: state.isDarkMode,
        rawTexMacros: state.rawTexMacros,
        slides: state.slides,
    });
}

export function serializeProject() {
    return JSON.stringify({
        version: PROJECT_SCHEMA_VERSION,
        name: state.projectName,
        slideWidth: state.slideWidth,
        slideHeight: state.slideHeight,
        gridSize: state.gridSize,
        isDarkMode: state.isDarkMode,
        slides: state.slides,
    });
}

/**
 * Loads project data into state (data only — call applyUiFromState()
 * afterwards to sync the DOM). Throws on invalid content.
 */
export function deserializeProject(content) {
    const data = JSON.parse(content);
    if (!Array.isArray(data.slides)) throw new Error("Missing 'slides' array");
    state.slides = data.slides;
    state.slideWidth = data.slideWidth || 1920;
    state.slideHeight = data.slideHeight || 1080;
    state.gridSize = data.gridSize !== undefined ? data.gridSize : 20;
    state.isDarkMode = !!data.isDarkMode;
    state.projectName = data.name || 'Untitled Project';
    state.currentSlideIndex = 0;
    state.selectedSlideIndices = state.slides.length > 0 ? [0] : [];
    state.selectedElementIndex = null;
    state.selectedElementIndices = [];
}

export function flashSaveIndicator(text) {
    const el = document.getElementById('save-indicator');
    if (!el) return;
    el.textContent = text;
    el.classList.add('visible');
    clearTimeout(flashSaveIndicator._t);
    flashSaveIndicator._t = setTimeout(() => el.classList.remove('visible'), 1600);
}

async function autoSaveTick() {
    const api = pyApi();
    if (!state.projectPath || !state.isDirty || !api) return;
    const snap = currentSnapshot();
    if (snap === state.lastSnapshot) {
        state.isDirty = false;
        return;
    }
    const res = await api.save_project_data(state.projectPath, serializeProject());
    if (res.success) {
        state.lastSnapshot = snap;
        state.isDirty = false;
        flashSaveIndicator('Autosaved ✓');
    } else {
        console.error('Autosave failed:', res.error);
    }
}

export function startAutosave() {
    setInterval(autoSaveTick, AUTOSAVE_INTERVAL_MS);
}

export async function flushPendingSave() {
    const api = pyApi();
    if (state.projectPath && state.isDirty && api && currentSnapshot() !== state.lastSnapshot) {
        const res = await api.save_project_data(state.projectPath, serializeProject());
        if (res.success) {
            state.lastSnapshot = currentSnapshot();
            state.isDirty = false;
        }
    }
}

export async function renameProject(value) {
    state.projectName = (value || '').trim() || 'Untitled Project';
    markDirty();
    const api = pyApi();
    if (state.projectPath && api) {
        const res = await api.save_project_data(state.projectPath, serializeProject());
        if (res.success) {
            state.lastSnapshot = currentSnapshot();
            state.isDirty = false;
            flashSaveIndicator('Saved ✓');
        }
    }
}