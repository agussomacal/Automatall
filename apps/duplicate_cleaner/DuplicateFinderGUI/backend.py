"""
DuplicateFinderGUI backend bridge: wraps DuplicateFinderLogic functionality.
Captures progress and routes it to callbacks.
"""
import io
import sys
from pathlib import Path
from contextlib import redirect_stdout

# Ensure parent dir is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from DuplicateFinderLogic.logic import DuplicateFinderLogic, FileInfo


def _capture(fn, *args, **kwargs):
    """Capture stdout from logic functions."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


_logic_instance = DuplicateFinderLogic()


def scan_folder(folder_path: str, recursive: bool = False, progress_callback=None):
    """Scan folder and return (success, message, stats)."""

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    # Monkey-patch print in logic
    old_print = print

    def custom_print(*args, **kwargs):
        msg = " ".join(map(str, args))
        log(msg)
        old_print(msg, **kwargs)

    # Temporarily replace print
    builtins_import_needed = "builtins"
    import builtins
    original_print = builtins.print

    try:
        builtins.print = custom_print
        success, msg = _logic_instance.scan_folder(folder_path, recursive)
        return success, msg, _logic_instance.scan_stats
    finally:
        builtins.print = original_print


def load_duplicates() -> list:
    """Get all duplicate groups."""
    return _logic_instance.get_duplicate_groups()


def delete_selected_files(files_to_delete: list) -> tuple:
    """Delete multiple files, return (success, failed_list)."""
    return _logic_instance.cleanup_duplicates(files_to_delete)


def get_scan_stats():
    """Get current scan statistics."""
    return _logic_instance.scan_stats