// ============================================================
// export/html.js — Interactive HTML viewer string builder.
// Consumes only the element registry (exportInner) and core helpers.
// The output is both the interactive viewer AND the print source
// for the vector PDF (headless Chromium) — one HTML serves both.
// ============================================================

import { state } from '../core/state.js';
import { ElementRegistry } from '../core/registry.js';
import { escapeHtml } from '../core/render.js';

export async function getExportHtmlString() {
    let katexCss = '';
    try {
        const resp = await fetch('libs/katex.min.css');
        katexCss = await resp.text();
        katexCss = katexCss.replace(/url\((?!["']?(?:data:|https?:))/g,
            'url(https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/');
    } catch (e) {
        console.warn('Could not load KaTeX CSS for export:', e);
    }

    // Same stylesheet the editor uses — viewer matches canvas by construction.
    let textStyles = '';
    try {
        const resp = await fetch('text-styles.css');
        textStyles = await resp.text();
    } catch (e) {
        console.warn('Could not load text-styles.css for export:', e);
    }

    const activeSlideBg = state.isDarkMode ? '#1e293b' : '#ffffff';

    let slidesMarkup = '';
    state.slides.forEach((s, idx) => {
        const slideStyle = `width: ${state.slideWidth}px; height: ${state.slideHeight}px;`
            + `background: ${activeSlideBg}; position: absolute;`
            + `box-shadow: 0 25px 50px rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden;`;

        slidesMarkup += `<div class="slide ${idx === 0 ? 'active' : ''}" id="slide-${idx}" style="${slideStyle}">`;

        s.elements.forEach(el => {
            const def = ElementRegistry.get(el.type);
            const geo = `position: absolute; left:${el.x}px; top:${el.y}px;`
                + `width:${el.width}px; height:${el.height}px;`
                + `background-color:${el.bg};`
                + `border: ${el.borderWidth}px ${el.borderStyle} ${el.borderCol};`
                + `box-sizing: border-box;`;

            if (!def) {
                slidesMarkup += `<div class="el" style="${geo}"></div>`;
            } else if (el.type === 'text') {
                slidesMarkup += `<div class="el ${def.className} align-${el.textAlign || 'center'}" style="${geo} ${textElementSharedStyle(el)}">${def.exportInner(el)}</div>`;
            } else {
                slidesMarkup += `<div class="el" style="${geo}">${def.exportInner(el)}</div>`;
            }
        });

        slidesMarkup += `</div>`;
    });

    let htmlContent = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${escapeHtml(state.projectName || 'Presentation')}</title>
        <style>${katexCss}</style>
        <style>${textStyles}</style>
        <style>
            .katex .mathbb { font-family: 'KaTeX_Math', 'Times New Roman', serif !important; font-weight: bold; letter-spacing: 0.05em; }
            body { background: #0f172a; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: sans-serif; overflow: hidden; }
            .slide-wrapper { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; position: relative; }
            .slide { display: none; }
            .slide.active { display: block; }
            .nav-hint { position: fixed; bottom: 20px; color: #94a3b8; font-size: 14px; pointer-events: none; z-index: 1000; }

            @page { size: ${state.slideWidth}px ${state.slideHeight}px; margin: 0; }
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
            const total = ${state.slides.length};
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
