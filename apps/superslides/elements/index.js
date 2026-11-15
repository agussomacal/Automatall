// ============================================================
// elements/index.js — THE REGISTRY HOOKUP.
// This is the ONLY file you edit when adding a new element type:
// one import line + one register call. The import itself triggers
// registration (each element module self-registers).
// ============================================================

import '../../elements/text/text.js';
import '../../elements/shape/shape.js';
import '../../elements/figure/figure.js';

// Future elements: add the import here. If you forget, the app
// throws at startup telling you the type is missing — loud, not silent.
