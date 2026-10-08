"""
GUI backend bridge: wraps synclib/cmd_frontend functionality without
modifying them. Captures stdout (tqdm / prints) and routes it to a callback.
"""
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

# Ensure the original NoServerSync module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from NoServerSync.synclib import (
    CONFIG_PATH, CONFIG_DEVICES_KEY_NAME, CONFIG_SYNC_KEY_NAME, DEVICES_DEFAULT_PATH,
    load_config as _load_config, save_config, set_main_device,
    get_main_device, get_connected_devices, classify_linked_files,
    add_tracking_to_folder, add_sync_folder_settings, FOLDER_SETTINGS,
    DEVICE_TYPES, DEVICE_DIRECTIONS, BIDIRECTIONAL,
    init_sync_tracker,
    NEW, CHANGED, DELETE, CONFLICT, UNCHANGED, NOT_CLASSIFIED,
    get_folder_root,
    add_new_files, update_changed_files, remove_deleted_files,
    append_conflicted_files, duplicate_conflicted_files,
    update_sync_time,
)
from NoServerSync.synclib import add_device as _add_device
from NoServerSync.synclib import get_main_device as _get_main_device

MODE_DIFF = "diff"
MODE_SYNC = "sync"


# Add this getter function
def get_main_device(config):
    """Return the current main device name (may be None)."""
    return _get_main_device(config)


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
    main = get_main_device(config)
    rows = []
    for name, dev in config[CONFIG_DEVICES_KEY_NAME].items():
        connected = Path(dev["path"]).exists()
        rows.append({
            "name": name,
            "subtitle": f"{dev['type']} — {dev['path']}",
            "connected": connected,
            "is_main": name == main,
            "badge": "main" if name == main else ("online" if connected else "offline"),
        })
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
               folder_settings):
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

    for setting in FOLDER_SETTINGS:
        vals = folder_settings.get(setting, [])
        if vals:
            config = add_sync_folder_settings(setting, config, folder, *vals)

    save_config_debug(config)
    return msg, config


def run_sync_report(config, mode, folder, log_callback=lambda s: None):
    """Run sync classification/report."""
    device_list = get_connected_devices(config)
    if not device_list:
        return {"ERROR": ["No connected device found."]}, config, None

    device = device_list[0]

    out_buf = io.StringIO()
    with redirect_stdout(out_buf):
        classified = classify_linked_files(config, device, folder)

    for line in out_buf.getvalue().splitlines():
        if line.strip():
            log_callback(line)

    main = get_main_device(config)

    def take(keys):
        files = []
        for k in keys:
            if k in classified:
                v = classified[k]
                files.extend(sorted(v) if isinstance(v, (set, list)) else [])
        return sorted(files)

    report = {
        "NEW (main)": take([(NEW, main)]),
        "NEW (device)": take([(NEW, device)]),
        "CHANGED (main)": take([(CHANGED, main)]),
        "CHANGED (device)": take([(CHANGED, device)]),
        "DELETED (main)": take([(DELETE, main)]),
        "DELETED (device)": take([(DELETE, device)]),
        "CONFLICTS": take([CONFLICT]),
        "UNCLASSIFIED": take([NOT_CLASSIFIED]),
    }

    if mode == MODE_SYNC:
        _do_sync(config, device, folder, classified, main, log_callback)

    return report, config, None


def _do_sync(config, device, folder, classified, main, log_callback):
    """Execute all sync operations non-interactively."""

    def batch(label, fn, device_from, device_to, keys):
        for key in keys:
            if key in classified and classified[key]:
                log_callback(f"{label}: {len(classified[key])} file(s)")
                with redirect_stdout(io.StringIO()):
                    fn(config, device_from, device_to, folder, classified, DEVICES_DEFAULT_PATH)
                break

    batch("Transferring new files (main→device)", add_new_files, main, device, [(NEW, main)])
    batch("Transferring new files (device→main)", add_new_files, device, main, [(NEW, device)])
    batch("Updating changed (main→device)", update_changed_files, main, device, [(CHANGED, main)])
    batch("Updating changed (device→main)", update_changed_files, device, main, [(CHANGED, device)])
    batch("Removing deleted (main→device)", remove_deleted_files, main, device, [(DELETE, main)])
    batch("Removing deleted (device→main)", remove_deleted_files, device, main, [(DELETE, device)])

    conflicted = classified.get(CONFLICT, set())
    if conflicted:
        log_callback(f"Solving {len(conflicted)} conflicts")
        append_conflicted_files(config, device, folder, classified, DEVICES_DEFAULT_PATH)
        duplicate_conflicted_files(config, device, folder, classified, DEVICES_DEFAULT_PATH)

    config = update_sync_time(config, device=device, folder=folder)
    save_config_debug(config)


def list_folders(config, device_names) -> list:
    """Folders shared between devices, aggregated by folder name."""
    try:
        main = get_main_device(config)
    except Exception as e:
        print(f"[BACKEND] list_folders() error getting main device: {e}")
        return []

    # Group folders by name, collecting all devices that track each folder
    folder_devices_map = {}  # folder_name -> list of device info dicts

    for dev_name in device_names:
        if dev_name not in config[CONFIG_DEVICES_KEY_NAME]:
            continue

        dev_config = config[CONFIG_DEVICES_KEY_NAME][dev_name]
        for folder in dev_config.get("tracked_folders", []):
            if folder not in folder_devices_map:
                folder_devices_map[folder] = []

            folder_devices_map[folder].append({
                "name": dev_name,
                "direction": config.get("tracked_folders", {}).get(folder, {})
                .get("devices_direction", {}).get(dev_name, "bidirectional"),
                "last_sync": config.get("tracked_folders", {}).get(folder, {})
                .get("devices_sync", {}).get(dev_name, None),
                "connected": Path(dev_config["path"]).exists(),
            })

    # Build rows from aggregated data
    folders = []
    for folder_name, device_infos in folder_devices_map.items():
        # Determine subtitle and detail based on how many devices track this folder
        if len(device_infos) == 1:
            dev = device_infos[0]
            subtitle = f"{dev['direction']} — on {dev['name']}"
            detail = {"devices": dev['name'], "direction": dev['direction']}
            badge = None if dev["connected"] else "offline"
        else:
            # Multiple devices tracking same folder
            connected_devs = [d["name"] for d in device_infos if d["connected"]]
            directions = set(d["direction"] for d in device_infos)
            subtitle = f"{', '.join(connected_devs)} ({len(connected_devs)}/{len(device_infos)})"
            detail = {"devices": ", ".join(connected_devs),
                      "direction": "mixed" if len(directions) > 1 else list(directions)[0]}
            badge = f"{len(connected_devs)}/{len(device_infos)} online"

        row = {
            "name": folder_name,
            "subtitle": subtitle,
            "detail": detail,
            "badge": badge,
            "devices": device_infos,  # Store for later use if needed
        }

        folders.append(row)

    print(f"[BACKEND] list_folders() returning {len(folders)} folders: {[f['name'] for f in folders]}")
    return folders
