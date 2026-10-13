import threading
from pathlib import Path

from gi.repository import Gtk, GLib, Gdk, Gio, Pango
from noserversync.synclib import get_main_device

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
        self._folder_sync_cache = {}  # Stores {folder_name: {"report": ..., "classified": ..., "has_changes": bool}}
        self._checking_folders = set()  # Tracks which folders are actively running checks
        self._just_synced_folders = set()  # Track folders that were just synced
        self._build_ui()
        self.refresh_all()

        css_provider = Gtk.CssProvider()
        # css_provider.load_from_data(b"""
        #     /* Make the row itself styled with transparent blue for the main device */
        #     .main-device {
        #         color: rgba(53, 132, 228, 0.8);
        #         font-weight: bold;
        #         background-color: rgba(53, 132, 228, 0.12);
        #     }
        #     .connected-badge {
        #         color: #f5c211;
        #         font-weight: bold;
        #     }
        #     .selected-badge {
        #         color: #2ec27e;
        #         font-weight: bold;
        #     }
        # """)

        # Get the directory where main_window.py is located
        css_path = Path(__file__).parent / "style.css"
        css_provider.load_from_path(str(css_path))

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Poll for device connection changes every 5 seconds
        GLib.timeout_add_seconds(5, self._on_device_poll_tick)

    def _on_device_poll_tick(self):
        """Called periodically by GLib to refresh devices and check connectivity."""
        self.refresh_devices()
        # Return True to keep the timeout active, or False to stop it.
        return True

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
                icon_name = "computer-symbolic"

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
            folder_name = row_data["name"]

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          margin_top=6, margin_bottom=6, margin_start=12, margin_end=12)

            icon_name = row_data.get("icon", "folder-symbolic")
            icon = Gtk.Image(icon_name=icon_name)
            box.append(icon)

            label = Gtk.Label(label=folder_name, halign=Gtk.Align.START, css_classes=["heading"])
            sub = Gtk.Label(label=row_data["subtitle"], halign=Gtk.Align.START, css_classes=["dim-label"])
            box.append(label)
            box.append(sub)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            box.append(spacer)

            # Dynamic badges or sync action buttons per folder tile
            if folder_name in self._just_synced_folders:
                synced_badge = Gtk.Label(label="Just synced", css_classes=["connected-badge"])
                box.append(synced_badge)
            elif folder_name in self._checking_folders:
                # Create a progress bar matching the current progress value
                pbar = Gtk.ProgressBar()
                # Get fraction safely, default to 0.0
                fraction = getattr(self, "_folder_progress", {}).get(folder_name, 0.0)
                pbar.set_fraction(fraction)
                pbar.set_size_request(120, -1)
                box.append(pbar)
            elif folder_name in self._folder_sync_cache:
                cache_entry = self._folder_sync_cache[folder_name]
                if cache_entry["has_changes"]:
                    sync_btn = Gtk.Button(label="Do Sync", css_classes=["suggested-action"])
                    sync_btn.connect("clicked", lambda _, f=folder_name: self._open_sync_for_folder(f))
                    box.append(sync_btn)
                else:
                    badge = Gtk.Label(label="Nothing new to sync", css_classes=["dim-label"])
                    box.append(badge)

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
            return

        self._selected_device = data["name"]
        # Clear cache when changing devices
        self._folder_sync_cache.clear()
        self._checking_folders.clear()
        self._just_synced_folders.clear()
        self.refresh_folders()
        if data.get("connected", False):
            self.btn_check.set_sensitive(True)

    def on_folder_selected(self, listbox, row):
        if row is None:
            self._selected_folder = None
            return
        data = row.row_data
        self._selected_folder = data["name"]

    def run_check_diff(self):
        from . import backend
        from noserversync.synclib import get_connected_devices, classify_linked_files, NEW, CHANGED, DELETE

        if not self._selected_device:
            return

        config = self.get_config()
        device_list = get_connected_devices(config)
        if not device_list:
            return

        main = get_main_device(config)
        target_device = self._selected_device

        # Get all shared folders for this device
        folders = backend.list_folders(config, [target_device], target_device)
        folder_names = [f["name"] for f in folders]

        if not folder_names:
            return

        # Clear just_synced_folders so they get rechecked instead of ignored
        self._just_synced_folders.clear()

        # Track progress fraction dictionary and mark all folders as checking
        self._folder_progress = {}
        for fname in folder_names:
            self._checking_folders.add(fname)
            self._folder_progress[fname] = 0.0

        self.refresh_folders()
        self.btn_check.set_sensitive(False)

        def worker():
            for folder_name in folder_names:
                last_time = [0.0]

                def update_progress(current, total):
                    if total > 0:
                        current_time = time.time()
                        fraction = min(max(current / float(total), 0.0), 1.0)
                        if (current_time - last_time[0] >= 1.0) or (current == total):
                            self._folder_progress[folder_name] = fraction
                            GLib.idle_add(self.refresh_folders)
                            last_time[0] = current_time

                classified = classify_linked_files(
                    config, target_device, folder_name,
                    progress_callback=update_progress
                )

                def take(keys):
                    files = []
                    for k in keys:
                        if k in classified:
                            v = classified[k]
                            files.extend(sorted(v) if isinstance(v, (set, list)) else [])
                    return sorted(files)

                report = {
                    f"New files ({main} → {target_device})": take([(NEW, main)]),
                    f"New files ({target_device} → {main})": take([(NEW, target_device)]),
                    f"Changed files ({main} → {target_device})": take([(CHANGED, main)]),
                    f"Changed files ({target_device} → {main})": take([(CHANGED, target_device)]),
                    f"Deleted files ({main} → {target_device})": take([(DELETE, main)]),
                    f"Deleted files ({target_device} → {main})": take([(DELETE, target_device)]),
                }

                has_any = any(len(files) > 0 for files in report.values())

                GLib.idle_add(self._store_folder_cache, folder_name, {
                    "report": report,
                    "classified": classified,
                    "main": main,
                    "device": target_device,
                    "has_changes": has_any
                })

            GLib.idle_add(self._finish_checking)

        threading.Thread(target=worker, daemon=True).start()

    def _store_folder_cache(self, folder_name, data):
        self._checking_folders.discard(folder_name)
        self._folder_sync_cache[folder_name] = data
        self.refresh_folders()
        return GLib.SOURCE_REMOVE

    def _finish_checking(self):
        self.spinner.stop()
        self.btn_check.set_sensitive(True)
        self.refresh_folders()
        return GLib.SOURCE_REMOVE

    def _open_sync_for_folder(self, folder_name):
        cache_data = self._folder_sync_cache.get(folder_name)
        if not cache_data:
            return

        sync_win = SyncWindow(
            parent=self,
            config=self.get_config(),
            device=cache_data["device"],
            folder=folder_name,
            classified=cache_data["classified"],
            report=cache_data["report"],
            main=cache_data["main"],
            on_synced_callback=self._on_folder_synced
        )
        sync_win.present()

    def _on_folder_synced(self, folder_name):
        # Remove from cache so the sync button goes away and show 'Just synced' badge
        if folder_name in self._folder_sync_cache:
            del self._folder_sync_cache[folder_name]
        self._just_synced_folders.add(folder_name)
        self.refresh_folders()

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


