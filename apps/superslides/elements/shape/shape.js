// ============================================================
// elements/shape/shape.js — Rectangle shape element
// ============================================================

import { state } from '../../core/state.js';
import { ElementRegistry } from '../../core/registry.js';

const ShapeElement = {
    type: 'shape',
    label: 'Add Rectangle',
    icon: '⬛',
    className: 'element-shape',

    defaults(ctx) {
        const scale = state.slideWidth / 1920;
        return {
            type: 'shape',
            x: 0, y: 0,
            width: Math.round(400 * scale),
            height: Math.round(300 * scale),
            bg: state.isDarkMode ? '#334155' : '#cbd5e1',
            borderCol: state.isDarkMode ? '#64748b' : '#475569',
            borderWidth: 2,
            borderStyle: 'solid',
        };
    },

    renderDom(domEl, el, ctx) {
        // Shapes are purely visual boxes — the common box styles
        // (position/size/background/border) already applied by the editor.
    },

    exportInner(el) {
        return '';
    },

    properties(el, elIndex) {
        return ''; // shape-specific properties: none (common ones cover it)
    },
};

ElementRegistry.register(ShapeElement);
