// ============================================================
// main.js — FINAL version. Entry module: loads the module graph,
// exposes the functions referenced by inline onclick="" handlers
// in index.html onto window, starts the app.
//
// index.html loads ONLY:
//   <script type="module" src="main.js"></script>
// ============================================================

import {
    state, pyApi, parseTexMacros, resetMacros, markDirty,
    startAutosave, flushPendingSave, renameProject, flashSaveIndicator,
    serializeProject, deserializeProject, currentSnapshot,
    DEFAULT_TEX_MACROS,
} from './core/state.js';
import { ElementRegistry } from './core/registry.js';
import {
    bindMarkDirtyAndRender, changeGridSize, changeSlideSizePreset,
    syncSlideSizeSelect, syncGridSizeSelect, updateDimensionsCSS,
} from './core/render.js';
import { initKeyboardShortcuts } from './core/clipboard.js';

// Side-effectful import: each element module self-registers.
import './elements/index.js';

// Editor + export modules.
import {
    renderEditor, addElement, addSlide, selectSlide, updateThumbnailLive,
} from './editor/editor.js';
import { projectExportHtml, projectExportPdf } from './export/index.js';

// ---------- View switching ----------

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
        v.style.display = 'none';
    });
    const target = document.getElementById(viewId);
    target.classList.add('active');
    target.style.display = 'flex';
}

// ---------- Dark mode ----------

function applyThemeToggle() {
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.innerHTML = state.isDarkMode ? '<span>☀️</span> Day Mode' : '<span>🌙</span> Night Mode';
    }
}

function toggleDarkMode() {
    state.isDarkMode = !state.isDarkMode;
    document.body.classList.toggle('dark-mode', state.isDarkMode);
    applyThemeToggle();
    markDirty();
    renderEditor();
}

// ---------- Recents ----------

function renderRecents() {
    const ul = document.getElementById('project-list');
    if (!ul) return;
    ul.innerHTML = '';
    state.recents.forEach(r => {
        const li = document.createElement('li');
        li.className = 'project-item';
        li.innerHTML = `<span>${r.name}</span><span style="font-size: 10px; opacity: 0.6; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${r.path}</span>`;
        li.onclick = () => openProjectByPath(r.path);
        ul.appendChild(li);
    });
    if (state.recents.length === 0) {
        ul.innerHTML = '<li class="project-item" style="cursor: default;">No projects found on disk</li>';
    }
}

async function initRecents() {
    const api = pyApi();
    if (api) {
        try {
            const res = await api.get_recent_projects();
            if (res.success && Array.isArray(res.projects)) {
                state.recents = res.projects;
            }
        } catch (e) {
            console.error('Could not load recent projects:', e);
        }
    }
    renderRecents();
}

function addRecent(name, path) {
    state.recents = state.recents.filter(r => r.path !== path);
    state.recents.unshift({ name, path });
    state.recents = state.recents.slice(0, 5);
    const api = pyApi();
    if (api && api.add_recent_project) {
        api.add_recent_project(name, path).then(initRecents);
    } else {
        renderRecents();
    }
}

// ---------- Project lifecycle ----------

function startProject(name, path, folder) {
    state.projectName = name || 'Untitled Project';
    state.projectPath = path;
    state.projectFolder = folder;

    state.slides = [{ id: 1, title: 'Title Slide', elements: [] }];
    state.currentSlideIndex = 0;
    state.selectedElementIndex = null;

    document.getElementById('project-title-input').value = state.projectName;
    if (path) addRecent(state.projectName, path);

    state.lastSnapshot = currentSnapshot();
    state.isDirty = false;

    showView('editor-view');
    renderEditor();
}

async function loadProjectMacrosFromDisk() {
    const api = pyApi();
    if (!api || !state.projectFolder) {
        resetMacros();
        return;
    }
    const res = await api.load_text_file(state.projectFolder, 'macros.tex');
    if (res.success) {
        state.rawTexMacros = res.content;
        state.projectMacros = parseTexMacros(state.rawTexMacros);
    } else {
        state.rawTexMacros = DEFAULT_TEX_MACROS;
        state.projectMacros = parseTexMacros(state.rawTexMacros);
        await api.save_text_file(state.projectFolder, 'macros.tex', state.rawTexMacros);
        await api.save_text_file(state.projectFolder, 'macros.json', JSON.stringify(state.projectMacros, null, 2));
    }
}

async function openProjectByPath(path, content) {
    try {
        if (!content) {
            const api = pyApi();
            const res = await api.load_project_at(path);
            if (!res.success) {
                alert(`Could not open project: ${res.error}`);
                return;
            }
            content = res.content;
        }
        deserializeProject(content);
        state.projectPath = path;
        state.projectFolder = path.replace(/[/\\][^/\\]+$/, '');

        document.body.classList.toggle('dark-mode', state.isDarkMode);
        applyThemeToggle();
        syncSlideSizeSelect();
        syncGridSizeSelect();
        updateDimensionsCSS();
        document.getElementById('project-title-input').value = state.projectName;

        await loadProjectMacrosFromDisk();

        addRecent(state.projectName, path);
        state.lastSnapshot = currentSnapshot();
        state.isDirty = false;
        showView('editor-view');
        renderEditor();
    } catch (e) {
        alert(`Could not open project: ${e.message}`);
    }
}

async function openProjectFromFile() {
    const api = pyApi();
    if (!api) {
        openSampleProject();
        return;
    }
    const res = await api.load_project();
    if (!res.success) {
        if (res.error !== 'Cancelled') alert(`Could not open project: ${res.error}`);
        return;
    }
    openProjectByPath(res.path, res.content);
}

