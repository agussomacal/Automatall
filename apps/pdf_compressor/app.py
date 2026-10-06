#!/usr/bin/env python3
"""PDF Compressor Application - GTK GUI"""

import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import os
import logic

# Compression presets
PRESETS = {
    '/screen': 'Screen (Smallest)',
    '/ebook': 'eBook (Balanced)',
    '/printer': 'Printer (High Quality)',
    '/prepress': 'PrePress (Best)',
    '/default': 'Default'
}


class PDFCompressorApp(Gtk.Window):
    """PDF compressor with file selection and compression options"""

    def __init__(self):
        super().__init__(title="PDF Compressor")
        self.set_default_size(550, 320)
        self.set_border_width(15)

        # Store paths
        self.input_path = ""
        self.output_path = ""
        self.current_preset = "/ebook"

        # Main layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(12)
        main_vbox.set_margin_start(15)
        main_vbox.set_margin_end(15)
        main_vbox.set_margin_top(15)
        main_vbox.set_margin_bottom(15)

        # === ROW 1: INPUT FILE ===
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row1.set_spacing(10)

        input_label = Gtk.Label(label="<b>Input PDF</b>:")
        input_label.set_use_markup(True)
        input_label.set_width_chars(12)
        input_label.set_halign(Gtk.Align.END)
        row1.pack_start(input_label, False, False, 0)

        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text("Select PDF file to compress...")
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

        output_label = Gtk.Label(label="<b>Output</b>:")
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

        # === ROW 3: PRESET SELECTION ===
        row3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row3.set_spacing(10)

        preset_label = Gtk.Label(label="<b>Preset</b>:")
        preset_label.set_use_markup(True)
        preset_label.set_width_chars(12)
        preset_label.set_halign(Gtk.Align.END)
        row3.pack_start(preset_label, False, False, 0)

        self.preset_combo = Gtk.ComboBoxText()
        for preset, desc in PRESETS.items():
            self.preset_combo.append(preset, f"{desc}")
        self.preset_combo.set_active_id("/ebook")
        self.preset_combo.connect("changed", self.on_preset_changed)
        row3.pack_start(self.preset_combo, False, False, 0)

        preset_info = Gtk.Label()
        preset_info.set_text("")
        preset_info.set_halign(Gtk.Align.START)
        self.preset_info_label = preset_info
        row3.pack_start(preset_info, True, True, 0)

        main_vbox.pack_start(row3, False, False, 0)

        # === ROW 4: FILE INFO ===
        info_frame = Gtk.Frame(label="File Information")
        info_frame.set_margin_start(5)
        info_frame.set_margin_end(5)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_spacing(5)
        info_box.set_margin_start(10)
        info_box.set_margin_end(10)
        info_box.set_margin_top(10)
        info_box.set_margin_bottom(10)

        self.size_label = Gtk.Label(label="Size: --")
        self.size_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.size_label, False, False, 0)

        self.status_info_label = Gtk.Label(label="Status: Ready")
        self.status_info_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.status_info_label, False, False, 0)

        info_frame.add(info_box)
        main_vbox.pack_start(info_frame, False, False, 5)

        # === SEPARATOR ===
        separator = Gtk.Separator()
        main_vbox.pack_start(separator, False, False, 10)

        # === PROGRESS BAR ===
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_show_text(True)
        self.progress_text = ""
        main_vbox.pack_start(self.progress_bar, False, False, 5)

        # === BUTTONS ===
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_spacing(10)
        button_box.set_halign(Gtk.Align.END)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", self.on_clear)
        button_box.pack_start(clear_btn, False, False, 0)

        compress_btn = Gtk.Button(label="🗜️ Compress PDF")
        compress_btn.get_style_context().add_class("suggested-action")
        compress_btn.connect("clicked", self.on_compress)
        button_box.pack_start(compress_btn, False, False, 0)

        main_vbox.pack_start(button_box, False, False, 0)

        self.add(main_vbox)

        # Initial update
        self.update_preset_info()
        self.update_status("Ready")

    def on_input_changed(self, entry):
        """Handle input file path changes"""
        path = entry.get_text().strip()
        if path:
            self.input_path = path
            is_valid, error = logic.validate_input_path(path)

            if is_valid:
                # Auto-generate output filename
                if not self.output_path or self.output_path.startswith(
                        logic.generate_default_output_name(self.input_path)):
                    self.output_path = logic.generate_default_output_name(path)
                    self.output_entry.set_text(self.output_path)

                # Update file info
                size = logic.get_file_size_bytes(path)
                self.size_label.set_text(f"Size: {logic.format_file_size(size)}")
                self.status_info_label.set_markup('<span foreground="#2ecc71">✓ Valid PDF</span>')
            else:
                self.size_label.set_text("Size: --")
                self.status_info_label.set_markup(f'<span foreground="#e74c3c">✗ {error}</span>')

    def on_output_changed(self, entry):
        """Handle output file path changes"""
        self.output_path = entry.get_text().strip()

    def on_preset_changed(self, combo):
        """Handle preset selection changes"""
        self.current_preset = combo.get_active_id()
        self.update_preset_info()

    def update_preset_info(self):
        """Update preset description label"""
        desc = logic.get_preset_description(self.current_preset)
        self.preset_info_label.set_text(desc)

    def on_browse_input(self, button):
        """Open file chooser for input PDF"""
        chooser = Gtk.FileChooserDialog(
            title="Select PDF to Compress",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        # Filter for PDF only
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
            title="Save Compressed PDF As",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )

        # Set default name
        if self.input_path:
            default_name = logic.generate_default_output_name(self.input_path)
            chooser.set_current_name(os.path.basename(default_name))

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            # Ensure .pdf extension
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
        self.size_label.set_text("Size: --")
        self.status_info_label.set_text("Status: Ready")
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("")

    def on_compress(self, button):
        """Start PDF compression"""
        # Validate inputs
        is_valid, error = logic.validate_input_path(self.input_path)
        if not is_valid:
            self.show_error(error)
            return

        is_valid, error = logic.validate_output_path(self.output_path, self.input_path)
        if not is_valid:
            # Check if overwriting (allow that)
            if not os.path.exists(self.output_path):
                self.show_error(error)
                return

        # Check Ghostscript availability
        gs_available, gs_msg = logic.check_ghostscript_available()
        if not gs_available:
            self.show_error(f"Ghostscript required:\n{gs_msg}")
            return

        # Show progress
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Starting compression...")
        self.set_sensitive(False)

        # Run compression asynchronously
        GLib.idle_add(self.perform_compression)

    def perform_compression(self):
        """Perform compression in background thread"""
        # Show dialog
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text="Compressing PDF..."
        )
        dialog.format_secondary_text("Please wait...")
        dialog.show_all()

        # Perform compression
        success, error = logic.compress_pdf(
            self.input_path,
            self.output_path,
            self.current_preset
        )

        # Hide dialog
        dialog.destroy()

        if success:
            # Show success
            orig_size = logic.get_file_size_bytes(self.input_path)
            comp_size = logic.get_file_size_bytes(self.output_path)
            ratio = logic.calculate_compression_ratio(orig_size, comp_size)

            self.progress_bar.set_fraction(1.0)
            self.progress_bar.set_text(f"Complete! Reduced by {ratio:.1f}%")

            msg = (f"Compression successful!\n\n"
                   f"Original: {logic.format_file_size(orig_size)}\n"
                   f"Compressed: {logic.format_file_size(comp_size)}\n"
                   f"Reduction: {ratio:.1f}%\n\n"
                   f"Saved to:\n{self.output_path}")

            self.show_info(msg)
        else:
            self.progress_bar.set_fraction(0.0)
            self.progress_bar.set_text("Error")
            self.show_error(f"Compression failed:\n{error}")

        self.set_sensitive(True)
        return False

    def set_sensitive(self, sensitive: bool):
        """Enable/disable all controls"""
        self.input_entry.set_sensitive(sensitive)
        self.output_entry.set_sensitive(sensitive)
        self.preset_combo.set_sensitive(sensitive)

    def update_status(self, message: str):
        """Update status label"""
        self.status_info_label.set_text(f"Status: {message}")

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
    app = PDFCompressorApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    launch()