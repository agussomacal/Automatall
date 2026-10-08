import sys
from pathlib import Path

# Ensure parent dir is in path for NoServerSync module
sys.path.insert(0, str(Path(__file__).parent.parent))

from gi.repository import Gtk, Adw, Gio, GLib

from .main_window import MainWindow
from .backend import load_config as _load_config


class NoServerSyncGUIApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(flags=Gio.ApplicationFlags.NON_UNIQUE, **kwargs)
        self.config = None
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Create About dialog
        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.on_about)
        self.add_action(action)

        # Create Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)

    def do_activate(self):
        print("[GUI_APP] Loading config on startup...")
        self.config = _load_config()

        # Check if main device is set
        from .backend import get_main_device
        main = get_main_device(self.config)
        if not main:
            print("[GUI_APP] WARNING: No main device configured!")
            # Could show warning dialog, or just rely on run_sync() check

        print(f"[GUI_APP] Config loaded: devices={list(self.config['devices'].keys())}, main={main}")

        if self.window is None:
            self.window = MainWindow(application=self)
        self.window.present()

    def get_config(self):
        """Return the app's config (single source of truth)."""
        return self.config

    def update_config(self, new_config):
        """Update the app's config and persist to disk."""
        self.config = new_config
        print(f"[GUI_APP] Config updated in memory")

    def on_about(self, action, param):
        """Show About dialog."""
        dialog = Gtk.AboutDialog(
            transient_for=self.window,
            program_name="NoServerSync",
            version="0.1.0",
            comments="Serverless folder synchronization between devices",
            authors=["Agus Somacal"],
            license_type=Gtk.License.MIT_X11,
            logo_icon_name="folder-sync-symbolic"
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def on_quit(self, action, param):
        """Quit the application."""
        self.quit()
