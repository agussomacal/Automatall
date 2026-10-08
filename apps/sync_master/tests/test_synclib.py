import os
import shutil
import time
import unittest
from functools import partial
from pathlib import Path

from NoServerSync.synclib import CONFIG_FILENAME, init_sync_tracker, load_config, CONFIG_KEYS, add_device, DEVICE_ADDED, \
    CONFIG_DEVICES_KEY_NAME, DEVICE_EXISTS, get_connected_devices, USB, COMPUTER, set_main_device, CONFIG_SYNC_KEY_NAME, \
    set_conflict_append_strategy_to_file_endings, DEFAULT_TEXT_FILES, add_tracking_to_folder, FOLDER_TRACKING_ADDED, \
    FOLDER_TRACKING_ALREADY_ADDED, CONFIG_FOLDERS_KEY_NAME, FOLDER_NOT_REACHABLE, add_sync_folder_settings, \
    IGNORED_FILE_ENDINGS, get_tracked_files_info, classify_linked_files, NEW, CONFLICT, add_new_files, \
    update_changed_files, remove_deleted_files, append_conflicted_files, duplicate_conflicted_files, update_sync_time, \
    UNCHANGED, save_config, CHANGED, DEVICES_SYMLINK_FOLDER_NAME, TO_MAIN, FROM_MAIN, BIDIRECTIONAL

computer_device = "computer"
usb_device = "usb"
folder_name = "yoda"
computer_relative_path2folder = f"/subfolder/{folder_name}"
usb_relative_path2folder = f"/{folder_name}"
ignored_file_endings = "txt"

TEST_PATH = f"{Path(os.path.dirname(__file__))}/temp"
TEST_DEVICES_DEFAULT_PATH = Path(f"{TEST_PATH}/{DEVICES_SYMLINK_FOLDER_NAME}/")
TEST_DEVICES_DEFAULT_PATH.mkdir(exist_ok=True, parents=True)
DEVICES_DEFAULT_PATH = TEST_DEVICES_DEFAULT_PATH

TEST_CONFIG_FOLDER = TEST_DEVICES_DEFAULT_PATH
TEST_CONFIG_PATH = f"{TEST_CONFIG_FOLDER}/{CONFIG_FILENAME}"

TEST_COMPUTER_PATH = f"{TEST_PATH}/{computer_device}"
TEST_USB_PATH = f"{TEST_PATH}/{usb_device}"
TEST_COMPUTER_FOLDER_YODA_PATH = f"{TEST_COMPUTER_PATH}/{computer_relative_path2folder}"
TEST_USB_FOLDER_YODA_PATH = f"{TEST_USB_PATH}/{usb_relative_path2folder}"

