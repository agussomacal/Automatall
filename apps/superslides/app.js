let slides = [];
let currentSlideIndex = 0;
let selectedElementIndex = null;
let slideWidth = 1920;
let slideHeight = 1080;
let gridSize = 20;
let isDarkMode = false;

let elementClipboard = null;

let rawTexMacros = `\\usepackage{amssymb}
\\usepackage{amsfonts}
\\newcommand{\\R}{\\mathbb{R}}
\\newcommand{\\N}{\\mathbb{N}}
\\newcommand{\\eps}{\\varepsilon}
\\newcommand{\\vec}[1]{\\mathbf{#1}}`;
let projectMacros = parseTexMacros(rawTexMacros);

let projectPath = null;
let projectFolder = null;
let projectName = '';
let isDirty = false;
let lastSnapshot = '';
let recents = [];

const AUTOSAVE_INTERVAL_MS = 5000;

function parseTexMacros(texText) {
    const macros = {};
    const lines = texText.split('\n');

    for (let line of lines) {
        line = line.trim();
        if (!line || line.startsWith('%') || line.startsWith('\\usepackage')) continue;

        const ncMatch = line.match(/\\newcommand\{\s*(\\[a-zA-Z]+)\s*\}(?:\[(\d+)\])?\s*\{([\s\S]*)\}/);
        if (ncMatch) {
            let [, cmd, numArgs, expansion] = ncMatch;
            macros[cmd] = expansion.trim();
            continue;
        }

        const defMatch = line.match(/\\def\s*(\\[a-zA-Z]+)\s*\{([\s\S]*)\}/);
        if (defMatch) {
            let [, cmd, expansion] = defMatch;
            macros[cmd] = expansion.trim();
            continue;
        }
    }
    return macros;
}

function openMacrosModal() {
    const textarea = document.getElementById('macros-textarea');
    textarea.value = rawTexMacros;
    document.getElementById('macros-error').textContent = '';
    document.getElementById('macros-modal').classList.add('show');
}

function closeMacrosModal() {
    document.getElementById('macros-modal').classList.remove('show');
}

async function loadProjectMacrosFromDisk() {
    if (!window.pywebview || !window.pywebview.api || !projectFolder) {
        rawTexMacros = defaultTexMacros;
        projectMacros = parseTexMacros(rawTexMacros);
        return;
    }

    const res = await window.pywebview.api.load_text_file(projectFolder, 'macros.tex');
    if (res.success) {
        rawTexMacros = res.content;
        projectMacros = parseTexMacros(rawTexMacros);
    } else {
        rawTexMacros = defaultTexMacros;
        projectMacros = parseTexMacros(rawTexMacros);
        await window.pywebview.api.save_text_file(projectFolder, 'macros.tex', rawTexMacros);
        await window.pywebview.api.save_text_file(projectFolder, 'macros.json', JSON.stringify(projectMacros, null, 2));
    }
}

async function saveMacros() {
    const textarea = document.getElementById('macros-textarea');
    const errEl = document.getElementById('macros-error');
    try {
        rawTexMacros = textarea.value;
        projectMacros = parseTexMacros(rawTexMacros);
        markDirty();

        if (window.pywebview && window.pywebview.api && projectFolder) {
            await window.pywebview.api.save_text_file(projectFolder, 'macros.tex', rawTexMacros);
            await window.pywebview.api.save_text_file(projectFolder, 'macros.json', JSON.stringify(projectMacros, null, 2));
        }

        closeMacrosModal();
        renderEditor();
    } catch (e) {
        errEl.textContent = `Parsing error: ${e.message}`;
    }
}

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
        v.style.display = 'none';
    });
    const target = document.getElementById(viewId);
    target.classList.add('active');
    target.style.display = 'flex';
}

function toggleDarkMode() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark-mode', isDarkMode);
    const btn = document.getElementById('theme-toggle-btn');
    if (isDarkMode) {
        btn.innerHTML = '<span>☀️</span> Day Mode';
    } else {
        btn.innerHTML = '<span>🌙</span> Night Mode';
    }
    markDirty();
    renderCanvas();
    updateThumbnailLive();
}

function toggleExportMenu(e) {
    e.stopPropagation();
    const menu = document.getElementById('export-menu');
    menu.classList.toggle('show');
}

window.addEventListener('click', () => {
    const menu = document.getElementById('export-menu');
    if (menu) menu.classList.remove('show');
});

function serializeProject() {
    return JSON.stringify({
        version: 1,
        name: projectName,
        slideWidth: slideWidth,
        slideHeight: slideHeight,
        gridSize: gridSize,
        isDarkMode: isDarkMode,
        slides: slides
    });
}

function deserializeProject(content) {
    const data = JSON.parse(content);
    if (!Array.isArray(data.slides)) throw new Error("Missing 'slides' array");
    slides = data.slides;
    slideWidth = data.slideWidth || 1920;
    slideHeight = data.slideHeight || 1080;
    gridSize = data.gridSize !== undefined ? data.gridSize : 20;
    isDarkMode = !!data.isDarkMode;
    projectName = data.name || 'Untitled Project';

    document.body.classList.toggle('dark-mode', isDarkMode);
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) btn.innerHTML = isDarkMode ? '<span>☀️</span> Day Mode' : '<span>🌙</span> Night Mode';

    syncSlideSizeSelect();
    syncGridSizeSelect();
    document.getElementById('project-title-input').value = projectName;
    currentSlideIndex = 0;
    selectedElementIndex = null;
}

function syncSlideSizeSelect() {
    const sel = document.getElementById('global-slide-size');
    const key = `${slideWidth}x${slideHeight}`;
    sel.value = ['1920x1080', '960x540', '1280x960'].includes(key) ? key : 'custom';
}

function syncGridSizeSelect() {
    const sel = document.getElementById('grid-size-select');
    if (sel) sel.value = gridSize;
}

function changeGridSize(val) {
    gridSize = parseInt(val, 10);
    markDirty();
    renderCanvas();
}

function flashSaveIndicator(text) {
    const el = document.getElementById('save-indicator');
    el.textContent = text;
    el.classList.add('visible');
    clearTimeout(flashSaveIndicator._t);
    flashSaveIndicator._t = setTimeout(() => el.classList.remove('visible'), 1600);
}

function markDirty() {
    isDirty = true;
}

function currentSnapshot() {
    return JSON.stringify({slideWidth, slideHeight, gridSize, isDarkMode, rawTexMacros, slides});
}

async function autoSaveTick() {
    if (!projectPath || !isDirty) return;
    const snap = currentSnapshot();
    if (snap === lastSnapshot) {
        isDirty = false;
        return;
    }
    const res = await window.pywebview.api.save_project_data(projectPath, serializeProject());
    if (res.success) {
        lastSnapshot = snap;
        isDirty = false;
        flashSaveIndicator('Autosaved ✓');
    } else {
        console.error('Autosave failed:', res.error);
    }
}