function openSampleProject() {
    state.projectName = 'Sample Presentation';
    state.projectPath = null;
    state.projectFolder = null;
    state.slides = [{
        id: 1,
        title: 'Introduction',
        elements: [{
            type: 'text',
            x: 200, y: 200, width: 800, height: 160,
            content: 'Welcome to Slide Studio with **Markdown** and LaTeX: $E = mc^2$',
            fontSize: 42,
            fontFamily: 'sans-serif',
            fontColor: '#0f172a',
            textAlign: 'center',
            verticalAlign: 'center',
            bg: 'transparent',
            borderCol: 'transparent',
            borderWidth: 0,
            borderStyle: 'solid',
        }],
    }];
    state.currentSlideIndex = 0;
    state.selectedElementIndex = null;
    document.getElementById('project-title-input').value = state.projectName;
    showView('editor-view');
    renderEditor();
}

async function goToHome() {
    await flushPendingSave();
    showView('welcome-view');
}

// ---------- New-project modal ----------

let newProjectChosen = false;

function showNewProjectModal() {
    document.getElementById('new-project-name').value = '';
    newProjectChosen = false;
    document.getElementById('new-project-folder').textContent = 'No folder selected';
    document.getElementById('new-project-error').textContent = '';
    document.getElementById('new-project-create-btn').disabled = true;
    document.getElementById('new-project-modal').classList.add('show');
    document.getElementById('new-project-name').focus();
}

function closeNewProjectModal() {
    document.getElementById('new-project-modal').classList.remove('show');
}

function validateNewProjectForm() {
    const name = document.getElementById('new-project-name').value.trim();
    const err = document.getElementById('new-project-error');
    err.textContent = '';
    const btn = document.getElementById('new-project-create-btn');
    if (name && newProjectChosen) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
        if (name && !newProjectChosen) err.textContent = 'Pick a folder for the project.';
    }
}

async function chooseNewProjectFolder() {
    const api = pyApi();
    if (!api) {
        document.getElementById('new-project-folder').textContent = '(dialog unavailable in browser preview)';
        return;
    }
    const parent = await api.select_folder();
    if (parent && parent.success) {
        newProjectChosen = true;
        document.getElementById('new-project-folder').textContent = parent.path;
        validateNewProjectForm();
    }
}

async function confirmCreateProject() {
    const name = document.getElementById('new-project-name').value.trim();
    const err = document.getElementById('new-project-error');

    const api = pyApi();
    if (!api) {
        startProject(name, null, null);
        closeNewProjectModal();
        return;
    }

    const res = await api.create_project(name);
    if (!res.success) {
        err.textContent = res.error;
        return;
    }

    state.projectPath = res.path;
    state.projectFolder = res.folder;

    resetMacros();
    await api.save_text_file(state.projectFolder, 'macros.tex', state.rawTexMacros);
    await api.save_text_file(state.projectFolder, 'macros.json', JSON.stringify(state.projectMacros, null, 2));

    const saveRes = await api.save_project_data(state.projectPath, serializeProject());
    if (!saveRes.success) {
        err.textContent = saveRes.error;
        return;
    }

    startProject(name, state.projectPath, state.projectFolder);
    closeNewProjectModal();
}

// ---------- LaTeX macros modal ----------

function openMacrosModal() {
    document.getElementById('macros-textarea').value = state.rawTexMacros;
    document.getElementById('macros-error').textContent = '';
    document.getElementById('macros-modal').classList.add('show');
}

function closeMacrosModal() {
    document.getElementById('macros-modal').classList.remove('show');
}

async function saveMacros() {
    const errEl = document.getElementById('macros-error');
    try {
        state.rawTexMacros = document.getElementById('macros-textarea').value;
        state.projectMacros = parseTexMacros(state.rawTexMacros);
        markDirty();

        const api = pyApi();
        if (api && state.projectFolder) {
            await api.save_text_file(state.projectFolder, 'macros.tex', state.rawTexMacros);
            await api.save_text_file(state.projectFolder, 'macros.json', JSON.stringify(state.projectMacros, null, 2));
        }

        closeMacrosModal();
        renderEditor();
    } catch (e) {
        errEl.textContent = `Parsing error: ${e.message}`;
    }
}

// ---------- Exports ----------

async function directExport(type) {
    if (type === 'html') {
        await projectExportHtml();
    } else if (type === 'pdf') {
        await projectExportPdf();
    }
}

// ---------- Window bridge for inline onclick handlers ----------

Object.assign(window, {
    showView, showNewProjectModal, closeNewProjectModal,
    validateNewProjectForm, chooseNewProjectFolder, confirmCreateProject,
    openProjectFromFile, openProjectByPath, openSampleProject, goToHome,
    renderEditor, addElement, addSlide, selectSlide, updateThumbnailLive,
    toggleDarkMode, changeGridSize, changeSlideSizePreset,
    renameProject,
    openMacrosModal, closeMacrosModal, saveMacros,
    directExport, projectExportHtml, projectExportPdf,
    ElementRegistry,
});

// ---------- Startup ----------

// Bind state->render bridge (avoids circular static imports).
bindMarkDirtyAndRender(renderEditor);

// Initial UI state.
applyThemeToggle();
syncGridSizeSelect();
syncSlideSizeSelect();
updateDimensionsCSS();
renderRecents();

// Autosave + keyboard shortcuts.
startAutosave();
initKeyboardShortcuts();

// Flush pending changes when the window closes.
window.addEventListener('beforeunload', flushPendingSave);

// pywebview readiness: load persisted recents.
window.addEventListener('pywebviewready', initRecents);
if (!window.pywebview) {
    initRecents(); // browser preview fallback
}
