// ============================================================
// elements/figure/figure.js — Figure/image element.
// Fixed version: no static import of editor.js. After assigning
// a figure source we dispatch 'slide-content-changed' (canvas +
// properties) and 'slide-thumbnail-changed' (thumbnail only).
// Figure drop/browse bridges are exposed on window for inline handlers.
// ============================================================

import { state, pyApi, markDirty } from '../../core/state.js';
import { ElementRegistry } from '../../core/registry.js';
import { escapeHtml } from '../../core/render.js';

function notifyFullRender() {
    document.dispatchEvent(new CustomEvent('slide-content-changed'));
}

function notifyThumbnailOnly() {
    document.dispatchEvent(new CustomEvent('slide-thumbnail-changed'));
}

async function processAndAssignFigure(elIndex, filePath) {
    const api = pyApi();
    if (api && state.projectFolder) {
        const res = await api.import_figure(state.projectFolder, filePath);
        if (res.success) {
            assignFigureSource(elIndex, res.data_uri, filePath, res.relative_path);
            return;
        }
    }
    assignFigureSource(elIndex, filePath, filePath, filePath);
}

function assignFigureSource(elIndex, dataUri, originalPath, storedPath) {
    const slide = state.slides[state.currentSlideIndex];
    if (!slide || !slide.elements[elIndex]) return;

    const el = slide.elements[elIndex];
    el.src = dataUri;
    el.originalPath = originalPath;
    el.filePath = storedPath;
    el.borderStyle = 'solid';
    markDirty();
    notifyFullRender();
}

async function handleFigureDrop(e, elIndex) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.path) {
            processAndAssignFigure(elIndex, file.path);
        } else {
            const blobUrl = URL.createObjectURL(file);
            assignFigureSource(elIndex, blobUrl, file.name, file.name);
        }
    }
}

async function browseFigurePath(elIndex) {
    const api = pyApi();
    if (api) {
        const res = await api.select_figure_file();
        if (res.success && res.path) {
            processAndAssignFigure(elIndex, res.path);
        }
    } else {
        const path = prompt('Enter path or URL to figure:');
        if (path) assignFigureSource(elIndex, path, path, path);
    }
}

async function openPathInSystem(fullPath) {
    if (!fullPath) return;
    const folderPath = fullPath.replace(/[/\\][^/\\]*$/, '');
    const api = pyApi();
    if (api) {
        await api.open_file_with_system(folderPath);
    } else {
        alert('Folder Path: ' + folderPath);
    }
}

function absoluteLocalPath(localPath) {
    if (state.projectFolder && localPath
        && !localPath.startsWith('/') && !localPath.match(/^[a-zA-Z]:\\/)) {
        return `${state.projectFolder}/${localPath}`;
    }
    return localPath;
}

// Inline-handler bridge for canvas placeholder clicks and
// properties-panel buttons.
window.SlideStudioFigure = { browseFigurePath, handleFigureDrop, openPathInSystem };

const FigureElement = {
    type: 'figure',
    label: 'Add Figure',
    icon: '🖼️',
    className: 'element-shape', // box styling shared with shapes

    defaults(ctx) {
        const scale = state.slideWidth / 1920;
        return {
            type: 'figure',
            x: 0, y: 0,
            width: Math.round(400 * scale),
            height: Math.round(300 * scale),
            src: '',
            originalPath: '',
            filePath: '',
            bg: state.isDarkMode ? '#1e293b' : '#f1f5f9',
            borderCol: state.isDarkMode ? '#475569' : '#cbd5e1',
            borderWidth: 2,
            borderStyle: 'dashed',
        };
    },

    renderDom(domEl, el, ctx) {
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
            if (ctx.context === 'canvas') {
                domEl.onclick = () => browseFigurePath(ctx.elIndex);
            }
        }

        if (ctx.context === 'canvas') {
            domEl.ondragover = (e) => { e.preventDefault(); e.stopPropagation(); };
            domEl.ondrop = (e) => handleFigureDrop(e, ctx.elIndex);
        }
    },

    exportInner(el) {
        if (el.src) {
            return `<img src="${el.src}" style="width:100%; height:100%; object-fit:contain;" />`;
        }
        return `<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-family:sans-serif;">[Figure Placeholder]</div>`;
    },

    properties(el, elIndex) {
        const origPath = el.originalPath || '';
        const localPath = el.filePath || '';
        const absLocalPath = absoluteLocalPath(localPath);

        return `
            <div class="prop-group">
                <label>Original Path</label>
                <div style="display: flex; gap: 6px;">
                    <input type="text" class="prop-control" readonly value="${escapeHtml(origPath)}" placeholder="No original path">
                    <button class="btn btn-secondary" style="width: auto; padding: 6px 10px; margin-bottom: 0;"
                            onclick="SlideStudioFigure.openPathInSystem('${escapeHtml(origPath).replace(/'/g, "\\'")}')"
                            title="Open in File Manager">📂</button>
                </div>
            </div>
            <div class="prop-group" style="margin-top: 8px;">
                <label>Local Copy Path</label>
                <div style="display: flex; gap: 6px;">
                    <input type="text" class="prop-control" readonly value="${escapeHtml(localPath)}" placeholder="No local copy">
                    <button class="btn btn-secondary" style="width: auto; padding: 6px 10px; margin-bottom: 0;"
                            onclick="SlideStudioFigure.openPathInSystem('${escapeHtml(absLocalPath || origPath).replace(/'/g, "\\'")}')"
                            title="Open in File Manager">📂</button>
                </div>
            </div>
            <div class="prop-group" style="margin-top: 12px;">
                <button class="btn btn-secondary" style="width: 100%;"
                        onclick="SlideStudioFigure.browseFigurePath(${elIndex})">📁 Browse New File...</button>
            </div>
        `;
    },
};

ElementRegistry.register(FigureElement);
