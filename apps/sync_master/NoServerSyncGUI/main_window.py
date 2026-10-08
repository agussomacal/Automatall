import threading

from gi.repository import Gtk, GLib, Gdk, Gio, Adw

from .backend import MODE_DIFF, MODE_SYNC
from .dialogs import AddDeviceDialog, AddFolderDialog

APP_NAME = "NoServerSync"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title=APP_NAME, default_width=1400, default_height=800, **kwargs)
        self._selected_device = None
        self._selected_folder = None
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        # Main vertical box - ONE container only
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # HeaderBar (replaces the duplicated header)
        header = Gtk.HeaderBar()

        # Menu button on right
        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        # Set title in header
        title_label = Gtk.Label(label=APP_NAME, css_classes=["title"])
        header.set_title_widget(title_label)

        main_box.append(header)

        # ==================== TOP PANEL: DEVICES (full width) ====================
        devices_panel = self._build_devices_panel()
        main_box.append(devices_panel)

        # ==================== MIDDLE PANEL: 3 COLUMNS ====================
        middle_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        middle_paned.set_position(280)  # Left column width

        # Column 1: Folders list
        folders_column = self._build_folders_panel()
        middle_paned.set_start_child(folders_column)

        # Column 2: Folder details
        details_column = self._build_details_panel()

        # Inner paned for columns 2 and 3
        inner_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        inner_paned.set_position(500)  # Details column width
        inner_paned.set_start_child(details_column)

        # Column 3: Sync activity
        sync_column = self._build_sync_panel()
        inner_paned.set_end_child(sync_column)

        middle_paned.set_end_child(inner_paned)
        main_box.append(middle_paned)

        self.set_child(main_box)

    # ============================================================
    # Devices Panel (Full Width)
    # ============================================================
    def _build_devices_panel(self):
        """Devices list spanning full window width."""
        frame = Gtk.Frame(margin_start=12, margin_end=12, margin_top=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)

        # Header row - FIXED: use Gtk.Box() instead of Gtk.Widget()
        header_row = Gtk.Box(spacing=12)
        header_row.append(Gtk.Label(label="Devices", css_classes=["title-3"]))
        # Create a flexible spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_row.append(spacer)
        add_btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text="Add Device")
        add_btn.connect("clicked", lambda *_: self.on_add_device())
        header_row.append(add_btn)
        vbox.append(header_row)

        # Listbox
        scroller = Gtk.ScrolledWindow(vexpand=True, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=150)
        self.devices_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                        css_classes=["boxed-list"])
        self.devices_list.connect("row-selected", self.on_device_selected)
        scroller.set_child(self.devices_list)
        vbox.append(scroller)

        frame.set_child(vbox)
        return frame

    def _build_folders_panel(self):
        """Folders list in left column."""
        frame = Gtk.Frame(margin_start=12, margin_end=6, margin_top=12, margin_bottom=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)

        # Header row - FIXED
        header_row = Gtk.Box(spacing=12)
        header_row.append(Gtk.Label(label="Folders", css_classes=["title-3"]))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_row.append(spacer)
        add_btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text="Add Folder")
        add_btn.connect("clicked", lambda *_: self.on_add_folder())
        header_row.append(add_btn)
        vbox.append(header_row)

        # Listbox
        scroller = Gtk.ScrolledWindow(vexpand=True, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=300)
        self.folders_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                        css_classes=["boxed-list"])
        self.folders_list.connect("row-selected", self.on_folder_selected)
        scroller.set_child(self.folders_list)
        vbox.append(scroller)

        frame.set_child(vbox)
        return frame

    # ============================================================
    # Details Panel (Center Column - 1/3)
    # ============================================================
    def _build_details_panel(self):
        """Selected folder details in center column."""
        frame = Gtk.Frame(margin_start=6, margin_end=6, margin_top=12, margin_bottom=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)

        # Placeholder when no folder selected
        self.empty_placeholder = Gtk.Label(
            label="Select a folder to see details",
            css_classes=["dim-label"],
            margin_top=60
        )
        vbox.append(self.empty_placeholder)

        # Details stack (hidden initially)
        self.details_stack = Gtk.Stack(visible=False)

        # Title
        self.detail_title = Gtk.Label(css_classes=["title-3"], halign=Gtk.Align.START)
        self.detail_subtitle = Gtk.Label(halign=Gtk.Align.START, css_classes=["dim-label"])
        self.details_stack.add_titled(self.detail_title, "title", "")
        vbox.append(self.detail_title)
        vbox.append(self.detail_subtitle)

        # Grid for info
        self.detail_grid = Gtk.Grid(column_spacing=24, row_spacing=12, margin_top=6)
        self.details_stack.add_titled(self.detail_grid, "grid", "")
        vbox.append(self.detail_grid)

        vbox.append(self.details_stack)
        frame.set_child(vbox)
        return frame

    # ============================================================
    # Sync Activity Panel (Right Column - 1/3)
    # ============================================================
    def _build_sync_panel(self):
        """Sync activity and logs in right column."""
        frame = Gtk.Frame(margin_start=6, margin_end=12, margin_top=12, margin_bottom=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)

        # Header
        header_row = Gtk.Box(spacing=6)
        header_row.append(Gtk.Label(label="Sync Activity", css_classes=["title-3"]))
        self.spinner = Gtk.Spinner(spinning=False)
        header_row.append(self.spinner)
        self.status_lbl = Gtk.Label(css_classes=["dim-label"])
        header_row.append(self.status_lbl)
        vbox.append(header_row)

        # Classification summary
        self.class_grid = Gtk.Grid(column_spacing=24, row_spacing=6, margin_top=6)
        vbox.append(self.class_grid)

        # File list - FIXED: Use set_min_content_height() method
        file_scroller = Gtk.ScrolledWindow(vexpand=True)
        file_scroller.set_min_content_height(200)  # Set on scrolled window instead

        self.file_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.NONE, editable=False,
                                      css_classes=["file-table", "log"])
        file_scroller.set_child(self.file_view)
        vbox.append(file_scroller)

        # Action buttons
        btn_box = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_bottom=4)
        self.btn_preview = Gtk.Button(label="Preview (diff)")
        self.btn_preview.connect("clicked", lambda *_: self.run_sync(MODE_DIFF))
        self.btn_sync = Gtk.Button(label="Sync", css_classes=["suggested-action"])
        self.btn_sync.connect("clicked", lambda *_: self.run_sync(MODE_SYNC))
        btn_box.append(self.btn_preview)
        btn_box.append(self.btn_sync)
        vbox.append(btn_box)

        frame.set_child(vbox)
        return frame

    # ============================================================
    # Data Refresh Methods
    # ============================================================
    def refresh_all(self):
        self.refresh_devices()
        self.refresh_folders()

    def refresh_devices(self):
        from . import backend
        rows = backend.list_devices(self.get_config())
        self._fill_list_devices(self.devices_list, rows)

    def refresh_folders(self):
        from . import backend
        devices = backend.list_devices(self.get_config())
        names = [d["name"] for d in devices]
        rows = backend.list_folders(self.get_config(), names)
        self._fill_list_folders(self.folders_list, rows)

    def _fill_list_devices(self, listbox, rows):
        self._clear_listbox(listbox)
        for row_data in rows:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          margin_top=6, margin_bottom=6)
            line = Gtk.Box(spacing=6)

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

    def _fill_list_folders(self, listbox, rows):
        self._clear_listbox(listbox)
        for row_data in rows:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          margin_top=6, margin_bottom=6)
            line = Gtk.Box(spacing=6)

            label = Gtk.Label(label=row_data["name"], halign=Gtk.Align.START,
                              css_classes=["heading"])
            sub = Gtk.Label(label=row_data["subtitle"], halign=Gtk.Align.START,
                            css_classes=["caption", "dim-label"])

            line.append(label)

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
        from . import backend
        config = backend.load_config()
        self.get_application().update_config(config)
        return config

    # ============================================================
    # Event Handlers
    # ============================================================
    def on_device_selected(self, listbox, row):
        if row is None:
            return
        data = row.row_data
        self._selected_device = data["name"]
        print(f"[MAIN_WINDOW] Selected device: {self._selected_device}")
        self.refresh_folders()

    def on_folder_selected(self, listbox, row):
        if row is None:
            # Deselect - show empty placeholder
            self.empty_placeholder.set_visible(True)
            self.details_stack.set_visible_child_name("")
            return
        data = row.row_data
        self._selected_folder = data["name"]
        print(f"[MAIN_WINDOW] Selected folder: {self._selected_folder}")
        self.show_folder_detail(data)

    def show_folder_detail(self, row_data):
        # Hide placeholder, show details
        self.empty_placeholder.set_visible(False)
        self.details_stack.set_visible_child_name("title")

        self.detail_title.set_text(row_data["name"])
        self.detail_subtitle.set_text(row_data["subtitle"])

        # Clear and rebuild grid
        for child in list(self.detail_grid):
            self.detail_grid.remove(child)

        detail = row_data.get("detail", {})
        col = 0
        for key, value in detail.items():
            self.detail_grid.attach(Gtk.Label(label=key.upper(), halign=Gtk.Align.START,
                                              css_classes=["caption", "dim-label"]), col, 0, 1, 1)
            self.detail_grid.attach(Gtk.Label(label=str(value), halign=Gtk.Align.START), col, 1, 1, 1)
            col += 1

        self.details_stack.set_visible_child_name("grid")

    def on_add_device(self):
        from . import backend
        existing = [d["name"] for d in backend.list_devices(self.get_config())]
        dlg = AddDeviceDialog(self, existing=existing)
        dlg.connect("response", self.on_add_device_response)
        dlg.present()

    def on_add_device_response(self, dlg, response):
        from . import backend
        if response == "ok":
            values = dlg.get_values()
            msg, config = backend.add_device(self.get_config(), **values)
            self.log(msg)
            self.get_application().update_config(config)
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
        if response == "ok":
            values = dlg.get_values()
            msg, config = backend.add_folder(self.get_config(), **values)
            self.log(msg)
            self.get_application().update_config(config)
            self.refresh_all()
        dlg.destroy()

    # ============================================================
    # Sync Operations
    # ============================================================
    def run_sync(self, mode):
        from . import backend
        if not self._selected_folder:
            self.log("No folder selected.")
            return

        config = self.get_config()  # Get config BEFORE defining worker
        main_device = backend.get_main_device(config)
        if not main_device:
            err_dialog = Adw.MessageDialog(
                transient_for=self,
                heading="No Main Device",
                body="You must set a main device before syncing."
            )
            err_dialog.add_response("ok", "OK")
            err_dialog.present()
            return

        folder = self._selected_folder
        self.btn_sync.set_sensitive(False)
        self.btn_preview.set_sensitive(False)
        self.spinner.start()
        self.status_lbl.set_text("Scanning…" if mode == MODE_DIFF else "Synchronizing…")

        # Capture config and other variables for worker thread
        def worker():
            # Use the config captured from outer scope
            report, updated_config, error = backend.run_sync_report(config, mode, folder,
                                                                    log_callback=self.log_from_thread)
            GLib.idle_add(self._sync_finished, report, updated_config, error)

        threading.Thread(target=worker, daemon=True).start()

    def _sync_finished(self, report, config, error):
        self.spinner.stop()
        self.btn_sync.set_sensitive(True)
        self.btn_preview.set_sensitive(True)
        self.status_lbl.set_text("")

        if error:
            self.log(f"Error: {error}")
        else:
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
        buf = self.file_view.get_buffer()
        buf.insert_markup(buf.get_end_iter(), f"[LOG] {GLib.markup_escape_text(str(message))}\n", -1)

    def log_from_thread(self, message):
        GLib.idle_add(self.log, message)