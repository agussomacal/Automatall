import os

from NoServerSync.synclib import CONFIG_DEVICES_KEY_NAME
from gi.overrides.Gio import Gio
from gi.repository import Gtk, Adw

from .backend import DEVICE_TYPES, DEVICE_DIRECTIONS

OK = "ok"


class AddDeviceDialog(Adw.MessageDialog):
    """Maps to synclib.add_device()."""

    def __init__(self, parent, existing):
        super().__init__(transient_for=parent, modal=True,
                         heading="Add Device", body="Register a device for synchronization.")
        self.add_response("cancel", "Cancel")
        self.add_response("ok", "Add")
        self.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
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

        # NEW: Main device checkbox
        self.main_checkbox = Adw.ActionRow(title="Set as main device")
        self.main_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.main_switch.set_active(False)  # Default: not main
        self.main_checkbox.add_suffix(self.main_switch)

        for w in (self.name_entry, self.path_entry, type_row, dir_row, self.main_checkbox):
            form.add(w)
        self.set_extra_child(form)

        self._valid = False
        self.existing = existing

        # Wire live validation
        self.name_entry.connect("changed", lambda *_: self._validate())
        self.path_entry.connect("changed", lambda *_: self._validate())
        self._validate()

    def _on_response(self, dlg, response):
        if response == OK:
            self._valid = True

    def _validate(self):
        name = self.name_entry.get_text().strip()
        path = self.path_entry.get_text().strip()
        ok = name and path not in ("", "/") and os.path.exists(path) and name not in self.existing
        self.set_response_enabled(OK, ok)

    def get_values(self):
        return {
            "device_name": self.name_entry.get_text().strip(),
            "mount_path": self.path_entry.get_text().strip(),
            "device_type": DEVICE_TYPES[self.type_drop.get_selected()],
            "device_direction": DEVICE_DIRECTIONS[self.dir_drop.get_selected()],
            "set_as_main": self.main_switch.get_active(),  # NEW: Return checkbox state
        }

    def _browse(self, *_):
        dlg = Gtk.FileChooserNative(transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.connect("response", self._folder_chosen)
        dlg.show()

    def _folder_chosen(self, dlg, resp):
        if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
            self.path_entry.set_text(dlg.get_file().get_path())
        dlg.destroy()


class AddFolderDialog(Adw.MessageDialog):
    """Maps to cmd_frontend.add_folder / synclib.add_tracking_to_folder."""

    def __init__(self, parent, device_name, config):
        try:
            device_config = config[CONFIG_DEVICES_KEY_NAME][device_name]
            base_path = device_config["path"]
        except Exception as e:
            print(f"[DIALOGS] Error getting device path: {e}")
            base_path = "/"

        super().__init__(transient_for=parent, modal=True,
                         heading=f"Add Folder to '{device_name}'",
                         body="Select a folder within this device's mount path.")
        self.add_response("cancel", "Cancel")
        self.add_response("ok", "Add")
        self.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        self.device_name = device_name
        self.base_path = base_path

        form = Adw.PreferencesGroup()

        self.path_entry = Adw.EntryRow(
            title="Absolute path to folder",
            text=base_path
        )

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

        # REMOVED: Icon dropdown
        for w in (self.path_entry, dir_row, self.append_entry,
                  self.only_entry, self.ignfe_entry, self.ignored_entry):
            form.add(w)
        self.set_extra_child(form)

        self.path_entry.connect("changed", lambda *_: self._validate())
        self._validate()

    def _browse(self, *_):
        dlg = Gtk.FileChooserNative(
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            title="Select Folder",
            accept_label="Select",
            cancel_label="Cancel"
        )

        if os.path.exists(self.base_path):
            try:
                file = Gio.File.new_for_path(self.base_path)
                dlg.set_current_folder(file, None)
            except:
                pass

        dlg.connect("response", self._folder_chosen)
        dlg.show()

    def _folder_chosen(self, dlg, resp):
        if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
            selected_path = dlg.get_file().get_path()

            if not selected_path.startswith(self.base_path):
                err_dlg = Adw.MessageDialog(
                    transient_for=self,
                    heading="Invalid Path",
                    body=f"This folder must be within the device's mount path:\n\n{self.base_path}\n\nSelected: {selected_path}"
                )
                err_dlg.add_response("ok", "OK")
                err_dlg.present()
                dlg.destroy()
                return

            self.path_entry.set_text(selected_path)

        dlg.destroy()

    def _split(self, entry):
        return [t for t in entry.get_text().strip().split(" ") if t]

    def _validate(self):
        path = self.path_entry.get_text().strip()

        if not path:
            self.set_response_enabled("ok", False)
            return

        if not os.path.exists(path):
            self.set_response_enabled("ok", False)
            return

        if not os.path.isdir(path):
            self.set_response_enabled("ok", False)
            return

        try:
            real_base = os.path.realpath(self.base_path)
            real_path = os.path.realpath(path)

            if not real_path.startswith(real_base + os.sep) and real_path != real_base:
                self.set_response_enabled("ok", False)
                return
        except Exception as e:
            print(f"[DIALOGS] Validation error: {e}")
            self.set_response_enabled("ok", False)
            return

        self.set_response_enabled("ok", True)

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
