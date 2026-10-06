#!/usr/bin/env python3
"""Symbolic Link Creator Application"""

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import os
from urllib.parse import unquote


class SymlinkCreatorApp(Gtk.Window):
    """Symbolic link creator with drag-and-drop"""

    def __init__(self):
        super().__init__(title="Create Symbolic Link")
        self.set_default_size(500, 280)
        self.set_border_width(15)

        # Store paths
        self.target_path = ""
        self.destination_path = ""

        # Main layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(12)
        main_vbox.set_margin_start(15)
        main_vbox.set_margin_end(15)
        main_vbox.set_margin_top(15)
        main_vbox.set_margin_bottom(15)

        # === ROW 1: TARGET PATH (Editable + DND) ===
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.set_spacing(10)

        target_label = Gtk.Label(label="<b>Target</b>:")
        target_label.set_use_markup(True)
        target_label.set_width_chars(12)
        target_label.set_halign(Gtk.Align.END)
        row1.pack_start(target_label, False, False, 0)

        # Editable drop zone for target (CAN TYPE NOW!)
        self.target_drop_zone = Gtk.Entry()
        self.target_drop_zone.set_placeholder_text("Type or drag file/folder path here...")
        self.target_drop_zone.set_editable(True)  # ← ALLOW EDITING!
        self.target_drop_zone.set_hexpand(True)
        self.target_drop_zone.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "document-open")
        self.target_drop_zone.set_tooltip_text("Type path or drop from file manager")
        self.target_drop_zone.connect("changed", self.on_target_changed)

        # Enable drag-and-drop
        self.setup_drag_and_drop(self.target_drop_zone, self.on_target_drop)
        row1.pack_start(self.target_drop_zone, True, True, 0)

        browse_target_btn = Gtk.Button(label="Browse...")
        browse_target_btn.connect("clicked", self.on_browse_target)
        row1.pack_start(browse_target_btn, False, False, 0)

        main_vbox.pack_start(row1, False, False, 0)

        # === ROW 2: DESTINATION FOLDER (Editable + DND) ===
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row2.set_spacing(10)

        dest_label = Gtk.Label(label="<b>Destination</b>:")
        dest_label.set_use_markup(True)
        dest_label.set_width_chars(12)
        dest_label.set_halign(Gtk.Align.END)
        row2.pack_start(dest_label, False, False, 0)

        # Editable drop zone for destination (CAN TYPE NOW!)
        self.dest_drop_zone = Gtk.Entry()
        self.dest_drop_zone.set_placeholder_text("Type or drag destination folder path...")
        self.dest_drop_zone.set_editable(True)  # ← ALLOW EDITING!
        self.dest_drop_zone.set_hexpand(True)
        self.dest_drop_zone.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "folder")
        self.dest_drop_zone.set_tooltip_text("Type folder path or drop from file manager")
        self.dest_drop_zone.connect("changed", self.on_dest_changed)

        self.setup_drag_and_drop(self.dest_drop_zone, self.on_dest_drop)
        row2.pack_start(self.dest_drop_zone, True, True, 0)

        browse_dest_btn = Gtk.Button(label="Browse...")
        browse_dest_btn.connect("clicked", self.on_browse_dest)
        row2.pack_start(browse_dest_btn, False, False, 0)

        main_vbox.pack_start(row2, False, False, 0)

        # === ROW 3: LINK NAME ===
        row3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row3.set_spacing(10)

        name_label = Gtk.Label(label="<b>Name</b>:")
        name_label.set_use_markup(True)
        name_label.set_width_chars(12)
        name_label.set_halign(Gtk.Align.END)
        row3.pack_start(name_label, False, False, 0)

        self.link_name_entry = Gtk.Entry()
        self.link_name_entry.set_placeholder_text("Auto-filled from target name")
        self.link_name_entry.set_hexpand(True)
        self.link_name_entry.set_tooltip_text("Custom name for the symlink (optional)")
        row3.pack_start(self.link_name_entry, True, True, 0)

        main_vbox.pack_start(row3, False, False, 0)

        # === SEPARATOR ===
        separator = Gtk.Separator()
        main_vbox.pack_start(separator, False, False, 10)

        # === STATUS BAR ===
        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_markup('<span foreground="#666">Ready</span>')
        main_vbox.pack_start(self.status_label, False, False, 5)

        # === BUTTONS ===
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_spacing(10)
        button_box.set_halign(Gtk.Align.END)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", self.on_clear)
        button_box.pack_start(clear_btn, False, False, 0)

        create_btn = Gtk.Button(label="🔗 Create Link")
        create_btn.get_style_context().add_class("suggested-action")
        create_btn.connect("clicked", self.on_create_link)
        button_box.pack_start(create_btn, False, False, 0)

        main_vbox.pack_start(button_box, False, False, 5)

        self.add(main_vbox)

        # Initialize status
        self.update_status("Choose target folder/file")

    def setup_drag_and_drop(self, widget, callback):
        """Setup drag-and-drop for a widget"""
        targets = [
            Gtk.TargetEntry.new("text/uri-list", 0, 0),
            Gtk.TargetEntry.new("text/plain", 0, 1),
        ]

        widget.drag_dest_set(
            Gtk.DestDefaults.ALL,
            targets,
            Gdk.DragAction.COPY | Gdk.DragAction.DEFAULT
        )

        widget.connect("drag-data-received", callback)

    def on_target_changed(self, entry):
        """Handle manual typing in target field"""
        path = entry.get_text().strip()
        if path and os.path.exists(path):
            self.target_path = path
            self.auto_fill_link_name()
            self.update_status(f"Target: {os.path.basename(path)}")

    def on_dest_changed(self, entry):
        """Handle manual typing in destination field"""
        path = entry.get_text().strip()
        if path and os.path.isdir(path):
            self.destination_path = path
            self.update_status(f"Destination: {os.path.basename(path)}")

    def on_target_drop(self, widget, context, x, y, selection_data, info, time):
        """Handle target path drop"""
        paths = self.extract_paths_from_selection(selection_data)

        if paths:
            self.target_path = paths[0]
            widget.set_text(self.target_path)
            self.auto_fill_link_name()
            self.set_drop_zone_color(widget, True)
            self.update_status(f"Target: {os.path.basename(self.target_path)}")
        else:
            self.set_drop_zone_color(widget, False)

    def on_dest_drop(self, widget, context, x, y, selection_data, info, time):
        """Handle destination path drop"""
        paths = self.extract_paths_from_selection(selection_data)

        if paths:
            self.destination_path = paths[0]
            widget.set_text(self.destination_path)
            self.set_drop_zone_color(widget, True)
            self.update_status(f"Destination: {os.path.basename(self.destination_path)}")

    def extract_paths_from_selection(self, selection_data):
        """Extract file paths from drag-and-drop data"""
        data = selection_data.get_data()

        if not data:
            return []

        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            return []

        paths = []

        # Handle URI list format (file:// paths)
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            if line.startswith('file://'):
                path = unquote(line[7:])
                if path and os.path.exists(path):
                    paths.append(path)
            else:
                if os.path.exists(line):
                    paths.append(line)

        return paths

    def set_drop_zone_color(self, widget, valid):
        """Visual feedback for drop zones"""
        if valid:
            widget.override_background_color(
                Gtk.StateFlags.NORMAL,
                Gdk.RGBA(red=0.2, green=0.6, blue=0.2, alpha=0.1)
            )
        else:
            widget.override_background_color(
                Gtk.StateFlags.NORMAL,
                Gdk.RGBA(red=0.0, green=0.0, blue=0.0, alpha=0.0)
            )

    def auto_fill_link_name(self):
        """Auto-fill link name from target filename"""
        if self.target_path:
            basename = os.path.basename(self.target_path.rstrip('/'))
            self.link_name_entry.set_text(basename)

    def on_browse_target(self, button):
        """Open file/folder chooser for target"""
        chooser = Gtk.FileChooserDialog(
            title="Select Target File/Folder",
            parent=self,
            action=Gtk.FileChooserAction.OPEN  # Allows both files AND folders
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        # Allow choosing folders by setting action appropriately
        chooser.set_action(Gtk.FileChooserAction.OPEN)

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            self.target_path = chooser.get_filename()
            self.target_drop_zone.set_text(self.target_path)
            self.auto_fill_link_name()
            self.set_drop_zone_color(self.target_drop_zone, True)

        chooser.close()

    def on_browse_dest(self, button):
        """Open folder chooser for destination"""
        chooser = Gtk.FileChooserDialog(
            title="Select Destination Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER  # Folders only
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            self.destination_path = chooser.get_filename()
            self.dest_drop_zone.set_text(self.destination_path)
            self.set_drop_zone_color(self.dest_drop_zone, True)

        chooser.close()

    def on_clear(self, button):
        """Clear all fields"""
        self.target_path = ""
        self.destination_path = ""
        self.target_drop_zone.set_text("")
        self.dest_drop_zone.set_text("")
        self.link_name_entry.set_text("")
        self.set_drop_zone_color(self.target_drop_zone, False)
        self.set_drop_zone_color(self.dest_drop_zone, False)
        self.update_status("Ready")

    def on_create_link(self, button):
        """Create the symbolic link"""
        if not self.target_path:
            self.show_error("Please specify a target file/folder")
            return

        if not self.destination_path:
            self.show_error("Please specify a destination folder")
            return

        if not os.path.exists(self.target_path):
            self.show_error(f"Target does not exist: {self.target_path}")
            return

        if not os.path.isdir(self.destination_path):
            self.show_error(f"Destination is not a folder: {self.destination_path}")
            return

        link_name = self.link_name_entry.get_text().strip()
        if not link_name:
            link_name = os.path.basename(self.target_path.rstrip('/'))

        link_path = os.path.join(self.destination_path, link_name)

        # Check if link already exists
        if os.path.lexists(link_path):
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.YES_NO,
                text="File Already Exists"
            )
            dialog.format_secondary_text(f"'{link_name}' already exists. Overwrite?")
            response = dialog.run()
            dialog.destroy()

            if response != Gtk.ResponseType.YES:
                return

        try:
            # Remove existing if needed
            if os.path.lexists(link_path):
                os.remove(link_path)

            # Create symbolic link
            os.symlink(self.target_path, link_path)
            self.update_status(
                f"✓ Created link: {link_name} → {self.target_path}",
                success=True
            )

            # Show success dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Link Created Successfully!"
            )
            dialog.format_secondary_text(f"Created: {link_path}")
            dialog.run()
            dialog.destroy()

        except Exception as e:
            self.show_error(f"Failed to create link:\n{str(e)}")

    def update_status(self, message, success=False):
        """Update status bar"""
        color = "#2ecc71" if success else "#666"
        self.status_label.set_markup(f'<span foreground="{color}">{message}</span>')

    def show_error(self, message):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error"
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()


def launch():
    """Entry point called by main.py"""
    app = SymlinkCreatorApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()