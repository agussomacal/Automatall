let slides = [];
let currentSlideIndex = 0;
let selectedElementIndex = null;
let slideWidth = 1920;
let slideHeight = 1080;
let gridSize = 20;
let isDarkMode = false;

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
        width: type === 'text' ? Math.round(600 * scaleFactor) : Math.round(350 * scaleFactor),
        height: type === 'text' ? Math.round(150 * scaleFactor) : Math.round(200 * scaleFactor),
        content: type === 'text' ? 'Type **markdown** or math like $x^2 + y^2 = r^2$' : '',
        bg: type === 'text' ? 'transparent' : (isDarkMode ? '#334155' : '#cbd5e1'),
        borderCol: type === 'text' ? 'transparent' : (isDarkMode ? '#64748b' : '#475569'),
        borderWidth: type === 'text' ? 0 : 2,
        borderStyle: 'solid',
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

function renderMarkdownAndKatex(element, rawText) {
    let html = rawText || '';
    if (window.marked && typeof window.marked.parse === 'function') {
        try {
            html = window.marked.parse(rawText || '');
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

function applyAlignmentStyles(domEl, el) {
    if (el.type !== 'text') return;

    // Vertical alignment
    const vAlign = el.verticalAlign || 'center';
    if (vAlign === 'top') domEl.style.justifyContent = 'flex-start';
    else if (vAlign === 'bottom') domEl.style.justifyContent = 'flex-end';
    else domEl.style.justifyContent = 'center';

    // Horizontal alignment
    const hAlign = el.textAlign || 'center';
    domEl.style.textAlign = hAlign;
    if (hAlign === 'left') {
        domEl.style.alignItems = 'flex-start';
    } else if (hAlign === 'right') {
        domEl.style.alignItems = 'flex-end';
    } else {
        domEl.style.alignItems = 'center';
    }
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

        if (el.type === 'text') {
            domEl.style.fontSize = `${el.fontSize}px`;
            domEl.style.fontFamily = el.fontFamily;
            domEl.style.color = el.fontColor;
            applyAlignmentStyles(domEl, el);
            domEl.contentEditable = "true";

            if (selectedElementIndex === elIndex) {
                domEl.innerText = el.content;
            } else {
                renderMarkdownAndKatex(domEl, el.content);
            }

            domEl.oninput = (e) => scheduleLiveUpdate(el, e.target.innerText);
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
            } else if (e.ctrlKey || e.metaKey) {
                domEl.style.cursor = 'grab';
            } else {
                domEl.style.cursor = '';
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

            const isCtrlMove = e.ctrlKey || e.metaKey;

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

                if (isCtrlMove && hasDragged) {
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
                if (hasDragged && isCtrlMove) {
                    renderEditor();
                }
            }

            window.addEventListener('mousemove', onMouseMove);
            window.addEventListener('mouseup', onMouseUp);

            if (!isResizing && !isCtrlMove && el.type === 'text') {
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

    const activeSlideBg = isDarkMode ? '#1e293b' : '#ffffff';

    let slidesMarkup = '';
    slides.forEach((s, idx) => {
        const slideStyle = `width: ${slideWidth}px; height: ${slideHeight}px; aspect-ratio: 16 / 9; background: ${activeSlideBg}; position: absolute; box-shadow: 0 25px 50px rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden;`;

        slidesMarkup += `<div class="slide ${idx === 0 ? 'active' : ''}" id="slide-${idx}" style="${slideStyle}">`;
        s.elements.forEach(el => {
            let style = `position: absolute; left:${el.x}px; top:${el.y}px; width:${el.width}px; height:${el.height}px; background-color:${el.bg}; border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol}; box-sizing: border-box;`;
            if (el.type === 'text') {
                style += `font-size:${el.fontSize}px; font-family:${el.fontFamily}; color:${el.fontColor}; padding:8px; display: flex; flex-direction: column; overflow: hidden;`;

                const vAlign = el.verticalAlign || 'center';
                if (vAlign === 'top') style += 'justify-content:flex-start;';
                else if (vAlign === 'bottom') style += 'justify-content:flex-end;';
                else style += 'justify-content:center;';

                const hAlign = el.textAlign || 'center';
                style += `text-align:${hAlign};`;
                if (hAlign === 'left') style += 'align-items:flex-start;';
                else if (hAlign === 'right') style += 'align-items:flex-end;';
                else style += 'align-items:center;';

                const tempDiv = document.createElement('div');
                renderMarkdownAndKatex(tempDiv, el.content);
                slidesMarkup += `<div class="el" style="${style}">${tempDiv.innerHTML}</div>`;
            } else {
                slidesMarkup += `<div class="el" style="${style}"></div>`;
            }
        });
        slidesMarkup += `</div>`;
    });

    let htmlContent = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${escapeHtml(projectName || 'Presentation')}</title>
        <style>${katexCss}</style>
        <style>
            .katex .mathbb { font-family: 'KaTeX_Math', 'Times New Roman', serif !important; font-weight: bold; letter-spacing: 0.05em; }
            body { background: #0f172a; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: sans-serif; overflow: hidden; }
            .slide-wrapper { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; position: relative; }
            .slide { display: none; }
            .slide.active { display: block; }
            .katex-mathml { display: none !important; }
            .nav-hint { position: fixed; bottom: 20px; color: #94a3b8; font-size: 14px; pointer-events: none; z-index: 1000; }

            /* ---- Print: one page per slide, page size == slide size ---- */
            @page {
                size: ${slideWidth}px ${slideHeight}px;
                margin: 0;
            }
            @media print {
                body {
                    height: auto;
                    display: block;
                    background: #ffffff;
                }
                .slide-wrapper {
                    width: auto;
                    height: auto;
                    display: block;
                    position: static;
                }
                .slide {
                    display: block !important;
                    position: relative !important;   /* ← overrides the inline absolute */
                    left: 0 !important;
                    top: 0 !important;
                    margin: 0 !important;
                    box-shadow: none !important;
                    border-radius: 0 !important;
                    page-break-after: always;
                    break-after: page;
                }
                .slide:last-child {
                    page-break-after: auto;
                    break-after: auto;
                }
                .nav-hint {
                    display: none;
                }
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

function slideMarkupForPdf(s, idx) {
    const activeSlideBg = isDarkMode ? '#1e293b' : '#ffffff';
    const slideStyle = `width: ${slideWidth}px; height: ${slideHeight}px; background: ${activeSlideBg}; position: relative; box-shadow: 0 25px 50px rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden;`;

    let markup = `<div class="slide" style="${slideStyle}">`;
    s.elements.forEach(el => {
        let style = `position: absolute; left:${el.x}px; top:${el.y}px; width:${el.width}px; height:${el.height}px; background-color:${el.bg}; border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol}; box-sizing: border-box;`;
        if (el.type === 'text') {
            style += `font-size:${el.fontSize}px; font-family:${el.fontFamily}; color:${el.fontColor}; padding:8px; display: flex; flex-direction: column; overflow: hidden;`;

            const vAlign = el.verticalAlign || 'center';
            if (vAlign === 'top') style += 'justify-content:flex-start;';
            else if (vAlign === 'bottom') style += 'justify-content:flex-end;';
            else style += 'justify-content:center;';

            const hAlign = el.textAlign || 'center';
            style += `text-align:${hAlign};`;
            if (hAlign === 'left') style += 'align-items:flex-start;';
            else if (hAlign === 'right') style += 'align-items:flex-end;';
            else style += 'align-items:center;';

            const tempDiv = document.createElement('div');
            renderMarkdownAndKatex(tempDiv, el.content);
            markup += `<div class="el" style="${style}">${tempDiv.innerHTML}</div>`;
        } else {
            markup += `<div class="el" style="${style}"></div>`;
        }
    });
    markup += `</div>`;
    return markup;
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

async function triggerExport(type) {
    document.getElementById('export-menu').classList.remove('show');
    const exportStartDir = projectFolder || null;
    const baseName = (projectName || 'presentation').replace(/\s+/g, '_');

    if (type === 'pdf' || type === 'html') {
        // 1. ONE dialog: user picks where the HTML goes.
        const htmlContent = await getExportHtmlString(false);
        const htmlRes = await window.pywebview.api.save_file(htmlContent, `${baseName}.html`, "html", exportStartDir);
        if (!htmlRes.success) {
            if (htmlRes.error !== 'Cancelled') alert(`Export failed: ${htmlRes.error}`);
            return;
        }
        const htmlPath = htmlRes.path;

        // 2. HTML-only export stops here.
        if (type === 'html') {
            alert(`Successfully exported presentation to:\n${htmlPath}`);
            return;
        }

        // 3. PDF export: try vector (headless browser) first, fall back
        //    to raster capture if no suitable browser is available.
        const vec = await exportAsVectorPdf(htmlPath);
        if (vec.success) {
            alert(`Successfully exported PDF and HTML to:\n${vec.path}\n\n(vector PDF via headless browser)`);
            return;
        }
        console.warn('Vector PDF unavailable:', vec.error);

        const raster = await exportAsRasterPdf(htmlPath, exportStartDir, baseName);
        if (raster.ok) {
            alert(`Successfully exported PDF and HTML to:\n${raster.pdfPath}\n\n(raster PDF — install Chrome/Edge for sharper vector output)`);
        } else {
            alert(`HTML exported to:\n${htmlPath}\n\nBut PDF export failed: ${raster.error}`);
        }
    }
}


function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function addRecent(name, path) {
    recents = recents.filter(r => r.path !== path);
    recents.unshift({name, path});
    recents = recents.slice(0, 10);
    renderRecents();

    if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.add_recent_project(name, path);
    }
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