import threading

from gi.repository import Gtk, GLib, Gdk, Gio

from .backend import MODE_DIFF, MODE_SYNC
from .dialogs import AddDeviceDialog, AddFolderDialog, OK

APP_NAME = "NoServerSync"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title=APP_NAME, default_width=1100, default_height=700, **kwargs)
        self._selected_device = None
        self._selected_folder = None
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        header = Gtk.HeaderBar()

        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu.append("Quit", "app.quit")

        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin_top=6,
                      margin_bottom=6, margin_start=6, margin_end=6)
        top.set_vexpand(False)

        dev_frame, self.devices_list = self._section("Devices", on_add=self.on_add_device)
        fold_frame, self.folders_list = self._section("Folders", on_add=self.on_add_folder)

        self.detail_stack = Gtk.Stack(vexpand=True)
        self.detail_stack.add_named(self._placeholder_label("Select a folder"), "empty")
        self.detail_stack.add_named(self._build_folder_detail(), "detail")
        self.detail_stack.set_visible_child_name("empty")

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        paned.set_position(240)
        paned.set_start_child(dev_frame)
        inner_paned = Gtk.Paned(wide_handle=True)
        inner_paned.set_position(280)
        inner_paned.set_start_child(fold_frame)
        inner_paned.set_end_child(self.detail_stack)
        paned.set_end_child(inner_paned)

        log_frame = Gtk.Frame(margin_start=6, margin_end=6, margin_bottom=6)
        log_scroller = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                          height_request=120)
        self.log_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, editable=False,
                                     css_classes=["log"])
        log_scroller.set_child(self.log_view)
        log_frame.set_child(log_scroller)

        top.append(paned)
        box.append(header)
        box.append(top)
        box.append(log_frame)
        self.set_child(box)

    def _section(self, title, on_add):
        frame = Gtk.Frame(margin_start=6, margin_top=6, margin_bottom=6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=4)

        header = Gtk.Box(spacing=6, margin_start=6, margin_end=6, margin_bottom=2)
        header.append(Gtk.Label(label=title, halign=Gtk.Align.START, hexpand=True,
                                css_classes=["heading"]))
        add_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=f"Add {title.lower()}")
        add_btn.connect("clicked", lambda *_: on_add())
        header.append(add_btn)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        lst = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        lst.connect("row-selected", self.on_section_selected, title)
        scroller.set_child(lst)

        vbox.append(header)
        vbox.append(scroller)
        frame.set_child(vbox)
        return frame, lst

    def _build_folder_detail(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                        margin_top=12, margin_start=12, margin_end=12)

        self.detail_title = Gtk.Label(css_classes=["title-2"], halign=Gtk.Align.START)
        self.detail_subtitle = Gtk.Label(halign=Gtk.Align.START, css_classes=["dim-label"])
        outer.append(self.detail_title)
        outer.append(self.detail_subtitle)

        self.class_grid = Gtk.Grid(column_spacing=24, row_spacing=6, margin_top=6,
                                   margin_bottom=6)
        outer.append(self.class_grid)

        self.file_scroller = Gtk.ScrolledWindow(vexpand=True)
        self.file_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.NONE, editable=False,
                                      css_classes=["file-table", "log"])
        self.file_scroller.set_child(self.file_view)
        outer.append(self.file_scroller)

        btn_box = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_bottom=4)
        self.btn_preview = Gtk.Button(label="Preview (diff)")
        self.btn_preview.connect("clicked", lambda *_: self.run_sync(MODE_DIFF))
        self.btn_sync = Gtk.Button(label="Sync", css_classes=["suggested-action"])
        self.btn_sync.connect("clicked", lambda *_: self.run_sync(MODE_SYNC))
        btn_box.append(self.btn_preview)
        btn_box.append(self.btn_sync)
        outer.append(btn_box)

        spinner_row = Gtk.Box(spacing=8)
        self.spinner = Gtk.Spinner(spinning=False)
        self.status_lbl = Gtk.Label(css_classes=["dim-label"])
        spinner_row.append(self.spinner)
        spinner_row.append(self.status_lbl)
        outer.append(spinner_row)

        return outer

    def _placeholder_label(self, text):
        lbl = Gtk.Label(label=text, css_classes=["dim-label"], margin_top=24)
        return lbl

    def refresh_all(self):
        print(f"[MAIN_WINDOW] refresh_all() - Devices: {list(self.get_config()['devices'].keys())}")
        self.refresh_devices()
        self.refresh_folders()

    def refresh_devices(self):
        from . import backend
        rows = backend.list_devices(self.get_config())
        print(f"[MAIN_WINDOW] refresh_devices() - Showing {len(rows)} devices")
        self._fill_list_devices(self.devices_list, rows)

    def refresh_folders(self):
        from . import backend
        devices = backend.list_devices(self.get_config())
        names = [d["name"] for d in devices]
        rows = backend.list_folders(self.get_config(), names)
        print(f"[MAIN_WINDOW] refresh_folders() - Showing {len(rows)} folders")
        self._fill_list_folders(self.folders_list, rows)

    # ============================================================
    # Device list WITH icons
    # ============================================================
    def _fill_list_devices(self, listbox, rows):
        self._clear_listbox(listbox)
        for row_data in rows:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          margin_top=6, margin_bottom=6)
            line = Gtk.Box(spacing=6)

            # Choose icon based on device type
            device_type = row_data.get("type", "COMPUTER")
            connected = row_data.get("connected", False)

            if device_type == "COMPUTER":
                icon_name = "computer-symbolic"
            elif device_type == "USB":
                icon_name = "media-removable-symbolic"
            elif device_type == "DRIVE":
                icon_name = "drive-harddisk-symbolic"
            elif device_type in ("PHONE", "IPAD"):
                icon_name = "phone-symbolic"
            else:
                icon_name = "computer-symbolic"

            icon = Gtk.Image(icon_name=icon_name)
            if not connected:
                icon.set_opacity(0.4)

            label = Gtk.Label(label=row_data["name"], halign=Gtk.Align.START)
            sub = Gtk.Label(label=row_data["subtitle"], halign=Gtk.Align.START,
                            css_classes=["caption", "dim-label"])
            line.append(icon)
            line.append(label)

            # Show MAIN badge if this is the main device
            if row_data.get("is_main"):
                main_badge = Gtk.Label(label="MAIN", css_classes=["accent", "success"],
                                       halign=Gtk.Align.END, hexpand=True)
                line.append(main_badge)
            elif "badge" in row_data and row_data["badge"]:
                badge = Gtk.Label(label=row_data["badge"],
                                  css_classes=["success"], halign=Gtk.Align.END, hexpand=True)
                line.append(badge)

            box.append(line)
            box.append(sub)
            row = Gtk.ListBoxRow(child=box)
            row.row_data = row_data
            listbox.append(row)

    # ============================================================
    # Folder list WITHOUT icons
    # ============================================================
    def _fill_list_folders(self, listbox, rows):
        self._clear_listbox(listbox)
        for row_data in rows:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          margin_top=6, margin_bottom=6)
            line = Gtk.Box(spacing=6)

            # NO ICON for folders - just text
            label = Gtk.Label(label=row_data["name"], halign=Gtk.Align.START,
                              css_classes=["heading"])
            sub = Gtk.Label(label=row_data["subtitle"], halign=Gtk.Align.START,
                            css_classes=["caption", "dim-label"])

            line.append(label)

            # Show sync status badge on the right
            if row_data.get("badge"):
                badge = Gtk.Label(label=row_data["badge"],
                                  css_classes=["success"], halign=Gtk.Align.END, hexpand=True)
                line.append(badge)

            box.append(line)
            box.append(sub)
            row = Gtk.ListBoxRow(child=box)
            row.row_data = row_data
            listbox.append(row)

    @staticmethod
    def _clear_listbox(listbox):
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

    def get_config(self):
        """Get config from application (NO reloading from disk)."""
        app = self.get_application()
        if hasattr(app, 'config') and app.config is not None:
            return app.config
        # Fallback: reload from disk
        print("[MAIN_WINDOW] WARNING: Using fallback config reload")
        from . import backend
        return backend.load_config()

    def on_section_selected(self, listbox, row, which):
        if row is None:
            return
        data = row.row_data
        if which == "Devices":
            self._selected_device = data["name"]
            print(f"[MAIN_WINDOW] Selected device: {self._selected_device}")
            self.refresh_folders()
        else:
            self._selected_folder = data["name"]
            print(f"[MAIN_WINDOW] Selected folder: {self._selected_folder}")
            self.show_folder_detail(data)

    def show_folder_detail(self, row_data):
        self.detail_title.set_text(row_data["name"])
        self.detail_subtitle.set_text(row_data["subtitle"])

        # Clear existing grid
        for child in list(self.class_grid):
            self.class_grid.remove(child)

        detail = row_data.get("detail", {})

        # NEW: Handle single vs multi-device display
        if "devices" in detail:
            devices_str = detail["devices"]
            self.class_grid.attach(Gtk.Label(label="DEVICES", halign=Gtk.Align.START,
                                             css_classes=["caption", "dim-label"]), 0, 0, 1, 1)
            self.class_grid.attach(Gtk.Label(label=devices_str, halign=Gtk.Align.START), 0, 1, 1, 1)

            if "direction" in detail:
                self.class_grid.attach(Gtk.Label(label="DIRECTION", halign=Gtk.Align.START,
                                                 css_classes=["caption", "dim-label"]), 1, 0, 1, 1)
                self.class_grid.attach(Gtk.Label(label=detail["direction"], halign=Gtk.Align.START), 1, 1, 1, 1)
        else:
            # Legacy single-device format
            for col, (key, value) in enumerate(detail.items()):
                self.class_grid.attach(Gtk.Label(label=key.upper(), halign=Gtk.Align.START,
                                                 css_classes=["caption", "dim-label"]), col, 0, 1, 1)
                self.class_grid.attach(Gtk.Label(label=str(value), halign=Gtk.Align.START), col, 1, 1, 1)

        self.detail_stack.set_visible_child_name("detail")

    def on_add_device(self):
        from . import backend
        existing = [d["name"] for d in backend.list_devices(self.get_config())]
        print(f"[MAIN_WINDOW] on_add_device - Existing devices: {existing}")
        dlg = AddDeviceDialog(self, existing=existing)
        dlg.connect("response", self.on_add_device_response)
        dlg.present()

    def on_add_device_response(self, dlg, response):
        from . import backend
        print(f"[MAIN_WINDOW] on_add_device_response - Response: {response}")
        if response == OK:
            values = dlg.get_values()
            print(f"[MAIN_WINDOW] Adding device with values: {values}")

            # Get CURRENT config from app (not from disk)
            config = self.get_config()
            print(f"[MAIN_WINDOW] Current config devices: {list(config['devices'].keys())}")

            msg, config = backend.add_device(config, **values)
            print(f"[MAIN_WINDOW] add_device returned: {msg}, new devices: {list(config['devices'].keys())}")

            self.log(msg)

            # Update app's config
            self.get_application().update_config(config)
            print(f"[MAIN_WINDOW] Updated app config, now refreshing...")

            self.refresh_all()
        dlg.destroy()

    def on_add_folder(self):
        from . import backend
        if not self._selected_device:
            self.log("Select a device first, then add a folder to it.")
            return
        dlg = AddFolderDialog(self, device_name=self._selected_device,
                              config=self.get_config())
        dlg.connect("response", self.on_add_folder_response)
        dlg.present()

    def on_add_folder_response(self, dlg, response):
        from . import backend
        print(f"[MAIN_WINDOW] on_add_folder_response - Response: {response}")
        if response == OK:
            values = dlg.get_values()
            print(f"[MAIN_WINDOW] Adding folder with values: {values}")

            # Get CURRENT config from app (not from disk)
            config = self.get_config()
            print(f"[MAIN_WINDOW] Current config devices: {list(config['devices'].keys())}")

            msg, config = backend.add_folder(config, **values)
            print(f"[MAIN_WINDOW] add_folder returned: {msg}")

            self.log(msg)

            # Update app's config
            self.get_application().update_config(config)
            print(f"[MAIN_WINDOW] Updated app config, now refreshing...")

            self.refresh_all()
        dlg.destroy()

    def run_sync(self, mode):
        from . import backend
        if not self._selected_folder:
            self.log("No folder selected.")
            return

        # NEW: Check if main device is set
        config = self.get_config()
        main_device = backend.get_main_device(config)
        if not main_device:
            self.log("ERROR: No main device configured. Add a device and set it as 'main' first.")
            # Show error dialog
            err_dialog = Adw.MessageDialog(
                transient_for=self,
                heading="No Main Device",
                body="You must set a main device before syncing. Click 'Add Device' and enable 'Set as main device'."
            )
            err_dialog.add_response("ok", "OK")
            err_dialog.present()
            return

        folder = self._selected_folder
        self.btn_sync.set_sensitive(False)
        self.btn_preview.set_sensitive(False)
        self.spinner.start()
        self.status_lbl.set_text("Scanning…" if mode == MODE_DIFF else "Synchronizing…")

        def worker():
            report, config, error = backend.run_sync_report(self.get_config(), mode, folder,
                                                            log_callback=self.log_from_thread)
            GLib.idle_add(self._sync_finished, report, config, error)

        threading.Thread(target=worker, daemon=True).start()

    def _sync_finished(self, report, config, error):
        self.spinner.stop()
        self.btn_sync.set_sensitive(True)
        self.btn_preview.set_sensitive(True)
        self.status_lbl.set_text("")

        if error:
            self.log(f"Error: {error}")
        else:
            # Update application config
            self.get_application().update_config(config)
            self._render_report(report)
        return GLib.SOURCE_REMOVE

    def _render_report(self, report):
        buf = self.file_view.get_buffer()
        buf.set_text("")
        for category, files in report.items():
            if files:
                buf.insert_markup(buf.get_end_iter(),
                                  f"<b>{category}</b>\n{'-' * 40}\n", -1)
                for i, f in enumerate(files):
                    buf.insert(buf.get_end_iter(), f"  ({i}) {f}\n")
                buf.insert(buf.get_end_iter(), "\n")

    def log(self, message):
        buf = self.log_view.get_buffer()
        buf.insert_markup(buf.get_end_iter(), f"[INFO] {GLib.markup_escape_text(str(message))}\n", -1)

    def log_from_thread(self, message):
        GLib.idle_add(self.log, message)
