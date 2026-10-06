#!/usr/bin/env python3
"""SuperMicroAppManager - A modular app launcher hub"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

# !/usr/bin/env python3
"""SuperMicroAppManager - A modular app launcher hub"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import subprocess
import yaml
import os
from pathlib import Path

# TILE CONFIGURATION
ICON_SIZE = 32  # Pixel size for icons (adjust as needed)
TILE_WIDTH = 180  # Maximum tile width
TILE_HEIGHT = 100  # Approximate tile height
SPACING = 15  # Spacing between tiles


class AppTile(Gtk.EventBox):
    """Individual app tile in the list"""

    def __init__(self, name, description, icon, command, script_dir=None):
        super().__init__()
        self.name = name
        self.command = command
        self.script_dir = script_dir or Path(__file__).parent.resolve()

        # Configure hover effect
        self.connect("button-press-event", self.on_clicked)
        self.connect("enter-notify-event", self.on_hover)
        self.connect("leave-notify-event", self.on_leave)

        # Create main hbox for tile content
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_hbox.set_spacing(10)
        main_hbox.set_margin_start(10)
        main_hbox.set_margin_end(10)
        main_hbox.set_margin_top(8)
        main_hbox.set_margin_bottom(8)

        # --- Icon with EXACT fixed size ---
        from gi.repository import GdkPixbuf

        self.icon_area = Gtk.Box()
        self.icon_area.set_size_request(ICON_SIZE, ICON_SIZE)

        self.image = Gtk.Image()

        if icon:
            expanded_icon = os.path.expanduser(icon)
            icon_path = Path(expanded_icon)

            if not icon_path.is_absolute():
                icon_path = self.script_dir / icon

            if icon_path.exists():
                try:
                    # Load and resize to EXACT ICON_SIZE x ICON_SIZE
                    scaled_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(icon_path), ICON_SIZE, ICON_SIZE, True
                    )
                    self.image.set_from_pixbuf(scaled_pixbuf)
                except Exception as e:
                    print(f"❌ Failed to load icon {icon_path}: {e}")
                    self.image.set_from_icon_name("image-x-generic", Gtk.IconSize.SMALL_TOOLBAR)
            else:
                self.image.set_from_icon_name("image-x-generic", Gtk.IconSize.SMALL_TOOLBAR)
        else:
            self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)

        self.icon_area.pack_start(self.image, False, False, 0)

        # --- Text section ---
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.set_spacing(2)

        name_label = Gtk.Label(label=name)
        name_label.set_xalign(0)
        name_label.set_markup(f"<b><big>{name}</big></b>")

        desc_label = Gtk.Label(label=description)
        desc_label.set_xalign(0)
        desc_label.set_line_wrap(True)
        desc_label.set_max_width_chars(25)

        text_box.pack_start(name_label, False, False, 0)
        text_box.pack_start(desc_label, True, True, 0)

        main_hbox.pack_start(self.icon_area, False, False, 0)
        main_hbox.pack_start(text_box, True, True, 0)

        self.add(main_hbox)
        self.set_size_request(TILE_WIDTH, -1)  # Allow flexible height
        self.show_all()

    def on_clicked(self, widget, event):
        if event.button == 1:
            subprocess.Popen([self.command])
            return True

    def on_hover(self, widget, event):
        self.override_background_color(
            Gtk.StateType.NORMAL,
            Gdk.RGBA(red=0.4, green=0.3, blue=0.6, alpha=0.15)
        )
        return False

    def on_leave(self, widget, event):
        self.override_background_color(
            Gtk.StateType.NORMAL,
            Gdk.RGBA(red=0.0, green=0.0, blue=0.0, alpha=0.0)
        )
        return False


class SuperMicroAppManager(Gtk.Window):
    """Main application window"""

    def __init__(self):
        super().__init__(title="SuperMicroAppManager")
        self.set_default_size(400, 600)
        self.set_border_width(20)

        # Load configuration
        self.apps = self.load_apps()

        # Create single vertical scrollable container
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_margin_start(5)
        scrolled_window.set_margin_end(5)

        # Vertical box for tiles (one above another)
        self.tiles_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tiles_vbox.set_spacing(SPACING)
        self.tiles_vbox.set_margin_start(5)
        self.tiles_vbox.set_margin_end(5)

        scrolled_window.add(self.tiles_vbox)

        # Header
        header_label = Gtk.Label()
        header_label.set_markup('<span size="x-large" weight="bold">✨ SuperMicro App Manager ✨</span>')
        header_label.set_margin_bottom(15)

        # Footer with buttons
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer_box.set_margin_top(15)

        refresh_btn = Gtk.Button(label="↻ Refresh")
        refresh_btn.connect("clicked", lambda _: self.refresh())
        footer_box.pack_start(refresh_btn, False, False, 5)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer_box.pack_start(spacer, True, True, 0)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda _: self.destroy())
        footer_box.pack_end(close_btn, False, False, 5)

        # Main layout: header | scrollable tiles | footer
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.pack_start(header_label, False, False, 0)
        main_vbox.pack_start(scrolled_window, True, True, 0)
        main_vbox.pack_start(footer_box, False, False, 0)

        # Add main_vbox as THE single child
        self.add(main_vbox)

        self.populate_tiles()
        self.show_all()

    def load_apps(self):
        env_path = os.environ.get('SUPERMICRO_CONFIG')
        if env_path and os.path.exists(env_path):
            config_path = Path(env_path)
        else:
            script_dir = Path(__file__).parent.resolve()
            config_path = script_dir / "config.yaml"

        try:
            with open(config_path) as f:
                return yaml.safe_load(f).get("apps", [])
        except FileNotFoundError:
            print(f"⚠️ Config not found: {config_path}")
            return []

    def populate_tiles(self):
        # Clear existing tiles
        for child in self.tiles_vbox.get_children():
            self.tiles_vbox.remove(child)

        self.script_dir = Path(__file__).parent.resolve()

        if not self.apps:
            msg = Gtk.Label(label="📭 No apps configured.\nAdd apps to your config.yaml")
            msg.set_use_markup(True)
            self.tiles_vbox.pack_start(msg, False, False, 10)
            return

        for app in self.apps:
            tile = AppTile(
                name=app.get("name", "Unknown"),
                description=app.get("description", ""),
                icon=app.get("icon"),
                command=app.get("command", ""),
                script_dir=self.script_dir
            )
            self.tiles_vbox.pack_start(tile, False, False, 0)

    def refresh(self):
        print("🔄 Refreshing app list...")
        self.populate_tiles()


def ensure_default_config():
    """Create a starter config if none exists"""
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / "config.yaml"

    if not config_path.exists():
        sample = """
# SuperMicroAppManager Configuration
# Add your apps below

apps:
  - name: "Link Creator"
    description: "Create symlink from clipboard path"
    command: "./apps/symlink_creator.sh"
    icon: "./icons/link.png"

  - name: "File Info"
    description: "Display detailed file information"
    command: "./apps/file_info.sh"

# Add more apps here...
"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(sample)
        print(f"✓ Created default config at {config_path}")

    return config_path


def main():
    ensure_default_config()
    app = SuperMicroAppManager()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
