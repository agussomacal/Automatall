import os
from os.path import relpath
from pathlib import Path
from typing import List

from NoServerSync.synclib import add_device, CONFIG_DEVICES_KEY_NAME, get_connected_devices, set_main_device, \
    CONFIG_SYNC_KEY_NAME, \
    set_conflict_append_strategy_to_file_endings, add_tracking_to_folder, add_sync_folder_settings, \
    classify_linked_files, NEW, CONFLICT, add_new_files, \
    update_changed_files, remove_deleted_files, append_conflicted_files, duplicate_conflicted_files, update_sync_time, \
    UNCHANGED, CHANGED, DEVICE_TYPES, get_main_device, FOLDER_SETTINGS, NOT_CLASSIFIED, DELETE, DEVICES_DEFAULT_PATH, \
    DEVICE_DIRECTIONS, save_config

PRINT_NEW_TASK = "\n_________________________"


def choose_from_list(what, list_of):
    print(f"Choose a {what} between:")
    [print("\t", i, element) for i, element in enumerate(list_of)]
    chosen = list_of[int(input(f"{what} number: "))] if len(list_of) > 1 else list_of[0]
    print(f"Chosen {what}:", chosen)
    return chosen


def choose_device_from_list(list_of_devices):
    return choose_from_list("device", list_of_devices)


def choose_folder_from_list(list_of_folders):
    return choose_from_list("folder", list_of_folders)


def choose_device_from_config(config):
    return choose_device_from_list(list(config[CONFIG_DEVICES_KEY_NAME].keys()))


def add_new_device(config, device_name=None, mount_path=None, device_type=None, device_direction=None,
                   devices_symlink_path=DEVICES_DEFAULT_PATH):
    print(PRINT_NEW_TASK)
    print(f"Add new device (already existing devices {list(config[CONFIG_DEVICES_KEY_NAME].keys())}):")
    device_name = input("\tDevice name (ex: 'computer'): ") if device_name is None else device_name
    mount_path = input("\tMount path (ex: path to /home): ") if mount_path is None else mount_path
    device_type = choose_from_list(what="Device type", list_of=DEVICE_TYPES) if device_type is None else device_type
    msg, config = add_device(config, name=device_name, mount_path=mount_path, device_type=device_type,
                             devices_symlink_path=devices_symlink_path)
    print(msg)
    return config


def define_main_device(config):
    print(PRINT_NEW_TASK)
    print("Define main device:")
    device_name = choose_device_from_list(get_connected_devices(config))
    set_main_device(config, device_name)
    print("Main device set successfully:", device_name)
    return config


def add_folder(config, device_name=None, path=None, direction=None, append_strategy_to_file_endings=None,
               folder_settings: dict = None, devices_symlink_path=DEVICES_DEFAULT_PATH):
    print(PRINT_NEW_TASK)
    print("Add new folder:")
    main_device = get_main_device(config)

    # check for DEVICE
    if device_name is None:
        device_name = choose_device_from_list(get_connected_devices(config) + [main_device])
        print("Already tracked folders in device: ",
              list(config[CONFIG_DEVICES_KEY_NAME][device_name]["tracked_folders"]))
    else:
        assert device_name in config[CONFIG_DEVICES_KEY_NAME].keys(), f"Device {device_name} not added in config."

    # check for PATH
    if path is None:
        path = input("Path to folder: ")
    else:
        assert os.path.exists(path), f"Path {path} not reachable."

    # check for DIRECTION
    direction = choose_from_list(what="Device direction", list_of=DEVICE_DIRECTIONS) if direction is None else direction

    # check for append_strategy_to_file_endings
    if append_strategy_to_file_endings is None:
        print(PRINT_NEW_TASK)
        print("Define strategy for conflicts:")
        append_strategy_to_file_endings = list(input(
            "List the file endings (ex: 'txt md') whose conflict strategy should be APPEND on file instead of duplicate file: ").split(
            " "))
    else:
        assert isinstance(append_strategy_to_file_endings, list), \
            f"append_strategy_to_file_endings should be of type list."

    # Add new tracked folder
    relative_path = os.path.relpath(path, config[CONFIG_DEVICES_KEY_NAME][device_name]["path"])
    folder = relative_path.split("/")[-1]

    tracked_folders = (set(config[CONFIG_DEVICES_KEY_NAME][device_name]["tracked_folders"])
                       .union(config[CONFIG_DEVICES_KEY_NAME][main_device]["tracked_folders"]))

    msg, config = add_tracking_to_folder(config=config, device_name=device_name, relative_path=relative_path,
                                         direction=direction,
                                         append_strategy_to_file_endings=append_strategy_to_file_endings,
                                         devices_symlink_path=devices_symlink_path)
    print(msg, "\t\trelative path:", relative_path)
    print("Linked folders", config[CONFIG_DEVICES_KEY_NAME][device_name]["tracked_folders"])

    # if folder not in tracked_folders:
    print("\tDefine folder settings")
    for setting in FOLDER_SETTINGS:
        new_setting = input(f"\t\tGive a list of {setting.upper()} separated by spaces: ") \
            if folder_settings is None else folder_settings[setting]
        if new_setting != "":
            config = add_sync_folder_settings(setting, config, folder, *new_setting.split(" "))


    return config


