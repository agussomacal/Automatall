// ============================================================
// export/index.js — Clean export module bridge.
// Connects UI export actions to html.js and pdf.js modules.
// ============================================================

import { state, pyApi } from '../core/state.js';
import { getExportHtmlString } from './html.js';
import { exportProjectPdf } from './pdf.js';

export async function projectExportHtml() {
    try {
        const htmlContent = await getExportHtmlString();
        const api = pyApi();

        if (api && state.projectFolder) {
            const safeName = (state.projectName || 'presentation').replace(/\s+/g, '_');
            const res = await api.save_text_file(state.projectFolder, `${safeName}.html`, htmlContent);
            if (res.success) {
                api.open_file_with_system(res.path);
                return;
            }
        }

        // Browser fallback / standalone save
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'presentation.html';
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert(`HTML export failed: ${e.message}`);
    }
}

export async function projectExportPdf() {
    const res = await exportProjectPdf();
    if (!res.ok) {
        alert(`PDF export failed: ${res.error}`);
        return;
    }
    const api = pyApi();
    if (api && res.pdfPath) {
        api.open_file_with_system(res.pdfPath);
    }
}