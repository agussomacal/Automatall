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

    def __init__(self, file_path, index):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.file_path = file_path
        self.index = index
        self.set_spacing(8)
        self.set_margin_start(5)
        self.set_margin_end(5)
        self.set_margin_top(3)
        self.set_margin_bottom(3)
        self.set_can_focus(False)

        # Background styling for tile
        self.get_style_context().add_class("pdf-tile")

        # Index label
        idx_label = Gtk.Label(label=f"{index + 1}")
        idx_label.set_size_request(25, -1)
        self.idx_label = idx_label
        self.pack_start(idx_label, False, False, 0)

        # Icon
        try:
            img = Gtk.Image.new_from_icon_name("application-pdf", Gtk.IconSize.SMALL_TOOLBAR)
        except:
            img = Gtk.Label(label="📄")
        self.pack_start(img, False, False, 0)

        # Filename (truncated with ellipsis)
        name_label = Gtk.Label(label=os.path.basename(file_path))
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.pack_start(name_label, True, True, 0)

        # Remove button
        remove_btn = Gtk.Button(label="×")
        remove_btn.get_style_context().add_class("destructive-action")
        remove_btn.set_size_request(28, 28)
        remove_btn.connect("clicked", self.on_remove)
        self.pack_start(remove_btn, False, False, 0)

        # Drag setup (optional for reordering)
        targets = [Gtk.TargetEntry.new("text/plain", 0, 0)]
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, targets, Gdk.DragAction.MOVE)
        self.connect("drag-data-get", self.on_drag_data_get)

    def on_remove(self, button):
        # Emit custom signal
        self.emit('tile-remove', self)

    def on_drag_data_get(self, widget, drag_context, selection_data, info, time):
        selection_data.set_text(str(self.file_path), -1)
        Gtk.drag_finish(drag_context, True, False, time)


class PDFConcatenatorApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="PDF Concatenator")
        self.set_default_size(700, 600)
        self.set_border_width(15)
        self.set_resizable(True)

        self.logic = PDFConcatenatorLogic()
        self.files = []  # List of file paths in order

        # Main Layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(15)

        # Header
        header = Gtk.Label()
        header.set_markup("<b><span size='x-large'>PDF Concatenator</span></b>")
        header.set_margin_bottom(5)
        main_vbox.pack_start(header, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup("<small>Drag & Drop PDF files below to merge them into one document</small>")
        subtitle.set_sensitive(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
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
        self.list_count_label = list_label  # Reference to update count
        right_vbox.pack_start(list_label, False, False, 0)

        # Scrollable file list
        self.scroll_win = Gtk.ScrolledWindow()
        self.scroll_win.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll_win.set_min_content_height(200)
        self.scroll_win.set_max_content_height(400)
        self.scroll_win.set_shadow_type(Gtk.ShadowType.IN)
        self.scroll_win.set_vexpand(True)
        self.scroll_win.set_hexpand(True)

        self.file_list = Gtk.ListBox()
        self.file_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.file_list.set_activate_on_single_click(True)
        self.file_list.get_style_context().add_class("tile-list")

        # Add file_list DIRECTLY to scroll window (not via placeholder)
        self.scroll_win.add(self.file_list)

        # Store ref for later updates
        self.file_list.set_hexpand(True)
        self.file_list.set_vexpand(True)

        right_vbox.pack_start(self.scroll_win, True, True, 0)

        # Add panes to Paned widget
        paned.pack1(drop_box, resize=True, shrink=True)  # LEFT: resizable
        paned.pack2(right_vbox, resize=False, shrink=False)  # RIGHT: fixed

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

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            #drop_zone {
                border: 3px dashed #999;
                border-radius: 12px;
                padding: 20px;
                background-color: rgba(109, 76, 255, 0.05);
            }
            #drop_zone:hover {
                background-color: rgba(109, 76, 255, 0.15);
                border-color: #6d4aff;
            }
            .pdf-tile {
                background-color: rgba(0,0,0,0.03);
                border: 1px solid #ddd;
                border-radius: 6px;
            }
            .pdf-tile:hover {
                background-color: rgba(109, 76, 255, 0.1);
                border-color: #6d4aff;
            }
            .tile-list {
                background-color: rgba(255,255,255,0.95);
                border-radius: 8px;
            }
        """)
        screen = Gdk.Screen.get_default()
        style_context = self.get_style_context()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def update_file_list_count(self):
        """Update the 'Added Files' label count"""
        count = len(self.files)
        self.list_count_label.set_markup("<b>Added Files</b> <small>({})</small>".format(count))

        # Show/hide empty placeholder
        if count == 0:
            # Switch back to placeholder
            for child in self.file_list.get_children():
                self.file_list.remove(child)
            # The viewport contains the placeholder
        else:
            # Make sure placeholder is not shown
            pass

    def on_drop(self, widget, context, x, y, selection_data, info, time):
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

        if not paths:
            self.show_error("No file paths found")
            return

        added_count = 0
        skipped_count = 0
        original_count = len(self.files)

        for path in paths:
            if path.endswith('.pdf') or '.pdf' in path.lower():
                self.add_file_to_list(path, silent=True)
                added_count += 1
            else:
                skipped_count += 1

        # Update count label
        self.update_file_list_count()

        # Final status update with total count
        total_now = len(self.files)
        self.update_status(f"{total_now} file{'s' if total_now != 1 else ''} in queue ({added_count} added)")

        if skipped_count > 0:
            self.show_info(f"Skipped {skipped_count} non-PDF file{'s' if skipped_count > 1 else ''}")

    def add_file_to_list(self, path, silent=False):
        """Add file to the list, optionally suppressing status updates"""
        is_valid, err = self.logic.validate_file(path)
        if not is_valid:
            if not silent:
                self.show_error(err)
            return False

        if path in self.files:
            if not silent:
                self.show_info("File already in list")
            return False

        # Clear empty state if first file
        if len(self.files) == 0:
            self.file_list.foreach(lambda w: self.file_list.remove(w))

        self.files.append(path)
        tile = PDFTile(path, len(self.files) - 1)
        tile.connect("tile-remove", self.remove_tile)
        self.file_list.add(tile)

        # Safe scrolling - check if parent exists
        parent = self.file_list.get_parent()
        if parent:
            adj = parent.get_vadjustment()
            if adj:
                adj.set_value(adj.get_upper())

        if not silent:
            self.update_status(f"Added: {os.path.basename(path)}")
        self.update_empty_state()
        return True

    def remove_tile(self, widget, tile):
        if tile in self.file_list:
            self.file_list.remove(tile)
            if tile.file_path in self.files:
                self.files.remove(tile.file_path)
            self.reorder_indices()
            self.update_empty_state()  # Add this
            self.update_status("File removed")

            # Show empty placeholder if no files left
            if len(self.files) == 0:
                for child in self.file_list.get_children():
                    self.file_list.remove(child)
                # Placeholder will be handled by container

    def reorder_indices(self):
        """Re-number the tiles after removal"""
        for i, row in enumerate(self.file_list):
            if isinstance(row, PDFTile):
                row.idx_label.set_text(f"{i + 1}")
                row.index = i

    def on_browse_click(self, button=None, event=None):
        """Open file browser dialog"""
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
            for path in filenames:
                self.add_file_to_list(path, silent=True)
            self.update_file_list_count()
            total = len(self.files)
            self.update_status(f"{total} file{'s' if total != 1 else ''} in queue")

        chooser.destroy()  # Always destroy after run()

    def on_browse_folder(self, button):
        chooser = Gtk.FileChooserDialog(
            title="Select Output Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SELECT, Gtk.ResponseType.OK)

        current_text = self.output_folder.get_text()
        if current_text and os.path.isdir(current_text):
            chooser.set_current_folder(current_text)

        if chooser.run() == Gtk.ResponseType.OK:
            self.output_folder.set_text(chooser.get_filename())
        chooser.destroy()

    def on_merge(self, button):
        if len(self.files) < 2:
            self.show_error("Please add at least 2 PDF files to merge.")
            return

        # Use selected folder as default
        default_folder = self.output_folder.get_text() or os.getcwd()
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

            self.update_status(f"Merging {len(self.files)} files...")

            # Run merge
            success, msg = self.logic.concat_pdfs(self.files, output_path)

            if success:
                self.update_status(f"✓ Successfully saved to: {output_path}", success=True)
                self.show_info(f"Merged {len(self.files)} files!\nSaved to:\n{output_path}")
            else:
                self.update_status(f"✗ {msg}", success=False)
                self.show_error(f"Merge failed:\n{msg}")

        chooser.destroy()

    def on_clear(self, button):
        self.files.clear()
        for row in list(self.file_list.get_children()):
            self.file_list.remove(row)
        self.update_file_list_count()
        self.update_status("Cleared all files")

    def update_status(self, msg, success=None):
        if success is None:
            color = "#666"
        elif success:
            color = "#2ecc71"
        else:
            color = "#e74c3c"
        self.status_label.set_markup(f'<span foreground="{color}">{msg}</span>')

    def update_empty_state(self):
        """Show/hide empty placeholder message"""
        count = len(self.file_list.get_children())
        self.list_count_label.set_markup("<b>Added Files</b> <small>({})</small>".format(count))

        if count == 0:
            # Optionally add a label at bottom of list
            pass  # List is empty, nothing to show

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
