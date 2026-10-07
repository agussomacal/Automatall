#!/usr/bin/env python3
"""GUI for Projects Manager with Status Tracking"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, GObject
import os

# Import local logic
try:
    from .logic import ProjectsManagerLogic
except ImportError:
    from logic import ProjectsManagerLogic


class ProjectsManagerApp(Gtk.Window):
    """Main application window"""

    def __init__(self):
        super().__init__(title="Projects Manager")
        self.set_default_size(850, 650)
        self.set_border_width(15)
        self.set_resizable(True)

        # Initialize logic
        self.logic = ProjectsManagerLogic()

        # Prevent reentrant refresh
        self._refreshing = False
        self._search_timeout = None
        self.auto_refresh_timer = None

        # Main Layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(15)

        # Header
        header = Gtk.Label()
        header.set_markup("<b><span size='x-large'>Projects Manager</span></b>")
        header.set_margin_bottom(5)
        main_vbox.pack_start(header, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup(
            "<small>Create project templates with predefined folder structures and track publication status</small>")
        subtitle.set_sensitive(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.set_line_wrap(True)
        main_vbox.pack_start(subtitle, False, False, 0)

        # Top section: Create new project
        create_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        create_section.set_spacing(10)

        create_header = Gtk.Label()
        create_header.set_markup("<b>Create New Project</b>")
        create_header.set_halign(Gtk.Align.START)
        create_header.set_xalign(0)
        create_section.pack_start(create_header, False, False, 5)

        # Project Name Input
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        name_box.set_spacing(10)

        name_label = Gtk.Label(label="Project Name:")
        name_label.set_xalign(0)
        name_label.set_size_request(120, -1)

        self.project_name = Gtk.Entry()
        self.project_name.set_placeholder_text("Enter project name...")
        self.project_name.set_hexpand(True)
        self.project_name.connect("changed", self.on_name_changed)

        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(self.project_name, True, True, 0)
        create_section.pack_start(name_box, False, False, 0)

        # Target Folder Selection
        folder_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        folder_box.set_spacing(10)

        folder_label = Gtk.Label(label="Target Folder:")
        folder_label.set_xalign(0)
        folder_label.set_size_request(120, -1)

        self.target_folder = Gtk.Entry()
        self.target_folder.set_placeholder_text(str(self.logic.default_folder))
        self.target_folder.set_text(str(self.logic.default_folder))
        self.target_folder.set_hexpand(True)
        self.target_folder.set_editable(True)
        self.target_folder.connect("changed", self.on_folder_changed)

        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.connect("clicked", self.on_browse_folder)

        folder_box.pack_start(folder_label, False, False, 0)
        folder_box.pack_start(self.target_folder, True, True, 0)
        folder_box.pack_start(browse_btn, False, False, 0)
        create_section.pack_start(folder_box, False, False, 0)

        # Drop Zone on folder line
        drop_zone = Gtk.EventBox()
        drop_zone.add(folder_box)
        drop_zone.set_visible_window(False)

        targets = [Gtk.TargetEntry.new("text/uri-list", 0, 0)]
        drop_zone.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.COPY)
        drop_zone.connect("drag-data-received", self.on_folder_drop)
        drop_zone.connect("drag-motion", self.on_drag_motion)

        create_section.pack_start(drop_zone, False, True, 0)

        # Subfolders Preview
        preview_label = Gtk.Label()
        preview_label.set_markup(
            "<small>Subfolders to be created: Bibliography, Code, Notes, Boards, Article, Blog</small>")
        preview_label.set_halign(Gtk.Align.START)
        create_section.pack_start(preview_label, False, False, 5)

        create_section.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)

        # Status Selection
        status_label = Gtk.Label()
        status_label.set_markup("<b>Initial Status:</b>")
        status_label.set_halign(Gtk.Align.START)
        status_label.set_xalign(0)
        create_section.pack_start(status_label, False, False, 0)

        status_box_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box_input.set_spacing(10)

        self.status_combo = Gtk.ComboBoxText()
        for status in self.logic.VALID_STATUSES:
            label = self.logic.STATUS_LABELS.get(status, status).replace("_", " ").title()
            self.status_combo.append_text(label)
        default_status = self.logic.settings.get("default_status", "developing").replace("_", " ").title()
        self.status_combo.set_active_id(default_status)

        status_box_input.pack_start(status_label, False, False, 0)
        status_box_input.pack_start(self.status_combo, True, True, 0)
        create_section.pack_start(status_box_input, False, False, 0)

        create_btn = Gtk.Button(label="📁 Create Template")
        create_btn.get_style_context().add_class("suggested-action")
        create_btn.connect("clicked", self.on_create)
        create_section.pack_start(create_btn, False, False, 5)

        main_vbox.pack_start(create_section, False, False, 0)

        # Middle section: Existing Projects List
        projects_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        projects_section.set_spacing(5)

        projects_header = Gtk.Label()
        projects_header.set_markup("<b>Your Projects</b>")
        projects_header.set_halign(Gtk.Align.START)
        projects_header.set_xalign(0)
        projects_section.pack_start(projects_header, False, False, 5)

        # Projects list
        projects_scroll = Gtk.ScrolledWindow()
        projects_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        projects_scroll.set_min_content_height(200)
        projects_scroll.set_shadow_type(Gtk.ShadowType.IN)

        self.projects_list = Gtk.ListBox()
        self.projects_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.projects_list.get_style_context().add_class("projects-list")
        self.projects_list.connect("row-activated", self.on_project_activated)

        projects_scroll.add(self.projects_list)
        projects_section.pack_start(projects_scroll, True, True, 0)

        main_vbox.pack_start(projects_section, True, True, 0)

        # Status Legend
        legend_label = Gtk.Label()
        legend_text = "<small>Status Legend: </small>"
        for status in self.logic.VALID_STATUSES:
            color = self.logic.STATUS_COLORS.get(status, "#000")
            label_text = self.logic.STATUS_LABELS.get(status, status).replace("_", " ").title()
            legend_text += f"<span foreground='{color}'><b>■</b></span> {label_text}  "

        legend_label.set_markup(legend_text)
        legend_label.set_halign(Gtk.Align.START)
        legend_label.set_xalign(0)
        legend_label.set_line_wrap(True)
        main_vbox.pack_start(legend_label, False, False, 0)

        # Status Bar
        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_markup('<span foreground="#666">Ready</span>')
        main_vbox.pack_start(self.status_label, False, False, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_spacing(10)
        btn_box.set_halign(Gtk.Align.END)

        settings_btn = Gtk.Button(label="⚙ Settings")
        settings_btn.connect("clicked", self.on_settings)
        btn_box.pack_start(settings_btn, False, False, 0)

        export_btn = Gtk.Button(label="📊 Export List")
        export_btn.connect("clicked", self.on_export_list)
        btn_box.pack_start(export_btn, False, False, 0)

        main_vbox.pack_start(btn_box, False, False, 0)

        self.add(main_vbox)
        self.connect("destroy", self.on_destroy)

        # Apply CSS
        self.apply_css()

        # Load existing projects
        self.refresh_projects()

        # Start auto-refresh every 10 seconds (slower to reduce churn)
        self.auto_refresh_timer = GLib.timeout_add_seconds(10, self.refresh_projects)

        print("[INFO] Projects Manager app initialized with auto-refresh")

    def on_destroy(self, widget):
        """Cleanup on window close"""
        if self.auto_refresh_timer:
            GLib.source_remove(self.auto_refresh_timer)
            self.auto_refresh_timer = None
        Gtk.main_quit()

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .projects-list row {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin: 3px 0;
                padding: 8px;
            }
            .projects-list row:hover {
                background-color: #f0f0ff;
                border-color: #6d4aff;
            }
            .suggested-action {
                background-color: #6d4aff;
                color: white;
            }
            .destructive-action {
                background-color: #e74c3c;
                color: white;
            }
            .status-developing { border-left: 4px solid #6d4aff; }
            .status-in_review { border-left: 4px solid #f39c12; }
            .status-answering_review { border-left: 4px solid #e67e22; }
            .status-preprint { border-left: 4px solid #3498db; }
            .status-published { border-left: 4px solid #2ecc71; }
            .status-inactive { border-left: 4px solid #95a5a6; }
        """)
        screen = Gdk.Screen.get_default()
        style_context = self.get_style_context()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def on_name_changed(self, entry):
        """Validate project name in real-time"""
        name = entry.get_text().strip()
        if name:
            is_valid, msg = self.logic.validate_project_name(name)
            if is_valid:
                self.status_label.set_markup('<span foreground="#2ecc71">Name OK</span>')
            else:
                self.status_label.set_markup(f'<span foreground="#e74c3c">{msg}</span>')
        else:
            self.status_label.set_markup('<span foreground="#666">Ready</span>')

    def on_folder_changed(self, entry):
        """Update status when folder is manually changed"""
        folder = entry.get_text()
        if folder and os.path.isdir(folder):
            self.status_label.set_markup(f'<span foreground="#666">Target folder: {folder}</span>')

    def on_browse_folder(self, button):
        """Open folder browser dialog"""
        chooser = Gtk.FileChooserDialog(
            title="Select Target Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        chooser.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        current_text = self.target_folder.get_text()
        if current_text and os.path.isdir(current_text):
            chooser.set_current_folder(current_text)

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            folder = chooser.get_filename()
            self.target_folder.set_text(folder)
            self.status_label.set_markup(f'<span foreground="#2ecc71">Folder selected: {folder}</span>')

        chooser.destroy()

    def on_drag_motion(self, widget, context, x, y, time):
        return True

    def on_folder_drop(self, widget, context, x, y, selection_data, info, time):
        data = selection_data.get_data()
        if not data:
            return

        try:
            text = data.decode('utf-8')
        except:
            return

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('file://'):
                path = line[7:].replace('%20', ' ')
                if os.path.isdir(path):
                    self.target_folder.set_text(path)
                    self.status_label.set_markup(f'<span foreground="#2ecc71">Folder: {path}</span>')
                    break

    def on_create(self, button):
        """Create the project template"""
        name = self.project_name.get_text().strip()
        folder = self.target_folder.get_text()

        status_text = self.status_combo.get_active_text()
        status = status_text.lower().replace(" ", "_") if status_text else "developing"

        if not name:
            self.show_error("Please enter a project name")
            return

        is_valid, msg = self.logic.validate_project_name(name)
        if not is_valid:
            self.show_error(msg)
            return

        self.update_status("Creating project...")
        success, result = self.logic.create_project(name, folder, status)


        if success:
            self.update_status("✓ Project created successfully!", success=True)
            self.show_dialog(Gtk.MessageType.INFO, "Success", result)
            self.project_name.set_text("")
            # Force immediate refresh instead of scheduled
            # GLib.idle_add(self.refresh_projects)
            self.refresh_projects()
        else:
            self.update_status(f"✗ {result}", success=False)
            self.show_dialog(Gtk.MessageType.ERROR, "Failed", f"Failed to create project:\n{result}")

    def refresh_projects(self):
        """Refresh the projects list - prevents reentrancy and handles errors safely"""
        # Prevent concurrent refresh calls (CRITICAL!)
        if getattr(self, '_refreshing', False):
            print("[DEBUG] Refresh already in progress, skipping...")
            return True

        self._refreshing = True

        try:
            # Fetch projects BEFORE touching UI
            success, projects = self.logic.list_projects()

            if not success or projects is None:
                print("[ERROR] Failed to load projects from disk")
                self.update_status("Error loading projects", success=False)
                return True  # Keep timer running

            # Clear existing rows safely
            rows_to_remove = list(self.projects_list)
            for row in rows_to_remove:
                self.projects_list.remove(row)

            # Handle empty list
            if not projects:

                no_projects = Gtk.Label()
                no_projects.set_markup("<i>No projects found</i>")
                no_projects.set_sensitive(False)
                no_projects.set_margin_top(50)
                no_projects.set_halign(Gtk.Align.CENTER)
                self.projects_list.add(no_projects)
                no_projects.show_all()
                return True

            # Build rows for all projects
            for project in projects:
                row = Gtk.ListBoxRow()
                row.set_selectable(False)
                row.set_activatable(True)

                # Horizontal layout
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                hbox.set_spacing(15)
                hbox.set_margin_start(10)
                hbox.set_margin_end(10)
                hbox.set_margin_top(8)
                hbox.set_margin_bottom(8)
                hbox.set_hexpand(True)

                # Status indicator
                status = project.get("status", "developing")
                status_color = self.logic.STATUS_COLORS.get(status, "#95a5a6")
                status_label_display = self.logic.STATUS_LABELS.get(status, status).replace("_", " ").title()

                status_indicator = Gtk.Label()
                status_indicator.set_markup(f'<span foreground="{status_color}" size="xx-large">●</span>')
                status_indicator.set_halign(Gtk.Align.CENTER)

                status_lbl = Gtk.Label()
                status_lbl.set_markup(f'<span foreground="{status_color}"><small>{status_label_display}</small></span>')
                status_lbl.set_halign(Gtk.Align.START)

                status_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                status_col.set_spacing(0)
                status_col.pack_start(status_indicator, False, False, 0)
                status_col.pack_start(status_lbl, False, False, 0)

                hbox.pack_start(status_col, False, False, 0)

                # Project name and path
                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                info_box.set_spacing(2)
                info_box.set_hexpand(True)

                name_label = Gtk.Label()
                name_label.set_markup(f'<b>{project["name"]}</b>')
                name_label.set_halign(Gtk.Align.START)
                info_box.pack_start(name_label, False, False, 0)

                path_label = Gtk.Label()
                path_label.set_markup(f'<small>{os.path.basename(project["path"])}</small>')
                path_label.set_halign(Gtk.Align.START)
                path_label.set_sensitive(False)
                path_label.set_ellipsize(Pango.EllipsizeMode.END)
                info_box.pack_start(path_label, False, False, 0)

                hbox.pack_start(info_box, True, True, 0)

                # Action buttons
                action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                action_box.set_spacing(5)
                action_box.set_halign(Gtk.Align.END)

                # Go to Project button
                go_btn = Gtk.Button(label="📂 Open")
                go_btn.set_size_request(100, 35)
                go_btn.get_style_context().add_class("suggested-action")
                go_btn.connect("clicked", lambda btn, p=project["path"]: os.system(f"xdg-open '{p}'"))
                action_box.pack_start(go_btn, False, False, 0)

                # Status dropdown
                status_combo = Gtk.ComboBoxText()
                for s in self.logic.VALID_STATUSES:
                    label = self.logic.STATUS_LABELS.get(s, s).replace("_", " ").title()
                    status_combo.append_text(label)
                status_combo.set_active_id(status_label_display)
                status_combo.set_size_request(140, -1)

                def make_status_handler(name, row_ref):
                    def handler(combo):
                        new_text = combo.get_active_text()
                        if not new_text:
                            return
                        new_status = new_text.lower().replace(" ", "_")
                        ok, msg = self.logic.update_project_status(name, new_status)
                        if ok:
                            self.update_status(f"{name}: {msg}", success=True)
                            new_color = self.logic.STATUS_COLORS.get(new_status, "#95a5a6")
                            new_label = self.logic.STATUS_LABELS.get(new_status, new_status).replace("_", " ").title()
                            row_ref.status_indicator.set_markup(
                                f'<span foreground="{new_color}" size="xx-large">●</span>')
                            row_ref.status_lbl.set_markup(
                                f'<span foreground="{new_color}"><small>{new_label}</small></span>')
                            ctx = row_ref.get_style_context()
                            for old in self.logic.VALID_STATUSES:
                                ctx.remove_class(f"status-{old}")
                            ctx.add_class(f"status-{new_status}")

                    return handler

                status_combo.connect("changed", make_status_handler(project["name"], row))
                action_box.pack_start(status_combo, False, False, 0)

                hbox.pack_start(action_box, False, False, 0)

                row.add(hbox)
                row.get_style_context().add_class(f"status-{status}")
                row.status_indicator = status_indicator
                row.status_lbl = status_lbl

                self.projects_list.add(row)
                row.show_all()

            # self.projects_list = set(self.projects_list)
            self.update_status(f"Loaded {len(projects)} project(s)")

        except Exception as e:
            print(f"[ERROR] Exception in refresh_projects: {e}")
            import traceback
            traceback.print_exc()
            self.update_status(f"Refresh failed: {str(e)}", success=False)

        finally:
            # Always reset the flag, even on error
            self._refreshing = False

        return True  # Keep timer running

    def on_search_changed(self, entry):
        """Debounced search - rebuilds list with filter"""
        # Cancel pending timeout
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)

        # Schedule rebuild after 300ms
        self._search_timeout = GLib.timeout_add(300, self.refresh_projects)

    def on_project_activated(self, listbox, row):
        """Double-click opens project folder"""
        if hasattr(row, 'project_path'):
            os.system(f"xdg-open '{row.project_path}'")

    def on_settings(self, button):
        """Open settings dialog with folder drag-and-drop support"""
        dialog = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)  # Fixed: was TOPPLevel
        dialog.set_title("Settings")
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_default_size(500, 200)
        dialog.set_border_width(15)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(15)
        dialog.add(vbox)

        # Default folder section
        folder_frame = Gtk.Frame(label="Default Projects Folder")
        folder_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        folder_box.set_spacing(10)
        folder_box.set_border_width(10)
        folder_frame.add(folder_box)

        # Folder entry (editable)
        folder_input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        folder_input_box.set_spacing(10)

        self.settings_folder_entry = Gtk.Entry()
        self.settings_folder_entry.set_text(str(self.logic.default_folder))
        self.settings_folder_entry.set_hexpand(True)
        self.settings_folder_entry.connect("changed", self.on_settings_folder_changed)

        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.connect("clicked", self.on_settings_browse, self.settings_folder_entry)

        folder_input_box.pack_start(self.settings_folder_entry, True, True, 0)
        folder_input_box.pack_start(browse_btn, False, False, 0)
        folder_box.pack_start(folder_input_box, False, False, 0)

        # Drag and drop zone for folder
        drop_eventbox = Gtk.EventBox()
        drop_label = Gtk.Label()
        drop_label.set_markup("<small>Drag & drop a folder here or type path above</small>")
        drop_label.set_halign(Gtk.Align.CENTER)
        drop_label.set_sensitive(False)
        drop_eventbox.add(drop_label)
        drop_eventbox.set_visible_window(False)

        # Enable drag-and-drop
        targets = [Gtk.TargetEntry.new("text/uri-list", 0, 0)]
        drop_eventbox.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.COPY)
        drop_eventbox.connect("drag-data-received", self.on_settings_folder_drop, self.settings_folder_entry)
        drop_eventbox.connect("drag-motion", self.on_drag_motion)

        folder_box.pack_start(drop_eventbox, False, False, 0)
        folder_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Default status section
        status_frame = Gtk.Frame(label="Default Project Status")
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        status_box.set_spacing(10)
        status_box.set_border_width(10)
        status_frame.add(status_box)

        default_status_combo = Gtk.ComboBoxText()
        for status in self.logic.VALID_STATUSES:
            label = self.logic.STATUS_LABELS.get(status, status).replace("_", " ").title()
            default_status_combo.append_text(label)

        current_default = self.logic.settings.get("default_status", "developing")
        default_status_combo.set_active_id(current_default.replace("_", " ").title())
        status_box.pack_start(default_status_combo, False, False, 0)

        vbox.pack_start(folder_frame, False, False, 0)
        vbox.pack_start(status_frame, False, False, 0)

        # Button box
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_spacing(10)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda x: dialog.destroy())
        btn_box.pack_start(cancel_btn, False, False, 0)

        save_btn = Gtk.Button(label="Save")
        save_btn.get_style_context().add_class("suggested-action")
        save_btn.connect("clicked", self.on_settings_save, default_status_combo)
        btn_box.pack_start(save_btn, False, False, 0)

        vbox.pack_start(btn_box, False, False, 0)

        dialog.show_all()

    def on_settings_folder_changed(self, entry):
        """Validate folder path in real-time"""
        folder = entry.get_text()
        if folder and os.path.isdir(folder):
            entry.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA.parse("#2ecc71"))
        else:
            entry.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA.parse("#666"))

    def on_settings_browse(self, button, entry):
        """Browse folder from settings dialog"""
        chooser = Gtk.FileChooserDialog(
            title="Select Default Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        chooser.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        current_text = entry.get_text()
        if current_text and os.path.isdir(current_text):
            chooser.set_current_folder(current_text)

        if chooser.run() == Gtk.ResponseType.OK:
            entry.set_text(chooser.get_filename())

        chooser.destroy()

    def on_settings_folder_drop(self, widget, context, x, y, selection_data, info, time, entry):
        """Handle folder drop on settings dialog"""
        data = selection_data.get_data()
        if not data:
            return

        try:
            text = data.decode('utf-8')
        except:
            return

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('file://'):
                path = line[7:].replace('%20', ' ')
                if os.path.isdir(path):
                    entry.set_text(path)
                    entry.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA.parse("#2ecc71"))
                    break

    def on_settings_save(self, button, status_combo):
        """Save settings from dialog"""
        # Save folder
        new_folder = self.settings_folder_entry.get_text()
        is_valid, msg = self.logic.set_default_folder(new_folder)
        if not is_valid:
            self.show_dialog(Gtk.MessageType.ERROR, "Invalid Folder", msg)
            return

        # Save status
        new_default_status = status_combo.get_active_text()
        if new_default_status:
            new_default_status_code = new_default_status.lower().replace(" ", "_")
            self.logic.set_setting("default_status", new_default_status_code)

        # Update the target folder in the create section
        self.target_folder.set_text(new_folder)
        self.target_folder.set_placeholder_text(new_folder)

        self.update_status("Settings saved", success=True)
        self.refresh_projects()
        button.get_toplevel().destroy()

    def on_export_list(self, button):
        chooser = Gtk.FileChooserDialog(
            title="Save Project List",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        chooser.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        chooser.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        chooser.set_current_name("projects_list.json")

        if chooser.run() == Gtk.ResponseType.OK:
            output_path = chooser.get_filename()
            if not output_path.endswith('.json'):
                output_path += '.json'

            success, projects = self.logic.list_projects()
            if success:
                import json as json_module
                with open(output_path, 'w', encoding='utf-8') as f:
                    json_module.dump(projects, f, indent=2)
                self.update_status(f"Exported {len(projects)} project(s)", success=True)
            else:
                self.show_dialog(Gtk.MessageType.ERROR, "Export Error", "Error exporting project list")

        chooser.destroy()

    def update_status(self, msg, success=None):
        if success is None:
            color = "#666"
        elif success:
            color = "#2ecc71"
        else:
            color = "#e74c3c"
        self.status_label.set_markup(f'<span foreground="{color}">{msg}</span>')

    def show_error(self, msg):
        self.show_dialog(Gtk.MessageType.ERROR, "Error", msg)

    def show_dialog(self, msg_type, title, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=msg_type,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()


def launch():
    app = ProjectsManagerApp()
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()
