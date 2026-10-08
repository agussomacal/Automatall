import os

from gi.repository import Gtk, Adw

from .backend import DEVICE_TYPES, DEVICE_DIRECTIONS

OK = "ok"

class AddDeviceDialog(Adw.MessageDialog):
    """Maps to synclib.add_device()."""

    def __init__(self, parent, existing):
        super().__init__(transient_for=parent, modal=True,
                         heading="Add Device", body="Register a device for synchronization.")
        self.add_response("cancel", "Cancel")
        self.add_response(OK, "Add")
        self.set_response_appearance(OK, Adw.ResponseAppearance.SUGGESTED)
        self.connect("response", self._on_response)

        form = Adw.PreferencesGroup()
        self.name_entry = Adw.EntryRow(title="Device name (ex: 'usb')")
        self.path_entry = Adw.EntryRow(title="Mount path (ex: /media/user/usb)")
        self.path_chooser = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER)
        self.path_chooser.connect("clicked", self._browse)
        self.path_entry.add_suffix(self.path_chooser)

        self.type_drop = Gtk.DropDown.new_from_strings(list(DEVICE_TYPES))
        self.type_drop.set_selected(DEVICE_TYPES.index("COMPUTER"))
        type_row = Adw.ActionRow(title="Device type")
        type_row.add_suffix(self.type_drop)

        self.dir_drop = Gtk.DropDown.new_from_strings(list(DEVICE_DIRECTIONS))
        self.dir_drop.set_selected(DEVICE_DIRECTIONS.index("bidirectional"))
        dir_row = Adw.ActionRow(title="Sync direction")
        dir_row.add_suffix(self.dir_drop)

        for w in (self.name_entry, self.path_entry, type_row, dir_row):
            form.add(w)
        self.set_extra_child(form)
        self._valid = False
        self.existing = existing

        # Wire live validation
        self.name_entry.connect("changed", lambda *_: self._validate())
        self.path_entry.connect("changed", lambda *_: self._validate())
        self._validate()  # initial state

    def _browse(self, *_):
        dlg = Gtk.FileChooserNative(transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.connect("response", self._folder_chosen)
        dlg.show()

    def _folder_chosen(self, dlg, resp):
        if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
            self.path_entry.set_text(dlg.get_file().get_path())
        dlg.destroy()

    def _validate(self):
        name = self.name_entry.get_text().strip()
        path = self.path_entry.get_text().strip()
        ok = name and path not in ("", "/") and os.path.exists(path) and name not in self.existing
        self.set_response_enabled(OK, ok)

    def _on_response(self, dlg, response):
        if response == OK:
            self._valid = True

    def get_values(self):
        return {
            "device_name": self.name_entry.get_text().strip(),
            "mount_path": self.path_entry.get_text().strip(),
            "device_type": DEVICE_TYPES[self.type_drop.get_selected()],
            "device_direction": DEVICE_DIRECTIONS[self.dir_drop.get_selected()],
        }

class AddFolderDialog(Adw.MessageDialog):
    """Maps to cmd_frontend.add_folder / synclib.add_tracking_to_folder."""

    def __init__(self, parent, device_name, config):
        super().__init__(transient_for=parent, modal=True,
                         heading=f"Add Folder to '{device_name}'")
        self.add_response("cancel", "Cancel")
        self.add_response(OK, "Add")
        self.set_response_appearance(OK, Adw.ResponseAppearance.SUGGESTED)

        self.device_name = device_name

        form = Adw.PreferencesGroup()
        self.path_entry = Adw.EntryRow(title="Absolute path to folder")
        browse = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER)
        browse.connect("clicked", self._browse)
        self.path_entry.add_suffix(browse)

        self.dir_drop = Gtk.DropDown.new_from_strings(list(DEVICE_DIRECTIONS))
        self.dir_drop.set_selected(DEVICE_DIRECTIONS.index("bidirectional"))
        dir_row = Adw.ActionRow(title="Sync direction")
        dir_row.add_suffix(self.dir_drop)

        self.append_entry = Adw.EntryRow(title="Append strategy file endings (space-separated, ex: 'txt md')")
        self.only_entry = Adw.EntryRow(title="Only file endings (optional, space-separated)")
        self.ignfe_entry = Adw.EntryRow(title="Ignored file endings (space-separated)")
        self.ignored_entry = Adw.EntryRow(title="Ignored paths (space-separated, ex: '.git logseq/bak')")

        for w in (self.path_entry, dir_row, self.append_entry,
                  self.only_entry, self.ignfe_entry, self.ignored_entry):
            form.add(w)
        self.set_extra_child(form)

        self.path_entry.connect("changed", lambda *_:
        self.set_response_enabled(OK, bool(self.path_entry.get_text().strip())))

    def _browse(self, *_):
        dlg = Gtk.FileChooserNative(transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.connect("response", self._folder_chosen)
        dlg.show()

    def _folder_chosen(self, dlg, resp):
        if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
            self.path_entry.set_text(dlg.get_file().get_path())
        dlg.destroy()

    def _split(self, entry):
        return [t for t in entry.get_text().strip().split(" ") if t]

    def get_values(self):
        return {
            "device_name": self.device_name,
            "path": self.path_entry.get_text().strip(),
            "direction": DEVICE_DIRECTIONS[self.dir_drop.get_selected()],
            "append_strategy_to_file_endings": self._split(self.append_entry),
            "folder_settings": {
                "only_file_endings": self._split(self.only_entry),
                "ignored_file_endings": self._split(self.ignfe_entry),
                "ignored": self._split(self.ignored_entry),
                "not_ignored": [],
            },
        }