setInterval(autoSaveTick, AUTOSAVE_INTERVAL_MS);

async function flushPendingSave() {
    if (projectPath && isDirty && currentSnapshot() !== lastSnapshot) {
        const res = await window.pywebview.api.save_project_data(projectPath, serializeProject());
        if (res.success) {
            lastSnapshot = currentSnapshot();
            isDirty = false;
        }
    }
}

window.addEventListener('beforeunload', flushPendingSave);

async function renameProject(value) {
    projectName = value.trim() || 'Untitled Project';
    markDirty();
    if (projectPath) {
        const res = await window.pywebview.api.save_project_data(projectPath, serializeProject());
        if (res.success) {
            lastSnapshot = currentSnapshot();
            isDirty = false;
            flashSaveIndicator('Saved ✓');
        }
    }
}

function addRecent(name, path) {
    recents = recents.filter(r => r.path !== path);
    recents.unshift({name, path});
    recents = recents.slice(0, 5);
    renderRecents();
}

function renderRecents() {
    const ul = document.getElementById('project-list');
    ul.innerHTML = '';
    recents.forEach(r => {
        const li = document.createElement('li');
        li.className = 'project-item';
        li.innerHTML = `<span>${r.name}</span>`;
        li.onclick = () => openProjectByPath(r.path);
        ul.appendChild(li);
    });
    if (recents.length === 0) {
        ul.innerHTML = '<li class="project-item" style="cursor: default;">No projects opened yet</li>';
    }
}

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
    if (!(window.pywebview && window.pywebview.api)) {
        document.getElementById('new-project-folder').textContent = '(dialog unavailable in browser preview)';
        return;
    }
    const parent = await window.pywebview.api.select_folder();
    if (parent && parent.success) {
        newProjectChosen = true;
        document.getElementById('new-project-folder').textContent = parent.path;
        validateNewProjectForm();
    }
}

async function confirmCreateProject() {
    const name = document.getElementById('new-project-name').value.trim();
    const err = document.getElementById('new-project-error');

    if (!(window.pywebview && window.pywebview.api)) {
        startProject(name, null, null);
        closeNewProjectModal();
        return;
    }

    const res = await window.pywebview.api.create_project(name);
    if (!res.success) {
        err.textContent = res.error;
        return;
    }

    projectPath = res.path;
    projectFolder = res.folder;

    let defaultTexMacros = `\\usepackage{amssymb}
                            \\usepackage{amsfonts}
                            \\newcommand{\\R}{\\mathbb{R}}
                            \\newcommand{\\N}{\\mathbb{N}}
                            \\newcommand{\\eps}{\\varepsilon}
                            \\newcommand{\\vec}[1]{\\mathbf{#1}}`;

    rawTexMacros = defaultTexMacros;
    projectMacros = parseTexMacros(rawTexMacros);
    await window.pywebview.api.save_text_file(projectFolder, 'macros.tex', rawTexMacros);
    await window.pywebview.api.save_text_file(projectFolder, 'macros.json', JSON.stringify(projectMacros, null, 2));

    const saveRes = await window.pywebview.api.save_project_data(projectPath, serializeProject());
    if (!saveRes.success) {
        err.textContent = saveRes.error;
        return;
    }

    startProject(name, projectPath, projectFolder);
    closeNewProjectModal();
}

function startProject(name, path, folder) {
    projectName = name || 'Untitled Project';
    projectPath = path;
    projectFolder = folder;

    slides = [{id: 1, title: "Title Slide", elements: []}];
    currentSlideIndex = 0;
    selectedElementIndex = null;

    document.getElementById('project-title-input').value = projectName;
    if (path) addRecent(projectName, path);

    lastSnapshot = currentSnapshot();
    isDirty = false;

    showView('editor-view');
    renderEditor();
}

async function openProjectFromFile() {
    if (!(window.pywebview && window.pywebview.api)) {
        openSampleProject();
        return;
    }
    const res = await window.pywebview.api.load_project();
    if (!res.success) {
        if (res.error !== 'Cancelled') alert(`Could not open project: ${res.error}`);
        return;
    }
    openProjectByPath(res.path, res.content);
}

async function openProjectByPath(path, content) {
    try {
        if (!content) {
            const res = await window.pywebview.api.load_project_at(path);
            if (!res.success) {
                alert(`Could not open project: ${res.error}`);
                return;
            }
            content = res.content;
        }
        deserializeProject(content);
        projectPath = path;
        projectFolder = path.replace(/[/\\][^/\\]+$/, '');

        await loadProjectMacrosFromDisk();

        addRecent(projectName, path);
        lastSnapshot = currentSnapshot();
        isDirty = false;
        showView('editor-view');
        renderEditor();
    } catch (e) {
        alert(`Could not open project: ${e.message}`);
    }
}

function openSampleProject() {
    projectName = 'Sample Presentation';
    projectPath = null;
    projectFolder = null;
    slides = [
        {
            id: 1,
            title: "Introduction",
            elements: [
                {
                    type: 'text',
                    x: 200,
                    y: 200,
                    width: 800,
                    height: 160,
                    content: 'Welcome to Slide Studio with **Markdown** and LaTeX: $E = mc^2$',
                    fontSize: 42,
                    fontFamily: 'sans-serif',
                    fontColor: '#0f172a',
                    textAlign: 'center',
                    verticalAlign: 'center',
                    bg: 'transparent',
                    borderCol: 'transparent',
                    borderWidth: 0,
                    borderStyle: 'solid'
                }
            ]
        }
    ];
    currentSlideIndex = 0;
    selectedElementIndex = null;
    document.getElementById('project-title-input').value = projectName;
    showView('editor-view');
    renderEditor();
}

async function goToHome() {
    await flushPendingSave();
    showView('welcome-view');
}

function addSlide() {
    const newSlideId = slides.length + 1;
    slides.push({id: newSlideId, title: `Slide ${newSlideId}`, elements: []});
    currentSlideIndex = slides.length - 1;
    selectedElementIndex = null;
    markDirty();
    renderEditor();
}

function selectSlide(index) {
    currentSlideIndex = index;
    selectedElementIndex = null;
    renderEditor();
}

function changeSlideSizePreset(val) {
    if (val === '1920x1080') {
        slideWidth = 1920;
        slideHeight = 1080;
    } else if (val === '960x540') {
        slideWidth = 960;
        slideHeight = 540;
    } else if (val === '1280x960') {
        slideWidth = 1280;
        slideHeight = 960;
    } else if (val === 'custom') {
        const w = prompt("Enter slide width in pixels:", slideWidth);
        const h = prompt("Enter slide height in pixels:", slideHeight);
        if (w && h && !isNaN(w) && !isNaN(h)) {
            slideWidth = parseInt(w);
            slideHeight = parseInt(h);
        } else {
            syncSlideSizeSelect();
        }
    }
    updateDimensionsCSS();
    markDirty();
    renderEditor();
}