def check_not_yet_synced_folder(config, device, folder, devices_symlink_path: Path = DEVICES_DEFAULT_PATH):
    classified_files = classify_linked_files(config, device, folder, devices_symlink_path)
    if set(classified_files.keys()).issubset({UNCHANGED, NOT_CLASSIFIED}):
        return False
    return True


def print_list_of_modifications(files_relative_paths: List[str], num_cols=2):
    row_length = max(map(len, files_relative_paths)) + 1
    for i, relative_path_to_file in enumerate(files_relative_paths):
        print(f"\t- ({i})", relative_path_to_file,
              end="\n" if i % num_cols == (num_cols - 1) else " " * (row_length - len(relative_path_to_file)))
    print("")


DIFF = "diff"
SYNC = "sync"


def sync_folder(config, num_cols=2, mode=DIFF, folder=None, devices_symlink_path: Path = DEVICES_DEFAULT_PATH):
    print(PRINT_NEW_TASK)
    print(mode)
    try:
        device = get_connected_devices(config)[0]  # first or only connected device
    except IndexError:
        raise Exception("No device connected.")
    main_device = get_main_device(config)
    if folder is None:
        shared_folders = config[CONFIG_DEVICES_KEY_NAME][device]["tracked_folders"]
        shared_folders = set(shared_folders).intersection(
            config[CONFIG_DEVICES_KEY_NAME][main_device]["tracked_folders"])
        shared_folders = [folder for folder in shared_folders if
                          check_not_yet_synced_folder(config, device, folder, devices_symlink_path)]
        folder = choose_folder_from_list(shared_folders)
    if folder not in config[CONFIG_DEVICES_KEY_NAME][device]["tracked_folders"]:
        print(f"Folder {folder} not tracked in device {device}.")
    else:
        print("for folder: ", folder)

        classified_files = classify_linked_files(config, device, folder, devices_symlink_path)

        # NEW files transfer
        print(f"NEW files in: {main_device}")
        modifs = classified_files.get((NEW, main_device), list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Transfer files to {device}? [y/n]"):
                add_new_files(config, main_device, device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No new files detected in {main_device}.")

        print(f"NEW files in: {device}")
        modifs = classified_files.get((NEW, device), list())
        if len(modifs) > 0:
            print_list_of_modifications(classified_files.get((NEW, device), list()), num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Transfer files to {main_device}? [y/n]"):
                add_new_files(config, device, main_device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No new files detected in {device}.")

        # CHANGED files transfer
        print(f"CHANGED files in: {main_device}")
        modifs = classified_files.get((CHANGED, main_device), list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Update files in {device}? [y/n]"):
                update_changed_files(config, main_device, device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No changes detected in {main_device}.")

        print(f"CHANGED files in: {device}")
        modifs = classified_files.get((CHANGED, device), list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Update files in {main_device}? [y/n]"):
                update_changed_files(config, device, main_device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No changes detected in {device}.")

        # REMOVED files transfer
        print(f"REMOVED files in: {main_device}")
        modifs = classified_files.get((DELETE, main_device), list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Remove files in {device}? [y/n]"):
                remove_deleted_files(config, device, main_device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No deleted files detected in {main_device}.")

        print(f"REMOVED files in: {device}")
        modifs = classified_files.get((DELETE, device), list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Remove files in {main_device}? [y/n]"):
                remove_deleted_files(config, device, main_device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No deleted files detected in {device}.")

        print(f"CONFLICTED files:")
        modifs = classified_files.get(CONFLICT, list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
            if mode == SYNC and "y" == input(f"Solve conflicted files? [y/n]"):
                append_conflicted_files(config, device, folder, classified_files, devices_symlink_path)
                duplicate_conflicted_files(config, device, folder, classified_files, devices_symlink_path)
        else:
            print(f"No conflicted files detected.")

        print(f"NOT CLASSIFIED files:")
        modifs = classified_files.get(NOT_CLASSIFIED, list())
        if len(modifs) > 0:
            print_list_of_modifications(modifs, num_cols=num_cols)
        else:
            print(f"No unclassified files detected.")
        if mode==SYNC:
            config = update_sync_time(config, device=device, folder=folder)
            save_config(config)
    return config
