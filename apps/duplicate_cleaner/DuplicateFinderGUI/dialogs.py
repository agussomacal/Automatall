"""Dialogs for Duplicate Finder."""

import os
from gi.repository import Gtk, Adw, Gio


class ScanOptionsDialog(Adw.MessageDialog):
    """Dialog to configure scan options."""

    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True,
                         heading="Scan Options",
                         body="Configure how to scan for duplicates")
        self.add_response("cancel", "Cancel")
        self.add_response("ok", "Scan")
        self.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        form = Adw.PreferencesGroup()

        # Recursive scan option
        self.recursive_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.recursive_switch.set_active(False)
        recursive_row = Adw.ActionRow(title="Scan subdirectories recursively")
        recursive_row.add_suffix(self.recursive_switch)
        form.add(recursive_row)

        # Min file size filter
        self.min_size_entry = Adw.EntryRow(
            title="Minimum file size (bytes)",
            text="0"
        )
        form.add(self.min_size_entry)

        # File extensions filter
        self.extensions_entry = Adw.EntryRow(
            title="Include only these extensions (comma-separated, leave empty for all)",
            text=""
        )
        form.add(self.extensions_entry)

        self.set_extra_child(form)

    def get_values(self):
        min_text = self.min_size_entry.get_text().strip()
        min_size = int(min_text) if min_text.isdigit() else 0

        ext_text = self.extensions_entry.get_text().strip()
        extensions = []
        if ext_text:
            extensions = [ext.strip().lower() for ext in ext_text.split(",")]

        return {
            "recursive": self.recursive_switch.get_active(),
            "min_size": min_size,
            "extensions": extensions,
        }