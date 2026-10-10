"""NoServerSyncGUI package - GTK4 frontend for NoServerSync."""
__version__ = "0.1.0"

from .gui_app import NoServerSyncGUIApp
from .main_window import MainWindow
from .dialogs import AddDeviceDialog, AddFolderDialog
from .backend import load_config, list_devices, add_device, list_folders, add_folder

__all__ = [
    "NoServerSyncGUIApp",
    "MainWindow",
    "AddDeviceDialog",
    "AddFolderDialog",
    "load_config",
    "list_devices",
    "add_device",
    "list_folders",
    "add_folder",
]