function updateDimensionsCSS() {
    document.documentElement.style.setProperty('--slide-width', `${slideWidth}px`);
    document.documentElement.style.setProperty('--slide-height', `${slideHeight}px`);
}

function addElement(type) {
    const currentSlide = slides[currentSlideIndex];
    const scaleFactor = slideWidth / 1920;
    const newElement = {
        type: type,
        x: Math.round(200 + (currentSlide.elements.length * 30)),
        y: Math.round(200 + (currentSlide.elements.length * 30)),
        width: type === 'text' ? Math.round(600 * scaleFactor) : Math.round(400 * scaleFactor),
        height: type === 'text' ? Math.round(150 * scaleFactor) : Math.round(300 * scaleFactor),
        content: type === 'text' ? 'Type **markdown** or math like $x^2 + y^2 = r^2$' : '',
        src: type === 'figure' ? '' : undefined,
        bg: type === 'text' ? 'transparent' : (type === 'figure' ? (isDarkMode ? '#1e293b' : '#f1f5f9') : (isDarkMode ? '#334155' : '#cbd5e1')),
        borderCol: type === 'text' ? 'transparent' : (type === 'figure' ? (isDarkMode ? '#475569' : '#cbd5e1') : (isDarkMode ? '#64748b' : '#475569')),
        borderWidth: type === 'text' ? 0 : 2,
        borderStyle: type === 'figure' ? 'dashed' : 'solid',
        fontSize: Math.round(32 * scaleFactor),
        fontFamily: 'sans-serif',
        fontColor: isDarkMode ? '#f8fafc' : '#0f172a',
        textAlign: 'center',
        verticalAlign: 'center'
    };
    currentSlide.elements.push(newElement);
    selectedElementIndex = currentSlide.elements.length - 1;
    markDirty();
    renderEditor();
}


async function processAndAssignFigure(elementIndex, filePath) {
    if (window.pywebview && window.pywebview.api && projectFolder) {
        const res = await window.pywebview.api.import_figure(projectFolder, filePath);
        if (res.success) {
            assignFigureSource(elementIndex, res.data_uri, filePath, res.relative_path);
            return;
        }
    }
    assignFigureSource(elementIndex, filePath, filePath, filePath);
}

function handleFigureDrop(e, elIndex) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        const filePath = file.path; // Absolute file path from file system drop
        if (filePath) {
            processAndAssignFigure(elIndex, filePath);
        } else {
            const blobUrl = URL.createObjectURL(file);
            assignFigureSource(elIndex, blobUrl, file.name, file.name);
        }
    }
}

function assignFigureSource(elementIndex, dataUri, originalPath, storedPath) {
    const currentSlide = slides[currentSlideIndex];
    if (!currentSlide || !currentSlide.elements[elementIndex]) return;

    const el = currentSlide.elements[elementIndex];
    el.src = dataUri;
    el.originalPath = originalPath;
    el.filePath = storedPath;
    el.borderStyle = 'solid';
    markDirty();
    renderCanvas();
    renderPropertiesPanel();
    updateThumbnailLive();
}

async function browseFigurePath(elementIndex) {
    if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.select_figure_file();
        if (res.success && res.path) {
            processAndAssignFigure(elementIndex, res.path);
        }
    } else {
        const path = prompt("Enter path or URL to figure:");
        if (path) assignFigureSource(elementIndex, path, path, path);
    }
}

async function openPathInSystem(fullPath) {
    if (!fullPath) return;

    // Extract the containing folder path from the file path
    // Handles both forward slashes and backslashes
    const folderPath = fullPath.replace(/[/\\][^/\\]*$/, '');

    if (window.pywebview && window.pywebview.api) {
        // Call the backend Python API to open the directory
        // (Assumes you have a method like open_folder or open_file_with_system that accepts folder paths)
        await window.pywebview.api.open_file_with_system(folderPath);
    } else {
        alert("Folder Path: " + folderPath);
    }
}

function renderMarkdownAndKatex(element, rawText) {
    let html = rawText || '';
    if (window.marked && typeof window.marked.parse === 'function') {
        try {
            // Pass breaks: true directly so single newlines convert to <br> consistently
            html = window.marked.parse(rawText || '', {breaks: true, gfm: true});
        } catch (e) {
            console.error("Markdown parsing error:", e);
        }
    }
    element.innerHTML = html;
    if (window.renderMathInElement) {
        try {
            renderMathInElement(element, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false},
                    {left: "\\(", right: "\\)", display: false},
                    {left: "\\[", right: "\\]", display: true}
                ],
                macros: projectMacros,
                throwOnError: false
            });
        } catch (e) {
            console.error("KaTeX rendering error:", e);
        }
    }
}

function renderAllMath() {
    renderEditor();
}

let liveUpdateTimer = null;

function scheduleLiveUpdate(el, text) {
    el.content = text;
    markDirty();
    clearTimeout(liveUpdateTimer);
    liveUpdateTimer = setTimeout(updateThumbnailLive, 250);
}

// ------------------------------------------------------------------
// SINGLE SOURCE OF TRUTH for alignment.
// The editor (applyAlignmentStyles), the HTML export
// (getExportHtmlString) and the PDF raster fallback
// (slideMarkupForPdf) all derive from these three helpers.
// ------------------------------------------------------------------

function getHAlign(el) {
    return el.textAlign || 'center';
}

function getVJustify(el) {
    switch (el.verticalAlign || 'center') {
        case 'top':
            return 'flex-start';
        case 'bottom':
            return 'flex-end';
        default:
            return 'center';
    }
}

// Inline style shared by every text element in every context.
// Per-element geometry/looks only — structural markup styling
// (padding, lists, equations) lives in text-styles.css, which is
// linked in index.html and embedded in every export.
function textElementSharedStyle(el) {
    return `font-size:${el.fontSize}px; font-family:${el.fontFamily}; color:${el.fontColor};`
        + `display:flex; flex-direction:column;`
        + `justify-content:${getVJustify(el)};`
        + `text-align:${getHAlign(el)};`;
}

// Class hook for text-styles.css to adapt lists per alignment.
function textElementClass(el) {
    return `element-text align-${getHAlign(el)}`;
}


