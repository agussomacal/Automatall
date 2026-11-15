// ============================================================
// export/index.js — Export entry points.
// projectExportHtml: save + open the viewer HTML.
// projectExportPdf: HTML + vector/fallback PDF, then open it.
// ============================================================

import { state, pyApi } from '../core/state.js';
import { exportProjectPdf } from './pdf.js';

async function saveAndOpenHtml() {
    const api = pyApi();
    if (!state.projectFolder) {
        alert('Please create or open a project folder first before exporting.');
        return null;
    }

    const { getExportHtmlString } = await import('./html.js');
    const baseName = (state.projectName || 'presentation').replace(/\s+/g, '_');
    const htmlContent = await getExportHtmlString();

    const res = await api.save_text_file(state.projectFolder, `${baseName}.html`, htmlContent);
    if (!res.success) {
        alert(`Export failed to save HTML: ${res.error}`);
        return null;
    }
    return res.path;
}

export async function projectExportHtml() {
    const api = pyApi();
    const path = await saveAndOpenHtml();
    if (path) await api.open_file_with_system(path);
}

export async function projectExportPdf() {
    const api = pyApi();
    const result = await exportProjectPdf();
    if (!result.ok) {
        alert(result.error);
        return;
    }
    await api.open_file_with_system(result.pdfPath);
}
