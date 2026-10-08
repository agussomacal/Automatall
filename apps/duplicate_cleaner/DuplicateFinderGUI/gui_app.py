import sys
from pathlib import Path

# Ensure parent dir is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from .main_window import MainWindow


class DuplicateFinderApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(flags=Gio.ApplicationFlags.NON_UNIQUE, **kwargs)
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = MainWindow(application=self)
        self.window.present()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Load CSS
        css_provider = Gtk.CssProvider()
        css_path = Path(__file__).parent.parent / "style.css"
        if css_path.exists():
            css_provider.load_from_path(str(css_path))

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
