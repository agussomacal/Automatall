import threading
from gi.repository import Gtk, GLib, Gdk, Gio, Adw, Pango

from .backend import _do_sync
from .dialogs import AddDeviceDialog, AddFolderDialog

SKIP = "skip"
MANUAL = "manual"
MANUAL_CUSTOM = "manual_custom"
ACCEPT = "accept"

APP_NAME = "NoServerSync"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title=APP_NAME, default_width=1100, default_height=800, **kwargs)
        self._selected_device = None
        self._selected_folder = None
        self._last_report = None
        self._classified = None
        self._current_device = None
        self._build_ui()
        self.refresh_all()

        # Add this inside MainWindow._build_ui or __init__
        css_provider = Gtk.CssProvider()
        #
        #         background-color: rgba(53, 132, 228, 0.12); /* Nice transparent blue matching the full width */
        #         border-bottom: 1px solid rgba(53, 132, 228, 0.2);
        #
        css_provider.load_from_data(b"""
            /* Make the row itself styled with transparent blue for the main device */
            .main-device {
                color: rgba(53, 132, 228, 0.8); /* Green for selected device */
                font-weight: bold;
                background-color: rgba(53, 132, 228, 0.12); /* Nice transparent blue matching the full width */
            }
            .connected-badge {
                color: #f5c211; /* Yellow for online devices */
                font-weight: bold;
            }
            .selected-badge {
                color: #2ec27e; /* Green for selected device */
                font-weight: bold;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # HeaderBar
        header = Gtk.HeaderBar()
        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu.append("Quit", "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        title_label = Gtk.Label(label=APP_NAME, css_classes=["title"])
        header.set_title_widget(title_label)
        main_box.append(header)

        # Top Panel: Devices
        devices_panel = self._build_devices_panel()
        main_box.append(devices_panel)

        # Bottom / Single Central Panel
        main_panel = self._build_single_main_panel()
        main_box.append(main_panel)

        self.set_child(main_box)

    def _build_devices_panel(self):
        frame = Gtk.Frame(margin_start=12, margin_end=12, margin_top=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)

        header_row = Gtk.Box(spacing=12)
        header_row.append(Gtk.Label(label="Devices", css_classes=["title-3"]))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_row.append(spacer)
        add_btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER,
                             tooltip_text="Add Device")
        add_btn.connect("clicked", lambda *_: self.on_add_device())
        header_row.append(add_btn)
        vbox.append(header_row)

        scroller = Gtk.ScrolledWindow(vexpand=False, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=130)
        self.devices_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                        css_classes=["boxed-list"])
        self.devices_list.connect("row-selected", self.on_device_selected)
        scroller.set_child(self.devices_list)
        vbox.append(scroller)

        frame.set_child(vbox)
        return frame

    def _build_single_main_panel(self):
        """Single panel containing folders and check button."""
        frame = Gtk.Frame(margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)

        top_row = Gtk.Box(spacing=12)
        top_row.append(Gtk.Label(label="Tracked Folders & Differences", css_classes=["title-3"]))

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_row.append(spacer)

        add_folder_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add Folder")
        add_folder_btn.connect("clicked", lambda *_: self.on_add_folder())
        top_row.append(add_folder_btn)

        self.btn_check = Gtk.Button(label="Check for differences", css_classes=["suggested-action"])
        self.btn_check.connect("clicked", lambda *_: self.run_check_diff())
        self.btn_check.set_sensitive(False)
        top_row.append(self.btn_check)

        self.spinner = Gtk.Spinner(spinning=False)
        top_row.append(self.spinner)
        vbox.append(top_row)

        folders_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                            vscrollbar_policy=Gtk.PolicyType.NEVER)
        folders_scroll.set_min_content_height(70)
        self.folders_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        self.folders_list.connect("row-selected", self.on_folder_selected)
        folders_scroll.set_child(self.folders_list)
        vbox.append(folders_scroll)

        frame.set_child(vbox)
        return frame

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
        rows = backend.list_folders(self.get_config(), names, self._selected_device)
        self._fill_list_folders(self.folders_list, rows)

    def _fill_list_devices(self, listbox, rows):
        self._clear_listbox(listbox)

        # Sort so main device is at the very top
        rows_sorted = sorted(rows, key=lambda d: not d.get("is_main", False))

        for row_data in rows_sorted:
            is_main = row_data.get("is_main", False)
            connected = row_data.get("connected", False)
            is_selected = (row_data["name"] == self._selected_device)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          margin_top=8, margin_bottom=8,
                          margin_start=12, margin_end=12)

            # Create and add the icon image using row_data["icon"]
            device_type = row_data.get("type", "COMPUTER").upper()

            if device_type == "COMPUTER":
                icon_name = "computer-symbolic"
            elif device_type == "USB":
                icon_name = "media-removable-symbolic"
            elif device_type == "DRIVE":
                icon_name = "drive-harddisk-symbolic"
            elif device_type in ("PHONE", "IPAD"):
                icon_name = "phone-symbolic"
            else:
                icon_name = "computer-symbolic"  # fallback icon

            icon = Gtk.Image(icon_name=icon_name)
            box.append(icon)

            label = Gtk.Label(label=row_data["name"], halign=Gtk.Align.START)
            sub = Gtk.Label(label=row_data["subtitle"], halign=Gtk.Align.START, css_classes=["dim-label"])
            box.append(label)
            box.append(sub)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            box.append(spacer)

            if is_main:
                main_badge = Gtk.Label(label="MAIN DEVICE", css_classes=["main-device"])
                box.append(main_badge)
            elif is_selected and connected:
                sel_badge = Gtk.Label(label="Selected to Sync", css_classes=["selected-badge"])
                box.append(sel_badge)
            elif connected:
                online_badge = Gtk.Label(label="Connected", css_classes=["connected-badge"])
                box.append(online_badge)
            else:
                offline_badge = Gtk.Label(label="Offline", css_classes=["dim-label"])
                box.append(offline_badge)

            row = Gtk.ListBoxRow(child=box)
            row.row_data = row_data

            if is_main:
                row.get_style_context().add_class("main-device")
                row.set_selectable(False)
                row.set_activatable(False)

            listbox.append(row)

    def _fill_list_folders(self, listbox, rows):
        self._clear_listbox(listbox)
        for row_data in rows:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          margin_top=6, margin_bottom=6, margin_start=12, margin_end=12)

            # Create and add the icon image using row_data["icon"]
            icon_name = row_data.get("icon", "folder-symbolic")  # fallback to folder if missing
            icon = Gtk.Image(icon_name=icon_name)
            box.append(icon)

            label = Gtk.Label(label=row_data["name"], halign=Gtk.Align.START, css_classes=["heading"])
            sub = Gtk.Label(label=row_data["subtitle"], halign=Gtk.Align.START, css_classes=["dim-label"])
            box.append(label)
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

    def on_device_selected(self, listbox, row):
        if row is None:
            return
        data = row.row_data
        if data.get("is_main", False):
            return  # Main device is always implicitly part of sync operations

        self._selected_device = data["name"]
        self.refresh_folders()

    def on_folder_selected(self, listbox, row):
        if row is None:
            self._selected_folder = None
            self.btn_check.set_sensitive(False)
            return
        data = row.row_data
        self._selected_folder = data["name"]
        self.btn_check.set_sensitive(True)

    def run_check_diff(self):
        from . import backend
        from NoServerSync.synclib import get_connected_devices
        if not self._selected_folder:
            return

        config = self.get_config()
        device_list = get_connected_devices(config)
        if not device_list:
            return
        main = backend.get_main_device(config)
        self._current_device = device_list[0]

        self.spinner.start()
        self.btn_check.set_sensitive(False)

        def worker():
            from NoServerSync.synclib import classify_linked_files, NEW, CHANGED, DELETE
            classified = classify_linked_files(config, self._current_device, self._selected_folder)

            def take(keys):
                files = []
                for k in keys:
                    if k in classified:
                        v = classified[k]
                        files.extend(sorted(v) if isinstance(v, (set, list)) else [])
                return sorted(files)

            report = {
                f"New files ({main} → {self._current_device})": take([(NEW, main)]),
                f"New files ({self._current_device} → {main})": take([(NEW, self._current_device)]),
                f"Changed files ({main} → {self._current_device})": take([(CHANGED, main)]),
                f"Changed files ({self._current_device} → {main})": take([(CHANGED, self._current_device)]),
                f"Deleted files ({main} → {self._current_device})": take([(DELETE, main)]),
                f"Deleted files ({self._current_device} → {main})": take([(DELETE, self._current_device)]),
            }
            GLib.idle_add(self._open_sync_window, report, classified, config, main)

        threading.Thread(target=worker, daemon=True).start()

    def _open_sync_window(self, report, classified, config, main):
        self.spinner.stop()
        self.btn_check.set_sensitive(True)

        sync_win = SyncWindow(
            parent=self,
            config=config,
            device=self._current_device,
            folder=self._selected_folder,
            classified=classified,
            report=report,
            main=main
        )
        sync_win.present()
        return GLib.SOURCE_REMOVE

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
            self.get_application().update_config(config)
            self.refresh_all()
        dlg.destroy()

    def on_add_folder(self):
        from . import backend
        if not self._selected_device:
            return
        dlg = AddFolderDialog(self, device_name=self._selected_device, config=self.get_config())
        dlg.connect("response", self.on_add_folder_response)
        dlg.present()

    def on_add_folder_response(self, dlg, response):
        from . import backend
        if response == "ok":
            values = dlg.get_values()
            msg, config = backend.add_folder(self.get_config(), **values)
            self.get_application().update_config(config)
            self.refresh_all()
        dlg.destroy()


class SyncWindow(Gtk.Window):
    def __init__(self, parent, config, device, folder, classified, report, main):
        super().__init__(title="Sync Decisions & Differences", transient_for=parent, modal=True)
        self.set_default_size(700, 600)

        self.config = config
        self.device = device
        self.folder = folder
        self.classified = classified
        self.report = report
        self.main = main

        self.decisions = {}
        self.category_labels_map = {}
        self.manual_overrides = {}

        self._build_ui()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                           margin_start=16, margin_end=16, margin_top=16, margin_bottom=16)

        title_lbl = Gtk.Label(label=f"Review Changes for Folder: {self.folder}", css_classes=["title-3"])
        title_lbl.set_halign(Gtk.Align.START)
        main_box.append(title_lbl)

        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        vbox_categories = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        has_any = False
        for category, files in self.report.items():
            if files:
                has_any = True
                self.decisions[category] = SKIP

                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["card"])
                card.set_margin_start(4)
                card.set_margin_end(4)

                header = Gtk.Box(spacing=12, margin_top=8, margin_start=8, margin_end=8)
                header.append(Gtk.Label(label=category, css_classes=["heading"], halign=Gtk.Align.START))

                spacer = Gtk.Box()
                spacer.set_hexpand(True)
                header.append(spacer)

                btn_accept = Gtk.ToggleButton(label="Accept Sync")
                btn_manual = Gtk.ToggleButton(label="Manual Sync")
                btn_manual.set_group(btn_accept)

                btn_accept.connect("toggled", lambda b, cat=category: self._on_option_toggled(cat,
                                                                                              ACCEPT if b.get_active() else SKIP))
                btn_manual.connect("toggled", lambda b, cat=category: self._on_option_toggled(cat,
                                                                                              MANUAL if b.get_active() else SKIP))

                header.append(btn_accept)
                header.append(btn_manual)
                card.append(header)

                # File list label mapped for live color updates
                files_lbl = Gtk.Label(halign=Gtk.Align.START, margin_start=16, margin_bottom=8,
                                      css_classes=["dim-label"])
                self.category_labels_map[category] = files_lbl
                self._update_category_display(category)

                card.append(files_lbl)
                vbox_categories.append(card)

        if not has_any:
            vbox_categories.append(Gtk.Label(label="Everything is up to date! No changes found.", margin_top=20))

        scroller.set_child(vbox_categories)
        main_box.append(scroller)

        footer_box = Gtk.Box(spacing=12, halign=Gtk.Align.END, margin_top=12)
        close_btn = Gtk.Button(label="Cancel")
        close_btn.connect("clicked", lambda *_: self.destroy())

        self.btn_do_sync = Gtk.Button(label="Do Sync", css_classes=["suggested-action"])
        self.btn_do_sync.connect("clicked", self._execute_sync_decisions)
        self.btn_do_sync.set_sensitive(False)

        footer_box.append(close_btn)
        footer_box.append(self.btn_do_sync)
        main_box.append(footer_box)

        self.set_child(main_box)

    def _on_option_toggled(self, category, choice):
        self.decisions[category] = choice
        if choice == ACCEPT:
            if category in self.manual_overrides:
                del self.manual_overrides[category]
            self._update_category_display(category)
        elif choice == MANUAL:
            files_in_category = self.report.get(category, [])
            manual_win = ManualSyncWindow(
                parent=self,
                config=self.config,
                device=self.device,
                folder=self.folder,
                classified=self.classified,
                category=category,
                files_list=files_in_category,
                main=self.main,
                on_save_callback=self._store_manual_decisions
            )
            manual_win.present()
        else:
            self._update_category_display(category)

        # Check sensitivity: all categories must have a non-SKIP choice
        all_decided = all(val != SKIP for val in self.decisions.values()) and len(self.decisions) > 0
        self.btn_do_sync.set_sensitive(all_decided)

    def _store_manual_decisions(self, category, approved_files):
        self.manual_overrides[category] = set(approved_files)
        self.decisions[category] = MANUAL_CUSTOM
        self._update_category_display(category)

        all_decided = all(val != SKIP for val in self.decisions.values()) and len(self.decisions) > 0
        self.btn_do_sync.set_sensitive(all_decided)

    def _update_category_display(self, target_category):
        label_widget = self.category_labels_map.get(target_category)
        if not label_widget:
            return

        files = self.report.get(target_category, [])
        choice = self.decisions.get(target_category, SKIP)

        file_lines = []
        for f in files:
            if choice == ACCEPT:
                file_lines.append(f"<span color='green'> • {f} (to sync)</span>")
            elif choice == MANUAL_CUSTOM:
                approved_set = self.manual_overrides.get(target_category, set())
                if f in approved_set:
                    file_lines.append(f"<span color='green'> • {f} (to sync)</span>")
                else:
                    file_lines.append(f"<span color='red'> • {f} (to skip)</span>")
            else:
                file_lines.append(f"<span color='gray'> • {f} (to skip)</span>")

        label_widget.set_use_markup(True)
        label_widget.set_markup("\n".join(file_lines))

    def _execute_sync_decisions(self, btn):
        from NoServerSync.synclib import (
            add_new_files, update_changed_files, remove_deleted_files,
            DEVICES_DEFAULT_PATH, update_sync_time, save_config
        )
        import io
        from contextlib import redirect_stdout

        with redirect_stdout(io.StringIO()):
            for category, choice in self.decisions.items():
                if choice == SKIP or not choice:
                    continue

                allowed_files = set()
                if choice == ACCEPT:
                    allowed_files = set(self.report.get(category, []))
                elif choice == MANUAL_CUSTOM:
                    allowed_files = self.manual_overrides.get(category, set())

                if not allowed_files:
                    continue

                filtered_classified = {}
                for cat_key, file_set in self.classified.items():
                    if isinstance(file_set, (set, list)):
                        matched = {f for f in file_set if f in allowed_files}
                        if matched:
                            filtered_classified[cat_key] = matched

                if not filtered_classified:
                    continue

                _do_sync(self.config, self.device, self.folder, filtered_classified, self.main)
            self.config = update_sync_time(self.config, device=self.device, folder=self.folder)
            save_config(self.config)

        self.destroy()


class SyncFileTile(Gtk.Box):
    def __init__(self, file_path, panel_type, on_swap_callback=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.file_path = file_path
        self.panel_type = panel_type
        self.on_swap_callback = on_swap_callback

        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.set_halign(Gtk.Align.FILL)

        if panel_type == "sync":
            self.get_style_context().add_class("keep-tile")
        else:
            self.get_style_context().add_class("delete-tile")

        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        info_row.set_halign(Gtk.Align.FILL)

        icon = Gtk.Image(icon_name="text-x-generic")
        icon.set_valign(Gtk.Align.CENTER)
        info_row.append(icon)

        filename = file_path.split("/")[-1]
        label = Gtk.Label(label=filename)
        label.set_hexpand(True)
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label.set_xalign(0)
        info_row.append(label)

        if panel_type == "sync":
            arrow = Gtk.Label(label="→")
            arrow.set_css_classes(["dim-label"])
            arrow.set_margin_start(6)
            arrow.set_valign(Gtk.Align.CENTER)
            info_row.append(arrow)

        self.append(info_row)
        self.setup_drag_and_drop()

    def setup_drag_and_drop(self):
        source = Gtk.DragSource()
        source.set_actions(Gdk.DragAction.MOVE)
        source.connect("prepare", lambda src, x, y: Gdk.ContentProvider.new_for_value(self.file_path))
        source.connect("drag-begin", lambda src, drag: self.set_opacity(0.5))
        source.connect("drag-end", lambda src, drag: self.set_opacity(1.0))
        self.add_controller(source)

        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

    def _on_drop(self, target, value, x, y):
        dragged_path = str(value)
        if self.on_swap_callback:
            self.on_swap_callback(dragged_path, target_panel=self.panel_type)
            return True
        return False


class ManualSyncWindow(Gtk.Window):
    def __init__(self, parent, config, device, folder, classified, category, files_list, main, on_save_callback=None):
        super().__init__(title=f"Manual Sync: {category}", transient_for=parent, modal=True)
        self.set_default_size(1000, 650)

        self.config = config
        self.device = device
        self.folder = folder
        self.classified = classified
        self.category = category
        self.main = main
        self.on_save_callback = on_save_callback

        self.sync_files = list(files_list)
        self.skip_files = []

        self._build_ui()
        self._rebuild_lists()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        header = Gtk.HeaderBar()
        title_label = Gtk.Label(label=f"Manual Selection: {self.category}", css_classes=["title"])
        header.set_title_widget(title_label)
        main_box.append(header)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        paned.set_position(500)
        paned.set_margin_top(12)
        paned.set_margin_bottom(12)
        paned.set_margin_start(12)
        paned.set_margin_end(12)

        paned.set_start_child(self._build_sync_panel())
        paned.set_end_child(self._build_skip_panel())
        main_box.append(paned)

        action_box = Gtk.Box(spacing=12, halign=Gtk.Align.END, margin_end=12, margin_bottom=12)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.destroy())

        self.btn_apply = Gtk.Button(label="Confirm Choices", css_classes=["suggested-action"])
        self.btn_apply.connect("clicked", self._confirm_manual_choices)

        action_box.append(cancel_btn)
        action_box.append(self.btn_apply)
        main_box.append(action_box)

        self.set_child(main_box)

    def _build_sync_panel(self):
        frame = Gtk.Frame(margin_end=6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=12,
                       margin_bottom=12)

        header_box = Gtk.Box(spacing=12)
        header_box.append(Gtk.Label(label="Files to Sync", css_classes=["title-3"]))
        header_box.append(Gtk.Box(hexpand=True))

        move_all_skip_btn = Gtk.Button(label="Move All to Skip →")
        move_all_skip_btn.connect("clicked", lambda *_: self._move_all(SKIP))
        header_box.append(move_all_skip_btn)

        self.sync_count_lbl = Gtk.Label(label="0 files", css_classes=["dim-label"])
        header_box.append(self.sync_count_lbl)
        vbox.append(header_box)

        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.sync_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)

        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop_target.connect("drop", lambda target, val, x, y: self._handle_drop_to_panel(str(val), "sync"))
        self.sync_list.add_controller(drop_target)

        scroller.set_child(self.sync_list)
        vbox.append(scroller)
        frame.set_child(vbox)
        return frame

    def _build_skip_panel(self):
        frame = Gtk.Frame(margin_start=6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=12,
                       margin_bottom=12)

        header_box = Gtk.Box(spacing=12)

        move_all_sync_btn = Gtk.Button(label="← Move All to Sync")
        move_all_sync_btn.connect("clicked", lambda *_: self._move_all("sync"))
        header_box.append(move_all_sync_btn)

        header_box.append(Gtk.Box(hexpand=True))
        header_box.append(Gtk.Label(label="Files NOT to Sync (Skip)", css_classes=["title-3"]))

        self.skip_count_lbl = Gtk.Label(label="0 files", css_classes=["dim-label"])
        header_box.append(self.skip_count_lbl)
        vbox.append(header_box)

        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.skip_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)

        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop_target.connect("drop", lambda target, val, x, y: self._handle_drop_to_panel(str(val), "skip"))
        self.skip_list.add_controller(drop_target)

        scroller.set_child(self.skip_list)
        vbox.append(scroller)
        frame.set_child(vbox)
        return frame

    def _move_all(self, target_panel):
        if target_panel == SKIP:
            self.skip_files.extend(self.sync_files)
            self.sync_files.clear()
        elif target_panel == "sync":
            self.sync_files.extend(self.skip_files)
            self.skip_files.clear()
        self._rebuild_lists()

    def _handle_swap_callback(self, dragged_path, target_panel):
        self._handle_drop_to_panel(dragged_path, target_panel)

    def _handle_drop_to_panel(self, dragged_path, target_panel):
        if target_panel == "skip" and dragged_path in self.sync_files:
            self.sync_files.remove(dragged_path)
            self.skip_files.append(dragged_path)
        elif target_panel == "sync" and dragged_path in self.skip_files:
            self.skip_files.remove(dragged_path)
            self.sync_files.append(dragged_path)
        self._rebuild_lists()

    def _rebuild_lists(self):
        self._clear_listbox(self.sync_list)
        self._clear_listbox(self.skip_list)

        for path in self.sync_files:
            tile = SyncFileTile(path, "sync", on_swap_callback=self._handle_swap_callback)
            self.sync_list.append(tile)

        for path in self.skip_files:
            tile = SyncFileTile(path, "skip", on_swap_callback=self._handle_swap_callback)
            self.skip_list.append(tile)

        self.sync_count_lbl.set_text(f"{len(self.sync_files)} files")
        self.skip_count_lbl.set_text(f"{len(self.skip_files)} files")

    @staticmethod
    def _clear_listbox(listbox):
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

    def _confirm_manual_choices(self, btn):
        if self.on_save_callback:
            self.on_save_callback(self.category, self.sync_files)
        self.destroy()
