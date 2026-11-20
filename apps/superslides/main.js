// ============================================================
// main.js — Patched entry module: handles recents robustness,
// toolbar plugin registration without duplication, and startup hooks.
// ============================================================
import {
    state, pyApi, parseTexMacros, resetMacros, markDirty,
    startAutosave, flushPendingSave, renameProject, flashSaveIndicator,
    serializeProject, deserializeProject, currentSnapshot,
    setSelectedElementIndices, setSelectedSlideIndices,
    DEFAULT_TEX_MACROS,
} from './core/state.js';
import {ElementRegistry} from './core/registry.js';
import {
    bindMarkDirtyAndRender, changeGridSize, changeSlideSizePreset,
    syncSlideSizeSelect, syncGridSizeSelect, updateDimensionsCSS,
} from './core/render.js';
import {initKeyboardShortcuts} from './core/clipboard.js';

// Side-effectful import: each element module self-registers.
import './elements/index.js';

// Editor + export modules.
import {
    renderEditor, addElement, addSlide, selectSlide, updateThumbnailLive,
} from './editor/editor.js';
import {projectExportHtml, projectExportPdf} from './export/index.js';

// ---------- View switching ----------

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
        v.style.display = 'none';
    });
    const target = document.getElementById(viewId);
    if (target) {
        target.classList.add('active');
        target.style.display = 'flex';
    }
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

    if (!Array.isArray(state.recents)) {
        state.recents = [];
    }

    state.recents.forEach(r => {
        if (!r || !r.path) return;
        const li = document.createElement('li');
        li.className = 'project-item';
        li.innerHTML = `<span>${r.name || 'Untitled'}</span><span style="font-size: 10px; opacity: 0.6; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${r.path}</span>`;
        li.onclick = () => openProjectByPath(r.path);
        ul.appendChild(li);
    });
    if (state.recents.length === 0) {
        ul.innerHTML = '<li class="project-item" style="cursor: default;">No recent projects found</li>';
    }
}

async function initRecents() {
    const api = pyApi();
    if (api) {
        try {
            const res = await api.get_recent_projects();
            if (res && res.success && Array.isArray(res.projects)) {
                state.recents = res.projects;
            }
        } catch (e) {
            console.error('Could not load recent projects:', e);
        }
    }
    renderRecents();
}

function addRecent(name, path) {
    if (!path) return;
    state.recents = (state.recents || []).filter(r => r && r.path !== path);
    state.recents.unshift({name: name || 'Untitled', path});
    state.recents = state.recents.slice(0, 10);
    const api = pyApi();
    if (api && api.add_recent_project) {
        api.add_recent_project(name, path).then(initRecents).catch(() => renderRecents());
    } else {
        renderRecents();
    }
}

// ---------- Project lifecycle ----------

function startProject(name, path, folder) {
    state.projectName = name || 'Untitled Project';
    state.projectPath = path;
    state.projectFolder = folder;

    state.slides = [{id: 1, title: 'Title Slide', elements: []}];
    state.currentSlideIndex = 0;
    setSelectedSlideIndices([0]);
    setSelectedElementIndices([], null);

    const titleInput = document.getElementById('project-title-input');
    if (titleInput) titleInput.value = state.projectName;
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
    try {
        const res = await api.load_text_file(state.projectFolder, 'macros.tex');
        if (res && res.success) {
            state.rawTexMacros = res.content;
            state.projectMacros = parseTexMacros(state.rawTexMacros);
        } else {
            state.rawTexMacros = DEFAULT_TEX_MACROS;
            state.projectMacros = parseTexMacros(state.rawTexMacros);
            await api.save_text_file(state.projectFolder, 'macros.tex', state.rawTexMacros);
            await api.save_text_file(state.projectFolder, 'macros.json', JSON.stringify(state.projectMacros, null, 2));
        }
    } catch (e) {
        resetMacros();
    }
}

