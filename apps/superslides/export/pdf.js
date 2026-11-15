// ============================================================
// export/pdf.js — PDF generation.
// Preferred: vector via headless Chromium (backend print_html_to_pdf)
// printing the SAME HTML the viewer uses — pixel-perfect math.
// Fallback: raster via SVG <foreignObject> drawn by the browser's
// real engine (fonts embedded as data URIs).
// ============================================================

import { state, pyApi } from '../core/state.js';
import { ElementRegistry } from '../core/registry.js';
import { textElementSharedStyle, renderMarkdownAndKatexToString } from '../core/render.js';

// ---------- Raster fallback helpers ----------

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

        // Embed text-styles.css as well so raster matches the editor.
        try {
            const ts = await (await fetch('text-styles.css')).text();
            css = ts + '\n' + css;
        } catch (e) { /* non-fatal */ }

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

function slideMarkupForPdf(s) {
    const activeSlideBg = state.isDarkMode ? '#1e293b' : '#ffffff';
    const slideStyle = `width: ${state.slideWidth}px; height: ${state.slideHeight}px;`
        + `background: ${activeSlideBg}; position: relative;`
        + `box-shadow: 0 25px 50px rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden;`;

    let markup = `<div class="slide" style="${slideStyle}">`;
    s.elements.forEach(el => {
        const def = ElementRegistry.get(el.type);
        const geo = `position: absolute; left:${el.x}px; top:${el.y}px;`
            + `width:${el.width}px; height:${el.height}px;`
            + `background-color:${el.bg};`
            + `border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol};`
            + `box-sizing: border-box;`;

        if (!def) {
            markup += `<div class="el" style="${geo}"></div>`;
        } else if (el.type === 'text') {
            markup += `<div class="el ${def.className} align-${el.textAlign || 'center'}" style="${geo} ${textElementSharedStyle(el)}">${def.exportInner(el)}</div>`;
        } else {
            markup += `<div class="el" style="${geo}">${def.exportInner(el)}</div>`;
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
            `<svg xmlns="http://www.w3.org/2000/svg" width="${state.slideWidth}" height="${state.slideHeight}">` +
            `<foreignObject width="100%" height="100%">` +
            `<div xmlns="http://www.w3.org/1999/xhtml" style="width:${state.slideWidth}px;height:${state.slideHeight}px;overflow:hidden;">` +
            `<style>${embeddedCss}</style>` +
            slideXml.documentElement.innerHTML +
            `</div></foreignObject></svg>`;

        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = state.slideWidth * scale;
            canvas.height = state.slideHeight * scale;
            const ctx = canvas.getContext('2d');
            ctx.scale(scale, scale);
            ctx.drawImage(img, 0, 0, state.slideWidth, state.slideHeight);
            resolve(canvas.toDataURL('image/jpeg', 0.95));
        };
        img.onerror = () => reject(new Error('Failed to rasterize slide'));
        img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);
    });
}

// ---------- Orchestration ----------

async function exportAsVectorPdf(htmlPath) {
    const pdfPath = htmlPath.replace(/\.[^.]+$/, '') + '.pdf';
    const api = pyApi();
    return api.print_html_to_pdf(htmlPath, pdfPath, 5000);
}

async function exportAsRasterPdf(projectFolder, pdfFilename) {
    const api = pyApi();
    const embeddedCss = await getEmbeddedKatexCss();
    await document.fonts.ready;

    const imageDataList = [];
    for (let idx = 0; idx < state.slides.length; idx++) {
        imageDataList.push(await rasterizeSlide(slideMarkupForPdf(state.slides[idx]), embeddedCss, 2));
    }

    return api.save_direct_pdf_from_images(projectFolder, pdfFilename, imageDataList);
}

/**
 * Generates and saves the viewer HTML in the project folder, then
 * produces the PDF (vector preferred, raster fallback).
 * Returns {ok, htmlPath?, pdfPath?, error?}.
 */
export async function exportProjectPdf() {
    const api = pyApi();
    if (!state.projectFolder) {
        return { ok: false, error: 'Please create or open a project folder first before exporting.' };
    }

    const baseName = (state.projectName || 'presentation').replace(/\s+/g, '_');

    // 1. Save the HTML (single source for viewer + print)
    const htmlContent = await getExportHtmlString();
    const htmlSaveRes = await api.save_text_file(state.projectFolder, `${baseName}.html`, htmlContent);
    if (!htmlSaveRes.success) {
        return { ok: false, error: `Export failed to save HTML: ${htmlSaveRes.error}` };
    }
    const htmlPath = htmlSaveRes.path;

    // 2. Vector PDF via headless Chromium
    const vec = await exportAsVectorPdf(htmlPath);
    if (vec.success) {
        return { ok: true, htmlPath, pdfPath: vec.path };
    }
    console.warn('Vector PDF unavailable, falling back to raster engine:', vec.error);

    // 3. Raster fallback
    try {
        const rasterRes = await exportAsRasterPdf(state.projectFolder, `${baseName}.pdf`);
        if (rasterRes.success) {
            return { ok: true, htmlPath, pdfPath: rasterRes.path };
        }
        return { ok: false, error: `HTML exported successfully, but raster PDF export failed: ${rasterRes.error}` };
    } catch (err) {
        return { ok: false, error: `PDF Export error: ${err.message}` };
    }
}
