#!/usr/bin/env python3
"""SuperMicroAppManager - A modular app launcher hub with filtering"""

import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import yaml
import os
import stat
import json
import subprocess
import threading
from pathlib import Path

# Import dependency checker
from check_deps import DependencyChecker

# Constants
ICON_SIZE = 32
TILE_WIDTH = 180
SPACING = 15
PERSISTENCE_FILE = "app_order.json"


class AppTile(Gtk.EventBox):
    """Individual app tile"""

    def __init__(self, name, description, icon, app_base_dir, index, app_config, launcher_callback):
        super().__init__()
        self.name = name
        self.app_config = app_config or {}
        self.app_base_dir = app_base_dir or Path(__file__).parent.resolve()
        self.index = index
        self.launch_callback = launcher_callback  # Callback to main window

        # Connect click event
        self.connect("button-press-event", self.on_clicked)
        self.connect("enter-notify-event", self.on_hover)
        self.connect("leave-notify-event", self.on_leave)

        # Create UI
        self._build_ui(name, description, icon)
        self.set_size_request(TILE_WIDTH, -1)
        self.show_all()

    def _build_ui(self, name, description, icon):
        """Build the tile UI elements"""
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_hbox.set_spacing(10)
        main_hbox.set_margin_start(10)
        main_hbox.set_margin_end(10)
        main_hbox.set_margin_top(8)
        main_hbox.set_margin_bottom(8)

        # Icon
        icon_area = Gtk.Box()
        icon_area.set_size_request(ICON_SIZE, ICON_SIZE)
        self.image = Gtk.Image()

        if icon:
            expanded_icon = os.path.expanduser(icon)
            icon_path = Path(expanded_icon)

            if not icon_path.is_absolute():
                icon_path = self.app_base_dir / icon
                if not icon_path.exists():
                    icon_path = Path(__file__).parent / "icons" / icon

            if icon_path.exists():
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon_path), ICON_SIZE, ICON_SIZE, True)
                    self.image.set_from_pixbuf(pixbuf)
                except Exception:
                    self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)
            else:
                self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)
        else:
            self.image.set_from_icon_name("utilities-terminal", Gtk.IconSize.SMALL_TOOLBAR)

        icon_area.pack_start(self.image, False, False, 0)

        # Text
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

        main_hbox.pack_start(icon_area, False, False, 0)
        main_hbox.pack_start(text_box, True, True, 0)

        self.add(main_hbox)

    def on_clicked(self, widget, event):
        """Handle tile click - delegate to main window"""
        if event.button == 1:
            self.launch_callback(self.name)
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

        # === STATE ===
        self.apps_dir = Path(__file__).parent / "apps"
        self.dependency_checker = DependencyChecker(str(self.apps_dir))

        self.apps = self.discover_apps()
        self.original_apps = self.apps.copy()
        self.load_app_order()

        self.current_category = "All"
        self.search_query = ""

        # === UI ELEMENTS ===
        self.tiles_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tiles_vbox.set_spacing(SPACING)
        self.tiles_vbox.set_margin_start(5)
        self.tiles_vbox.set_margin_end(5)

        self.count_label = Gtk.Label()
        self.search_entry = Gtk.Entry()
        self.category_buttons = {}

        # === BUILD UI ===
        self._build_ui()
        self.populate_tiles()
        self.show_all()

    def _build_ui(self):
        """Build the complete UI"""
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(15)
        main_vbox.set_border_width(15)

        # Header
        header_label = Gtk.Label()
        header_label.set_markup('<span size="x-large" weight="bold">✨ SuperMicro App Manager ✨</span>')
        main_vbox.pack_start(header_label, False, False, 5)

        # Search
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

        # Categories
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

        categories = sorted(set(app.get('category', 'Uncategorized') for app in self.apps))
        total_apps = len(self.apps)
        category_counts = {cat: sum(1 for a in self.apps if a.get('category', 'Uncategorized') == cat) for cat in
                           categories}

        for category in ['All'] + categories:
            count = total_apps if category == 'All' else category_counts.get(category, 0)
            btn = Gtk.ToggleButton(label=f"{category} ({count})")
            btn.set_margin_start(5)
            btn.set_margin_end(5)
            btn.connect("toggled", self.on_category_toggled, category)

            if category == 'All':
                btn.set_active(True)

            self.category_buttons[category] = btn
            cat_hbox.add(btn)

        cat_scroll.add(cat_hbox)
        main_vbox.pack_start(cat_scroll, False, False, 0)

        # Count label
        self.count_label.set_markup('<span size="small">0/0 app(s) visible</span>')
        main_vbox.pack_start(self.count_label, False, False, 0)

        # Tiles area
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_margin_start(5)
        scrolled_window.set_margin_end(5)
        scrolled_window.add(self.tiles_vbox)
        main_vbox.pack_start(scrolled_window, True, True, 0)

        # Footer
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

    # ========== EVENT HANDLERS ==========

    def on_search_changed(self, entry):
        self.search_query = entry.get_text().lower()
        self.populate_tiles()

    def clear_search(self, button):
        self.search_entry.set_text("")
        self.search_query = ""
        self.populate_tiles()

    def on_category_toggled(self, button, category):
        if button.get_active():
            for cat, btn in self.category_buttons.items():
                if cat != category:
                    btn.set_active(False)
            self.current_category = category
            self.populate_tiles()

    def update_count_label(self):
        total = len(self.apps)
        visible = len([a for a in self.apps if self.matches_filters(a)])
        self.count_label.set_markup(f'<span size="small">{visible}/{total} app(s) visible</span>')

    def matches_filters(self, app):
        """Check if app passes current search and category filters"""
        if self.current_category != "All":
            if app.get('category', 'Uncategorized') != self.current_category:
                return False

        if self.search_query:
            name = app.get('name', '').lower()
            desc = app.get('description', '').lower()
            tags = ' '.join(app.get('tags', [])).lower()

            if not (self.search_query in name or self.search_query in desc or self.search_query in tags):
                return False

        return True

    # ========== APP DISCOVERY ==========

    def discover_apps(self):
        """Scan apps/ folder for self-contained app modules"""
        loaded_apps = []

        if not self.apps_dir.exists():
            print(f"⚠️ Apps directory not found: {self.apps_dir}")
            return loaded_apps

        for app_folder in self.apps_dir.iterdir():
            if not app_folder.is_dir():
                continue

            config_path = app_folder / "config.yaml"
            if not config_path.exists():
                continue

            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}

                if 'name' not in config:
                    continue

                if 'command' not in config and 'module' not in config:
                    continue

                config['_base_dir'] = app_folder
                config['type'] = 'gui' if 'module' in config else 'script'
                loaded_apps.append(config)

            except Exception as e:
                print(f"❌ Failed to load {app_folder.name}: {e}")

        return loaded_apps

    def load_app_order(self):
        """Load saved app order from JSON file"""
        order_file = Path(__file__).parent / PERSISTENCE_FILE

        if not order_file.exists():
            return

        try:
            with open(order_file) as f:
                saved_order = json.load(f)

            ordered_apps = []
            for name in saved_order:
                for i, app in enumerate(self.apps):
                    if app.get('name') == name:
                        ordered_apps.append(self.apps.pop(i))
                        break

            ordered_apps.extend(self.apps)
            self.apps = ordered_apps

        except Exception as e:
            print(f"⚠️ Could not load app order: {e}")

    def save_app_order(self):
        """Save current app order to JSON file"""
        order_file = Path(__file__).parent / PERSISTENCE_FILE

        try:
            order_list = [app.get('name') for app in self.apps]
            with open(order_file, 'w') as f:
                json.dump(order_list, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save app order: {e}")

    def ensure_script_executable(self, script_path):
        """Ensure script files have executable permissions"""
        script_path = Path(script_path)

        if not script_path.exists():
            return False

        if script_path.suffix in ['.sh', '.py', '.pl', '.rb']:
            current_mode = script_path.stat().st_mode
            if not bool(current_mode & stat.S_IXUSR):
                try:
                    script_path.chmod(script_path.stat().st_mode | stat.S_IRWXU)
                    return True
                except PermissionError:
                    return False

        return False

    def ensure_all_scripts_executable(self):
        """Check and fix permissions for all configured scripts"""
        for app in self.apps:
            cmd = app.get("command", "")
            base_dir = app.get("_base_dir")

            if base_dir and cmd:
                if cmd.startswith('./'):
                    script_path = base_dir / cmd.lstrip('./')
                else:
                    script_path = Path(cmd)

                if script_path.exists():
                    self.ensure_script_executable(script_path)

    # ========== TILE MANAGEMENT ==========

    def populate_tiles(self):
        """Create tiles for filtered apps"""
        for child in self.tiles_vbox.get_children():
            self.tiles_vbox.remove(child)

        self.ensure_all_scripts_executable()

        filtered_apps = [a for a in self.apps if self.matches_filters(a)]

        if not filtered_apps:
            msg = Gtk.Label(label="🔍 No apps match your filter.")
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
                    app_base_dir=app.get("_base_dir"),
                    index=idx,
                    app_config=app,
                    launcher_callback=self.handle_app_launch  # Pass callback
                )
                self.tiles_vbox.pack_start(tile, False, False, 0)

        self.update_count_label()

    def refresh(self):
        """Re-scan and reload apps"""
        print("🔄 Re-scanning apps...")
        self.apps = self.discover_apps()
        self.original_apps = self.apps.copy()
        self.populate_tiles()

    # ========== LAUNCH LOGIC - SINGLE METHOD ==========

    def handle_app_launch(self, app_name):
        """
        Unified app launch handler with dependency checking.
        Called when user clicks any app tile.
        """
        # Step 1: Check dependencies
        all_ok, missing, status = self.dependency_checker.check_app(app_name)

        if not all_ok:
            self._show_missing_deps_dialog(app_name, missing)
        else:
            self._execute_app(app_name)

    def _show_missing_deps_dialog(self, app_name, missing):
        """Show dialog asking to install missing dependencies"""
        descriptions = [dep.get('description', dep['name']) for dep in missing]

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Missing Dependencies for {app_name}"
        )

        dialog.format_secondary_text(
            f"This app requires:\n\n" +
            "\n".join([f"• {d}" for d in descriptions]) +
            "\n\nInstall now? (requires sudo)"
        )

        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            self._install_dependencies_and_retry(app_name, missing)
        # If NO, do nothing - user cancels launch

    def _install_dependencies_and_retry(self, app_name, missing):
        """Install dependencies in background, then retry launch"""
        self.set_sensitive(False)

        thread = threading.Thread(
            target=self._do_install_and_retry,
            args=(app_name, missing)
        )
        thread.daemon = True
        thread.start()

    def _do_install_and_retry(self, app_name, missing):
        """Perform installation in background thread"""
        success, msg = self.dependency_checker.install_missing(missing, sudo=True)

        # Return to main thread for UI update
        GLib.idle_add(self._on_install_complete, app_name, success, msg)

    def _on_install_complete(self, app_name, success, msg):
        """Handle installation completion in main thread"""
        self.set_sensitive(True)

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Dependency Installation"
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

        if success:
            self._execute_app(app_name)

    def _execute_app(self, app_name):
        """Actually execute the app (no dependency check)"""
        # Find app config
        app_config = None
        for app in self.apps:
            if app.get('name') == app_name:
                app_config = app
                break

        if not app_config:
            print(f"❌ App not found: {app_name}")
            return

        try:
            app_base_dir = app_config.get('_base_dir')

            # GUI app (has module)
            if app_config.get('module'):
                gui_module = app_base_dir / f"{app_config['module']}.py"
                if gui_module.exists():
                    subprocess.Popen(['python3', str(gui_module)])
                else:
                    print(f"❌ Module not found: {gui_module}")

            # Script app (has command)
            elif app_config.get('command'):
                cmd = app_config['command']
                if cmd.startswith('./'):
                    cmd = str(app_base_dir / cmd.lstrip('./'))

                if cmd.endswith('.sh'):
                    subprocess.Popen(['/bin/bash', cmd])
                else:
                    subprocess.Popen([cmd])

        except Exception as e:
            print(f"❌ Error launching {app_name}: {e}")


def main():
    app = SuperMicroAppManager()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()