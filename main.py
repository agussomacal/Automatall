#!/usr/bin/env python3
"""SuperMicroAppManager - A modular app launcher hub"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import subprocess
import yaml
import os
import stat
from pathlib import Path

# TILE CONFIGURATION
ICON_SIZE = 32
TILE_WIDTH = 180
TILE_HEIGHT = 100
SPACING = 15


class AppTile(Gtk.EventBox):
    """Individual app tile in the list"""

    def __init__(self, name, description, icon, command, script_dir=None, app_base_dir=None):
        super().__init__()
        self.name = name
        self.app_base_dir = app_base_dir or script_dir or Path(__file__).parent.resolve()
        self.script_dir = script_dir or Path(__file__).parent.resolve()

        # Convert relative command paths to absolute (relative to APP folder)
        if command.startswith('./'):
            abs_command = str(self.app_base_dir / command.lstrip('./'))
            self.command = abs_command
        elif command.startswith('/'):
            self.command = command
        else:
            # Assume it's relative to app folder
            self.command = str(self.app_base_dir / command)

        self.connect("button-press-event", self.on_clicked)
        self.connect("enter-notify-event", self.on_hover)
        self.connect("leave-notify-event", self.on_leave)

        # Create main hbox
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_hbox.set_spacing(10)
        main_hbox.set_margin_start(10)
        main_hbox.set_margin_end(10)
        main_hbox.set_margin_top(8)
        main_hbox.set_margin_bottom(8)

        # --- Icon ---
        self.icon_area = Gtk.Box()
        self.icon_area.set_size_request(ICON_SIZE, ICON_SIZE)

        self.image = Gtk.Image()

        if icon:
            expanded_icon = os.path.expanduser(icon)
            icon_path = Path(expanded_icon)

            if not icon_path.is_absolute():
                # Try app folder first, then fall back to shared icons
                icon_path = self.app_base_dir / icon
                if not icon_path.exists():
                    icon_path = self.script_dir / "icons" / icon

            if icon_path.exists():
                try:
                    from gi.repository import GdkPixbuf
                    scaled_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(icon_path), ICON_SIZE, ICON_SIZE, True
                    )
                    self.image.set_from_pixbuf(scaled_pixbuf)
                except Exception as e:
                    self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)
            else:
                self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)
        else:
            self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)

        self.icon_area.pack_start(self.image, False, False, 0)

        # --- Text ---
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
        self.set_size_request(TILE_WIDTH, -1)
        self.show_all()

    def on_clicked(self, widget, event):
        if event.button == 1:
            print(f"▶️ Executing: {self.command}")

            try:
                if self.command.endswith('.sh'):
                    subprocess.Popen(['/bin/bash', self.command])
                else:
                    subprocess.Popen([self.command])
            except PermissionError:
                print(f"⚠️ Permission denied: {self.command}")
            except FileNotFoundError:
                print(f"⚠️ Command not found: {self.command}")
            return True

    def on_hover(self, widget, event):
        self.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(red=0.4, green=0.3, blue=0.6, alpha=0.15))
        return False

    def on_leave(self, widget, event):
        self.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(red=0.0, green=0.0, blue=0.0, alpha=0.0))
        return False


class SuperMicroAppManager(Gtk.Window):
    """Main application window"""

    def __init__(self):
        super().__init__(title="SuperMicroAppManager")
        self.set_default_size(400, 600)
        self.set_border_width(20)

        # Discover and load apps
        self.apps = self.discover_apps()

        # Create scrollable container
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_margin_start(5)
        scrolled_window.set_margin_end(5)

        self.tiles_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tiles_vbox.set_spacing(SPACING)
        self.tiles_vbox.set_margin_start(5)
        self.tiles_vbox.set_margin_end(5)

        scrolled_window.add(self.tiles_vbox)

        # Header with app count
        app_count = len([a for a in self.apps if a.get('enabled', True)])
        header_label = Gtk.Label()
        header_label.set_markup(
            f'<span size="x-large" weight="bold">✨ SuperMicro App Manager ✨</span>\n'
            f'<span size="small">{app_count} app(s) discovered</span>'
        )
        header_label.set_margin_bottom(15)

        # Footer
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

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.pack_start(header_label, False, False, 0)
        main_vbox.pack_start(scrolled_window, True, True, 0)
        main_vbox.pack_start(footer_box, False, False, 0)

        self.add(main_vbox)

        self.populate_tiles()
        self.show_all()

    def discover_apps(self):
        """Scan apps/ folder for self-contained app modules."""
        script_dir = Path(__file__).parent.resolve()
        apps_dir = script_dir / "apps"
        loaded_apps = []

        if not apps_dir.exists():
            print(f"⚠️ Apps directory not found: {apps_dir}")
            return loaded_apps

        print(f"🔍 Discovering apps in: {apps_dir}")

        for app_folder in apps_dir.iterdir():
            if not app_folder.is_dir():
                continue

            config_path = app_folder / "config.yaml"

            if not config_path.exists():
                print(f"⚠️ Skipping {app_folder.name}: no config.yaml")
                continue

            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                # Validate required fields
                if 'name' not in config:
                    print(f"⚠️ Skipping {app_folder.name}: missing 'name' in config")
                    continue

                if 'command' not in config:
                    print(f"⚠️ Skipping {app_folder.name}: missing 'command' in config")
                    continue

                config['_base_dir'] = app_folder  # Store base directory
                loaded_apps.append(config)
                print(f"✅ Loaded: {config['name']} ({app_folder.name})")

            except Exception as e:
                print(f"❌ Failed to load {app_folder.name}: {e}")

        return loaded_apps

    def ensure_script_executable(self, script_path):
        """Ensure script files have executable permissions."""
        script_path = Path(script_path)

        if not script_path.exists():
            return False

        if script_path.suffix in ['.sh', '.py', '.pl', '.rb']:
            current_mode = script_path.stat().st_mode
            is_executable = bool(current_mode & stat.S_IXUSR)

            if not is_executable:
                try:
                    script_path.chmod(script_path.stat().st_mode | stat.S_IRWXU)
                    return True
                except PermissionError:
                    return False

        return False

    def ensure_all_scripts_executable(self):
        """Check and fix permissions for all configured scripts."""
        fixed_count = 0

        for app in self.apps:
            cmd = app.get("command", "")
            base_dir = app.get("_base_dir")

            if base_dir and cmd:
                if cmd.startswith('./'):
                    script_path = base_dir / cmd.lstrip('./')
                else:
                    script_path = Path(cmd)

                if script_path.exists():
                    if self.ensure_script_executable(script_path):
                        print(f"✅ Made executable: {script_path.name}")
                        fixed_count += 1

        if fixed_count > 0:
            print(f"📝 Fixed permissions for {fixed_count} script(s)")

    def populate_tiles(self):
        # Clear existing tiles
        for child in self.tiles_vbox.get_children():
            self.tiles_vbox.remove(child)

        # Auto-fix script permissions BEFORE creating tiles
        self.ensure_all_scripts_executable()

        if not self.apps:
            msg = Gtk.Label(
                label="📭 No apps found.\n\n"
                      "Create app folders in ~/repos/SuperMicroAppManager/apps/\n"
                      "Each folder needs a config.yaml with 'name' and 'command'"
            )
            msg.set_use_markup(True)
            msg.set_justify(Gtk.Justification.CENTER)
            self.tiles_vbox.pack_start(msg, False, False, 10)
            return

        for app in self.apps:
            if not app.get('enabled', True):
                continue

            tile = AppTile(
                name=app.get("name", "Unknown"),
                description=app.get("description", ""),
                icon=app.get("icon"),
                command=app.get("command", ""),
                script_dir=Path(__file__).parent.resolve(),
                app_base_dir=app.get("_base_dir")
            )
            self.tiles_vbox.pack_start(tile, False, False, 0)

    def refresh(self):
        print("🔄 Re-scanning apps...")
        self.apps = self.discover_apps()
        self.populate_tiles()


def main():
    app = SuperMicroAppManager()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()