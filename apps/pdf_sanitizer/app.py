#!/usr/bin/env python3
"""PDF Sanitizer Application - GTK GUI"""

import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import os
import logic


class PDFSanitizerApp(Gtk.Window):
    """PDF sanitizer - removes hidden text/metadata via image conversion"""

    def __init__(self):
        super().__init__(title="PDF Sanitizer")
        self.set_default_size(550, 350)
        self.set_border_width(15)

        # Store paths
        self.input_path = ""
        self.output_path = ""
        self.current_dpi = 150

        # Main layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(12)
        main_vbox.set_margin_start(15)
        main_vbox.set_margin_end(15)
        main_vbox.set_margin_top(15)
        main_vbox.set_margin_bottom(15)

        # === INFO BOX ===
        info_frame = Gtk.Frame(label="About PDF Sanitizer")
        info_frame.set_margin_start(5)
        info_frame.set_margin_end(5)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_spacing(5)
        info_box.set_margin_start(10)
        info_box.set_margin_end(10)
        info_box.set_margin_top(10)
        info_box.set_margin_bottom(10)

        info_text = Gtk.Label()
        info_text.set_markup(
            "<b>Removes:</b> Hidden text, annotations, metadata, form data\n"
            "<b>Preserves:</b> Visual content, images, layout\n"
            "<b>Process:</b> PDF → PNG → PDF (flattens all layers)"
        )
        info_text.set_halign(Gtk.Align.START)
        info_text.set_line_wrap(True)
        info_box.pack_start(info_text, False, False, 0)

        info_frame.add(info_box)
        main_vbox.pack_start(info_frame, False, False, 5)

        # === ROW 1: INPUT FILE ===
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.set_spacing(10)

        input_label = Gtk.Label(label="<b>Input PDF</b>:")
        input_label.set_use_markup(True)
        input_label.set_width_chars(12)
        input_label.set_halign(Gtk.Align.END)
        row1.pack_start(input_label, False, False, 0)

        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text("Select PDF to sanitize...")
        self.input_entry.set_editable(True)
        self.input_entry.set_hexpand(True)
        self.input_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "document-open")
        self.input_entry.connect("changed", self.on_input_changed)
        row1.pack_start(self.input_entry, True, True, 0)

        browse_input_btn = Gtk.Button(label="Browse...")
        browse_input_btn.connect("clicked", self.on_browse_input)
        row1.pack_start(browse_input_btn, False, False, 0)

        main_vbox.pack_start(row1, False, False, 0)

        # === ROW 2: OUTPUT FILE ===
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row2.set_spacing(10)

        output_label = Gtk.Label(label="<b>Output PDF</b>:")
        output_label.set_use_markup(True)
        output_label.set_width_chars(12)
        output_label.set_halign(Gtk.Align.END)
        row2.pack_start(output_label, False, False, 0)

        self.output_entry = Gtk.Entry()
        self.output_entry.set_placeholder_text("Output file will be auto-generated")
        self.output_entry.set_editable(True)
        self.output_entry.set_hexpand(True)
        self.output_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "folder-save")
        row2.pack_start(self.output_entry, True, True, 0)

        browse_output_btn = Gtk.Button(label="Browse...")
        browse_output_btn.connect("clicked", self.on_browse_output)
        row2.pack_start(browse_output_btn, False, False, 0)

        main_vbox.pack_start(row2, False, False, 0)

        # === ROW 3: QUALITY SETTING ===
        row3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row3.set_spacing(10)

        quality_label = Gtk.Label(label="<b>Quality</b>:")
        quality_label.set_use_markup(True)
        quality_label.set_width_chars(12)
        quality_label.set_halign(Gtk.Align.END)
        row3.pack_start(quality_label, False, False, 0)

        self.quality_combo = Gtk.ComboBoxText()
        quality_options = logic.get_quality_options()
        for name, dpi in quality_options.items():
            self.quality_combo.append(str(dpi), name)
        self.quality_combo.set_active_id("150")
        self.quality_combo.connect("changed", self.on_quality_changed)
        row3.pack_start(self.quality_combo, False, False, 0)

        info_label = Gtk.Label()
        info_label.set_halign(Gtk.Align.START)
        self.quality_info_label = info_label
        row3.pack_start(info_label, True, True, 0)

        main_vbox.pack_start(row3, False, False, 0)

        # === ROW 4: FILE INFO ===
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_spacing(5)
        info_box.set_margin_start(5)
        info_box.set_margin_end(5)

        self.size_label = Gtk.Label(label="Input size: --")
        self.size_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.size_label, False, False, 0)

        self.status_label = Gtk.Label(label="Status: Ready")
        self.status_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.status_label, False, False, 0)

        main_vbox.pack_start(info_box, False, False, 5)

        # === PROGRESS BAR ===
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_show_text(True)
        main_vbox.pack_start(self.progress_bar, False, False, 5)

        # === BUTTONS ===
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_spacing(10)
        button_box.set_halign(Gtk.Align.END)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", self.on_clear)
        button_box.pack_start(clear_btn, False, False, 0)

        sanitize_btn = Gtk.Button(label="🛡️ Sanitize PDF")
        sanitize_btn.get_style_context().add_class("suggested-action")
        sanitize_btn.connect("clicked", self.on_sanitize)
        button_box.pack_start(sanitize_btn, False, False, 0)

        main_vbox.pack_start(button_box, False, False, 0)

        self.add(main_vbox)

        # Initial update
        self.update_quality_info()
        self.update_status("Ready")

    def on_input_changed(self, entry):
        """Handle input file path changes"""
        path = entry.get_text().strip()
        if path:
            self.input_path = path
            is_valid, error = logic.validate_input_path(path)

            if is_valid:
                # Auto-generate output filename
                if not self.output_path:
                    self.output_path = logic.generate_default_output_name(path)
                    self.output_entry.set_text(self.output_path)

                # Update file info
                size = logic.get_file_size_bytes(path)
                self.size_label.set_text(f"Input size: {logic.format_file_size(size)}")
                self.status_label.set_markup('<span foreground="#2ecc71">✓ Valid PDF</span>')
            else:
                self.size_label.set_text("Input size: --")
                self.status_label.set_markup(f'<span foreground="#e74c3c">✗ {error}</span>')
        else:
            self.size_label.set_text("Input size: --")
            self.status_label.set_text("Status: Ready")

    def on_output_changed(self, entry):
        """Handle output file path changes"""
        self.output_path = entry.get_text().strip()

    def on_quality_changed(self, combo):
        """Handle quality setting changes"""
        self.current_dpi = int(combo.get_active_id())
        self.update_quality_info()

    def update_quality_info(self):
        """Update quality description"""
        options = logic.get_quality_options()
        desc = options.get(str(self.current_dpi), "Custom")
        self.quality_info_label.set_text(f"{desc} - Higher = better quality, slower")

    def on_browse_input(self, button):
        """Open file chooser for input PDF"""
        chooser = Gtk.FileChooserDialog(
            title="Select PDF to Sanitize",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files")
        filter_pdf.add_pattern("*.pdf")
        chooser.add_filter(filter_pdf)

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            self.input_entry.set_text(path)

        chooser.close()

    def on_browse_output(self, button):
        """Open file saver for output"""
        chooser = Gtk.FileChooserDialog(
            title="Save Sanitized PDF As",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )

        if self.input_path:
            default_name = logic.generate_default_output_name(self.input_path)
            chooser.set_current_name(os.path.basename(default_name))

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            if not path.lower().endswith('.pdf'):
                path += '.pdf'
            self.output_entry.set_text(path)

        chooser.close()

    def on_clear(self, button):
        """Clear all fields"""
        self.input_path = ""
        self.output_path = ""
        self.input_entry.set_text("")
        self.output_entry.set_text("")
        self.size_label.set_text("Input size: --")
        self.status_label.set_text("Status: Ready")
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("")

    def on_sanitize(self, button):
        """Start PDF sanitization"""
        # Validate inputs
        is_valid, error = logic.validate_input_path(self.input_path)
        if not is_valid:
            self.show_error(error)
            return

        is_valid, error = logic.validate_output_path(self.output_path)
        if not is_valid:
            self.show_error(error)
            return

        # Check tools availability
        tools_ok, msg = logic.check_tools_available()
        if not tools_ok:
            self.show_error(f"Required tools missing:\n{msg}")
            return

        # Show confirmation if output exists
        if os.path.exists(self.output_path):
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Overwrite existing file?"
            )
            dialog.format_secondary_text(f" '{os.path.basename(self.output_path)}' already exists.")
            response = dialog.run()
            dialog.destroy()

            if response != Gtk.ResponseType.YES:
                return

        # Disable controls during processing
        self.set_sensitive(False)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Starting sanitization...")
        self.status_label.set_text("Processing...")

        # Run sanitization asynchronously
        GLib.idle_add(self.perform_sanitization)

    def perform_sanitization(self):
        """Perform sanitization in background thread"""
        # Show progress dialog
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="Sanitizing PDF..."
        )
        dialog.format_secondary_text("Converting through PNG images...\nThis may take a moment.")
        dialog.show_all()

        # Perform sanitization
        success, error = logic.sanitize_pdf(
            self.input_path,
            self.output_path,
            self.current_dpi
        )

        # Hide dialog
        dialog.destroy()

        if success:
            # Calculate size change
            orig_size = logic.get_file_size_bytes(self.input_path)
            san_size = logic.get_file_size_bytes(self.output_path)
            change, desc = logic.calculate_size_change(orig_size, san_size)

            self.progress_bar.set_fraction(1.0)
            self.progress_bar.set_text("Complete!")

            msg = (f"Sanitization successful!\n\n"
                   f"Input: {logic.format_file_size(orig_size)}\n"
                   f"Output: {logic.format_file_size(san_size)}\n"
                   f"Size: {desc}\n\n"
                   f"Saved to:\n{self.output_path}\n\n"
                   f"Hidden text and metadata have been removed.")

            self.show_info(msg)
        else:
            self.progress_bar.set_fraction(0.0)
            self.progress_bar.set_text("Error")
            self.show_error(f"Sanitization failed:\n{error}")

        self.set_sensitive(True)
        return False

    def set_sensitive(self, sensitive: bool):
        """Enable/disable all controls"""
        self.input_entry.set_sensitive(sensitive)
        self.output_entry.set_sensitive(sensitive)
        self.quality_combo.set_sensitive(sensitive)

    def update_status(self, message: str):
        """Update status label"""
        self.status_label.set_text(f"Status: {message}")

    def show_error(self, message: str):
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

    def show_info(self, message: str):
        """Show info dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Information"
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()


def launch():
    """Entry point called by main.py"""
    app = PDFSanitizerApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()