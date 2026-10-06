#!/usr/bin/env python3
"""App Generator Application - Creates new app templates"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import os
import threading
from pathlib import Path
import logic

class AppGeneratorApp(Gtk.Window):
    """App template generator - creates new modular apps"""

    def __init__(self):
        super().__init__(title="App Generator")
        self.set_default_size(500, 600)
        self.set_border_width(15)

        # Store user inputs
        self.app_name = ""
        self.description = ""
        self.category = ""
        self.tags = []
        self.icon_url = ""
        self.apps_base_dir = ""

        # Determine apps directory
        script_dir = Path(__file__).parent.resolve().parent.resolve()
        self.apps_base_dir = str(script_dir)

        # Main layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.set_spacing(12)
        main_vbox.set_margin_start(15)
        main_vbox.set_margin_end(15)
        main_vbox.set_margin_top(15)
        main_vbox.set_margin_bottom(15)

        # === HEADER ===
        header_label = Gtk.Label()
        header_label.set_markup('<span size="x-large" weight="bold">✨ Create New App ✨</span>')
        header_label.set_halign(Gtk.Align.CENTER)
        main_vbox.pack_start(header_label, False, False, 5)

        # === APP NAME ===
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        name_box.set_spacing(10)

        name_label = Gtk.Label(label="<b>App Name</b>:")
        name_label.set_use_markup(True)
        name_label.set_width_chars(12)
        name_label.set_halign(Gtk.Align.END)
        name_box.pack_start(name_label, False, False, 0)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("e.g., PDF Compressor")
        self.name_entry.set_hexpand(True)
        self.name_entry.connect("changed", self.on_name_changed)
        name_box.pack_start(self.name_entry, True, True, 0)

        main_vbox.pack_start(name_box, False, False, 5)

        # Name preview
        self.preview_label = Gtk.Label()
        self.preview_label.set_halign(Gtk.Align.START)
        self.preview_label.set_markup('<span size="small">Normalized: --</span>')
        main_vbox.pack_start(self.preview_label, False, False, 0)

        # === DESCRIPTION ===
        desc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        desc_box.set_spacing(10)

        desc_label = Gtk.Label(label="<b>Description</b>:")
        desc_label.set_use_markup(True)
        desc_label.set_width_chars(12)
        desc_label.set_halign(Gtk.Align.END)
        desc_box.pack_start(desc_label, False, False, 0)

        self.desc_entry = Gtk.Entry()
        self.desc_entry.set_placeholder_text("Brief description of your app")
        self.desc_entry.set_hexpand(True)
        self.desc_entry.connect("changed", self.on_desc_changed)
        desc_box.pack_start(self.desc_entry, True, True, 0)

        main_vbox.pack_start(desc_box, False, False, 5)

        # Description hint
        self.desc_hint_label = Gtk.Label()
        self.desc_hint_label.set_halign(Gtk.Align.START)
        self.desc_hint_label.set_markup('<span size="small">Required • Max 500 characters</span>')
        main_vbox.pack_start(self.desc_hint_label, False, False, 0)

        # === CATEGORY ===
        cat_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cat_box.set_spacing(10)

        cat_label = Gtk.Label(label="<b>Category</b>:")
        cat_label.set_use_markup(True)
        cat_label.set_width_chars(12)
        cat_label.set_halign(Gtk.Align.END)
        cat_box.pack_start(cat_label, False, False, 0)

        self.cat_entry = Gtk.Entry()
        self.cat_entry.set_placeholder_text("e.g., media, files, tools, examples...")
        self.cat_entry.set_hexpand(True)
        self.cat_entry.connect("changed", self.on_cat_changed)
        cat_box.pack_start(self.cat_entry, True, True, 0)

        main_vbox.pack_start(cat_box, False, False, 5)

        # === TAGS ===
        tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tags_box.set_spacing(10)

        tags_label = Gtk.Label(label="<b>Tags</b>:")
        tags_label.set_use_markup(True)
        tags_label.set_width_chars(12)
        tags_label.set_halign(Gtk.Align.END)
        tags_box.pack_start(tags_label, False, False, 0)

        self.tags_entry = Gtk.Entry()
        self.tags_entry.set_placeholder_text("comma, separated, tags (optional)")
        self.tags_entry.set_hexpand(True)
        tags_box.pack_start(self.tags_entry, True, True, 0)

        main_vbox.pack_start(tags_box, False, False, 5)

        # === ICON URL (Optional) ===
        icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        icon_box.set_spacing(10)

        icon_label = Gtk.Label(label="<b>Icon URL</b>:")
        icon_label.set_use_markup(True)
        icon_label.set_width_chars(12)
        icon_label.set_halign(Gtk.Align.END)
        icon_box.pack_start(icon_label, False, False, 0)

        self.icon_entry = Gtk.Entry()
        self.icon_entry.set_placeholder_text("https://example.com/icon.png (optional)")
        self.icon_entry.set_hexpand(True)
        icon_box.pack_start(self.icon_entry, True, True, 0)

        main_vbox.pack_start(icon_box, False, False, 5)

        # === INFO BOX ===
        info_frame = Gtk.Frame(label="App Structure")
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
            "Generated structure:\n"
            "<tt>apps/app_name/</tt>\n"
            "├── config.yaml ✓ (filled)\n"
            "├── dependencies.yaml ⚪ (placeholder)\n"
            "├── __init__.py ⚪ (placeholder)\n"
            "├── logic.py ⚪ (placeholder)\n"
            "├── app.py ⚪ (placeholder)\n"
            "├── icon.png ✓\n"
            "└── tests/\n"
            "    └── test_app_name.py ⚪ (placeholder)"
        )
        info_text.set_halign(Gtk.Align.START)
        info_text.set_line_wrap(True)
        info_box.pack_start(info_text, False, False, 0)

        info_frame.add(info_box)
        main_vbox.pack_start(info_frame, False, False, 5)

        # === PROGRESS ===
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_visible(False)
        main_vbox.pack_start(self.progress_bar, False, False, 5)

        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_markup('<span foreground="#666">Ready to create</span>')
        main_vbox.pack_start(self.status_label, False, False, 5)

        # === BUTTONS ===
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_spacing(10)
        button_box.set_halign(Gtk.Align.END)

        reset_btn = Gtk.Button(label="Clear")
        reset_btn.connect("clicked", self.on_reset)
        button_box.pack_start(reset_btn, False, False, 0)

        generate_btn = Gtk.Button(label="🚀 Generate App")
        generate_btn.get_style_context().add_class("suggested-action")
        generate_btn.connect("clicked", self.on_generate)
        button_box.pack_start(generate_btn, False, False, 0)

        main_vbox.pack_start(button_box, False, False, 0)

        self.add(main_vbox)

        self.update_preview()

    def on_name_changed(self, entry):
        """Update name preview as user types"""
        self.update_preview()

    def on_desc_changed(self, entry):
        """Update description validation hint"""
        desc = entry.get_text()
        if len(desc) > 480:
            remaining = 500 - len(desc)
            self.desc_hint_label.set_markup(
                f'<span foreground="#e74c3c">{remaining} characters remaining</span>'
            )
        else:
            self.desc_hint_label.set_markup('<span size="small">Required • Max 500 characters</span>')

    def update_preview(self):
        """Show normalized app name"""
        raw_name = self.name_entry.get_text()
        is_valid, result = logic.validate_app_name(raw_name)

        if is_valid:
            self.preview_label.set_markup(
                f'<span foreground="#2ecc71">Normalized: <b>{result}</b></span>'
            )
            self.app_name = result
        else:
            self.preview_label.set_markup(
                f'<span foreground="#e74c3c">{result}</span>'
            )
            self.app_name = ""

    def on_cat_changed(self, entry):
        """Update category"""
        self.category = entry.get_text().strip()

    def on_reset(self, button):
        """Reset all fields"""
        self.name_entry.set_text("")
        self.desc_entry.set_text("")
        self.cat_entry.set_text("")
        self.tags_entry.set_text("")
        self.icon_entry.set_text("")
        self.app_name = ""
        self.description = ""
        self.category = ""
        self.tags = []
        self.icon_url = ""
        self.update_preview()
        self.status_label.set_markup('<span foreground="#666">Ready to create</span>')
        self.progress_bar.set_visible(False)

    def on_generate(self, button):
        """Start app generation"""
        # Validate all inputs
        is_valid, result = logic.validate_app_name(self.name_entry.get_text())
        if not is_valid:
            self.show_error(result)
            return
        self.app_name = result

        is_valid, result = logic.validate_description(self.desc_entry.get_text())
        if not is_valid:
            self.show_error(result)
            return
        self.description = result

        is_valid, result = logic.validate_category(self.category)
        if not is_valid:
            self.show_error(result)
            return
        self.category = result

        self.tags = logic.parse_tags(self.tags_entry.get_text())

        self.icon_url = self.icon_entry.get_text().strip()
        if self.icon_url:
            is_valid, msg, _ = logic.validate_icon_url(self.icon_url)
            if not is_valid:
                self.show_error(msg)
                return

        # Disable controls
        self.set_sensitive(False)
        self.progress_bar.set_visible(True)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Generating...")
        self.status_label.set_markup('<span foreground="#3498db">Creating app template...</span>')

        # Run in thread to keep UI responsive
        thread = threading.Thread(target=self.do_generate)
        thread.daemon = True
        thread.start()

    def do_generate(self):
        """Perform generation in background thread"""
        try:
            success, message, app_path = logic.create_app_structure(
                self.apps_base_dir,
                self.app_name,
                self.description,
                self.category,
                self.tags,
                self.icon_url if self.icon_url else None
            )

            # Update UI in main thread
            GLib.idle_add(self.on_generation_complete, success, message, app_path)

        except Exception as e:
            GLib.idle_add(self.on_generation_complete, False, str(e), "")

    def on_generation_complete(self, success: bool, message: str, app_path: str):
        """Handle generation completion"""
        self.progress_bar.set_visible(False)
        self.set_sensitive(True)

        if success:
            self.status_label.set_markup('<span foreground="#2ecc71">✓ ' + message + '</span>')

            # Show success dialog with link to app
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="App Created Successfully!"
            )
            dialog.format_secondary_text(f"Location:\n{app_path}\n\nRefresh the main hub to see your new app.")
            dialog.run()
            dialog.destroy()

            # Reset form
            self.on_reset(None)
        else:
            self.status_label.set_markup('<span foreground="#e74c3c">✗ ' + message + '</span>')
            self.show_error(message)

    def set_sensitive(self, sensitive: bool):
        """Enable/disable controls"""
        self.name_entry.set_sensitive(sensitive)
        self.desc_entry.set_sensitive(sensitive)
        self.cat_entry.set_sensitive(sensitive)
        self.tags_entry.set_sensitive(sensitive)
        self.icon_entry.set_sensitive(sensitive)

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

def launch():
    """Entry point called by main.py"""
    app = AppGeneratorApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    launch()