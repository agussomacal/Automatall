"""DuplicateFinderGUI package - GTK4 frontend for Duplicate Finder."""
__version__ = "0.1.0"

from .gui_app import DuplicateFinderApp
from .main_window import MainWindow
from .backend import load_duplicates, scan_folder, delete_selected_files

__all__ = [
    "DuplicateFinderApp",
    "MainWindow",
    "load_duplicates",
    "scan_folder",
    "delete_selected_files",
]