#!/usr/bin/env python3
"""GUI for PDF Concatenator"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, GObject
import os
import sys
from pathlib import Path

# Import local logic
try:
    from .logic import PDFConcatenatorLogic
except ImportError:
    from logic import PDFConcatenatorLogic


class PDFTile(Gtk.Box):
    """A single row representing a PDF file"""

    __gsignals__ = {
        'tile-remove': (GObject.SignalFlags.RUN_FIRST, None, (object,))
    }

    def __init__(self, file_path, index, on_move_callback=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.file_path = file_path
        self.index = index
        self.selected = False
        self.on_move_callback = on_move_callback
        self.set_spacing(8)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_can_focus(True)

        # Background styling for tile - IMPORTANT: visible borders
        self.get_style_context().add_class("pdf-tile")

        # Selection indicator
        self.selection_indicator = Gtk.Label(label="○")
        self.selection_indicator.set_size_request(25, -1)
        self.selection_indicator.set_xalign(0.5)
        self.selection_indicator.set_yalign(0.5)
        self.pack_start(self.selection_indicator, False, False, 0)

        # Icon
        try:
            img = Gtk.Image.new_from_icon_name("application-pdf", Gtk.IconSize.SMALL_TOOLBAR)
        except:
            img = Gtk.Label(label="📄")
        self.pack_start(img, False, False, 5)

        # Filename (truncated with ellipsis)
        name_label = Gtk.Label(label=os.path.basename(file_path))
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_xalign(0)
        self.pack_start(name_label, True, True, 0)

        # Move buttons
        move_up_btn = Gtk.Button(label="↑")
        move_up_btn.set_size_request(25, 28)
        move_up_btn.connect("clicked", self._on_move_up)
        self.pack_start(move_up_btn, False, False, 2)

        move_down_btn = Gtk.Button(label="↓")
        move_down_btn.set_size_request(25, 28)
        move_down_btn.connect("clicked", self._on_move_down)
        self.pack_start(move_down_btn, False, False, 2)

        # Remove button
        remove_btn = Gtk.Button(label="×")
        remove_btn.get_style_context().add_class("destructive-action")
        remove_btn.set_size_request(28, 28)
        remove_btn.connect("clicked", self.on_remove)
        self.pack_start(remove_btn, False, False, 5)

        # Connect keyboard events
        self.connect("key-press-event", self.on_key_press)

        # Enable selection click
        self.connect("button-press-event", self.on_button_press)

        # Debug: confirm tile creation
        print(f"[DEBUG] Tile created for: {os.path.basename(file_path)}")

    def _on_move_up(self, button):
        if self.on_move_callback:
            self.on_move_callback(self.file_path, "up")

    def _on_move_down(self, button):
        if self.on_move_callback:
            self.on_move_callback(self.file_path, "down")

    def on_key_press(self, widget, event):
        """Handle keyboard shortcuts when tile is selected"""
        if not self.selected:
            return False

        # Up arrow
        if event.keyval == Gdk.KEY_Up:
            if self.on_move_callback:
                self.on_move_callback(self.file_path, "up")
            return True

        # Down arrow
        elif event.keyval == Gdk.KEY_Down:
            if self.on_move_callback:
                self.on_move_callback(self.file_path, "down")
            return True

        return False

    def on_button_press(self, widget, event):
        """Handle click to select"""
        if event.button == 1:  # Left click
            if self.on_move_callback:
                self.on_move_callback(self.file_path, "select")
            return True
        return False

    def on_remove(self, button):
        # Emit custom signal
        print(f"[DEBUG] Removing tile: {os.path.basename(self.file_path)}")
        self.emit('tile-remove', self)

    def on_drag_data_get(self, widget, drag_context, selection_data, info, time):
        # Send the file_path as text so receiver can identify it
        selection_data.set_text(str(self.file_path), -1)
        print("[DEBUG] Drag data sent: {}".format(os.path.basename(self.file_path)))

    def on_drag_begin(self, widget, context):
        """Visual feedback when drag starts"""
        self.set_opacity(0.6)
        print("[DEBUG] Drag started for: {}".format(os.path.basename(self.file_path)))

    def on_drag_end(self, widget, context):
        """Reset opacity when drag ends"""
        self.set_opacity(1.0)

    def set_selected(self, selected):
        """Change selection state"""
        self.selected = selected
        if selected:
            self.get_style_context().add_class("selected")
            self.selection_indicator.set_text("●")
        else:
            self.get_style_context().remove_class("selected")
            self.selection_indicator.set_text("○")


class PDFConcatenatorApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="PDF Concatenator")
        self.set_default_size(800, 650)
        self.set_border_width(15)
        self.set_resizable(True)

        self.logic = PDFConcatenatorLogic()
        self.files = []  # List of file paths in order
        self.inferred_folder = None  # Track inferred output folder from first file
        self.selected_tile = None  # Currently selected tile

        # Main Layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(15)

        # Header
        header = Gtk.Label()
        header.set_markup("<b><span size='x-large'>PDF Concatenator</span></b>")
        header.set_margin_bottom(5)
        main_vbox.pack_start(header, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup(
            "<small>Drag & Drop PDF files below to merge them into one document. Click a file to select, then use ↑↓ arrows to reorder.</small>")
        subtitle.set_sensitive(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.set_line_wrap(True)
        main_vbox.pack_start(subtitle, False, False, 0)

        # Split view: Left = Drop Zone, Right = File List
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(350)  # Split at 350px

        # LEFT SIDE: Permanent Drop Zone
        drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        drop_box.set_spacing(15)
        drop_box.set_margin_start(10)
        drop_box.set_margin_end(10)
        drop_box.set_margin_top(10)
        drop_box.set_margin_bottom(10)
        drop_box.set_name("drop_zone")
        drop_box.set_vexpand(True)
        drop_box.set_hexpand(True)

        # Drop zone icon
        drop_icon = Gtk.Image.new_from_icon_name("document-new", Gtk.IconSize.DIALOG)
        drop_icon.set_pixel_size(64)
        drop_icon.set_margin_top(20)
        drop_box.pack_start(drop_icon, False, False, 0)

        # Drop zone label
        drop_label = Gtk.Label(label="<span size='large'>Drop PDF files here</span>")
        drop_label.set_use_markup(True)
        drop_label.set_margin_top(10)
        drop_label.set_margin_bottom(5)
        drop_box.pack_start(drop_label, False, False, 0)

        # Browse hint
        browse_hint = Gtk.Label(label="or click to browse")
        browse_hint.set_sensitive(False)
        browse_hint.set_margin_bottom(20)
        drop_box.pack_start(browse_hint, False, False, 0)

        # Add a visible "Browse Files" button inside drop zone
        browse_btn = Gtk.Button(label="📂 Browse PDF Files")
        browse_btn.get_style_context().add_class("suggested-action")
        browse_btn.set_margin_top(10)
        browse_btn.set_margin_bottom(20)
        browse_btn.connect("clicked", self.on_browse_click)
        drop_box.pack_start(browse_btn, False, False, 0)

        # Enable drag directly on drop_box
        targets = [Gtk.TargetEntry.new("text/uri-list", 0, 0)]
        drop_box.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.COPY)
        drop_box.connect("drag-data-received", self.on_drop)
        drop_box.connect("button-press-event", self.on_browse_click)

        paned.pack1(drop_box, resize=True, shrink=True)

        # RIGHT SIDE: File List with Scroll
        right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_vbox.set_spacing(5)
        right_vbox.set_margin_start(10)
        right_vbox.set_margin_end(10)
        right_vbox.set_margin_top(10)
        right_vbox.set_margin_bottom(10)
        right_vbox.set_vexpand(True)
        right_vbox.set_hexpand(True)

        # Label for file list
        list_label = Gtk.Label()
        list_label.set_markup("<b>Added Files</b> <small>(0)</small>")
        list_label.set_halign(Gtk.Align.START)
        list_label.set_xalign(0)
        self.list_count_label = list_label  # Reference to update count
        right_vbox.pack_start(list_label, False, False, 0)

        # Scrollable file list
        self.scroll_win = Gtk.ScrolledWindow()
        self.scroll_win.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll_win.set_min_content_height(250)
        self.scroll_win.set_max_content_height(500)
        self.scroll_win.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.scroll_win.set_vexpand(True)
        self.scroll_win.set_hexpand(True)
        self.scroll_win.get_style_context().add_class("scroll-container")

        self.file_list = Gtk.ListBox()
        self.file_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.file_list.set_activate_on_single_click(False)
        self.file_list.get_style_context().add_class("tile-list")

        # Add file_list DIRECTLY to scroll window
        self.scroll_win.add(self.file_list)

        right_vbox.pack_start(self.scroll_win, True, True, 0)

        # Add panes to Paned widget
        paned.pack2(right_vbox, resize=False, shrink=False)

        main_vbox.pack_start(paned, True, True, 0)

        # Output Folder Selector
        output_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        output_row.set_spacing(10)

        folder_label = Gtk.Label(label="Output Folder:")
        folder_label.set_xalign(0)
        folder_entry = Gtk.Entry()
        folder_entry.set_placeholder_text("/home/user/documents/")
        folder_entry.set_hexpand(True)
        self.output_folder = folder_entry  # Store reference

        browse_folder_btn = Gtk.Button(label="Browse...")
        browse_folder_btn.connect("clicked", self.on_browse_folder)

        output_row.pack_start(folder_label, False, False, 0)
        output_row.pack_start(folder_entry, True, True, 0)
        output_row.pack_start(browse_folder_btn, False, False, 0)
        main_vbox.pack_start(output_row, False, False, 0)

        # Status Bar
        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_markup('<span foreground="#666">Ready</span>')
        main_vbox.pack_start(self.status_label, False, False, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_spacing(10)
        btn_box.set_halign(Gtk.Align.END)

        clear_btn = Gtk.Button(label="Clear All")
        clear_btn.connect("clicked", self.on_clear)
        btn_box.pack_start(clear_btn, False, False, 0)

        merge_btn = Gtk.Button(label="🔗 Merge PDFs")
        merge_btn.get_style_context().add_class("suggested-action")
        merge_btn.connect("clicked", self.on_merge)
        btn_box.pack_start(merge_btn, False, False, 0)

        main_vbox.pack_start(btn_box, False, False, 0)

        self.add(main_vbox)
        self.connect("destroy", Gtk.main_quit)

        # Apply CSS styling
        self.apply_css()

        print("[INFO] PDF Concatenator app initialized. Click a file to select, use ↑↓ to reorder.")

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            #drop_zone {
                border: 3px dashed #6d4aff;
                border-radius: 12px;
                padding: 20px;
                background-color: rgba(109, 76, 255, 0.1);
            }
            #drop_zone:hover {
                background-color: rgba(109, 76, 255, 0.2);
                border-color: #6d4aff;
            }
            .pdf-tile {
                background-color: #ffffff;
                border: 1px solid #6d4aff;
                border-radius: 6px;
                margin: 3px 0;
                padding: 5px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .pdf-tile:hover {
                background-color: #e8e8ff;
                border-color: #6d4aff;
            }
            .pdf-tile.selected {
                background-color: rgba(109, 76, 255, 0.3);
                border-color: #4a3acc;
                border-width: 2px;
                box-shadow: 0 2px 6px rgba(109, 76, 255, 0.3);
            }
            .tile-list {
                background-color: #fafafa;
            }
            .scroll-container {
                border: 1px solid #ccc;
            }
            .suggested-action {
                background-color: #6d4aff;
                color: white;
            }
            .destructive-action {
                background-color: #e74c3c;
                color: white;
            }
        """)
        screen = Gdk.Screen.get_default()
        style_context = self.get_style_context()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def handle_tile_action(self, file_path, action):
        """Handle tile actions (select, move up, move down)"""
        if action == "select":
            print(f"[DEBUG] Selected: {os.path.basename(file_path)}")
            # Deselect all others
            for row in self.file_list:
                if isinstance(row, Gtk.ListBoxRow):
                    child = row.get_child()
                    if isinstance(child, PDFTile) and child.file_path != file_path:
                        child.set_selected(False)

            # Find and select clicked tile
            for row in self.file_list:
                if isinstance(row, Gtk.ListBoxRow):
                    child = row.get_child()
                    if isinstance(child, PDFTile) and child.file_path == file_path:
                        child.set_selected(True)
                        self.selected_tile = child
                        self.update_status(f"Selected: {os.path.basename(file_path)}")
                        break

        elif action in ["up", "down"]:
            print(f"[DEBUG] Move {action}: {os.path.basename(file_path)}")
            if file_path not in self.files:
                return

            idx = self.files.index(file_path)
            new_idx = idx - 1 if action == "up" else idx + 1

            if new_idx < 0 or new_idx >= len(self.files):
                self.update_status("Cannot move further in that direction")
                return

            # Swap in files list
            self.files[idx], self.files[new_idx] = self.files[new_idx], self.files[idx]

            # Rebuild list to reflect new order
            self._rebuild_file_list()

            # Re-select the moved tile
            self.handle_tile_action(file_path, "select")
            self.update_status(f"Moved {os.path.basename(file_path)} to position {new_idx + 1}")

    def _rebuild_file_list(self):
        """Rebuild the file list UI"""
        self.file_list.foreach(lambda w: self.file_list.remove(w))
        for i, path in enumerate(self.files):
            tile = PDFTile(path, i, on_move_callback=self.handle_tile_action)
            tile.connect("tile-remove", self.remove_tile)
            tile.show_all()
            self.file_list.add(tile)

    def update_file_list_count(self):
        """Update the 'Added Files' label count"""
        count = len(self.files)
        self.list_count_label.set_markup("<b>Added Files</b> <small>({})</small>".format(count))

    def on_drop(self, widget, context, x, y, selection_data, info, time):
        print("[DEBUG] Drag-drop received!")
        data = selection_data.get_data()
        if not data:
            self.show_error("No data received in drop")
            return

        try:
            text = data.decode('utf-8')
        except:
            self.show_error("Could not decode dropped data")
            return

        # Extract paths from URI list
        paths = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('file://'):
                p = line[7:].replace('%20', ' ').replace('%2F', '/')
                paths.append(p)

        print(f"[DEBUG] Extracted {len(paths)} paths")

        if not paths:
            self.show_error("No file paths found")
            return

        added_count = 0
        skipped_count = 0

        for path in paths:
            if path.endswith('.pdf') or '.pdf' in path.lower():
                print(f"[DEBUG] Processing: {path}")
                self.add_file_to_list(path, silent=True)
                added_count += 1
            else:
                print(f"[DEBUG] Skipping non-PDF: {path}")
                skipped_count += 1

        # Update count label
        self.update_file_list_count()

        # Final status update with total count
        total_now = len(self.files)
        self.update_status(
            "{} file{} in queue ({} added)".format(total_now, 's' if total_now != 1 else '', added_count))

        if skipped_count > 0:
            self.show_info("Skipped {} non-PDF file{}".format(skipped_count, 's' if skipped_count > 1 else ''))

    def add_file_to_list(self, path, silent=False):
        """Add file to the list"""
        is_valid, err = self.logic.validate_file(path)
        if not is_valid:
            if not silent:
                self.show_error(err)
            return False

        if path in self.files:
            if not silent:
                self.show_info("File already in list")
            return False

        # Infer output folder from first file
        if self.inferred_folder is None:
            self.inferred_folder = os.path.dirname(os.path.abspath(path))
            self.output_folder.set_text(self.inferred_folder)
            print(f"[DEBUG] Inferred output folder: {self.inferred_folder}")

        # Clear empty state if first file
        if len(self.files) == 0:
            self.file_list.foreach(lambda w: self.file_list.remove(w))

        self.files.append(path)

        # Create tile with callback
        tile = PDFTile(path, len(self.files) - 1, on_move_callback=self.handle_tile_action)
        tile.connect("tile-remove", self.remove_tile)
        tile.show_all()
        self.file_list.add(tile)

        # Safe scrolling
        parent = self.file_list.get_parent()
        if parent:
            adj = parent.get_vadjustment()
            if adj:
                adj.set_value(adj.get_upper())

        if not silent:
            self.update_status("Added: {}".format(os.path.basename(path)))
        self.update_empty_state()
        return True

    def remove_tile(self, widget, tile):
        print("[DEBUG] remove_tile called for: {}".format(os.path.basename(tile.file_path)))

        # Remove from files list
        if tile.file_path in self.files:
            self.files.remove(tile.file_path)

        # Find and remove the ListBoxRow containing the tile
        for row in self.file_list.get_children():
            if isinstance(row, Gtk.ListBoxRow):
                child = row.get_child()
                if child is tile or getattr(child, 'file_path', None) == tile.file_path:
                    self.file_list.remove(row)
                    print("[DEBUG] Removed row from listbox")
                    break

        # Clear selection if removed tile was selected
        if self.selected_tile and self.selected_tile.file_path == tile.file_path:
            self.selected_tile = None

        # Reorder remaining tiles
        self._rebuild_file_list()  # Rebuild to fix indices

        # Update count and status
        self.update_file_list_count()
        self.update_status("File removed")

        print("[DEBUG] Remaining files: {}".format(len(self.files)))

    def on_browse_click(self, button=None, event=None):
        """Open file browser dialog"""
        print("[DEBUG] Opening file browser...")
        chooser = Gtk.FileChooserDialog(
            title="Select PDF Files",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.set_select_multiple(True)
        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files")
        filter_pdf.add_pattern("*.pdf")
        filter_pdf.add_mime_type("application/pdf")
        chooser.add_filter(filter_pdf)

        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        response = chooser.run()  # Capture return value

        if response == Gtk.ResponseType.OK:
            filenames = chooser.get_filenames()
            print("[DEBUG] Selected {} files".format(len(filenames)))
            for path in filenames:
                self.add_file_to_list(path, silent=True)
            self.update_file_list_count()
            total = len(self.files)
            self.update_status("{} file{} in queue".format(total, 's' if total != 1 else ''))
        else:
            print("[DEBUG] File browser cancelled")

        chooser.destroy()  # Always destroy after run()

    def on_browse_folder(self, button):
        # Use current inferred folder as starting point
        start_folder = self.output_folder.get_text()
        if not start_folder or not os.path.isdir(start_folder):
            start_folder = self.inferred_folder or os.getcwd()

        chooser = Gtk.FileChooserDialog(
            title="Select Output Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.set_current_folder(start_folder)
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            folder = chooser.get_filename()
            self.output_folder.set_text(folder)
            self.inferred_folder = folder  # Update inferred folder
            print(f"[DEBUG] Output folder set to: {folder}")

        chooser.destroy()

    def on_merge(self, button):
        if len(self.files) < 2:
            self.show_error("Please add at least 2 PDF files to merge.")
            return

        # Use selected folder or inferred folder
        default_folder = self.output_folder.get_text() or self.inferred_folder or os.getcwd()
        if not os.path.isdir(default_folder):
            default_folder = os.getcwd()

        chooser = Gtk.FileChooserDialog(
            title="Save Merged PDF",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        chooser.set_current_folder(default_folder)
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        chooser.set_current_name("merged.pdf")

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files")
        filter_pdf.add_pattern("*.pdf")
        chooser.add_filter(filter_pdf)

        if chooser.run() == Gtk.ResponseType.OK:
            output_path = chooser.get_filename()
            if not output_path.endswith('.pdf'):
                output_path += '.pdf'

            self.update_status("Merging {} files...".format(len(self.files)))

            # Run merge
            success, msg = self.logic.concat_pdfs(self.files, output_path)

            if success:
                self.update_status("✓ Successfully saved to: {}".format(output_path), success=True)
                self.show_info("Merged {} files!\nSaved to:\n{}".format(len(self.files), output_path))
            else:
                self.update_status("✗ {}".format(msg), success=False)
                self.show_error("Merge failed:\n{}".format(msg))

        chooser.destroy()

    def on_clear(self, button):
        self.files.clear()
        self.selected_tile = None
        self.file_list.foreach(lambda w: self.file_list.remove(w))
        self.update_file_list_count()
        self.update_status("Cleared all files")

    def update_status(self, msg, success=None):
        if success is None:
            color = "#666"
        elif success:
            color = "#2ecc71"
        else:
            color = "#e74c3c"
        self.status_label.set_markup('<span foreground="{}">{}</span>'.format(color, msg))

    def update_empty_state(self):
        """Show/hide empty placeholder message"""
        count = len(self.file_list.get_children())
        self.list_count_label.set_markup("<b>Added Files</b> <small>({})</small>".format(count))

    def show_error(self, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error"
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

    def show_info(self, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Info"
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()


def launch():
    app = PDFConcatenatorApp()
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()