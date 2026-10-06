#!/usr/bin/env python3
"""SuperMicroAppManager - A modular app launcher hub with filtering"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf
import subprocess
import yaml
import os
import stat
import json
from pathlib import Path

# TILE CONFIGURATION
ICON_SIZE = 32
TILE_WIDTH = 180
SPACING = 15

# App order persistence file
PERSISTENCE_FILE = "app_order.json"


class AppTile(Gtk.EventBox):
    """Individual app tile"""

    def __init__(self, name, description, icon, command, script_dir=None,
                 app_base_dir=None, index=0, app_config=None):
        super().__init__()
        self.name = name
        self.app_config = app_config or {}  # Store full config
        self.app_base_dir = app_base_dir or script_dir or Path(__file__).parent.resolve()
        self.script_dir = script_dir or Path(__file__).parent.resolve()
        self.index = index

        # Convert relative command paths to absolute
        if command.startswith('./'):
            abs_command = str(self.app_base_dir / command.lstrip('./'))
            self.command = abs_command
        elif command.startswith('/'):
            self.command = command
        else:
            self.command = str(self.app_base_dir / command)

        # Connect single-click event (remove D&D handlers)
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

        # Icon
        self.icon_area = Gtk.Box()
        self.icon_area.set_size_request(ICON_SIZE, ICON_SIZE)

        self.image = Gtk.Image()

        if icon:
            expanded_icon = os.path.expanduser(icon)
            icon_path = Path(expanded_icon)

            if not icon_path.is_absolute():
                icon_path = self.app_base_dir / icon
                if not icon_path.exists():
                    icon_path = self.script_dir / "icons" / icon

            if icon_path.exists():
                try:
                    scaled_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(icon_path), ICON_SIZE, ICON_SIZE, True
                    )
                    self.image.set_from_pixbuf(scaled_pixbuf)
                except Exception:
                    self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)
            else:
                self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)
        else:
            self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)

        self.icon_area.pack_start(self.image, False, False, 0)

        # Text section
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
        """Launch app on click"""
        if event.button == 1:
            print(f"▶️ Launching app: {self.name}")

            try:
                import subprocess

                # Check if it's a GUI app (has 'module') or legacy script (has 'command')
                if hasattr(self, 'app_config') and self.app_config.get('module'):
                    # GUI app - launch the Python module
                    app_dir = getattr(self, 'app_base_dir', None)
                    module_name = self.app_config.get('module', 'app')
                    gui_module = app_dir / f"{module_name}.py"

                    if gui_module.exists():
                        # Launch as separate process so main window stays responsive
                        subprocess.Popen(['python3', str(gui_module)])
                    else:
                        print(f"❌ GUI module not found: {gui_module}")
                elif self.command:
                    # Legacy script execution
                    if self.command.endswith('.sh'):
                        subprocess.Popen(['/bin/bash', self.command])
                    else:
                        subprocess.Popen([self.command])
                else:
                    print(f"⚠️ No command or module defined for: {self.name}")

            except Exception as e:
                print(f"❌ Error launching app: {e}")

        return False

    def on_hover(self, widget, event):
        self.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(red=0.4, green=0.3, blue=0.6, alpha=0.15))
        return False

    def on_leave(self, widget, event):
        self.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(red=0.0, green=0.0, blue=0.0, alpha=0.0))
        return False


class SuperMicroAppManager(Gtk.Window):
    """Main application window with filtering"""

    def __init__(self):
        super().__init__(title="SuperMicroAppManager")
        self.set_default_size(500, 650)
        self.set_border_width(20)

        # === INITIALIZE ALL ATTRIBUTES FIRST ===
        # Discover and load apps
        self.apps = self.discover_apps()
        self.original_apps = self.apps.copy()

        # Load saved order
        self.load_app_order()

        # Current filter state
        self.current_category = "All"
        self.search_query = ""

        # Create tile container (used by populate_tiles)
        self.tiles_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tiles_vbox.set_spacing(SPACING)
        self.tiles_vbox.set_margin_start(5)
        self.tiles_vbox.set_margin_end(5)

        # Create count label (used by update_count_label -> populate_tiles)
        self.count_label = Gtk.Label()

        # Create search entry (used by on_search_changed)
        self.search_entry = Gtk.Entry()

        # Category buttons dict
        self.category_buttons = {}

        # === NOW CREATE UI LAYOUT ===
        # Create main vertical layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(15)
        main_vbox.set_border_width(15)

        # === HEADER ===
        header_label = Gtk.Label()
        header_label.set_markup('<span size="x-large" weight="bold">✨ SuperMicro App Manager ✨</span>')
        main_vbox.pack_start(header_label, False, False, 5)

        # === SEARCH BOX ===
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_spacing(10)

        self.search_entry.set_placeholder_text("🔍 Search apps by name, description, or tag...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("changed", self.on_search_changed)

        clear_btn = Gtk.Button(label="✕")
        clear_btn.set_size_request(30, 30)
        clear_btn.connect("clicked", self.clear_search)

        search_box.pack_start(self.search_entry, True, True, 0)
        search_box.pack_start(clear_btn, False, False, 0)
        main_vbox.pack_start(search_box, False, False, 0)

        # === CATEGORY FILTERS ===
        cat_scroll = Gtk.ScrolledWindow()
        cat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        cat_scroll.set_min_content_height(40)
        cat_scroll.set_vexpand(False)

        cat_hbox = Gtk.FlowBox()
        cat_hbox.set_selection_mode(Gtk.SelectionMode.NONE)
        cat_hbox.set_max_children_per_line(8)
        cat_hbox.set_min_children_per_line(4)
        cat_hbox.set_column_spacing(5)
        cat_hbox.set_row_spacing(5)

        # Get unique categories
        categories = sorted(set(app.get('category', 'Uncategorized') for app in self.apps))
        categories = ['All'] + categories

        for category in categories:
            btn = Gtk.ToggleButton(
                label=f"{category} ({sum(1 for a in self.apps if a.get('category', 'Uncategorized') == category)})")
            btn.set_margin_start(5)
            btn.set_margin_end(5)
            btn.connect("toggled", self.on_category_toggled, category)

            if category == 'All':
                btn.set_active(True)
                self.category_buttons['All'] = btn

            self.category_buttons[category] = btn
            cat_hbox.add(btn)

        cat_scroll.add(cat_hbox)
        main_vbox.pack_start(cat_scroll, False, False, 0)

        # === APP COUNT LABEL ===
        self.count_label.set_markup('<span size="small">0/0 app(s) visible</span>')
        main_vbox.pack_start(self.count_label, False, False, 0)

        # === SCROLLABLE TILES AREA ===
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_margin_start(5)
        scrolled_window.set_margin_end(5)

        scrolled_window.add(self.tiles_vbox)
        main_vbox.pack_start(scrolled_window, True, True, 0)

        # === FOOTER ===
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer_box.set_margin_top(10)

        refresh_btn = Gtk.Button(label="↻ Refresh")
        refresh_btn.connect("clicked", lambda _: self.refresh())
        footer_box.pack_start(refresh_btn, False, False, 5)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer_box.pack_start(spacer, True, True, 0)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda _: self.destroy())
        footer_box.pack_end(close_btn, False, False, 5)

        main_vbox.pack_start(footer_box, False, False, 0)

        self.add(main_vbox)

        # Now populate tiles (all attributes exist!)
        self.populate_tiles()
        self.show_all()

    def on_search_changed(self, entry):
        self.search_query = entry.get_text().lower()
        self.populate_tiles()

    def clear_search(self, button):
        self.search_entry.set_text("")
        self.search_query = ""
        self.populate_tiles()

    def on_category_toggled(self, button, category):
        if button.get_active():
            # Deactivate all other categories
            for cat, btn in self.category_buttons.items():
                if cat != category:
                    btn.set_active(False)

            self.current_category = category
            self.populate_tiles()

    def update_count_label(self):
        total = len(self.apps)
        visible = len([a for a in self.apps if self.matches_filters(a)])
        self.count_label.set_markup(
            f'<span size="small">{visible}/{total} app(s) visible</span>'
        )

    def matches_filters(self, app):
        """Check if app passes current search and category filters"""
        # Category filter
        if self.current_category != "All":
            if app.get('category', 'Uncategorized') != self.current_category:
                return False

        # Search filter
        if self.search_query:
            name = app.get('name', '').lower()
            desc = app.get('description', '').lower()
            tags = ' '.join(app.get('tags', [])).lower()

            if not (self.search_query in name or
                    self.search_query in desc or
                    self.search_query in tags):
                return False

        return True

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
                    config = yaml.safe_load(f) or {}

                # Validate required fields - accept EITHER 'command' OR 'module'
                if 'name' not in config:
                    print(f"⚠️ Skipping {app_folder.name}: missing 'name' in config")
                    continue

                # Accept 'command' (scripts) OR 'module' (GUI apps)
                if 'command' not in config and 'module' not in config:
                    print(f"⚠️ Skipping {app_folder.name}: missing 'command' or 'module' in config")
                    continue

                config['_base_dir'] = app_folder

                # Determine app type
                if 'module' in config:
                    config['type'] = 'gui'
                else:
                    config['type'] = 'script'

                loaded_apps.append(config)
                print(f"✅ Loaded: {config['name']} ({app_folder.name}) - {config['type']}")

            except Exception as e:
                print(f"❌ Failed to load {app_folder.name}: {e}")

        return loaded_apps

    def load_app_order(self):
        """Load saved app order from JSON file."""
        script_dir = Path(__file__).parent.resolve()
        order_file = script_dir / PERSISTENCE_FILE

        if not order_file.exists():
            return

        try:
            with open(order_file) as f:
                saved_order = json.load(f)

            # Reorder apps to match saved order
            ordered_apps = []
            for name in saved_order:
                for i, app in enumerate(self.apps):
                    if app.get('name') == name:
                        ordered_apps.append(self.apps.pop(i))
                        break

            ordered_apps.extend(self.apps)
            self.apps = ordered_apps
            print(f"📝 Restored saved order ({len(saved_order)} apps)")

        except Exception as e:
            print(f"⚠️ Could not load app order: {e}")

    def save_app_order(self):
        """Save current app order to JSON file."""
        script_dir = Path(__file__).parent.resolve()
        order_file = script_dir / PERSISTENCE_FILE

        try:
            order_list = [app.get('name') for app in self.apps]
            with open(order_file, 'w') as f:
                json.dump(order_list, f, indent=2)
            print(f"💾 Saved app order ({len(order_list)} apps)")
        except Exception as e:
            print(f"⚠️ Could not save app order: {e}")

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

        # Auto-fix script permissions
        self.ensure_all_scripts_executable()

        filtered_apps = [a for a in self.apps if self.matches_filters(a)]

        if not filtered_apps:
            msg = Gtk.Label(
                label=f"🔍 No apps match your filter.\n"
                      f"Try clearing search or selecting 'All' category."
            )
            msg.set_use_markup(True)
            msg.set_justify(Gtk.Justification.CENTER)
            self.tiles_vbox.pack_start(msg, False, False, 10)
        else:
            for idx, app in enumerate(filtered_apps):
                if not app.get('enabled', True):
                    continue
                tile = AppTile(
                    name=app.get("name", "Unknown"),
                    description=app.get("description", ""),
                    icon=app.get("icon"),
                    command=app.get("command", ""),
                    script_dir=Path(__file__).parent.resolve(),
                    app_base_dir=app.get("_base_dir"),
                    index=idx,
                    app_config=app  # Pass entire config!
                )

                self.tiles_vbox.pack_start(tile, False, False, 0)

        self.update_count_label()

    def refresh(self):
        print("🔄 Re-scanning apps...")
        self.apps = self.discover_apps()
        self.original_apps = self.apps.copy()
        self.populate_tiles()


def main():
    app = SuperMicroAppManager()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
