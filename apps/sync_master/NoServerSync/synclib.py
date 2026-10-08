import itertools
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set, Tuple, Union

import yaml
from tqdm import tqdm

# =============== Configuration =============== #
# automatically create local folder to regroup folders on computer device
DEVICES_SYMLINK_FOLDER_NAME = "DEVICES"
DEVICES_DEFAULT_PATH = Path(f"{os.path.dirname(__file__)}/{DEVICES_SYMLINK_FOLDER_NAME}/")
DEVICES_DEFAULT_PATH.mkdir(exist_ok=True, parents=True)
print(DEVICES_DEFAULT_PATH)

CONFIG_FOLDER = DEVICES_DEFAULT_PATH
CONFIG_FILENAME = "config.yml"
CONFIG_PATH = f"{CONFIG_FOLDER}/{CONFIG_FILENAME}"


def init_sync_tracker(path=CONFIG_PATH):
    basedir = os.path.dirname(path)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
    open(path, 'a').close()


USB = "USB"
DRIVE = "DRIVE"
IPAD = "IPAD"
PHONE = "PHONE"
COMPUTER = "COMPUTER"
DEVICE_TYPES = (COMPUTER, USB, IPAD, PHONE, DRIVE)


def Device(path: str = None, type: str = None, tracked_folders: List[str] = list()):
    """

    :param path:
    :param type:
    :param tracked_folders: the relative paths
    :return:
    """
    return {"path": str(path), "type": type, "tracked_folders": tracked_folders}


ONLY_FILE_ENDINGS = "only_file_endings"
IGNORED = "ignored"
NOT_IGNORED = "not_ignored"
IGNORED_FILE_ENDINGS = "ignored_file_endings"
FOLDER_SETTINGS = (ONLY_FILE_ENDINGS, IGNORED_FILE_ENDINGS, IGNORED, NOT_IGNORED)

BIDIRECTIONAL = "bidirectional"
FROM_MAIN = "from_main"
TO_MAIN = "to_main"
DEVICE_DIRECTIONS = (BIDIRECTIONAL, FROM_MAIN, TO_MAIN)


def TrackedFolder(only_file_endings: List[str] = list(), ignored: List[str] = list(), not_ignored: List[str] = list(),
                  ignored_file_endings: List[str] = list(), devices_sync: Dict[str, float] = dict(),
                  devices_direction: Dict[str, str] = dict(),
                  devices_append_strategy_to_file_endings: Dict[str, List[str]] = dict()):
    return {"only_file_endings": only_file_endings, "ignored": ignored, "not_ignored": not_ignored,
            "ignored_file_endings": ignored_file_endings,
            "devices_sync": devices_sync,
            "devices_direction": devices_direction,
            "devices_append_strategy_to_file_endings": devices_append_strategy_to_file_endings}


DEFAULT_TEXT_FILES = ("txt", "md")


def Sync(main_device: str = None):
    return {"main_device": main_device}


CONFIG_DEVICES_KEY_NAME = "devices"
CONFIG_FOLDERS_KEY_NAME = "tracked_folders"
CONFIG_SYNC_KEY_NAME = "sync"
CONFIG_KEYS = (CONFIG_DEVICES_KEY_NAME, CONFIG_FOLDERS_KEY_NAME, CONFIG_SYNC_KEY_NAME)


class NoAliasDumper(yaml.SafeDumper):
    """
    Redefining Dumper to avoid aliases like *id001 in config.yml creation
    """

    def ignore_aliases(self, data):
        return True


def save_config(config, path=CONFIG_PATH):
    # convert to dict the defaultdicts to safe_load yaml
    config[CONFIG_DEVICES_KEY_NAME] = dict(config[CONFIG_DEVICES_KEY_NAME])
    config[CONFIG_FOLDERS_KEY_NAME] = dict(config[CONFIG_FOLDERS_KEY_NAME])

    # save file
    with open(path, "w") as f:
        yaml.dump(config, f, Dumper=NoAliasDumper)


