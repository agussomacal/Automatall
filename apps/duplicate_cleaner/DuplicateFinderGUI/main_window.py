"""Main window for Duplicate Finder."""

import os
import threading
from gi.repository import Gtk, GLib, Gdk, Gio, Adw, Pango  # ← Added Pango

APP_NAME = "Duplicate Finder"

from .backend import scan_folder, load_duplicates, delete_selected_files, get_scan_stats
from .dialogs import ScanOptionsDialog

APP_NAME = "Duplicate Finder"


class FileTile(Gtk.Box):
    """A single file tile that can be dragged between panels."""

    def __init__(self, file_info, panel_type, on_remove_callback=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.file_info = file_info
        self.panel_type = panel_type  # "keep" or "delete"
        self.on_remove_callback = on_remove_callback

        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.set_halign(Gtk.Align.FILL)  # Tile fills available width

        # Style based on panel
        if panel_type == "keep":
            self.get_style_context().add_class("keep-tile")
        else:
            self.get_style_context().add_class("delete-tile")

        # Icon and basic info row
        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        info_row.set_halign(Gtk.Align.FILL)

        # Icon
        icon = Gtk.Image(icon_name="text-x-generic")
        icon.set_valign(Gtk.Align.CENTER)
        info_row.append(icon)

        # Filename - LEFT ALIGNED
        label = Gtk.Label(label=file_info.name)
        label.set_hexpand(True)
        label.set_ellipsize(Pango.EllipsizeMode.NONE)
        label.set_wrap(True)
        label.set_xalign(0)  # ← 0 = LEFT alignment
        self.append(label)

        # Size on separate line for clarity
        size_label = Gtk.Label(label=self._format_size(file_info.size))
        size_label.set_css_classes(["dim-label", "caption"])
        size_label.set_halign(Gtk.Align.END)
        size_label.set_xalign(1)  # ← 1 = RIGHT alignment (for size)
        info_row.append(size_label)

        # Right arrow icon for delete tiles
        if panel_type == "delete":
            arrow = Gtk.Label(label="→")
            arrow.set_css_classes(["dim-label"])
            arrow.set_margin_start(6)
            arrow.set_valign(Gtk.Align.CENTER)
            info_row.append(arrow)

        self.append(info_row)

        # Drag setup
        self.setup_drag()

    def _format_size(self, size_bytes):
        """Human-readable size formatting."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def setup_drag(self):
        """Setup drag source - only from DELETE panel to KEEP panel."""
        # Only enable dragging from delete tiles
        if self.panel_type != "delete":
            return

        # Make draggable
        source = Gtk.DragSource()
        source.set_actions(Gdk.DragAction.MOVE)
        source.connect("prepare", self._on_drag_prepare)
        source.connect("drag-begin", self._on_drag_begin)
        source.connect("drag-end", self._on_drag_end)
        self.add_controller(source)

        # Enable drop target on all tiles
        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

    def _on_drag_prepare(self, source, x, y):
        """Prepare drag data - file path and source panel."""
        content = Gdk.ContentProvider.new_for_value(self.file_info.path)
        return content

    def _on_drag_begin(self, source, drag, *args):
        """Visual feedback when drag starts."""
        self.set_opacity(0.5)

    def _on_drag_end(self, source, drag, *args):
        """Reset when drag ends."""
        self.set_opacity(1.0)

    def _on_drop(self, target, value, x, y):
        """Handle file being dropped on this tile."""
        # Only accept drops on KEEP panel tiles
        if self.panel_type != "keep":
            return False

        # Get dragged file path
        dragged_path = str(value)

        # Check if we have a callback to handle the swap
        if self.on_remove_callback:
            # Notify the MainWindow about the swap
            self.on_remove_callback(dragged_path, self.file_info)
            return True

        return False


class MainWindow(Gtk.ApplicationWindow):
    """Main application window."""

    def __init__(self, **kwargs):
        super().__init__(title=APP_NAME, default_width=1400, default_height=800, **kwargs)
        self.folder_path = None
        self.keep_files = []  # Files user wants to keep
        self.delete_files = []  # Files user wants to delete
        self.current_groups = []  # All duplicate groups from scan

        self._build_ui()
        self.reset_state()

    def _build_ui(self):
        """Build main UI layout."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header
        header = Gtk.HeaderBar()

        menu = Gio.Menu()
        menu.append("Scan Options...", "win.scan_options")
        menu.append("About", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        # Title
        title_label = Gtk.Label(label=APP_NAME, css_classes=["title"])
        header.set_title_widget(title_label)

        main_box.append(header)

        # Top: Folder selection
        folder_panel = self._build_folder_panel()
        main_box.append(folder_panel)

        # Middle: Two-panel view
        middle_paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            wide_handle=True
        )
        middle_paned.set_position(700)

        # Left panel: Keep files
        keep_column = self._build_keep_panel()
        middle_paned.set_start_child(keep_column)

        # Right panel: Delete files
        delete_column = self._build_delete_panel()
        middle_paned.set_end_child(delete_column)

        main_box.append(middle_paned)

        # Bottom: Action buttons
        action_panel = self._build_action_panel()
        main_box.append(action_panel)

        self.set_child(main_box)

        # Connect menu actions
        scan_action = Gio.SimpleAction.new("scan_options", None)
        scan_action.connect("activate", self.on_scan_options)
        self.add_action(scan_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *args: self.quit())
        self.add_action(quit_action)

    def _build_folder_panel(self):
        """Top panel for folder selection."""
        frame = Gtk.Frame(margin_start=12, margin_end=12, margin_top=12)
        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12
        )

        # Path entry with drop support - FIXED: No separate drop zone
        entry_row = Gtk.Box(spacing=8)
        folder_label = Gtk.Label(label="Folder:", halign=Gtk.Align.START)
        self.folder_entry = Gtk.Entry()
        self.folder_entry.set_hexpand(True)
        self.folder_entry.set_placeholder_text("Type path, browse, or drag & drop a folder here")
        browse_btn = Gtk.Button(label="Browse", css_classes=["suggested-action"])
        browse_btn.connect("clicked", self.on_browse_folder)

        entry_row.append(folder_label)
        entry_row.append(self.folder_entry)
        entry_row.append(browse_btn)

        # Add drop target directly to entry - FIXED: Drag to entry field
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_folder_drop)
        self.folder_entry.add_controller(drop_target)

        vbox.append(entry_row)

        # REMOVED: Large drop zone widget

        frame.set_child(vbox)
        return frame

    def _build_keep_panel(self):
        """Left panel for files to keep."""
        frame = Gtk.Frame(margin_start=12, margin_end=6, margin_top=12, margin_bottom=12)
        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12, margin_end=12, margin_top=12, margin_bottom=12
        )

        # Header row
        header_row = Gtk.Box(spacing=12)
        header_row.append(Gtk.Label(label="Files to KEEP", css_classes=["title-3"]))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_row.append(spacer)
        self.keep_count_label = Gtk.Label(label="0 files", css_classes=["dim-label"])
        header_row.append(self.keep_count_label)
        vbox.append(header_row)

        # Scrollable list - add drop target
        scroller = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            min_content_height=300
        )

        self.keep_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.keep_list.get_style_context().add_class("keep-list")

        # Allow dropping files onto the list
        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_keep_list_drop)
        self.keep_list.add_controller(drop_target)

        scroller.set_child(self.keep_list)
        vbox.append(scroller)

        frame.set_child(vbox)
        return frame

    def _build_delete_panel(self):
        """Right panel for files to delete."""
        frame = Gtk.Frame(margin_start=6, margin_end=12, margin_top=12, margin_bottom=12)
        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12, margin_end=12, margin_top=12, margin_bottom=12
        )

        # Header row
        header_row = Gtk.Box(spacing=12)
        header_row.append(Gtk.Label(label="Files to DELETE", css_classes=["title-3"]))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_row.append(spacer)
        self.delete_count_label = Gtk.Label(label="0 files", css_classes=["dim-label"])
        header_row.append(self.delete_count_label)
        vbox.append(header_row)

        # Scrollable list
        scroller = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            min_content_height=300
        )

        self.delete_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.delete_list.get_style_context().add_class("delete-list")
        scroller.set_child(self.delete_list)
        vbox.append(scroller)

        frame.set_child(vbox)
        return frame

    def _populate_lists(self):
        """Populate keep/delete lists from duplicate groups."""
        self._clear_lists()
        self.keep_files.clear()
        self.delete_files.clear()

        for group in self.current_groups:
            files = group["files"]

            # Auto-suggest keeping the first file (shortest name)
            sorted_files = sorted(files, key=lambda f: len(f.name))

            for i, file_info in enumerate(sorted_files):
                # Create tile with callback for swap
                tile = FileTile(
                    file_info,
                    "keep" if i == 0 else "delete",
                    on_remove_callback=self._handle_file_swap
                )

                if i == 0:
                    self.keep_list.append(tile)
                    self.keep_files.append(file_info)
                else:
                    self.delete_list.append(tile)
                    self.delete_files.append(file_info)

        self.keep_count_label.set_text(f"{len(self.keep_files)} files")
        self.delete_count_label.set_text(f"{len(self.delete_files)} files")

    def _handle_file_swap(self, dragged_path, target_file_info):
        """
        Handle swap when file is dragged from DELETE to KEEP.
        The dragged file goes to KEEP, the original KEEP file goes to DELETE.
        """
        print(f"[DEBUG] Swapping: {dragged_path} <-> {target_file_info.path}")

        # Find the dragged file in delete list
        dragged_file = None
        for df in self.delete_files:
            if df.path == dragged_path:
                dragged_file = df
                break

        # Find the target file in keep list
        target_file = target_file_info

        if dragged_file and target_file:
            # Swap them
            # Remove dragged from delete_files
            self.delete_files.remove(dragged_file)
            # Add dragged to keep_files
            self.keep_files.append(dragged_file)

            # Remove target from keep_files
            self.keep_files.remove(target_file)
            # Add target to delete_files
            self.delete_files.append(target_file)

            # Rebuild the lists UI
            self._rebuild_lists()

    def _rebuild_lists(self):
        """Rebuild both lists after swap."""
        self._clear_lists()

        for i, file_info in enumerate(self.keep_files):
            tile = FileTile(file_info, "keep", on_remove_callback=self._handle_file_swap)
            self.keep_list.append(tile)

        for i, file_info in enumerate(self.delete_files):
            tile = FileTile(file_info, "delete", on_remove_callback=self._handle_file_swap)
            self.delete_list.append(tile)

        self.keep_count_label.set_text(f"{len(self.keep_files)} files")
        self.delete_count_label.set_text(f"{len(self.delete_files)} files")

    def _on_keep_list_drop(self, target, value, x, y):
        """Handle drop directly on the keep list."""
        dragged_path = str(value)

        # Find the dragged file in delete list
        dragged_file = None
        for df in self.delete_files:
            if df.path == dragged_path:
                dragged_file = df
                break

        if dragged_file:
            # Swap logic same as tile drop
            # Find any keep file to swap with (first one for simplicity)
            if self.keep_files:
                target_file = self.keep_files[0]

                # Perform swap
                self.delete_files.remove(dragged_file)
                self.keep_files.append(dragged_file)
                self.keep_files.remove(target_file)
                self.delete_files.append(target_file)

                # Rebuild lists
                self._rebuild_lists()
                print(f"[DEBUG] Swapped via list drop: {dragged_file.name} <-> {target_file.name}")

        return True

    def _build_action_panel(self):
        """Bottom panel with action buttons."""
        frame = Gtk.Frame(margin_start=12, margin_end=12, margin_bottom=12)
        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12
        )

        # Status/progress
        self.status_label = Gtk.Label(css_classes=["dim-label"])
        self.spinner = Gtk.Spinner(spinning=False)
        status_row = Gtk.Box(spacing=8)
        status_row.append(self.spinner)
        status_row.append(self.status_label)
        vbox.append(status_row)

        # Buttons
        btn_box = Gtk.Box(spacing=8, halign=Gtk.Align.END)

        self.scan_btn = Gtk.Button(label="🔍 Scan for Duplicates", css_classes=["suggested-action"])
        self.scan_btn.connect("clicked", self.on_scan)
        self.scan_btn.set_sensitive(False)  # Disabled until folder selected
        btn_box.append(self.scan_btn)

        self.clean_btn = Gtk.Button(label="🗑️ Clean Up Selected", css_classes=["destructive-action"])
        self.clean_btn.connect("clicked", self.on_clean)
        self.clean_btn.set_sensitive(False)  # Disabled until scan completes
        btn_box.append(self.clean_btn)

        vbox.append(btn_box)

        frame.set_child(vbox)
        return frame

    def reset_state(self):
        """Reset UI state."""
        self.keep_files.clear()
        self.delete_files.clear()
        self.current_groups.clear()
        self._clear_lists()
        self.keep_count_label.set_text("0 files")
        self.delete_count_label.set_text("0 files")
        self.status_label.set_text("")
        self.scan_btn.set_sensitive(False)
        self.clean_btn.set_sensitive(False)
        # Also clear any lingering dialog references
        if hasattr(self, 'deletion_dialog'):
            delattr(self, 'deletion_dialog')

    def _clear_lists(self):
        """Clear both file lists."""
        self._clear_listbox(self.keep_list)
        self._clear_listbox(self.delete_list)

    @staticmethod
    def _clear_listbox(listbox):
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

    def on_browse_folder(self, button):
        """Open folder browser dialog using GTK4 FileDialog."""
        # Create a file dialog
        dlg = Gtk.FileDialog()
        dlg.set_title("Select Folder to Scan")
        dlg.set_modal(True)

        # Set preferred folder
        current_text = self.folder_entry.get_text()
        if current_text and os.path.isdir(current_text):
            try:
                file = Gio.File.new_for_path(current_text)
                dlg.set_initial_folder(file)
            except:
                pass

        # Use select_folder for async folder selection
        dlg.select_folder(
            parent=self,
            cancellable=None,
            callback=self._on_folder_chosen
        )

    def _on_folder_chosen(self, source, res, user_data=None):
        """Handle folder selection result (GTK4 async callback)."""
        try:
            file = source.select_folder_finish(res)
            if file:
                folder = file.get_path()
                self.folder_entry.set_text(folder)
                self.folder_path = folder
                self.scan_btn.set_sensitive(True)
                print(f"[DEBUG] Folder selected: {folder}")
        except GLib.Error as e:
            # User cancelled or error occurred
            print(f"[DEBUG] File dialog cancelled or error: {e.message}")

    def _on_folder_drop(self, target, value, x, y):
        """Handle folder drop on drop zone."""
        if isinstance(value, Gio.File):
            folder = value.get_path()
            self.folder_entry.set_text(folder)
            self.folder_path = folder
            self.scan_btn.set_sensitive(True)  # Enable scan button
            print(f"[DEBUG] Folder dropped: {folder}")
            return True
        return False

    def on_scan(self, button):
        """Start scanning for duplicates."""
        if not self.folder_path:
            self._show_error("Please select a folder first")
            return

        self.spinner.start()
        self.status_label.set_text("Scanning...")
        self.scan_btn.set_sensitive(False)

        def worker():
            success, msg, stats = scan_folder(self.folder_path)
            GLib.idle_add(self._scan_finished, success, msg, stats)

        threading.Thread(target=worker, daemon=True).start()

    def on_scan_options(self, action, param):
        """Show scan options dialog."""
        dlg = ScanOptionsDialog(self)
        # TODO: Implement scan with options
        dlg.present()

    def _scan_finished(self, success, msg, stats):
        """Handle scan completion."""
        self.spinner.stop()
        self.scan_btn.set_sensitive(True)

        if success:
            self.status_label.set_text(msg)
            self.current_groups = load_duplicates()
            self._populate_lists()
            self.clean_btn.set_sensitive(True)
        else:
            self._show_error(msg)

    def _populate_lists(self):
        """Populate keep/delete lists from duplicate groups."""
        self._clear_lists()

        for group in self.current_groups:
            files = group["files"]

            # Auto-suggest keeping the first file (shortest name)
            sorted_files = sorted(files, key=lambda f: len(f.name))

            for i, file_info in enumerate(sorted_files):
                tile = FileTile(file_info, "keep" if i == 0 else "delete")

                if i == 0:
                    self.keep_list.append(tile)
                    self.keep_files.append(file_info)
                else:
                    self.delete_list.append(tile)
                    self.delete_files.append(file_info)

        self.keep_count_label.set_text(f"{len(self.keep_files)} files")
        self.delete_count_label.set_text(f"{len(self.delete_files)} files")

    def on_clean(self, button):
        """Delete selected files."""
        if not self.delete_files:
            self._show_info("No files selected for deletion")
            return

        # Confirm deletion - FIXED: Store reference properly
        self.deletion_dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Confirm Deletion",
            body=f"Are you sure you want to permanently delete {len(self.delete_files)} files?\n\nThis cannot be undone!"
        )
        self.deletion_dialog.add_response("cancel", "Cancel")
        self.deletion_dialog.add_response("delete", "Delete")
        self.deletion_dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        self.deletion_dialog.connect("response", self._on_confirm_delete)
        self.deletion_dialog.present()

    def _on_confirm_delete(self, dialog, response):
        """Handle deletion confirmation."""
        dialog.destroy()  # FIXED: Use 'dialog' parameter, not 'dlg'

        if response != "delete":
            return

        self.spinner.start()
        self.status_label.set_text("Deleting files...")
        self.clean_btn.set_sensitive(False)

        def worker():
            file_paths = [f.path for f in self.delete_files]
            success, failed = delete_selected_files(file_paths)
            GLib.idle_add(self._cleanup_finished, success, failed)

        threading.Thread(target=worker, daemon=True).start()

    def _cleanup_finished(self, success, failed):
        """Handle deletion completion."""
        self.spinner.stop()
        self.clean_btn.set_sensitive(True)

        if success:
            deleted_count = len(self.delete_files)
            self.status_label.set_text(f"✓ Successfully deleted {deleted_count} files")
            self.reset_state()
        else:
            self._show_error(f"Failed to delete {len(failed)} files\nSee log for details")

    def on_about(self, action, param):
        """Show about dialog."""
        dialog = Gtk.AboutDialog(
            transient_for=self,
            program_name=APP_NAME,
            version="0.1.0",
            comments="Find and clean duplicate files using SHA256 hash comparison",
            authors=["Agus Somacal"],
            license_type=Gtk.License.MIT_X11,
            logo_icon_name="view-filter-symbolic"
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def _show_error(self, msg):
        """Show error dialog."""
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading="Error",
            body=msg
        )
        dlg.add_response("ok", "OK")
        dlg.present()

    def _show_info(self, msg):
        """Show info dialog."""
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading="Info",
            body=msg
        )
        dlg.add_response("ok", "OK")
        dlg.present()