async function openProjectByPath(path, content) {
    try {
        if (!content) {
            const api = pyApi();
            const res = await api.load_project_at(path);
            if (!res || !res.success) {
                alert(`Could not open project: ${res ? res.error : 'Unknown error'}`);
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

        const titleInput = document.getElementById('project-title-input');
        if (titleInput) titleInput.value = state.projectName;

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
    if (!res || !res.success) {
        if (res && res.error !== 'Cancelled') alert(`Could not open project: ${res.error}`);
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
    setSelectedSlideIndices([0]);
    setSelectedElementIndices([], null);
    const titleInput = document.getElementById('project-title-input');
    if (titleInput) titleInput.value = state.projectName;
    showView('editor-view');
    renderEditor();
}

async function goToHome() {
    await flushPendingSave();
    showView('welcome-view');
    initRecents();
}

// ---------- New-project modal ----------

let newProjectChosen = false;

function showNewProjectModal() {
    const nameInput = document.getElementById('new-project-name');
    if (nameInput) nameInput.value = '';
    newProjectChosen = false;
    const folderEl = document.getElementById('new-project-folder');
    if (folderEl) folderEl.textContent = 'No folder selected';
    const errEl = document.getElementById('new-project-error');
    if (errEl) errEl.textContent = '';
    const btn = document.getElementById('new-project-create-btn');
    if (btn) btn.disabled = true;
    const modal = document.getElementById('new-project-modal');
    if (modal) modal.classList.add('show');
    if (nameInput) nameInput.focus();
}

function closeNewProjectModal() {
    const modal = document.getElementById('new-project-modal');
    if (modal) modal.classList.remove('show');
}

function validateNewProjectForm() {
    const nameInput = document.getElementById('new-project-name');
    const name = nameInput ? nameInput.value.trim() : '';
    const err = document.getElementById('new-project-error');
    if (err) err.textContent = '';
    const btn = document.getElementById('new-project-create-btn');
    if (!btn) return;
    if (name && newProjectChosen) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
        if (name && !newProjectChosen && err) err.textContent = 'Pick a folder for the project.';
    }
}

async function chooseNewProjectFolder() {
    const api = pyApi();
    if (!api) {
        const folderEl = document.getElementById('new-project-folder');
        if (folderEl) folderEl.textContent = '(dialog unavailable in browser preview)';
        return;
    }
    const parent = await api.select_folder();
    if (parent && parent.success) {
        newProjectChosen = true;
        const folderEl = document.getElementById('new-project-folder');
        if (folderEl) folderEl.textContent = parent.path;
        validateNewProjectForm();
    }
}

async function confirmCreateProject() {
    const nameInput = document.getElementById('new-project-name');
    const name = nameInput ? nameInput.value.trim() : '';
    const err = document.getElementById('new-project-error');

    const api = pyApi();
    if (!api) {
        startProject(name, null, null);
        closeNewProjectModal();
        return;
    }

    const res = await api.create_project(name);
    if (!res || !res.success) {
        if (err) err.textContent = res ? res.error : 'Creation failed';
        return;
    }

    state.projectPath = res.path;
    state.projectFolder = res.folder;

    resetMacros();
    await api.save_text_file(state.projectFolder, 'macros.tex', state.rawTexMacros);
    await api.save_text_file(state.projectFolder, 'macros.json', JSON.stringify(state.projectMacros, null, 2));

    const saveRes = await api.save_project_data(state.projectPath, serializeProject());
    if (!saveRes || !saveRes.success) {
        if (err) err.textContent = saveRes ? saveRes.error : 'Save failed';
        return;
    }

    startProject(name, state.projectPath, state.projectFolder);
    closeNewProjectModal();
}

// ---------- LaTeX macros modal ----------

function openMacrosModal() {
    const ta = document.getElementById('macros-textarea');
    if (ta) ta.value = state.rawTexMacros;
    const err = document.getElementById('macros-error');
    if (err) err.textContent = '';
    const modal = document.getElementById('macros-modal');
    if (modal) modal.classList.add('show');
}

function closeMacrosModal() {
    const modal = document.getElementById('macros-modal');
    if (modal) modal.classList.remove('show');
}

async function saveMacros() {
    const errEl = document.getElementById('macros-error');
    try {
        const ta = document.getElementById('macros-textarea');
        if (ta) state.rawTexMacros = ta.value;
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
        if (errEl) errEl.textContent = `Parsing error: ${e.message}`;
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

bindMarkDirtyAndRender(renderEditor);

applyThemeToggle();
syncGridSizeSelect();
syncSlideSizeSelect();
updateDimensionsCSS();
renderRecents();

startAutosave();
initKeyboardShortcuts();

window.addEventListener('beforeunload', flushPendingSave);

if (window.pywebview) {
    initRecents();
} else {
    window.addEventListener('pywebviewready', initRecents);
    setTimeout(initRecents, 100);
}