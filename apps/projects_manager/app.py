#!/usr/bin/env python3
"""GUI for Projects Manager with Status Tracking"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, GObject
import os
import sys
from pathlib import Path

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

        # Store current search query
        self.current_search_query = ""

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

        # Header for create section
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

        # Search/filter
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_spacing(5)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search projects...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("changed", self.on_search_changed)

        search_box.pack_start(self.search_entry, True, True, 0)
        projects_section.pack_start(search_box, False, False, 0)

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

        # Start auto-refresh every 5 seconds
        self.auto_refresh_timer = GLib.timeout_add_seconds(5, self.refresh_projects)

        print("[INFO] Projects Manager app initialized with auto-refresh")

    def on_destroy(self, widget):
        """Cleanup on window close"""
        if hasattr(self, 'auto_refresh_timer'):
            GLib.source_remove(self.auto_refresh_timer)
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
        """Accept drag motion on folder line"""
        return True

    def on_folder_drop(self, widget, context, x, y, selection_data, info, time):
        """Handle folder drop on folder line"""
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
            # Refresh immediately after creation
            GLib.idle_add(self.refresh_projects)
        else:
            self.update_status(f"✗ {result}", success=False)
            self.show_dialog(Gtk.MessageType.ERROR, "Failed", f"Failed to create project:\n{result}")

        self.refresh_projects()

    def refresh_projects(self):
        """Refresh the projects list - call this directly, returns False to stop timer"""
        # Save current search query before refresh
        saved_search = self.search_entry.get_text()

        # Clear existing rows
        # self.projects_list.foreach(lambda w: self.projects_list.remove(w))

        success, projects = self.logic.list_projects()
        if not success or projects is None:
            self.update_status("Error loading projects", success=False)
            # Restore search if exists
            if saved_search:
                self.search_entry.set_text(saved_search)
            return True  # Continue timer

        if not projects:
            no_projects = Gtk.Label()
            no_projects.set_markup("<i>No projects found</i>")
            no_projects.set_sensitive(False)
            no_projects.set_margin_top(50)
            no_projects.set_halign(Gtk.Align.CENTER)
            self.projects_list.add(no_projects)
            self.update_status("No projects found")
            return True  # Continue timer

        for project in projects:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            row.set_activatable(True)

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            hbox.set_spacing(15)
            hbox.set_margin_start(10)
            hbox.set_margin_end(10)
            hbox.set_margin_top(8)
            hbox.set_margin_bottom(8)
            hbox.set_hexpand(True)

            # Store project name on row for access later
            row.project_name = project["name"]

            # Status indicator
            status = project.get("status", "developing")
            status_color = self.logic.STATUS_COLORS.get(status, "#95a5a6")
            status_label_display = self.logic.STATUS_LABELS.get(status, status).replace("_", " ").title()

            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            status_box.set_spacing(2)
            status_box.set_size_request(80, -1)

            status_indicator = Gtk.Label(label="●")
            status_indicator.set_markup(f'<span foreground="{status_color}" size="x-large">●</span>')
            status_box.pack_start(status_indicator, False, False, 0)

            status_lbl = Gtk.Label(label=status_label_display)
            status_lbl.set_markup(f'<span foreground="{status_color}"><small>{status_label_display}</small></span>')
            status_lbl.set_justify(Gtk.Justification.LEFT)
            status_lbl.set_halign(Gtk.Align.START)
            status_box.pack_start(status_lbl, False, False, 0)

            hbox.pack_start(status_box, False, False, 0)

            # Project info
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            info_box.set_spacing(2)
            info_box.set_hexpand(True)
            info_box.set_valign(Gtk.Align.CENTER)

            name_label = Gtk.Label(label=project["name"])
            name_label.set_halign(Gtk.Align.START)
            name_label.set_xalign(0)
            name_label.set_markup(f'<b>{project["name"]}</b>')
            info_box.pack_start(name_label, False, False, 0)

            path_label = Gtk.Label(label=project["path"])
            path_label.set_halign(Gtk.Align.START)
            path_label.set_xalign(0)
            path_label.set_sensitive(False)
            path_label.set_ellipsize(Pango.EllipsizeMode.END)
            path_label.set_markup(f'<small>{os.path.basename(project["path"])}</small>')
            info_box.pack_start(path_label, False, False, 0)

            hbox.pack_start(info_box, True, True, 0)

            # Action buttons
            action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            action_box.set_spacing(5)
            action_box.set_halign(Gtk.Align.END)

            # Go to Project button
            go_btn = Gtk.Button(label="📂 Go to Project")
            go_btn.set_size_request(130, 35)
            go_btn.get_style_context().add_class("suggested-action")

            def on_go_clicked(btn, proj_path=project["path"]):
                try:
                    os.system(f"xdg-open '{proj_path}'")
                except Exception as e:
                    self.show_dialog(Gtk.MessageType.ERROR, "Error", f"Cannot open folder: {e}")

            go_btn.connect("clicked", on_go_clicked)
            action_box.pack_start(go_btn, False, False, 0)

            # Store references for status update
            row.status_indicator = status_indicator
            row.status_lbl = status_lbl
            row.status_box = status_box

            # Status change dropdown
            status_combo = Gtk.ComboBoxText()
            for s in self.logic.VALID_STATUSES:
                label = self.logic.STATUS_LABELS.get(s, s).replace("_", " ").title()
                status_combo.append_text(label)
            status_combo.set_active_id(status_label_display)
            status_combo.set_size_request(150, -1)

            proj_name_capture = project["name"]

            def on_status_changed(combo, proj_name=proj_name_capture, sr=row.status_indicator, sl=row.status_lbl,
                                  rc=row):
                new_status_text = combo.get_active_text()
                if not new_status_text:
                    return

                new_status = new_status_text.lower().replace(" ", "_")
                success, msg = self.logic.update_project_status(proj_name, new_status)

                if success:
                    self.update_status(f"Updated {proj_name} to {msg}", success=True)

                    new_status_color = self.logic.STATUS_COLORS.get(new_status, "#95a5a6")
                    new_status_label = self.logic.STATUS_LABELS.get(new_status, new_status).replace("_", " ").title()

                    sr.set_markup(f'<span foreground="{new_status_color}" size="x-large">●</span>')
                    sl.set_markup(f'<span foreground="{new_status_color}"><small>{new_status_label}</small></span>')

                    old_context = rc.get_style_context()
                    for old_status in self.logic.VALID_STATUSES:
                        old_context.remove_class(f"status-{old_status}")
                    old_context.add_class(f"status-{new_status}")

                    # Don't clear search here - it breaks visibility
                else:
                    self.show_dialog(Gtk.MessageType.ERROR, "Error", msg)

            status_combo.connect("changed", on_status_changed)
            action_box.pack_start(status_combo, False, False, 0)

            # Delete button
            delete_btn = Gtk.Button(label="Delete")
            delete_btn.get_style_context().add_class("destructive-action")
            delete_btn.set_size_request(130, 35)

            def on_delete_clicked(btn, proj_name=project["name"]):
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text=f"Delete project '{proj_name}'?"
                )
                dialog.format_secondary_text("This will permanently delete all project files.")

                response = dialog.run()
                if response == Gtk.ResponseType.YES:
                    success, msg = self.logic.delete_project(proj_name)
                    if success:
                        self.update_status(msg, success=True)
                        GLib.idle_add(self.refresh_projects)
                    else:
                        self.show_dialog(Gtk.MessageType.ERROR, "Error", msg)

                dialog.destroy()

            delete_btn.connect("clicked", on_delete_clicked)
            action_box.pack_start(delete_btn, False, False, 0)

            hbox.pack_start(action_box, False, False, 0)

            row.add(hbox)
            row.get_style_context().add_class(f"status-{status}")
            self.projects_list.add(row)

        # Restore search filter after all rows are added
        if saved_search:
            self.search_entry.set_text(saved_search)

        self.update_status(f"Loaded {len(projects)} project(s)")

        return True  # Continue auto-refresh timer

    def on_project_activated(self, listbox, row):
        """Handle double-click on project row"""
        if hasattr(row, 'project_name'):
            proj_name = row.project_name
            success, projects = self.logic.list_projects()
            if success:
                for proj in projects:
                    if proj["name"] == proj_name:
                        os.system(f"xdg-open '{proj['path']}'")
                        break

    def on_search_changed(self, entry):
        """Filter projects based on search query"""
        self.current_search_query = entry.get_text().lower()

        for row in self.projects_list:
            try:
                if not isinstance(row, Gtk.ListBoxRow):
                    continue

                children = row.get_children()
                if not children or len(children) < 3:
                    # Placeholder row - always show if no search
                    row.set_visible(not self.current_search_query)
                    continue

                info_box = children[1]
                children_in_info = info_box.get_children()
                if not children_in_info:
                    row.set_visible(not self.current_search_query)
                    continue

                name_label = children_in_info[0]
                name = name_label.get_text().lower()

                row.set_visible(self.current_search_query in name)
            except Exception:
                row.set_visible(False)

    def on_settings(self, button):
        """Open settings dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Settings"
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.set_spacing(15)
        content.set_border_width(15)
        dialog.get_content_area().pack_start(content, True, True, 0)

        folder_label = Gtk.Label(label="Default Projects Folder:")
        folder_label.set_halign(Gtk.Align.START)
        content.pack_start(folder_label, False, False, 5)

        default_entry = Gtk.Entry()
        default_entry.set_text(str(self.logic.default_folder))
        default_entry.set_hexpand(True)
        content.pack_start(default_entry, False, False, 0)

        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.connect("clicked", self.on_settings_browse, default_entry)
        content.pack_start(browse_btn, False, False, 0)

        status_label = Gtk.Label(label="Default Project Status:")
        status_label.set_halign(Gtk.Align.START)
        content.pack_start(status_label, False, False, 10)

        default_status_combo = Gtk.ComboBoxText()
        for status in self.logic.VALID_STATUSES:
            label = self.logic.STATUS_LABELS.get(status, status).replace("_", " ").title()
            default_status_combo.append_text(label)

        current_default = self.logic.settings.get("default_status", "developing")
        default_status_combo.set_active_id(current_default.replace("_", " ").title())
        content.pack_start(default_status_combo, False, False, 0)

        dialog.resize(400, 200)

        if dialog.run() == Gtk.ResponseType.OK:
            new_folder = default_entry.get_text()
            is_valid, msg = self.logic.set_default_folder(new_folder)
            if not is_valid:
                self.show_dialog(Gtk.MessageType.ERROR, "Invalid Folder", msg)

            new_default_status = default_status_combo.get_active_text()
            if new_default_status:
                new_default_status_code = new_default_status.lower().replace(" ", "_")
                self.logic.set_setting("default_status", new_default_status_code)
                self.update_status("Settings saved", success=True)
                GLib.idle_add(self.refresh_projects)

        dialog.destroy()

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

    def on_export_list(self, button):
        """Export project list to JSON"""
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
        """Update status bar"""
        if success is None:
            color = "#666"
        elif success:
            color = "#2ecc71"
        else:
            color = "#e74c3c"
        self.status_label.set_markup(f'<span foreground="{color}">{msg}</span>')

    def show_error(self, msg):
        """Show error dialog"""
        self.show_dialog(Gtk.MessageType.ERROR, "Error", msg)

    def show_dialog(self, msg_type, title, msg):
        """Generic dialog display"""
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
    """Launch the application"""
    app = ProjectsManagerApp()
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()