def load_config(path=CONFIG_PATH):
    config = {
        CONFIG_SYNC_KEY_NAME: Sync(),
        CONFIG_DEVICES_KEY_NAME: defaultdict(Device),
        CONFIG_FOLDERS_KEY_NAME: defaultdict(TrackedFolder),
    }

    # Check if config file exists before reading
    if not os.path.exists(path):
        init_sync_tracker(path)  # Create it if missing
        return config

    # load config file
    with open(path, "r") as f:
        config_yaml = yaml.safe_load(f)

    if config_yaml is not None:
        for device, settings in config_yaml.get(CONFIG_DEVICES_KEY_NAME, dict()).items():
            config[CONFIG_DEVICES_KEY_NAME][device] = settings
        for folder, settings in config_yaml.get(CONFIG_FOLDERS_KEY_NAME, dict()).items():
            config[CONFIG_FOLDERS_KEY_NAME][folder] = settings
        config[CONFIG_SYNC_KEY_NAME].update(config_yaml.get(CONFIG_SYNC_KEY_NAME, Sync()))
    return config


# =============== Devices =============== #
DEVICE_EXISTS = "Device exists"
DEVICE_NOT_CONNECTED = "Device not connected"
DEVICE_ADDED = "Device added"
DEVICE_REMOVED = "Device removed"


def add_device(config, name, mount_path, device_type, devices_symlink_path=DEVICES_DEFAULT_PATH):
    if name in config[CONFIG_DEVICES_KEY_NAME].keys():
        return DEVICE_EXISTS, config
    elif not os.path.exists(mount_path):
        return DEVICE_NOT_CONNECTED, config
    else:
        assert device_type in DEVICE_TYPES, f"Device {device_type} type not in supported types {DEVICE_TYPES}."
        # creates a sub folder in DEVICES to store linked subfolders to original files
        local_relative_path = Path(f"{devices_symlink_path}/{name}")
        local_relative_path.mkdir(parents=True, exist_ok=True)
        config[CONFIG_DEVICES_KEY_NAME][name] = Device(path=os.path.abspath(str(mount_path)), type=device_type,
                                                       tracked_folders=list())
        return DEVICE_ADDED, config


def remove_device(config, name, devices_symlink_path=DEVICES_DEFAULT_PATH):
    config[CONFIG_DEVICES_KEY_NAME].pop(name)
    # TODO: remove folder and its linked subfolder references
    devices_symlink_path.joinpath(name).rmdir()
    return DEVICE_REMOVED, config


def get_main_device(config) -> str:
    return config[CONFIG_SYNC_KEY_NAME]["main_device"]


def set_main_device(config, main_device):
    config[CONFIG_SYNC_KEY_NAME]["main_device"] = main_device
    return config


def set_conflict_append_strategy_to_file_endings(config, folder, *file_endings):
    # TODO: make this dependent on device and folder
    config[CONFIG_FOLDERS_KEY_NAME][folder]["append_strategy_to_file_endings"] = list(file_endings)
    return config


def get_connected_devices(config):
    main_device = get_main_device(config)
    return [device_name for device_name, device in config[CONFIG_DEVICES_KEY_NAME].items() if
            os.path.exists(device["path"]) and device_name != main_device]


# =============== Tracked folders =============== #
FOLDER_TRACKING_ALREADY_ADDED = "Folder tracking already added"
FOLDER_TRACKING_ADDED = "Folder tracking added"
FOLDER_NOT_REACHABLE = "Folder not reachable"


def add_tracking_to_folder(config, device_name, relative_path, direction, append_strategy_to_file_endings,
                           devices_symlink_path=DEVICES_DEFAULT_PATH):
    device = config[CONFIG_DEVICES_KEY_NAME][device_name]
    path = f"{device["path"]}/{relative_path}"
    folder_name = path.split("/")[-1]
    if os.path.exists(path):
        if folder_name in device["tracked_folders"]:
            return FOLDER_TRACKING_ALREADY_ADDED, config  # no change on device
        else:
            # creates a symlink of the subfolder inside the device's folder
            symlink = Path(f"{devices_symlink_path}/{device_name}/{folder_name}")
            if not symlink.exists(): symlink.symlink_to(path, target_is_directory=True)

            config[CONFIG_DEVICES_KEY_NAME][device_name]["tracked_folders"].append(folder_name)  # relative_path
            if folder_name not in config[CONFIG_FOLDERS_KEY_NAME]:
                config[CONFIG_FOLDERS_KEY_NAME][folder_name] = TrackedFolder()
            assert direction in DEVICE_DIRECTIONS, f"Sync direction {direction} not in supported directions {DEVICE_DIRECTIONS}."
            config[CONFIG_FOLDERS_KEY_NAME][folder_name]["devices_direction"][device_name] = direction
            config[CONFIG_FOLDERS_KEY_NAME][folder_name]["devices_append_strategy_to_file_endings"][
                device_name] = append_strategy_to_file_endings

            return FOLDER_TRACKING_ADDED, config  # add folder track on device
    else:
        return FOLDER_NOT_REACHABLE, config  # no change on device


