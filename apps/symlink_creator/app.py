#!/usr/bin/env python3
"""Symbolic Link Creator Application - GTK GUI"""

import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import os
import logic


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

        # === ROW 1: TARGET PATH ===
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.set_spacing(10)

        target_label = Gtk.Label(label="<b>Target</b>:")
        target_label.set_use_markup(True)
        target_label.set_width_chars(12)
        target_label.set_halign(Gtk.Align.END)
        row1.pack_start(target_label, False, False, 0)

        self.target_drop_zone = Gtk.Entry()
        self.target_drop_zone.set_placeholder_text("Type or drag file/folder path here...")
        self.target_drop_zone.set_editable(True)
        self.target_drop_zone.set_hexpand(True)
        self.target_drop_zone.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "document-open")
        self.target_drop_zone.connect("changed", self.on_target_changed)

        self.setup_drag_and_drop(self.target_drop_zone, self.on_target_drop)
        row1.pack_start(self.target_drop_zone, True, True, 0)

        browse_target_btn = Gtk.Button(label="Browse...")
        browse_target_btn.connect("clicked", self.on_browse_target)
        row1.pack_start(browse_target_btn, False, False, 0)

        main_vbox.pack_start(row1, False, False, 0)

        # === ROW 2: DESTINATION ===
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row2.set_spacing(10)

        dest_label = Gtk.Label(label="<b>Destination</b>:")
        dest_label.set_use_markup(True)
        dest_label.set_width_chars(12)
        dest_label.set_halign(Gtk.Align.END)
        row2.pack_start(dest_label, False, False, 0)

        self.dest_drop_zone = Gtk.Entry()
        self.dest_drop_zone.set_placeholder_text("Type or drag destination folder path...")
        self.dest_drop_zone.set_editable(True)
        self.dest_drop_zone.set_hexpand(True)
        self.dest_drop_zone.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "folder")
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
        row3.pack_start(self.link_name_entry, True, True, 0)

        main_vbox.pack_start(row3, False, False, 0)

        # === SEPARATOR ===
        separator = Gtk.Separator()
        main_vbox.pack_start(separator, False, False, 10)

        # === STATUS ===
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
        self.update_status("Choose a target folder/file")

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
        if path:
            self.target_path = path
            self.auto_fill_link_name()
            if os.path.exists(path):
                self.update_status(f"Target: {os.path.basename(path)}")

    def on_dest_changed(self, entry):
        """Handle manual typing in destination field"""
        path = entry.get_text().strip()
        if path:
            self.destination_path = path
            if os.path.isdir(path):
                self.update_status(f"Destination: {os.path.basename(path)}")

    def on_target_drop(self, widget, context, x, y, selection_data, info, time):
        """Handle target path drop - uses logic.extract_paths_from_selection"""
        paths = logic.extract_paths_from_selection(selection_data.get_data())

        if paths:
            self.target_path = paths[0]
            widget.set_text(self.target_path)
            self.auto_fill_link_name()
            self.set_drop_zone_color(widget, True)
            self.update_status(f"Target: {os.path.basename(self.target_path)}")

    def on_dest_drop(self, widget, context, x, y, selection_data, info, time):
        """Handle destination path drop"""
        paths = logic.extract_paths_from_selection(selection_data.get_data())

        if paths:
            self.destination_path = paths[0]
            widget.set_text(self.destination_path)
            self.set_drop_zone_color(widget, True)
            self.update_status(f"Destination: {os.path.basename(self.destination_path)}")

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
        """Auto-fill link name from target - uses logic.auto_fill_link_name"""
        if self.target_path:
            name = logic.auto_fill_link_name(self.target_path)
            self.link_name_entry.set_text(name)

    def on_browse_target(self, button):
        """Open file/folder chooser for target"""
        chooser = Gtk.FileChooserDialog(
            title="Select Target File/Folder",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

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
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

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
        """Create the symbolic link - uses logic module"""
        # Validate using logic
        is_valid, errors = logic.validate_paths(self.target_path, self.destination_path)

        if not is_valid:
            self.show_error("\n".join(errors))
            return

        link_name = self.link_name_entry.get_text().strip()
        if not link_name:
            link_name = logic.auto_fill_link_name(self.target_path)

        link_path = logic.prepare_link_path(self.destination_path, link_name)

        # Check for existing file using logic
        if logic.check_link_exists(link_path):
            # Would show dialog here (omitted for brevity)
            pass

        # Create symlink using logic
        success, error_msg = logic.create_symlink(self.target_path, link_path)

        if success:
            # Verify using logic
            valid, msg = logic.verify_symlink_created(link_path, self.target_path)
            if valid:
                self.update_status(f"✓ Created link: {link_name}", success=True)
                self.show_info("Link created successfully!")
            else:
                self.show_error(f"Verification failed: {msg}")
        else:
            self.show_error(f"Failed to create link: {error_msg}")

    def update_status(self, message, success=False):
        """Update status bar"""
        color = "#2ecc71" if success else "#666"
        self.status_label.set_markup(f'<span foreground="{color}">{message}</span>')

    def show_error(self, message):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text="Error"
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def show_info(self, message):
        """Show info dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text="Info"
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
