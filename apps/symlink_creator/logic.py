#!/usr/bin/env python3
"""Business logic for Symlink Creator - Pure functions, no GTK dependencies"""

import os
from pathlib import Path
from urllib.parse import unquote


def extract_paths_from_selection(text_data):
    """
    Extract file paths from drag-and-drop data.

    Args:
        text_data: Bytes or string from selection_data.get_data()

    Returns:
        List of file paths as strings
    """
    paths = []

    if not text_data:
        return paths

    try:
        text = text_data.decode('utf-8') if isinstance(text_data, bytes) else text_data
    except UnicodeDecodeError:
        return paths

    # Handle URI list format (file:// paths)
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('file://'):
            path = unquote(line[7:])
            if path:
                paths.append(path)
        else:
            if line:
                paths.append(line)

    return paths


def auto_fill_link_name(target_path):
    """
    Auto-fill link name from target filename.

    Args:
        target_path: Full path to target file/folder

    Returns:
        Base name suitable for symlink
    """
    if target_path:
        return os.path.basename(target_path.rstrip('/'))
    return ""


def validate_paths(target_path, destination_path):
    """
    Validate input paths before creating symlink.

    Args:
        target_path: Path to source file/folder
        destination_path: Path to destination folder

    Returns:
        Tuple of (is_valid: bool, errors: list of error messages)
    """
    errors = []

    if not target_path:
        errors.append("Target path is empty")
    elif not os.path.exists(target_path):
        errors.append(f"Target does not exist: {target_path}")

    if not destination_path:
        errors.append("Destination path is empty")
    elif not os.path.isdir(destination_path):
        errors.append(f"Destination is not a folder: {destination_path}")

    return (len(errors) == 0, errors)


def prepare_link_path(destination_path, link_name):
    """
    Prepare the full path for the new symlink.

    Args:
        destination_path: Destination folder path
        link_name: Name for the symlink

    Returns:
        Full path where symlink will be created
    """
    return os.path.join(destination_path, link_name)


def check_link_exists(link_path):
    """
    Check if a symlink or file already exists at path.

    Args:
        link_path: Path to check

    Returns:
        True if file/symlink exists (including broken symlinks)
    """
    return os.path.lexists(link_path)


def create_symlink(target_path, link_path):
    """
    Create a symbolic link.

    Args:
        target_path: Path to target (what link points to)
        link_path: Path where symlink will be created

    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    try:
        # Remove existing file/link if it exists
        if os.path.lexists(link_path):
            os.remove(link_path)

        # Create symlink
        os.symlink(target_path, link_path)
        return (True, None)

    except PermissionError as e:
        return (False, f"Permission denied: {e}")
    except OSError as e:
        return (False, f"OS error: {e}")
    except Exception as e:
        return (False, f"Unexpected error: {e}")


def verify_symlink_created(link_path, expected_target):
    """
    Verify a symlink was created correctly.

    Args:
        link_path: Path to the symlink
        expected_target: Expected target path

    Returns:
        Tuple of (valid: bool, message: str)
    """
    if not os.path.islink(link_path):
        return (False, "Path is not a symlink")

    actual_target = os.readlink(link_path)
    if actual_target != expected_target:
        return (False, f"Wrong target: {actual_target} != {expected_target}")

    return (True, "Symlink verified successfully")