add_tracking_to_folder = partial(add_tracking_to_folder, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
add_device = partial(add_device, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
get_tracked_files_info = partial(get_tracked_files_info, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
classify_linked_files = partial(classify_linked_files, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
add_new_files = partial(add_new_files, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
update_changed_files = partial(update_changed_files, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
remove_deleted_files = partial(remove_deleted_files, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
append_conflicted_files = partial(append_conflicted_files, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
duplicate_conflicted_files = partial(duplicate_conflicted_files, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)


def create_test_folders_and_files():
    # prepare test
    shutil.rmtree(TEST_PATH) if os.path.exists(TEST_PATH) else None
    Path(TEST_PATH).mkdir(parents=True, exist_ok=True)
    Path(TEST_CONFIG_FOLDER).mkdir(parents=True, exist_ok=True)
    # create folder devices
    Path(TEST_COMPUTER_PATH).mkdir(parents=True, exist_ok=True)
    Path(TEST_USB_PATH).mkdir(parents=True, exist_ok=True)
    # create folder and files
    # computer
    Path(TEST_COMPUTER_FOLDER_YODA_PATH).mkdir(parents=True, exist_ok=True)
    Path(f"{TEST_COMPUTER_FOLDER_YODA_PATH}/file.md").touch()
    Path(f"{TEST_COMPUTER_FOLDER_YODA_PATH}/file.txt").touch()
    # usb
    Path(TEST_USB_FOLDER_YODA_PATH).mkdir(parents=True, exist_ok=True)
    Path(f"{TEST_USB_FOLDER_YODA_PATH}/file_usb.md").touch()
    Path(f"{TEST_USB_FOLDER_YODA_PATH}/file_mod.md").touch()
    Path(f"{TEST_COMPUTER_FOLDER_YODA_PATH}/file_mod.md").touch()


def modify_file(device_path, filename, text):
    with open(f"{device_path}/{filename}", "a") as f:
        f.write(text)


def read_file(device_path, filename):
    with open(f"{device_path}/{filename}", "r") as f:
        return f.read()


class TestSyncLib(unittest.TestCase):
    def setUp(self) -> None:
        create_test_folders_and_files()

    def test_init_sync_tracker(self):
        assert not os.path.exists(TEST_CONFIG_PATH)
        init_sync_tracker(path=TEST_CONFIG_PATH)
        assert os.path.exists(TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        assert isinstance(config, dict)
        assert set(CONFIG_KEYS) == set(config.keys())

    def test_add_new_device(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)

        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        assert msg == DEVICE_ADDED
        assert len(config[CONFIG_DEVICES_KEY_NAME]) == 1
        assert set(config[CONFIG_DEVICES_KEY_NAME].keys()) == {computer_device}
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        assert msg == DEVICE_ADDED
        assert len(config[CONFIG_DEVICES_KEY_NAME]) == 2
        assert set(config[CONFIG_DEVICES_KEY_NAME].keys()) == {computer_device, usb_device}
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        assert msg == DEVICE_EXISTS
        assert len(config[CONFIG_DEVICES_KEY_NAME]) == 2
        assert set(config[CONFIG_DEVICES_KEY_NAME].keys()) == {computer_device, usb_device}

    def test_connected_devices(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        connected_devices = get_connected_devices(config)
        assert set(connected_devices) == {"usb", "computer"}

    def test_set_main_device(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)
        assert config[CONFIG_SYNC_KEY_NAME]["main_device"] == computer_device

    def test_add_folder(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        assert msg == FOLDER_TRACKING_ADDED
        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        assert msg == FOLDER_TRACKING_ALREADY_ADDED
        assert set(config[CONFIG_FOLDERS_KEY_NAME].keys()) == {folder_name}

        shutil.rmtree(TEST_COMPUTER_FOLDER_YODA_PATH) if os.path.exists(TEST_COMPUTER_FOLDER_YODA_PATH) else None
        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        assert set(config[CONFIG_FOLDERS_KEY_NAME][folder_name]["ignored_file_endings"]) == {ignored_file_endings}
        save_config(config, path=TEST_CONFIG_PATH)
        assert msg == FOLDER_NOT_REACHABLE

    def test_add_sync_folder_settings(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)

        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        assert set(config[CONFIG_FOLDERS_KEY_NAME][folder_name]["ignored_file_endings"]) == {ignored_file_endings}

    def test_files_info(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)

        files_info = get_tracked_files_info(config, device_name=computer_device, folder=folder_name)
        assert len(files_info) == 2

    def test_classify_linked_files(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)

        add_tracking_to_folder(config, device_name=usb_device, direction=BIDIRECTIONAL,
                               append_strategy_to_file_endings=[], relative_path=usb_relative_path2folder)

        # test --- classify_linked_files
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert len(classified_files[(NEW, computer_device)]) == 1
        assert len(classified_files[(NEW, usb_device)]) == 1
        assert len(classified_files[UNCHANGED]) == 1

    def test_classify_linked_files_to_main(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)

        add_tracking_to_folder(config, device_name=usb_device, direction=TO_MAIN,
                               append_strategy_to_file_endings=[], relative_path=usb_relative_path2folder)

        # test --- classify_linked_files
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert (NEW, computer_device) not in classified_files
        assert len(classified_files[(NEW, usb_device)]) == 1
        assert UNCHANGED in classified_files

    def test_classify_linked_files_from_main(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        add_tracking_to_folder(config, device_name=usb_device, direction=FROM_MAIN,
                               append_strategy_to_file_endings=[], relative_path=usb_relative_path2folder)

        # test --- classify_linked_files
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert len(classified_files[(NEW, computer_device)]) == 1
        assert (NEW, usb_device) not in classified_files
        assert UNCHANGED in classified_files

    def test_sync(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        add_tracking_to_folder(config, device_name=usb_device, direction=BIDIRECTIONAL,
                               append_strategy_to_file_endings=[], relative_path=usb_relative_path2folder)
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)

        add_new_files(config, computer_device, usb_device, folder_name, classified_files)
        add_new_files(config, usb_device, computer_device, folder_name, classified_files)
        update_changed_files(config, computer_device, usb_device, folder_name, classified_files)
        update_changed_files(config, usb_device, computer_device, folder_name, classified_files)
        remove_deleted_files(config, computer_device, usb_device, folder_name, classified_files)
        remove_deleted_files(config, usb_device, computer_device, folder_name, classified_files)
        append_conflicted_files(config, usb_device, folder_name, classified_files)
        duplicate_conflicted_files(config, usb_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert (NEW, computer_device) not in classified_files
        assert (NEW, usb_device) not in classified_files
        assert CONFLICT not in classified_files
        assert len(classified_files[UNCHANGED]) == 3

    def test_sync_to_main(self):
        # weird thing: do not put inmediately after test_sync or all test fail
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        add_tracking_to_folder(config, device_name=usb_device, direction=TO_MAIN,
                               append_strategy_to_file_endings=[], relative_path=usb_relative_path2folder)
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)

        add_new_files(config, computer_device, usb_device, folder_name, classified_files)
        add_new_files(config, usb_device, computer_device, folder_name, classified_files)
        update_changed_files(config, computer_device, usb_device, folder_name, classified_files)
        update_changed_files(config, usb_device, computer_device, folder_name, classified_files)
        remove_deleted_files(config, computer_device, usb_device, folder_name, classified_files)
        remove_deleted_files(config, usb_device, computer_device, folder_name, classified_files)
        append_conflicted_files(config, usb_device, folder_name, classified_files)
        duplicate_conflicted_files(config, usb_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert (NEW, computer_device) not in classified_files
        assert (NEW, usb_device) not in classified_files
        assert CONFLICT not in classified_files
        assert UNCHANGED in classified_files

    def test_save_load(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        add_tracking_to_folder(config, device_name=usb_device, direction=BIDIRECTIONAL,
                               append_strategy_to_file_endings=[], relative_path=usb_relative_path2folder)
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)

        add_new_files(config, computer_device, usb_device, folder_name, classified_files)
        add_new_files(config, usb_device, computer_device, folder_name, classified_files)
        update_changed_files(config, computer_device, usb_device, folder_name, classified_files)
        update_changed_files(config, usb_device, computer_device, folder_name, classified_files)
        remove_deleted_files(config, computer_device, usb_device, folder_name, classified_files)
        remove_deleted_files(config, usb_device, computer_device, folder_name, classified_files)
        append_conflicted_files(config, usb_device, folder_name, classified_files)
        duplicate_conflicted_files(config, usb_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)

        save_config(config, path=TEST_CONFIG_PATH)
        new_config = load_config(path=TEST_CONFIG_PATH)
        assert new_config == config

        # ------------------------- #
        # prepare test --- classify_linked_files
        Path(f"{TEST_USB_FOLDER_YODA_PATH}/file_usb2.md").touch()
        Path(f"{TEST_USB_FOLDER_YODA_PATH}/file.md").touch()

        # test --- classify_linked_files
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert len(classified_files[(NEW, usb_device)]) == 1
        assert len(classified_files[(CHANGED, usb_device)]) == 1
        assert len(classified_files[CONFLICT]) == 0

    def test_set_conflict_append_strategy_to_file_endings(self):
        # weird thing: do not put inmediately after test_sync or all test fail
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        msg, config = add_device(config, name=computer_device, mount_path=TEST_COMPUTER_PATH, device_type=COMPUTER)
        msg, config = add_device(config, name=usb_device, mount_path=TEST_USB_PATH, device_type=USB)
        config = set_main_device(config, computer_device)

        msg, config = add_tracking_to_folder(config, device_name=computer_device, direction=BIDIRECTIONAL,
                                             append_strategy_to_file_endings=[],
                                             relative_path=computer_relative_path2folder)
        config = add_sync_folder_settings(IGNORED_FILE_ENDINGS, config, folder_name, ignored_file_endings)
        add_tracking_to_folder(config, device_name=usb_device, direction=TO_MAIN,
                               append_strategy_to_file_endings=["md"], relative_path=usb_relative_path2folder)
        assert set(
            config[CONFIG_FOLDERS_KEY_NAME][folder_name]["devices_append_strategy_to_file_endings"][usb_device]) == {
                   "md"}

        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        add_new_files(config, computer_device, usb_device, folder_name, classified_files)
        add_new_files(config, usb_device, computer_device, folder_name, classified_files)
        update_changed_files(config, computer_device, usb_device, folder_name, classified_files)
        update_changed_files(config, usb_device, computer_device, folder_name, classified_files)
        remove_deleted_files(config, computer_device, usb_device, folder_name, classified_files)
        remove_deleted_files(config, usb_device, computer_device, folder_name, classified_files)
        append_conflicted_files(config, usb_device, folder_name, classified_files)
        duplicate_conflicted_files(config, usb_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)

        # Modify same file in both devices
        time.sleep(0.01)
        modify_file(device_path=TEST_COMPUTER_FOLDER_YODA_PATH, filename="file_mod.md", text="compu text")
        time.sleep(0.01)
        modify_file(device_path=TEST_USB_FOLDER_YODA_PATH, filename="file_mod.md", text="usb text")
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert CONFLICT in classified_files
        assert len(classified_files[CONFLICT]) == 1
        assert len(classified_files[UNCHANGED]) == 1

        append_conflicted_files(config, usb_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)

        compu_file = read_file(device_path=TEST_COMPUTER_FOLDER_YODA_PATH, filename="file_mod.md")
        usb_file = read_file(device_path=TEST_USB_FOLDER_YODA_PATH, filename="file_mod.md")
        assert compu_file != usb_file
        assert len(usb_file.split("\n")) == 1
        assert len(compu_file.split("\n")) == 6

        # Modify file only in external device
        time.sleep(0.01)
        modify_file(device_path=TEST_USB_FOLDER_YODA_PATH, filename="file_mod.md", text="\nusb text2")
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert CONFLICT in classified_files
        assert len(classified_files[CONFLICT]) == 1
        assert len(classified_files[UNCHANGED]) == 1

        append_conflicted_files(config, usb_device, folder_name, classified_files)
        duplicate_conflicted_files(config, usb_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)
        compu_file = read_file(device_path=TEST_COMPUTER_FOLDER_YODA_PATH, filename="file_mod.md")
        usb_file = read_file(device_path=TEST_USB_FOLDER_YODA_PATH, filename="file_mod.md")
        assert compu_file != usb_file
        assert len(usb_file.split("\n")) == 2
        assert len(compu_file.split("\n")) == 12

        # Modify file only in main device
        time.sleep(0.01)
        modify_file(device_path=TEST_COMPUTER_FOLDER_YODA_PATH, filename="file_mod.md", text="\ncompu text3")
        classified_files = classify_linked_files(config, device=usb_device, folder=folder_name)
        assert CONFLICT not in classified_files
        assert len(classified_files[(CHANGED, computer_device)]) == 1
        assert len(classified_files[UNCHANGED]) == 1

        append_conflicted_files(config, usb_device, folder_name, classified_files)
        duplicate_conflicted_files(config, usb_device, folder_name, classified_files)
        update_changed_files(config, computer_device, usb_device, folder_name, classified_files)
        update_changed_files(config, usb_device, computer_device, folder_name, classified_files)
        config = update_sync_time(config, device=usb_device, folder=folder_name)
        compu_file = read_file(device_path=TEST_COMPUTER_FOLDER_YODA_PATH, filename="file_mod.md")
        usb_file = read_file(device_path=TEST_USB_FOLDER_YODA_PATH, filename="file_mod.md")
        assert compu_file == usb_file
        assert len(usb_file.split("\n")) == 13
        assert len(compu_file.split("\n")) == 13
