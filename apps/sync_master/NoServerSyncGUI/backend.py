"""
GUI backend bridge: wraps synclib/cmd_frontend functionality without
modifying them. Captures stdout (tqdm / prints) and routes it to a callback.
"""
import io
import os
from contextlib import redirect_stdout
from pathlib import Path

from noserversync.synclib import CONFIG_FOLDERS_KEY_NAME
from noserversync.synclib import (
    CONFIG_PATH, CONFIG_DEVICES_KEY_NAME, DEVICES_DEFAULT_PATH,
    load_config as _load_config, save_config, set_main_device,
    get_main_device, add_tracking_to_folder, add_sync_folder_settings, FOLDER_SETTINGS,
    init_sync_tracker,
)
from noserversync.synclib import add_device as _add_device

MODE_DIFF = "diff"
MODE_SYNC = "sync"


def _capture(fn, *args, **kwargs):
    """Run a synclib function, capturing its print output."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


def _ensure_config():
    """Ensure config file exists by running init_sync_tracker if needed."""
    if not os.path.exists(CONFIG_PATH):
        init_sync_tracker(path=CONFIG_PATH)


def load_config():
    """Load or initialize configuration. Creates config.yml automatically if missing."""
    _ensure_config()
    return _load_config()


def list_devices(config) -> list:
    """List all devices with their types and connection status."""
    main = get_main_device(config)
    rows = []

    for name, dev in config[CONFIG_DEVICES_KEY_NAME].items():
        connected = Path(dev["path"]).exists()

        # INCLUDE device_type in the returned data!
        rows.append({
            "name": name,
            "subtitle": f"{dev['type']} — {dev['path']}",
            "connected": connected,
            "is_main": name == main,
            "type": dev.get("type", "COMPUTER"),  # ← CRITICAL: Add this line!
            "badge": "main" if name == main else ("online" if connected else "offline"),
        })

    print(f"[BACKEND] list_devices() returning {len(rows)} devices")
    return rows


# ============================================================
# FIX: Return tuple of (message, updated_config) for all mutation ops
# ============================================================
def save_config_debug(config):
    """Wrapper around save_config with debug logging."""
    print(f"[BACKEND] save_config() called, writing to: {CONFIG_PATH}")
    print(f"[BACKEND] Devices to save: {list(config['devices'].keys())}")

    parent_dir = Path(CONFIG_PATH).parent
    if not parent_dir.exists():
        print(f"[BACKEND] ERROR: Parent directory doesn't exist: {parent_dir}")
        parent_dir.mkdir(parents=True, exist_ok=True)
        print(f"[BACKEND] Created parent directory")

    # FIX: Call _save_config (synclib version), not save_config (wrapper)
    save_config(config)

    if os.path.exists(CONFIG_PATH):
        size = os.path.getsize(CONFIG_PATH)
        print(f"[BACKEND] Config file written successfully, size: {size} bytes")

        with open(CONFIG_PATH, 'r') as f:
            content = f.read()
            print(f"[BACKEND] File content preview:\n{content[:200]}...")
    else:
        print(f"[BACKEND] ERROR: File still doesn't exist after save!")


def add_device(config, device_name, mount_path, device_type, device_direction, set_as_main=False):
    """Add a device and persist to disk."""
    print(f"[BACKEND] add_device() called with: name={device_name}, path={mount_path}, set_as_main={set_as_main}")

    # Call synclib add_device (without device_direction - it's not used there)
    (msg, config), out = _capture(
        _add_device, config, name=device_name, mount_path=mount_path, device_type=device_type
    )
    print(f"[BACKEND] add_device() returned msg={msg}")

    if set_as_main:
        config = set_main_device(config, device_name)
        print(f"[BACKEND] Set main device to: {device_name}")

    save_config_debug(config)
    return msg, config


def add_folder(config, device_name, path, direction, append_strategy_to_file_endings,
               folder_settings, icon=None):
    """Add a folder tracking and persist to disk."""
    print(f"[BACKEND] add_folder() called with: device={device_name}, path={path}")

    dev = config[CONFIG_DEVICES_KEY_NAME][device_name]
    rel = os.path.relpath(path, dev["path"])

    # FIX: Use the synclib function, not the wrapper
    (msg, config), out = _capture(
        add_tracking_to_folder,  # This one doesn't shadow, it's fine
        config=config,
        device_name=device_name,
        relative_path=rel,
        direction=direction,
        append_strategy_to_file_endings=append_strategy_to_file_endings,
        devices_symlink_path=DEVICES_DEFAULT_PATH
    )
    print(f"[BACKEND] add_folder() tracking returned msg={msg}")

    folder = path.rstrip("/").split("/")[-1]

    if icon:
        config[CONFIG_FOLDERS_KEY_NAME][folder]["icon"] = icon
        print(f"[BACKEND] Set folder '{folder}' icon to: {icon}")

    for setting in FOLDER_SETTINGS:
        vals = folder_settings.get(setting, [])
        if vals:
            config = add_sync_folder_settings(setting, config, folder, *vals)

    save_config_debug(config)
    return msg, config


def list_folders(config, device_names, selected_device=None) -> list:
    """Folders shared between the main device and the selected secondary device."""
    try:
        main = get_main_device(config)
    except Exception as e:
        return []

    if not main or not selected_device or main == selected_device:
        return []

    main_config = config.get(CONFIG_DEVICES_KEY_NAME, {}).get(main, {})
    main_folders = set(main_config.get("tracked_folders", []))

    sel_config = config.get(CONFIG_DEVICES_KEY_NAME, {}).get(selected_device, {})
    sel_folders = set(sel_config.get("tracked_folders", []))

    # Find folders shared between main and the selected device
    shared_folders = main_folders.intersection(sel_folders)

    folders = []
    tracked_settings = config.get("tracked_folders", {})
    for folder_name in shared_folders:
        folder_config = tracked_settings.get(folder_name, {})
        folder_icon = folder_config.get("icon", "folder")

        row = {
            "name": folder_name,
            "subtitle": f"Shared between {main} and {selected_device}",
            "detail": {"devices": f"{main}, {selected_device}"},
            "badge": "Shared",
            "icon": folder_icon,
        }
        folders.append(row)

    return sorted(folders, key=lambda row: row["name"])
