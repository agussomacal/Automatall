import os
import unittest
from functools import partial

import NoServerSync.cmd_frontend as cmd_frontend
from NoServerSync.synclib import init_sync_tracker, load_config, CONFIG_KEYS, CONFIG_DEVICES_KEY_NAME, \
    CONFIG_SYNC_KEY_NAME, \
    CONFIG_FOLDERS_KEY_NAME, save_config, COMPUTER, BIDIRECTIONAL, FOLDER_SETTINGS
from NoServerSync.tests.test_synclib import create_test_folders_and_files, computer_device, \
    TEST_COMPUTER_PATH, ignored_file_endings, TEST_COMPUTER_FOLDER_YODA_PATH, folder_name, usb_device, TEST_USB_PATH, \
    TEST_USB_FOLDER_YODA_PATH, TEST_DEVICES_DEFAULT_PATH, TEST_CONFIG_PATH


def forced_input(prompt, answer):
    a = next(answer)
    print(prompt, a)
    return a


cmd_frontend.add_new_device = partial(cmd_frontend.add_new_device, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
cmd_frontend.add_folder = partial(cmd_frontend.add_folder, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)
cmd_frontend.sync_folder = partial(cmd_frontend.sync_folder, devices_symlink_path=TEST_DEVICES_DEFAULT_PATH)


class TestCMDFrontEnd(unittest.TestCase):
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
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        assert len(config[CONFIG_DEVICES_KEY_NAME]) == 1
        assert set(config[CONFIG_DEVICES_KEY_NAME].keys()) == {computer_device}

    def test_add_new_device_no_input(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        config = cmd_frontend.add_new_device(config, device_name=computer_device, device_type=COMPUTER,
                                             mount_path=TEST_COMPUTER_PATH)
        assert len(config[CONFIG_DEVICES_KEY_NAME]) == 1
        assert set(config[CONFIG_DEVICES_KEY_NAME].keys()) == {computer_device}

    def test_define_main_device(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        config = cmd_frontend.define_main_device(config)
        assert config[CONFIG_SYNC_KEY_NAME]["main_device"] == computer_device

    # def test_define_strategy_for_conflicts(self):
    #     init_sync_tracker(path=TEST_CONFIG_PATH)
    #     config = load_config(path=TEST_CONFIG_PATH)
    #     cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
    #     config = cmd_frontend.add_new_device(config)
    #     config = cmd_frontend.define_main_device(config)
    #     # ----- ----- test ----- ----- #
    #     # modify input function to give programmatically the answers
    #     cmd_frontend.input = partial(forced_input, answer=(a for a in ("md",)))
    #     
    #     assert config[CONFIG_SYNC_KEY_NAME]["append_strategy_to_file_endings"] == ["md"]

    def test_add_folder(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)

        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        cmd_frontend.input = partial(
            forced_input,
            answer=(a for a in (TEST_COMPUTER_FOLDER_YODA_PATH, 0, "md", "", ignored_file_endings, "", "")))
        config = cmd_frontend.add_folder(config)
        assert set(config[CONFIG_FOLDERS_KEY_NAME].keys()) == {folder_name}
        assert set(config[CONFIG_FOLDERS_KEY_NAME][folder_name]["ignored_file_endings"]) == {ignored_file_endings}
        assert config[CONFIG_FOLDERS_KEY_NAME][folder_name]["devices_append_strategy_to_file_endings"][
                   computer_device] == ["md"]

    def test_add_folder_no_input(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)

        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        config = cmd_frontend.add_folder(config, device_name=computer_device, path=TEST_COMPUTER_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        assert set(config[CONFIG_FOLDERS_KEY_NAME].keys()) == {folder_name}
        assert set(config[CONFIG_FOLDERS_KEY_NAME][folder_name]["ignored_file_endings"]) == {ignored_file_endings}

    def test_add_new_device_2(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)
        config = cmd_frontend.add_folder(config, device_name=computer_device, path=TEST_COMPUTER_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        cmd_frontend.input = partial(forced_input, answer=(a for a in (usb_device, TEST_USB_PATH, 1, 0)))
        config = cmd_frontend.add_new_device(config)
        assert len(config[CONFIG_DEVICES_KEY_NAME]) == 2
        assert set(config[CONFIG_DEVICES_KEY_NAME].keys()) == {computer_device, usb_device}

    def test_add_folder_2(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)
        config = cmd_frontend.add_folder(config, device_name=computer_device, path=TEST_COMPUTER_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        cmd_frontend.input = partial(forced_input, answer=(a for a in (usb_device, TEST_USB_PATH, 1, 0)))
        config = cmd_frontend.add_new_device(config)
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        config = cmd_frontend.add_folder(config, device_name=usb_device, path=TEST_USB_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        assert set(config[CONFIG_DEVICES_KEY_NAME][usb_device]["tracked_folders"]) == {folder_name}
        assert set(config[CONFIG_FOLDERS_KEY_NAME].keys()) == {folder_name}
        assert set(config[CONFIG_FOLDERS_KEY_NAME][folder_name]["ignored_file_endings"]) == {ignored_file_endings}

    def test_diff_sync_folder(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (usb_device, TEST_USB_PATH, 1, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.add_folder(config, device_name=computer_device, path=TEST_COMPUTER_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        config = cmd_frontend.add_folder(config, device_name=usb_device, path=TEST_USB_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        assert len(list(os.walk(TEST_COMPUTER_FOLDER_YODA_PATH))[-1][-1]) == 3
        assert len(list(os.walk(TEST_USB_FOLDER_YODA_PATH))[-1][-1]) == 2
        cmd_frontend.input = partial(forced_input, answer=(a for a in ("n", "n", "n")))
        config = cmd_frontend.sync_folder(config)
        assert len(list(os.walk(TEST_COMPUTER_FOLDER_YODA_PATH))[-1][-1]) == 3
        assert len(list(os.walk(TEST_USB_FOLDER_YODA_PATH))[-1][-1]) == 2

    def test_sync_folder(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (usb_device, TEST_USB_PATH, 1, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.add_folder(config, device_name=computer_device, path=TEST_COMPUTER_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        config = cmd_frontend.add_folder(config, device_name=usb_device, path=TEST_USB_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        # ----- ----- test ----- ----- #
        # modify input function to give programmatically the answers
        assert len(list(os.walk(TEST_COMPUTER_FOLDER_YODA_PATH))[-1][-1]) == 3
        assert len(list(os.walk(TEST_USB_FOLDER_YODA_PATH))[-1][-1]) == 2
        cmd_frontend.input = partial(forced_input, answer=(a for a in ("y", "y", "y")))
        config = cmd_frontend.sync_folder(config, mode=cmd_frontend.SYNC)
        assert len(list(os.walk(TEST_COMPUTER_FOLDER_YODA_PATH))[-1][-1]) == 4
        assert len(list(os.walk(TEST_USB_FOLDER_YODA_PATH))[-1][-1]) == 3

    def test_save_load(self):
        init_sync_tracker(path=TEST_CONFIG_PATH)
        config = load_config(path=TEST_CONFIG_PATH)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (computer_device, TEST_COMPUTER_PATH, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.define_main_device(config)
        cmd_frontend.input = partial(forced_input, answer=(a for a in (usb_device, TEST_USB_PATH, 1, 0)))
        config = cmd_frontend.add_new_device(config)
        config = cmd_frontend.add_folder(config, device_name=computer_device, path=TEST_COMPUTER_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        config = cmd_frontend.add_folder(config, device_name=usb_device, path=TEST_USB_FOLDER_YODA_PATH,
                                         direction=BIDIRECTIONAL, append_strategy_to_file_endings=["md"],
                                         folder_settings=dict(zip(FOLDER_SETTINGS, ("", ignored_file_endings, "", ""))))
        cmd_frontend.input = partial(forced_input, answer=(a for a in ("y", "y", "y")))
        config = cmd_frontend.sync_folder(config, mode=cmd_frontend.SYNC)

        save_config(config, path=TEST_CONFIG_PATH)
        new_config = load_config(path=TEST_CONFIG_PATH)
        assert config == new_config

    def teardown_method(self, method):
        # This method is being called after each test case, and it will revert input back to original function
        cmd_frontend.input = input