def add_sync_folder_settings(setting_name, config, folder: str, *args: str):
    assert setting_name in FOLDER_SETTINGS, f"setting_name should be in {FOLDER_SETTINGS} but {setting_name} was given"
    config[CONFIG_FOLDERS_KEY_NAME][folder][setting_name] += args
    config[CONFIG_FOLDERS_KEY_NAME][folder][setting_name] = list(
        set(config[CONFIG_FOLDERS_KEY_NAME][folder][setting_name]))
    return config


def get_file_ending(path):
    return path.rsplit(".", 1)


def check_eligibility_of_file(tracked_folder: Dict, relative_filepath, filename):
    file_ending = get_file_ending(filename)[-1]
    if len(tracked_folder.get(ONLY_FILE_ENDINGS, [])) > 0:  # overrides the other settings
        if file_ending in tracked_folder[ONLY_FILE_ENDINGS]: return True
    else:
        if relative_filepath in tracked_folder[NOT_IGNORED]: return True
        if relative_filepath in tracked_folder[IGNORED]: return False
        for subfolder_or_file in tracked_folder[IGNORED]:
            if subfolder_or_file in relative_filepath: return False
        if file_ending in tracked_folder[IGNORED_FILE_ENDINGS]: return False
        return True
    return False


def get_folder_root(config, device: str, folder: str, devices_symlink_path=DEVICES_DEFAULT_PATH):
    return f"{devices_symlink_path}/{device}/{folder}/"


def get_tracked_files_info(config, device_name: str, folder: str, devices_symlink_path=DEVICES_DEFAULT_PATH):
    files_info = dict()
    root = get_folder_root(config, device_name, folder, devices_symlink_path)
    for dir_path, dirs, files in os.walk(root, followlinks=True):
        relative_dir_path = os.path.relpath(dir_path, root)
        for filename in files:
            relative_filepath = os.path.join(relative_dir_path, filename)
            if check_eligibility_of_file(config[CONFIG_FOLDERS_KEY_NAME][folder], relative_filepath, filename):
                files_info[relative_filepath] = os.path.getmtime(os.path.join(root, relative_filepath))
    return files_info


TIME_VERIFIER_FILENAME = '.time_verifier.txt'


def get_devices_time_difference(config, device_name: str, folder: str, devices_symlink_path=DEVICES_DEFAULT_PATH, m=0):
    if m == 0: return 0
    # TODO: run a full estimation of the time difference once and store it on device config.
    root_device = get_folder_root(config, device_name, folder, devices_symlink_path)
    root_main_device = get_folder_root(config, get_main_device(config), folder, devices_symlink_path)
    dtv_file = Path(root_device + TIME_VERIFIER_FILENAME)
    dtv_main_device = Path(root_main_device + TIME_VERIFIER_FILENAME)
    # touch/create files
    t_diff = 0
    for i in range(m):
        with open(dtv_file, "w") as f: f.write("")
        t0 = time.time()
        with open(dtv_main_device, "w") as f: f.write("")
        dt = time.time() - t0
        # get times
        t_diff += os.path.getmtime(dtv_file) - (os.path.getmtime(dtv_main_device) - dt)
    t_diff /= m
    return t_diff


# =============== Linked folders =============== #
NEVER = 0
NO_FILE = None

NOT_CLASSIFIED = "not classified"
NEW = "new"
CHANGED = "changed"
UNCHANGED = "unchanged"
DELETE = "delete"
CONFLICT = "conflict"

import difflib


