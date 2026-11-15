// ============================================================
// core/state.js — Application state + persistence + macros.
// No DOM manipulation here except the save indicator.
// ============================================================

export const AUTOSAVE_INTERVAL_MS = 5000;
export const PROJECT_SCHEMA_VERSION = 1;

export const DEFAULT_TEX_MACROS = `\\usepackage{amssymb}
\\usepackage{amsfonts}
\\newcommand{\\R}{\\mathbb{R}}
\\newcommand{\\N}{\\mathbb{N}}
\\newcommand{\\eps}{\\varepsilon}
\\newcommand{\\vec}[1]{\\mathbf{#1}}`;

export const state = {
    slides: [],
    currentSlideIndex: 0,
    selectedElementIndex: null,
    slideWidth: 1920,
    slideHeight: 1080,
    gridSize: 20,
    isDarkMode: false,

    elementClipboard: null,
    slideClipboard: null,

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

export function selectedElement() {
    const slide = currentSlide();
    if (state.selectedElementIndex === null || !slide) return null;
    return slide.elements[state.selectedElementIndex] || null;
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
    state.selectedElementIndex = null;
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