import time


class SyncWindow(Gtk.Window):
    def __init__(self, parent, config, device, folder, classified, report, main, on_synced_callback=None):
        super().__init__(title="Sync Decisions & Differences", transient_for=parent, modal=True)
        self.set_default_size(700, 650)

        self.config = config
        self.device = device
        self.folder = folder
        self.classified = classified
        self.report = report
        self.main = main
        self.on_synced_callback = on_synced_callback

        self.decisions = {}
        self.category_lists_map = {}  # Stores the listboxes to rebuild file rows dynamically
        self.category_progress_bars = {}  # Stores progress bars per category
        self.category_title_labels = {}  # Stores title labels to update counts dynamically
        self.manual_overrides = {}

        self._build_ui()

    def _get_icon_name_for_file(self, file_path):
        """Determine appropriate icon based on file extension."""
        ext = file_path.lower().split('.')[-1] if '.' in file_path else ""

        # Images
        if ext in ('png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp'):
            return "image-x-generic-symbolic"
        # Videos
        elif ext in ('mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm'):
            return "video-x-generic-symbolic"
        # Audio
        elif ext in ('mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a'):
            return "audio-x-generic-symbolic"
        # Documents / Text / Code
        elif ext in ('txt', 'md', 'pdf', 'doc', 'docx', 'rtf', 'odt'):
            return "x-office-document-symbolic"
        elif ext in ('py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'c', 'cpp', 'h'):
            return "text-x-script-symbolic"
        # Archives
        elif ext in ('zip', 'tar', 'gz', 'rar', '7z'):
            return "package-x-generic-symbolic"
        else:
            return "text-x-generic"

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                           margin_start=16, margin_end=16, margin_top=16, margin_bottom=16)

        title_lbl = Gtk.Label(label=f"Review Changes for Folder: {self.folder}", css_classes=["title-3"])
        title_lbl.set_halign(Gtk.Align.START)
        main_box.append(title_lbl)

        # Outer scroll window for all categories
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

                # Category Title Label storing total file count info
                title_text = f"{category} ({len(files)} files)"
                cat_title_lbl = Gtk.Label(label=title_text, css_classes=["heading"], halign=Gtk.Align.START)
                self.category_title_labels[category] = (category, len(files))
                header.append(cat_title_lbl)

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

                # Progress bar for this specific category
                pbar = Gtk.ProgressBar(margin_start=8, margin_end=8, margin_top=4)
                pbar.set_fraction(0.0)
                pbar.set_visible(False)
                self.category_progress_bars[category] = pbar
                card.append(pbar)

                # Inner ScrolledWindow for each category file list
                file_scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
                file_scroller.set_min_content_height(100)
                file_scroller.set_max_content_height(180)
                file_scroller.set_propagate_natural_height(True)

                file_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
                file_scroller.set_child(file_listbox)

                self.category_lists_map[category] = file_listbox
                self._update_category_display(category)

                card.append(file_scroller)
                vbox_categories.append(card)

        if not has_any:
            vbox_categories.append(Gtk.Label(label="Everything is up to date! No changes found.", margin_top=20))

        scroller.set_child(vbox_categories)
        main_box.append(scroller)

        # Footer box with Spinner and Sync Button
        footer_box = Gtk.Box(spacing=12, halign=Gtk.Align.END, margin_top=12)

        self.sync_spinner = Gtk.Spinner(spinning=False)
        footer_box.append(self.sync_spinner)

        close_btn = Gtk.Button(label="Cancel")
        close_btn.connect("clicked", lambda *_: self.destroy())
        self.close_btn = close_btn

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

        all_decided = all(val != SKIP for val in self.decisions.values()) and len(self.decisions) > 0
        self.btn_do_sync.set_sensitive(all_decided)

    def _store_manual_decisions(self, category, approved_files):
        self.manual_overrides[category] = set(approved_files)
        self.decisions[category] = MANUAL_CUSTOM
        self._update_category_display(category)

        all_decided = all(val != SKIP for val in self.decisions.values()) and len(self.decisions) > 0
        self.btn_do_sync.set_sensitive(all_decided)

    def _update_category_display(self, target_category):
        listbox = self.category_lists_map.get(target_category)
        if not listbox:
            return

        # Clear existing rows in the listbox
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

        files = self.report.get(target_category, [])
        choice = self.decisions.get(target_category, SKIP)
        approved_set = self.manual_overrides.get(target_category, set())

        for idx, f in enumerate(files, start=1):
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                              margin_top=4, margin_bottom=4, margin_start=8, margin_end=8)

            # File number label (1, 2, 3...) to the left of the icon
            num_label = Gtk.Label(label=f"{idx}.", css_classes=["dim-label"])
            num_label.set_width_chars(3)
            num_label.set_xalign(1.0)
            row_box.append(num_label)

            # Dynamic file type icon
            icon_name = self._get_icon_name_for_file(f)
            icon = Gtk.Image(icon_name=icon_name)
            icon.set_valign(Gtk.Align.CENTER)
            row_box.append(icon)

            filename = f.split("/")[-1]
            label = Gtk.Label(label=filename, xalign=0)
            label.set_hexpand(True)
            label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            row_box.append(label)

            # Determine sync status and color styling per file row
            status_label = Gtk.Label()
            if choice == ACCEPT:
                status_label.set_markup("<span color='green'>to sync</span>")
            elif choice == MANUAL_CUSTOM:
                if f in approved_set:
                    status_label.set_markup("<span color='green'>to sync</span>")
                else:
                    status_label.set_markup("<span color='red'>to skip</span>")
            else:
                status_label.set_markup("<span color='gray'>to skip</span>")

            row_box.append(status_label)

            row = Gtk.ListBoxRow(child=row_box)
            listbox.append(row)

    def _execute_sync_decisions(self, btn):
        self.btn_do_sync.set_sensitive(False)
        self.close_btn.set_sensitive(False)
        self.sync_spinner.start()

        for category, choice in self.decisions.items():
            if choice != SKIP and choice:
                pbar = self.category_progress_bars.get(category)
                if pbar:
                    pbar.set_visible(True)
                    pbar.set_fraction(0.0)

        def worker():
            from noserversync.synclib import update_sync_time, save_config, do_sync
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
                            matched = {file_item for file_item in file_set if file_item in allowed_files}
                            if matched:
                                filtered_classified[cat_key] = matched

                    if not filtered_classified:
                        continue

                    last_time = [0.0]

                    def progress_callback(current, total):
                        if total > 0:
                            current_time = time.time()
                            fraction = min(max(current / float(total), 0.0), 1.0)
                            if (current_time - last_time[0] >= 1.0) or (current == total):
                                GLib.idle_add(self._update_category_progress, category, fraction)
                                last_time[0] = current_time

                    self.config = do_sync(
                        self.config,
                        self.device,
                        self.folder,
                        filtered_classified,
                        self.main,
                        progress_callback=progress_callback
                    )

                self.config = update_sync_time(self.config, device=self.device, folder=self.folder)
                save_config(self.config)

            GLib.idle_add(self._finish_sync)

        threading.Thread(target=worker, daemon=True).start()

    def _update_category_progress(self, category, fraction):
        pbar = self.category_progress_bars.get(category)
        if pbar:
            pbar.set_fraction(fraction)
        return GLib.SOURCE_REMOVE

    def _finish_sync(self):
        self.sync_spinner.stop()
        if self.on_synced_callback:
            self.on_synced_callback(self.folder)
        self.destroy()
        return GLib.SOURCE_REMOVE


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