def diff_between_files(config, device: str, folder: str, rpath, devices_symlink_path=DEVICES_DEFAULT_PATH):
    main_device = get_main_device(config)
    path_to_folder_main = get_folder_root(config, main_device, folder, devices_symlink_path)
    path_to_folder_dev = get_folder_root(config, device, folder, devices_symlink_path)
    # True means conflicted file; False unchanged
    files_differ = os.path.getsize(f"{path_to_folder_main}/{rpath}") != os.path.getsize(f"{path_to_folder_dev}/{rpath}")

    # if it is a text file check difference if not only size
    ending = get_file_ending(rpath)[-1]
    if not files_differ and ending in DEFAULT_TEXT_FILES:
        try:
            with open(f"{path_to_folder_main}/{rpath}", "r") as f:
                file_in_main = f.read().strip().splitlines()
            with open(f"{path_to_folder_dev}/{rpath}", "r") as f:
                file_in_dev = f.read().strip().splitlines()
            # True means conflicted file; False unchanged
            files_differ = files_differ or (len([line for line in
                                                 difflib.unified_diff(file_in_main, file_in_dev, fromfile='file1',
                                                                      tofile='file2',
                                                                      lineterm='')]) > 0)
        except:
            pass
    return files_differ


def classify_linked_files(config, device: str, folder: str, devices_symlink_path=DEVICES_DEFAULT_PATH) -> Dict[
    Union[str, Tuple[str, str]], Set]:
    main_device = get_main_device(config)
    # last_sync is on main device time tmd
    last_sync = (config[CONFIG_FOLDERS_KEY_NAME].get(folder, dict())
                 .get("devices_sync", dict()).get(device, NEVER))
    t_diff = get_devices_time_difference(config, device, folder, devices_symlink_path)
    last_sync_d = last_sync + t_diff
    classified_files = defaultdict(set)

    files_info_main_device = get_tracked_files_info(config, main_device, folder, devices_symlink_path)
    files_info_device = get_tracked_files_info(config, device, folder, devices_symlink_path)
    for rpath in tqdm(itertools.chain(files_info_main_device.keys(), files_info_device.keys()),
                      desc="Classifying linked files..."):
        mtime_md = files_info_main_device.get(rpath, NO_FILE)
        mtime_d = files_info_device.get(rpath, NO_FILE)
        if mtime_d is NO_FILE and mtime_md > last_sync: classified_files[(NEW, main_device)].add(rpath); continue
        if mtime_md is NO_FILE and mtime_d > last_sync_d: classified_files[(NEW, device)].add(rpath); continue
        if mtime_d is NO_FILE and mtime_md < last_sync: classified_files[(DELETE, device)].add(rpath); continue
        if mtime_md is NO_FILE and mtime_d < last_sync_d: classified_files[(DELETE, main_device)].add(rpath); continue
        if mtime_md > last_sync and last_sync_d > mtime_d: classified_files[(CHANGED, main_device)].add(rpath); continue
        if mtime_d > last_sync_d and last_sync > mtime_md: classified_files[(CHANGED, device)].add(rpath); continue
        if mtime_d < last_sync_d and mtime_md < last_sync: classified_files[UNCHANGED].add(rpath); continue
        if mtime_d > last_sync_d and mtime_md > last_sync:
            classified_files[
                CONFLICT if diff_between_files(config, device, folder, rpath, devices_symlink_path) else UNCHANGED].add(
                rpath)
            continue
        classified_files[NOT_CLASSIFIED].add(rpath)

    direction = config[CONFIG_FOLDERS_KEY_NAME][folder]["devices_direction"][device]
    if direction == FROM_MAIN: classified_files = {k: v for k, v in classified_files.items() if
                                                   main_device == k[1] or k in [CONFLICT, UNCHANGED]}
    # Do not look at removed files when TO_MAIN direction is on otherwise after sync it will interpret that it
    # should eliminate from main but decisions should be taken in main if not BIDIRECTIONAL
    if direction == TO_MAIN:
        accepted_keys = [(NEW, device), (CHANGED, main_device), (CHANGED, device), CONFLICT, UNCHANGED]
        # changes in asymmetric device should be cast as conflicts
        if (CHANGED, device) in classified_files: classified_files[CONFLICT].update(
            classified_files.pop((CHANGED, device)))
        classified_files = {k: v for k, v in classified_files.items() if k in accepted_keys}
    print("")  # to add an enter and see the next line with the question y or n.
    return classified_files