// ------------------------------------------------------------------
// EDITOR (canvas + thumbnails)
// ------------------------------------------------------------------
function applyAlignmentStyles(domEl, el) {
    // Horizontal alignment: text-align only. Lists, paragraphs and
    // .katex-display equations inherit it via text-styles.css.
    // Do NOT set align-items — on a flex column it shrink-wraps
    // children and re-introduces box centering for lists/equations.
    domEl.style.textAlign = getHAlign(el);

    // Class hook so CSS can adapt (e.g. inside markers on the right,
    // fit-content centering for centered lists). No stale classes.
    domEl.classList.remove('align-left', 'align-center', 'align-right');
    domEl.classList.add('align-' + getHAlign(el));

    // Vertical alignment via flex on the container.
    domEl.style.display = 'flex';
    domEl.style.flexDirection = 'column';
    domEl.style.justifyContent = getVJustify(el);
}

function renderEditor() {
    updateDimensionsCSS();
    syncGridSizeSelect();
    const thumbList = document.getElementById('slides-thumb-list');
    thumbList.innerHTML = '';

    slides.forEach((slide, idx) => {
        const container = document.createElement('div');
        container.className = `thumb-container ${idx === currentSlideIndex ? 'active' : ''}`;
        container.onclick = () => selectSlide(idx);

        const labelRow = document.createElement('div');
        labelRow.className = 'thumb-label-row';
        labelRow.innerHTML = `<span>${slide.title}</span><span>${idx + 1}</span>`;

        const thumb = document.createElement('div');
        thumb.className = `slide-thumb`;

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
        <span>Add Slide</span>
    `;
    thumbList.appendChild(addThumb);

    renderCanvas();
    renderPropertiesPanel();
}

function buildThumbElement(el) {
    const thumbEl = document.createElement('div');
    thumbEl.className = `thumb-element ${el.type === 'text' ? 'element-text' : 'element-shape'}`;
    thumbEl.style.left = `${el.x}px`;
    thumbEl.style.top = `${el.y}px`;
    thumbEl.style.width = `${el.width}px`;
    thumbEl.style.height = `${el.height}px`;
    thumbEl.style.backgroundColor = el.bg;
    thumbEl.style.borderColor = el.borderCol;
    thumbEl.style.borderWidth = `${el.borderWidth}px`;
    thumbEl.style.borderStyle = el.borderStyle;

    if (el.type === 'text') {
        thumbEl.style.fontSize = `${el.fontSize}px`;
        thumbEl.style.fontFamily = el.fontFamily;
        thumbEl.style.color = el.fontColor;
        applyAlignmentStyles(thumbEl, el);
        renderMarkdownAndKatex(thumbEl, el.content);
    }

    // Inside renderCanvas() element loop:
    if (el.type === 'figure') {
        thumbEl.style.display = 'flex';
        thumbEl.style.flexDirection = 'column';
        thumbEl.style.alignItems = 'center';
        thumbEl.style.justifyContent = 'center';
        thumbEl.style.overflow = 'hidden';

        if (el.src) {
            thumbEl.innerHTML = `<img src="${el.src}" style="width: 100%; height: 100%; object-fit: contain; pointer-events: none;" />`;
        } else {
            thumbEl.innerHTML = `
            <div style="text-align: center; pointer-events: none; padding: 10px;">
                <span style="font-size: 28px; display: block; margin-bottom: 6px;">🖼️</span>
                <span style="font-size: 13px; font-weight: 500; color: var(--text-muted);">Drop / Browse Figure</span>
            </div>`;
            thumbEl.onclick = () => browseFigurePath(elIndex);
        }

        thumbEl.ondragover = (e) => {
            e.preventDefault();
            e.stopPropagation();
        };
        thumbEl.ondrop = (e) => handleFigureDrop(e, elIndex);
    }
    return thumbEl;


}

function getGridSvgDataUri(width, height, gridSize, isDarkMode) {
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

function renderCanvas() {
    const canvas = document.getElementById('slide-canvas');
    canvas.innerHTML = '';

    let stepX = gridSize;
    let stepY = gridSize;

    if (gridSize > 0) {
        const cols = Math.max(1, Math.round(slideWidth / gridSize));
        const rows = Math.max(1, Math.round(slideHeight / gridSize));
        stepX = slideWidth / cols;
        stepY = slideHeight / rows;

        canvas.style.backgroundImage = getGridSvgDataUri(slideWidth, slideHeight, gridSize, isDarkMode);
        canvas.style.backgroundSize = '100% 100%';
        canvas.style.backgroundPosition = '0px 0px';
        canvas.style.width = `${slideWidth}px`;
        canvas.style.height = `${slideHeight}px`;
    } else {
        canvas.style.backgroundImage = 'none';
    }

    const currentSlide = slides[currentSlideIndex];
    if (!currentSlide) return;

    currentSlide.elements.forEach((el, elIndex) => {
        const domEl = document.createElement('div');
        domEl.className = `canvas-element ${el.type === 'text' ? 'element-text' : 'element-shape'}`;
        if (selectedElementIndex === elIndex) {
            domEl.classList.add('selected');
        }

        domEl.style.left = `${el.x}px`;
        domEl.style.top = `${el.y}px`;
        domEl.style.width = `${el.width}px`;
        domEl.style.height = `${el.height}px`;
        domEl.style.backgroundColor = el.bg;
        domEl.style.borderColor = el.borderCol;
        domEl.style.borderWidth = `${el.borderWidth}px`;
        domEl.style.borderStyle = el.borderStyle;

        if (el.type === 'figure') {
            domEl.style.display = 'flex';
            domEl.style.flexDirection = 'column';
            domEl.style.alignItems = 'center';
            domEl.style.justifyContent = 'center';
            domEl.style.overflow = 'hidden';

            if (el.src) {
                domEl.innerHTML = `<img src="${el.src}" style="width: 100%; height: 100%; object-fit: contain; pointer-events: none;" />`;
            } else {
                domEl.innerHTML = `
                    <div style="text-align: center; pointer-events: none; padding: 10px;">
                        <span style="font-size: 28px; display: block; margin-bottom: 6px;">🖼️</span>
                        <span style="font-size: 13px; font-weight: 500; color: var(--text-muted);">Drop / Browse Figure</span>
                    </div>`;
                domEl.onclick = () => browseFigurePath(elIndex);
            }

            domEl.ondragover = (e) => {
                e.preventDefault();
                e.stopPropagation();
            };
            domEl.ondrop = (e) => handleFigureDrop(e, elIndex);
        }

        if (el.type === 'text') {
            domEl.style.fontSize = `${el.fontSize}px`;
            domEl.style.fontFamily = el.fontFamily;
            domEl.style.color = el.fontColor;
            applyAlignmentStyles(domEl, el);
            domEl.contentEditable = "false";

            if (selectedElementIndex === elIndex && domEl.classList.contains('editing-mode')) {
                domEl.contentEditable = "true";
                domEl.innerText = el.content;
            } else {
                renderMarkdownAndKatex(domEl, el.content);
            }

            domEl.ondblclick = (e) => {
                e.stopPropagation();
                domEl.classList.add('editing-mode');
                domEl.contentEditable = "true";
                domEl.innerText = el.content;
                domEl.focus();
            };

            domEl.oninput = (e) => scheduleLiveUpdate(el, e.target.innerText);

            // Press Escape to exit writing mode safely
            domEl.onkeydown = (e) => {
                if (e.key === 'Escape' || e.code === 'Escape') {
                    e.preventDefault();
                    e.stopPropagation();
                    saveAndExitTextEditing(domEl, el);
                }
            };
        }

        domEl.onmousemove = (e) => {
            const rect = domEl.getBoundingClientRect();
            const scale = rect.width / (el.width || 1) || 0.5;
            const localX = (e.clientX - rect.left) / scale;
            const localY = (e.clientY - rect.top) / scale;
            const threshold = 12;

            const isLeft = localX < threshold;
            const isRight = localX > (el.width - threshold);
            const isTop = localY < threshold;
            const isBottom = localY > (el.height - threshold);

            if (isTop && isLeft) {
                domEl.style.cursor = 'nwse-resize';
            } else if (isTop && isRight) {
                domEl.style.cursor = 'nesw-resize';
            } else if (isBottom && isLeft) {
                domEl.style.cursor = 'nesw-resize';
            } else if (isBottom && isRight) {
                domEl.style.cursor = 'nwse-resize';
            } else if (isLeft || isRight) {
                domEl.style.cursor = 'ew-resize';
            } else if (isTop || isBottom) {
                domEl.style.cursor = 'ns-resize';
            } else {
                domEl.style.cursor = 'move';
            }
        };

        domEl.onmousedown = (e) => {
            const rect = domEl.getBoundingClientRect();
            const scale = rect.width / (el.width || 1) || 0.5;
            const x = (e.clientX - rect.left) / scale;
            const y = (e.clientY - rect.top) / scale;
            const threshold = 12;

            const isLeft = x < threshold;
            const isRight = x > (el.width - threshold);
            const isTop = y < threshold;
            const isBottom = y > (el.height - threshold);
            const isResizing = isLeft || isRight || isTop || isBottom;

            if (selectedElementIndex !== elIndex) {
                selectedElementIndex = elIndex;
                renderCanvas();
                renderPropertiesPanel();
                return;
            }

            const startX = e.clientX;
            const startY = e.clientY;
            const origX = el.x;
            const origY = el.y;
            const origW = el.width;
            const origH = el.height;
            let hasDragged = false;

            function snapToGridPoint(val, step) {
                if (!gridSize || gridSize <= 0) return val;
                return Math.round(val / step) * step;
            }

            function onMouseMove(moveEvent) {
                const dx = (moveEvent.clientX - startX) / scale;
                const dy = (moveEvent.clientY - startY) / scale;

                if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                    hasDragged = true;
                }

                const useFreeform = moveEvent.altKey;

                if (!isResizing && hasDragged) {
                    if (useFreeform) {
                        el.x = origX + dx;
                        el.y = origY + dy;
                    } else {
                        el.x = snapToGridPoint(origX + dx, stepX);
                        el.y = snapToGridPoint(origY + dy, stepY);
                    }
                    domEl.style.left = `${el.x}px`;
                    domEl.style.top = `${el.y}px`;
                    domEl.style.cursor = 'grabbing';
                } else if (isResizing) {
                    let newW = origW + dx;
                    let newH = origH + dy;
                    let newX = origX;
                    let newY = origY;

                    if (isRight) newW = Math.max(50, origW + dx);
                    if (isBottom) newH = Math.max(40, origH + dy);
                    if (isLeft) {
                        const candidateW = origW - dx;
                        if (candidateW > 50) {
                            newW = candidateW;
                            newX = origX + dx;
                        }
                    }
                    if (isTop) {
                        const candidateH = origH - dy;
                        if (candidateH > 40) {
                            newH = candidateH;
                            newY = origY + dy;
                        }
                    }

                    if (!useFreeform) {
                        el.x = snapToGridPoint(newX, stepX);
                        el.y = snapToGridPoint(newY, stepY);
                        el.width = snapToGridPoint(newW, stepX);
                        el.height = snapToGridPoint(newH, stepY);
                    } else {
                        el.x = newX;
                        el.y = newY;
                        el.width = newW;
                        el.height = newH;
                    }

                    domEl.style.left = `${el.x}px`;
                    domEl.style.top = `${el.y}px`;
                    domEl.style.width = `${el.width}px`;
                    domEl.style.height = `${el.height}px`;
                }

                const xInput = document.getElementById('prop-x');
                const yInput = document.getElementById('prop-y');
                if (xInput) xInput.value = Math.round(el.x);
                if (yInput) yInput.value = Math.round(el.y);
            }

            function onMouseUp() {
                window.removeEventListener('mousemove', onMouseMove);
                window.removeEventListener('mouseup', onMouseUp);
                domEl.style.cursor = '';
                if (hasDragged) markDirty();
                renderPropertiesPanel();
                if (hasDragged && !isResizing) {
                    renderEditor();
                }
            }

            window.addEventListener('mousemove', onMouseMove);
            window.addEventListener('mouseup', onMouseUp);

            if (!isResizing && el.type === 'text' && domEl.classList.contains('editing-mode')) {
                return;
            }
            e.stopPropagation();
        };

        canvas.appendChild(domEl);
    });
}

function updateThumbnailLive() {
    const activeContainer = document.querySelectorAll('.thumb-container')[currentSlideIndex];
    if (!activeContainer) return;
    const scaler = activeContainer.querySelector('.thumb-canvas-scaler');
    if (!scaler) return;

    scaler.innerHTML = '';
    slides[currentSlideIndex].elements.forEach(el => {
        scaler.appendChild(buildThumbElement(el));
    });
}

document.getElementById('slide-canvas').onclick = (e) => {
    if (e.target.id === 'slide-canvas') {
        selectedElementIndex = null;
        renderCanvas();
        renderPropertiesPanel();
    }
};

function renderPropertiesPanel() {
    const panelBody = document.getElementById('properties-body');
    const currentSlide = slides[currentSlideIndex];

    if (selectedElementIndex === null || !currentSlide || !currentSlide.elements[selectedElementIndex]) {
        panelBody.innerHTML = `<div class="no-selection">Select an object on the canvas to inspect and customize its properties.</div>`;
        return;
    }

    const el = currentSlide.elements[selectedElementIndex];

    let html = `
        <div class="prop-group">
            <label>Object Type</label>
            <input type="text" class="prop-control" value="${el.type === 'text' ? 'Text Box' : 'Rectangle Shape'}" disabled style="opacity: 0.6;">
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
    if (el.type === 'figure') {
        const origPath = el.originalPath || '';
        const localPath = el.filePath || '';
        const absLocalPath = (projectFolder && localPath && !localPath.startsWith('/') && !localPath.match(/^[a-zA-Z]:\\/))
            ? `${projectFolder}/${localPath}`
            : localPath;

        html += `
            <div class="prop-group">
                <label>Original Path</label>
                <div style="display: flex; gap: 6px;">
                    <input type="text" class="prop-control" readonly value="${escapeHtml(origPath)}" placeholder="No original path">
                    <button class="btn btn-secondary" style="width: auto; padding: 6px 10px; margin-bottom: 0;" onclick="openPathInSystem('${escapeHtml(origPath).replace(/'/g, "\\'")}')" title="Open in File Manager">📂</button>
                </div>
            </div>
            <div class="prop-group" style="margin-top: 8px;">
                <label>Local Copy Path</label>
                <div style="display: flex; gap: 6px;">
                    <input type="text" class="prop-control" readonly value="${escapeHtml(localPath)}" placeholder="No local copy">
                    <button class="btn btn-secondary" style="width: auto; padding: 6px 10px; margin-bottom: 0;" onclick="openPathInSystem('${escapeHtml(absLocalPath || origPath).replace(/'/g, "\\'")}')" title="Open in File Manager">📂</button>
                </div>
            </div>
            <div class="prop-group" style="margin-top: 12px;">
                <button class="btn btn-secondary" style="width: 100%;" onclick="browseFigurePath(${selectedElementIndex})">📁 Browse New File...</button>
            </div>
        `;
    }
    if (el.type === 'text') {
        html += `
            <div style="border-top: 1px solid var(--border-color); padding-top: 12px; margin-top: 4px;"></div>
            <div class="prop-group">
                <label>Font Family</label>
                <select class="prop-control" onchange="updateProp('fontFamily', this.value)">
                    <option value="sans-serif" ${el.fontFamily === 'sans-serif' ? 'selected' : ''}>Sans-Serif</option>
                    <option value="serif" ${el.fontFamily === 'serif' ? 'selected' : ''}>Serif</option>
                    <option value="monospace" ${el.fontFamily === 'monospace' ? 'selected' : ''}>Monospace</option>
                </select>
            </div>
            <div class="prop-row">
                <div class="prop-group">
                    <label>Font Size (px)</label>
                    <input type="number" class="prop-control" value="${el.fontSize}" oninput="updateProp('fontSize', this.value)">
                </div>
                <div class="prop-group">
                    <label>Text Color</label>
                    <input type="color" class="prop-control" value="${el.fontColor}" style="height: 34px; padding: 2px;" oninput="updateProp('fontColor', this.value)">
                </div>
            </div>
            <div class="prop-row">
                <div class="prop-group">
                    <label>H-Alignment</label>
                    <select class="prop-control" onchange="updateProp('textAlign', this.value)">
                        <option value="left" ${(el.textAlign || 'center') === 'left' ? 'selected' : ''}>Left</option>
                        <option value="center" ${(el.textAlign || 'center') === 'center' ? 'selected' : ''}>Center</option>
                        <option value="right" ${(el.textAlign || 'center') === 'right' ? 'selected' : ''}>Right</option>
                    </select>
                </div>
                <div class="prop-group">
                    <label>V-Alignment</label>
                    <select class="prop-control" onchange="updateProp('verticalAlign', this.value)">
                        <option value="top" ${(el.verticalAlign || 'center') === 'top' ? 'selected' : ''}>Top</option>
                        <option value="center" ${(el.verticalAlign || 'center') === 'center' ? 'selected' : ''}>Center</option>
                        <option value="bottom" ${(el.verticalAlign || 'center') === 'bottom' ? 'selected' : ''}>Bottom</option>
                    </select>
                </div>
            </div>
        `;
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

function updateProp(propName, value) {
    const currentSlide = slides[currentSlideIndex];
    if (selectedElementIndex === null || !currentSlide) return;
    const el = currentSlide.elements[selectedElementIndex];

    if (['x', 'y', 'width', 'height', 'fontSize', 'borderWidth'].includes(propName)) {
        el[propName] = Number(value);
    } else {
        el[propName] = value;
    }

    markDirty();
    renderCanvas();
    updateThumbnailLive();
}

// ------------------------------------------------------------------
// HTML EXPORT — full function
// ------------------------------------------------------------------
async function getExportHtmlString() {
    let katexCss = '';
    try {
        const resp = await fetch('libs/katex.min.css');
        katexCss = await resp.text();
        katexCss = katexCss.replace(/url\((?!["']?(?:data:|https?:))/g,
            'url(https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/');
    } catch (e) {
        console.warn('Could not load KaTeX CSS for export:', e);
    }

    // Our dedicated text/list/equation styles — same file the editor
    // uses, so the viewer matches the canvas by construction.
    let textStyles = '';
    try {
        const resp = await fetch('text-styles.css');
        textStyles = await resp.text();
    } catch (e) {
        console.warn('Could not load text-styles.css for export:', e);
    }

    const activeSlideBg = isDarkMode ? '#1e293b' : '#ffffff';

    let slidesMarkup = '';
    slides.forEach((s, idx) => {
        const slideStyle = `width: ${slideWidth}px; height: ${slideHeight}px; background: ${activeSlideBg}; position: absolute; box-shadow: 0 25px 50px rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden;`;

        slidesMarkup += `<div class="slide ${idx === 0 ? 'active' : ''}" id="slide-${idx}" style="${slideStyle}">`;
        s.elements.forEach(el => {
            const geo = `position: absolute; left:${el.x}px; top:${el.y}px; width:${el.width}px; height:${el.height}px; background-color:${el.bg}; border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol}; box-sizing: border-box;`;

            if (el.type === 'text') {
                // Shared style + shared class. No duplicated alignment code.
                slidesMarkup += `<div class="el ${textElementClass(el)}" style="${geo} ${textElementSharedStyle(el)}">`
                    + renderMarkdownAndKatexToString(el)
                    + `</div>`;
            } else if (el.type === 'figure') {
                if (el.src) {
                    slidesMarkup += `<div class="el" style="${geo}"><img src="${el.src}" style="width:100%; height:100%; object-fit:contain;" /></div>`;
                } else {
                    slidesMarkup += `<div class="el" style="${geo} display:flex; align-items:center; justify-content:center; color:#94a3b8; font-family:sans-serif;">[Figure Placeholder]</div>`;
                }
            } else {
                slidesMarkup += `<div class="el" style="${geo}"></div>`;
            }
        });
        slidesMarkup += `</div>`;
    });

    let htmlContent = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${escapeHtml(projectName || 'Presentation')}</title>
        <style>${katexCss}</style>
        <style>${textStyles}</style>
        <style>
            .katex .mathbb { font-family: 'KaTeX_Math', 'Times New Roman', serif !important; font-weight: bold; letter-spacing: 0.05em; }
            body { background: #0f172a; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: sans-serif; overflow: hidden; }
            .slide-wrapper { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; position: relative; }
            .slide { display: none; }
            .slide.active { display: block; }
            .nav-hint { position: fixed; bottom: 20px; color: #94a3b8; font-size: 14px; pointer-events: none; z-index: 1000; }

            @page { size: ${slideWidth}px ${slideHeight}px; margin: 0; }
            @media print {
                body { height: auto; display: block; background: #ffffff; }
                .slide-wrapper { width: auto; height: auto; display: block; position: static; }
                .slide { display: block !important; position: relative !important; left: 0 !important; top: 0 !important; margin: 0 !important; box-shadow: none !important; border-radius: 0 !important; page-break-after: always; break-after: page; }
                .slide:last-child { page-break-after: auto; break-after: auto; }
                .nav-hint { display: none; }
            }
        </style></head><body><div class="slide-wrapper">`;

    htmlContent += slidesMarkup;
    htmlContent += `</div><div class="nav-hint">Use [Space] or [→] to go forward, [←] to go backward</div>`;
    htmlContent += `<script>
            let current = 0;
            const total = ${slides.length};
            document.addEventListener('keydown', (e) => {
                if (e.code === 'Space' || e.code === 'ArrowRight') {
                    if (current < total - 1) {
                        document.getElementById('slide-' + current).classList.remove('active');
                        current++;
                        document.getElementById('slide-' + current).classList.add('active');
                    }
                } else if (e.code === 'ArrowLeft') {
                    if (current > 0) {
                        document.getElementById('slide-' + current).classList.remove('active');
                        current--;
                        document.getElementById('slide-' + current).classList.add('active');
                    }
                }
            });
        <\/script></body></html>`;

    return htmlContent;
}

// Render content into a detached div and return its HTML string.
// One wrapper around renderMarkdownAndKatex used by both exports.
function renderMarkdownAndKatexToString(el) {
    const tempDiv = document.createElement('div');
    renderMarkdownAndKatex(tempDiv, el.content);
    return tempDiv.innerHTML;
}


// ------------------------------------------------------------------
// PDF RASTER FALLBACK — full function
// (figures were previously appended to the HTML-export variable;
//  that bug is fixed here too)
// ------------------------------------------------------------------
function slideMarkupForPdf(s, idx) {
    const activeSlideBg = isDarkMode ? '#1e293b' : '#ffffff';
    const slideStyle = `width: ${slideWidth}px; height: ${slideHeight}px; background: ${activeSlideBg}; position: relative; box-shadow: 0 25px 50px rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden;`;

    let markup = `<div class="slide" style="${slideStyle}">`;
    s.elements.forEach(el => {
        const geo = `position: absolute; left:${el.x}px; top:${el.y}px; width:${el.width}px; height:${el.height}px; background-color:${el.bg}; border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol}; box-sizing: border-box;`;

        if (el.type === 'text') {
            markup += `<div class="el ${textElementClass(el)}" style="${geo} ${textElementSharedStyle(el)}">`
                + renderMarkdownAndKatexToString(el)
                + `</div>`;
        } else if (el.type === 'figure') {
            if (el.src) {
                markup += `<div class="el" style="${geo}"><img src="${el.src}" style="width:100%; height:100%; object-fit:contain;" /></div>`;
            } else {
                markup += `<div class="el" style="${geo} display:flex; align-items:center; justify-content:center; color:#94a3b8; font-family:sans-serif;">[Figure Placeholder]</div>`;
            }
        } else {
            markup += `<div class="el" style="${geo}"></div>`;
        }
    });
    markup += `</div>`;
    return markup;
}

// =====================================================================
// PDF capture via the browser's REAL renderer (no html2canvas).
//
// Each slide is serialized into an SVG <foreignObject> and drawn onto a
// canvas with drawImage(). Because the rasterization is done by the
// browser's own layout engine — the exact same engine that renders the
// exported HTML correctly — the PDF matches the HTML viewer by
// construction. All CSS and fonts must be inlined as data URIs for this
// to work, since foreignObject content cannot load external resources.
// =====================================================================

// ---- helpers ---------------------------------------------------------


function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
}

let _embeddedKatexCssPromise = null;

function getEmbeddedKatexCss() {
    if (_embeddedKatexCssPromise) return _embeddedKatexCssPromise;
    _embeddedKatexCssPromise = (async () => {
        const base = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/';
        let css = await (await fetch('libs/katex.min.css')).text();

        const seen = new Map();
        for (const m of css.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
            const raw = m[1];
            if (raw.startsWith('data:') || /^https?:/.test(raw)) seen.set(raw, raw);
            else seen.set(raw, base + raw.replace(/^\.\//, ''));
        }

        for (const [raw, abs] of seen) {
            try {
                const resp = await fetch(abs);
                if (!resp.ok) throw new Error(resp.status);
                const buf = await resp.arrayBuffer();
                const mime = abs.endsWith('.woff2') ? 'font/woff2'
                    : abs.endsWith('.woff') ? 'font/woff'
                        : abs.endsWith('.ttf') ? 'font/ttf'
                            : 'application/octet-stream';
                css = css.split(raw).join(`data:${mime};base64,${arrayBufferToBase64(buf)}`);
            } catch (e) {
                console.warn('Could not embed KaTeX font:', abs, e);
            }
        }
        return css;
    })();
    return _embeddedKatexCssPromise;
}


function rasterizeSlide(markup, embeddedCss, scale) {
    return new Promise((resolve, reject) => {
        const slideXml = new DOMParser().parseFromString(
            `<div xmlns="http://www.w3.org/1999/xhtml">${markup}</div>`, 'text/xml');
        if (slideXml.querySelector('parsererror')) {
            reject(new Error('Slide markup not XML-clean; text may contain raw & or unclosed tags'));
            return;
        }

        const svgString =
            `<svg xmlns="http://www.w3.org/2000/svg" width="${slideWidth}" height="${slideHeight}">` +
            `<foreignObject width="100%" height="100%">` +
            `<div xmlns="http://www.w3.org/1999/xhtml" style="width:${slideWidth}px;height:${slideHeight}px;overflow:hidden;">` +
            `<style>${embeddedCss}</style>` +
            slideXml.documentElement.innerHTML +
            `</div></foreignObject></svg>`;

        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = slideWidth * scale;
            canvas.height = slideHeight * scale;
            const ctx = canvas.getContext('2d');
            ctx.scale(scale, scale);
            ctx.drawImage(img, 0, 0, slideWidth, slideHeight);
            resolve(canvas.toDataURL('image/jpeg', 0.95));
        };
        img.onerror = () => reject(new Error('Failed to rasterize slide'));
        img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);
    });
}

/**
 * Fallback: rasterize slides and hand JPEGs to the backend.
 */
async function exportAsRasterPdf(htmlPath, exportStartDir, baseName) {
    const embeddedCss = await getEmbeddedKatexCss();
    await document.fonts.ready;

    const imageDataList = [];
    for (let idx = 0; idx < slides.length; idx++) {
        imageDataList.push(await rasterizeSlide(slideMarkupForPdf(slides[idx], idx), embeddedCss, 2));
    }

    // One dialog for the PDF; HTML already saved next to it
    const pdfRes = await window.pywebview.api.save_pdf_from_images(imageDataList, `${baseName}.pdf`, exportStartDir);
    return pdfRes.success
        ? {ok: true, pdfPath: pdfRes.path}
        : {ok: false, error: pdfRes.error};
}

/**
 * Preferred: ask the backend to drive a headless Chromium/Edge render.
 */
async function exportAsVectorPdf(htmlPath) {
    const pdfPath = htmlPath.replace(/\.[^.]+$/, '') + '.pdf';
    return window.pywebview.api.print_html_to_pdf(htmlPath, pdfPath, 5000);
}

// ---- main export orchestration ---------------------------------------
// ---- Direct export orchestration (silent, no dialogs, auto-open) ----
async function directExport(type) {
    if (!projectFolder) {
        alert("Please create or open a project folder first before exporting.");
        return;
    }

    const baseName = (projectName || 'presentation').replace(/\s+/g, '_');
    const htmlFilename = `${baseName}.html`;
    const pdfFilename = `${baseName}.pdf`;

    // 1. Generate and save the HTML file silently in the project folder
    const htmlContent = await getExportHtmlString(false);
    const htmlSaveRes = await window.pywebview.api.save_text_file(projectFolder, htmlFilename, htmlContent);

    if (!htmlSaveRes.success) {
        alert(`Export failed to save HTML: ${htmlSaveRes.error}`);
        return;
    }
    const htmlPath = htmlSaveRes.path;

    // 2. If HTML-only export was requested, open it and finish
    if (type === 'html') {
        await window.pywebview.api.open_file_with_system(htmlPath);
        return;
    }

    // 3. PDF Export: Try headless vector PDF first
    const vec = await exportAsVectorPdf(htmlPath);
    if (vec.success) {
        await window.pywebview.api.open_file_with_system(vec.path);
        return;
    }
    console.warn('Vector PDF unavailable, falling back to raster engine:', vec.error);

    // 4. Fallback: Rasterize via SVG foreignObject and save silently
    try {
        const embeddedCss = await getEmbeddedKatexCss();
        await document.fonts.ready;

        const imageDataList = [];
        for (let idx = 0; idx < slides.length; idx++) {
            imageDataList.push(await rasterizeSlide(slideMarkupForPdf(slides[idx], idx), embeddedCss, 2));
        }

        const rasterRes = await window.pywebview.api.save_direct_pdf_from_images(projectFolder, pdfFilename, imageDataList);
        if (rasterRes.success) {
            await window.pywebview.api.open_file_with_system(rasterRes.path);
        } else {
            alert(`HTML exported successfully, but raster PDF export failed: ${rasterRes.error}`);
        }
    } catch (err) {
        alert(`PDF Export error: ${err.message}`);
    }
}


function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}


function renderRecents() {
    const ul = document.getElementById('project-list');
    if (!ul) return;
    ul.innerHTML = '';
    recents.forEach(r => {
        const li = document.createElement('li');
        li.className = 'project-item';
        li.innerHTML = `<span>${r.name}</span><span style="font-size: 10px; opacity: 0.6; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${r.path}</span>`;
        li.onclick = () => openProjectByPath(r.path);
        ul.appendChild(li);
    });
    if (recents.length === 0) {
        ul.innerHTML = '<li class="project-item" style="cursor: default;">No projects found on disk</li>';
    }
}

async function initRecents() {
    if (window.pywebview && window.pywebview.api) {
        try {
            const res = await window.pywebview.api.get_recent_projects();
            if (res.success && Array.isArray(res.projects)) {
                recents = res.projects;
            }
        } catch (e) {
            console.error("Could not load recent projects:", e);
        }
    }
    renderRecents();
}

// Call initRecents on startup instead of plain renderRecents
// Listen for pywebview to be ready before calling Python API methods
window.addEventListener('pywebviewready', () => {
    initRecents();
});

// Fallback in case it's loaded in a standard browser preview where pywebviewready doesn't fire
if (!window.pywebview) {
    renderRecents();
}

function saveAndExitTextEditing(domEl, el) {
    el.content = domEl.innerText;
    domEl.contentEditable = "false";
    domEl.classList.remove('editing-mode');
    markDirty();
    renderCanvas();
    updateThumbnailLive();
}


// Global click listener to exit text editing mode when clicking outside active text box
window.addEventListener('click', (e) => {
    const editingEl = document.querySelector('.canvas-element.editing-mode');
    if (editingEl && !editingEl.contains(e.target)) {
        const currentSlide = slides[currentSlideIndex];
        if (currentSlide && currentSlide.elements[selectedElementIndex]) {
            saveAndExitTextEditing(editingEl, currentSlide.elements[selectedElementIndex]);
        }
    }
});

window.addEventListener('keydown', (e) => {
    const activeEl = document.activeElement;
    const isEditing = activeEl && (activeEl.contentEditable === 'true' || activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA');

    // 1. Delete / Backspace
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedElementIndex !== null) {
        if (isEditing) return;
        const currentSlide = slides[currentSlideIndex];
        if (currentSlide && currentSlide.elements[selectedElementIndex]) {
            currentSlide.elements.splice(selectedElementIndex, 1);
            selectedElementIndex = null;
            markDirty();
            renderEditor();
            e.preventDefault();
        }
    }

    // 2. Copy (Ctrl + C / Cmd + C)
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
        if (isEditing) return;
        if (selectedElementIndex !== null) {
            const currentSlide = slides[currentSlideIndex];
            if (currentSlide && currentSlide.elements[selectedElementIndex]) {
                // Deep copy the selected element into our internal clipboard
                elementClipboard = JSON.parse(JSON.stringify(currentSlide.elements[selectedElementIndex]));
                e.preventDefault();
            }
        }
    }

    // 3. Paste (Ctrl + V / Cmd + V)
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
        if (isEditing) return;
        if (elementClipboard) {
            const currentSlide = slides[currentSlideIndex];
            if (currentSlide) {
                // Deep copy from clipboard to avoid reference linkage
                const newEl = JSON.parse(JSON.stringify(elementClipboard));

                // Shift slightly diagonally so the user can easily see the new duplicate
                newEl.x += 40;
                newEl.y += 40;

                currentSlide.elements.push(newEl);
                selectedElementIndex = currentSlide.elements.length - 1;
                markDirty();
                renderEditor();
                e.preventDefault();
            }
        }
    }
});