# =============== Sync =============== #
def add_new_files(config, device_from, device_to, folder, classified_files: Dict[Union[str, Tuple[str, str]], Set],
                  devices_symlink_path=DEVICES_DEFAULT_PATH):
    assert device_from != device_to, "Devices should be different."
    path_to_folder_from = get_folder_root(config, device_from, folder, devices_symlink_path)
    path_to_folder_to = get_folder_root(config, device_to, folder, devices_symlink_path)
    for relative_path_to_file in tqdm(classified_files.get((NEW, device_from), set()),
                                      desc=f"Adding new files to device: {device_to}"):
        try:
            target = f"{path_to_folder_to}/{relative_path_to_file}"
            Path(os.path.dirname(target)).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f"{path_to_folder_from}/{relative_path_to_file}", target)
        except Exception as e:
            print(f"Some problem copying file {relative_path_to_file}")
            print(e)
    else:
        print("")  # to add an enter and see the next line with the question y or n.


def update_changed_files(config, device_from, device_to, folder,
                         classified_files: Dict[Union[str, Tuple[str, str]], Set],
                         devices_symlink_path=DEVICES_DEFAULT_PATH):
    assert device_from != device_to, "Devices should be different."
    path_to_folder_from = get_folder_root(config, device_from, folder, devices_symlink_path)
    path_to_folder_to = get_folder_root(config, device_to, folder, devices_symlink_path)
    for relative_path_to_file in tqdm(classified_files.get((CHANGED, device_from), set()),
                                      desc=f"Update files in device: {device_to}"):
        shutil.copyfile(f"{path_to_folder_from}/{relative_path_to_file}",
                        f"{path_to_folder_to}/{relative_path_to_file}")
    else:
        print("")  # to add an enter and see the next line with the question y or n.


def remove_deleted_files(config, device_from, device_to, folder,
                         classified_files: Dict[Union[str, Tuple[str, str]], Set],
                         devices_symlink_path=DEVICES_DEFAULT_PATH):
    assert device_from != device_to, "Devices should be different."
    path_to_folder_to = get_folder_root(config, device_to, folder, devices_symlink_path)
    for relative_path_to_file in tqdm(classified_files.get((DELETE, device_from), set()),
                                      desc=f"Remove files in device: {device_to}"):
        Path(f"{path_to_folder_to}/{relative_path_to_file}").unlink(missing_ok=True)
    else:
        print("")  # to add an enter and see the next line with the question y or n.


def append_conflicted_files(config, device, folder, classified_files: Dict[Union[str, Tuple[str, str]], Set],
                            devices_symlink_path=DEVICES_DEFAULT_PATH):
    main_device = get_main_device(config)
    path_to_folder_main = get_folder_root(config, main_device, folder, devices_symlink_path)
    path_to_folder_sec = get_folder_root(config, device, folder, devices_symlink_path)
    for relative_path_to_file in tqdm(classified_files.get(CONFLICT, set()), desc=f"Solving conflicts by append."):
        if get_file_ending(relative_path_to_file)[-1] in \
                config[CONFIG_FOLDERS_KEY_NAME][folder]["devices_append_strategy_to_file_endings"][device]:
            with open(f"{path_to_folder_sec}/{relative_path_to_file}", 'r') as ffrom:
                with open(f"{path_to_folder_main}/{relative_path_to_file}", 'a') as fto:
                    fto.write(f"\n\n==========================\n")
                    fto.write(f"DEVICE: {device}\n\n")
                    fto.write(ffrom.read())
    else:
        print("")  # to add an enter and see the next line with the question y or n.


def duplicate_conflicted_files(config, device, folder, classified_files: Dict[Union[str, Tuple[str, str]], Set],
                               devices_symlink_path=DEVICES_DEFAULT_PATH):
    main_device = get_main_device(config)
    path_to_folder_main = get_folder_root(config, main_device, folder, devices_symlink_path)
    path_to_folder_sec = get_folder_root(config, device, folder, devices_symlink_path)
    for relative_path_to_file in tqdm(classified_files.get(CONFLICT, set()), desc=f"Solving conflicts by duplicate."):
        filepath, ending = get_file_ending(relative_path_to_file)
        if ending not in config[CONFIG_FOLDERS_KEY_NAME][folder]["devices_append_strategy_to_file_endings"][device]:
            shutil.copyfile(f"{path_to_folder_sec}/{filepath}.{ending}",
                            f"{path_to_folder_main}/{filepath}_{device}_conflicted_copy.{ending}")
    else:
        print("")  # to add an enter and see the next line with the question y or n.


def update_sync_time(config, device: str, folder: str):
    config[CONFIG_FOLDERS_KEY_NAME][folder]["devices_sync"][device] = time.time()
    return config
