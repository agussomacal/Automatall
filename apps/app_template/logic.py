#!/usr/bin/env python3
"""Business logic for App Generator - Creates new app templates"""

import os
import re
from pathlib import Path
from typing import Tuple, List, Optional
from urllib.parse import urlparse


def validate_app_name(name: str) -> Tuple[bool, str]:
    """
    Validate and normalize application name.

    Args:
        name: User-provided app name

    Returns:
        Tuple of (is_valid, normalized_name_or_error)
    """
    if not name or not name.strip():
        return (False, "App name cannot be empty")

    # Strip whitespace and convert to lowercase
    name = name.strip().lower()

    # Replace spaces with underscores
    name = name.replace(' ', '_')

    # Remove invalid characters (keep alphanumeric and underscores)
    name = re.sub(r'[^a-z0-9_]', '', name)

    if not name:
        return (False, "App name contains no valid characters")

    if name.startswith('_') or name.endswith('_'):
        return (False, "App name cannot start or end with underscore")

    if '__' in name:
        return (False, "App name cannot contain consecutive underscores")

    if len(name) < 2:
        return (False, "App name must be at least 2 characters")

    if len(name) > 50:
        return (False, "App name must be less than 50 characters")

    return (True, name)


def validate_description(description: str) -> Tuple[bool, str]:
    """
    Validate app description input.

    Args:
        description: User-provided description

    Returns:
        Tuple of (is_valid, normalized_description_or_error)
    """
    if not description or not description.strip():
        return (False, "Description is required")

    desc = description.strip()

    # Limit length
    if len(desc) > 500:
        return (False, "Description must be less than 500 characters")

    return (True, desc)


def validate_category(category: str) -> Tuple[bool, str]:
    """
    Validate category input.

    Args:
        category: User-provided category

    Returns:
        Tuple of (is_valid, normalized_category_or_error)
    """
    if not category or not category.strip():
        return (False, "Category is required")

    category = category.strip().lower()

    # Accept any alphanumeric category with underscores
    if not re.match(r'^[a-z_]+$', category):
        return (False, "Category must contain only letters, numbers, and underscores")

    return (True, category)


def parse_tags(tags_string: str) -> List[str]:
    """
    Parse comma-separated tags string into list.

    Args:
        tags_string: Comma-separated tags

    Returns:
        List of cleaned tag strings
    """
    if not tags_string or not tags_string.strip():
        return []

    tags = []
    for tag in tags_string.split(','):
        tag = tag.strip().lower()
        if tag:
            # Clean tag name
            tag = re.sub(r'[^a-z0-9_-]', '', tag)
            tags.append(tag)

    return tags


def validate_icon_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate icon URL if provided.

    Args:
        url: URL to download icon from (optional)

    Returns:
        Tuple of (is_valid, message, error_code_or_none)
    """
    if not url or not url.strip():
        return (True, "No icon URL provided", None)

    url = url.strip()

    # Check if valid HTTP/HTTPS URL
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return (False, "URL must start with http:// or https://", "INVALID_SCHEME")

        if not parsed.netloc:
            return (False, "Invalid URL format", "INVALID_FORMAT")

        return (True, "URL is valid", None)

    except Exception as e:
        return (False, f"Error validating URL: {str(e)}", "URL_ERROR")


def download_icon(url: str, output_path: str) -> Tuple[bool, str]:
    """
    Download icon from URL.

    Args:
        url: Icon URL
        output_path: Where to save the icon

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import urllib.request

        # Set timeout and user agent
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            # Read content
            content = response.read()

            # Validate it's an image (basic check)
            if len(content) < 1024:
                return (False, "Downloaded file is too small to be an image")

            # Write to file
            with open(output_path, 'wb') as f:
                f.write(content)

            return (True, "")

    except urllib.error.HTTPError as e:
        return (False, f"HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return (False, f"URL error: {str(e.reason)}")
    except TimeoutError:
        return (False, "Download timed out")
    except Exception as e:
        return (False, f"Download failed: {str(e)}")


def generate_config_yaml(name: str, description: str, category: str, tags: List[str]) -> str:
    """
    Generate config.yaml content.

    Args:
        name: App name
        description: App description
        category: Category
        tags: List of tags

    Returns:
        YAML string content
    """
    # Build tags YAML array
    if tags:
        tags_yaml = ", ".join([f"'{tag}'" for tag in tags])
        tags_section = f"tags: [{tags_yaml}]"
    else:
        tags_section = "tags: []"

    return f"""# apps/{name}/config.yaml
name: "{name.replace('_', ' ').title()}"
description: "{description}"
module: "app"
icon: "./icon.png"
enabled: true
category: "{category}"
type: "gui"
version: "1.0"
author: ""
{tags_section}
"""


def create_app_structure(
        base_apps_dir: str,
        app_name: str,
        description: str,
        category: str,
        tags: List[str],
        icon_url: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Create complete app directory structure.

    Args:
        base_apps_dir: Path to apps/ directory
        app_name: Normalized app name
        description: App description
        category: App category
        tags: List of tags
        icon_url: Optional URL to download icon from

    Returns:
        Tuple of (success, message, app_path_or_error)
    """
    app_dir = Path(base_apps_dir) / app_name

    # Check if app already exists
    if app_dir.exists():
        return (False, f"App already exists: {app_name}", "")

    # Create directories
    try:
        app_dir.mkdir(parents=True)
        tests_dir = app_dir / "tests"
        tests_dir.mkdir()
    except PermissionError:
        return (False, f"Permission denied creating: {app_dir}", "")
    except Exception as e:
        return (False, f"Failed to create directory: {str(e)}", "")

    # Generate ONLY config.yaml with actual content
    config_content = generate_config_yaml(app_name, description, category, tags)

    # Write config.yaml
    config_path = app_dir / 'config.yaml'
    try:
        config_path.write_text(config_content)
    except Exception as e:
        return (False, f"Failed to write config.yaml: {str(e)}", "")

    # Create placeholder files (empty __init__.py only)
    placeholder_files = [
        '__init__.py',
        'logic.py',
        'dependencies.yaml',
        'app.py',
        'tests/__init__.py',
        f'tests/test_{app_name}.py'
    ]

    for filename in placeholder_files:
        try:
            file_path = app_dir / filename
            file_path.write_text('# Placeholder - Fill in your implementation\n')
        except Exception as e:
            return (False, f"Failed to write {filename}: {str(e)}", "")

    # Handle icon
    default_icon = app_dir / "icon.png"

    if icon_url:
        # Download from URL
        success, error = download_icon(icon_url, str(default_icon))
        if success:
            icon_msg = "✓ Icon downloaded from URL"
        else:
            # Create placeholder instead
            create_default_icon(str(default_icon))
            icon_msg = f"⚠ Icon download failed ({error}), placeholder created"
    else:
        # Create placeholder icon
        create_default_icon(str(default_icon))
        icon_msg = "✓ Default icon created"

    return (True, f"App template created successfully!\n{icon_msg}", str(app_dir))


def create_default_icon(icon_path: str) -> bool:
    """
    Create a simple default PNG icon (32x32 purple square).
    """
    try:
        # Try using Pillow if available (simplest)
        from PIL import Image
        img = Image.new('RGB', (32, 32), color=(109, 76, 255))  # Purple #6d4aff
        img.save(icon_path)
        return True
    except ImportError:
        # Fallback: create simple placeholder text file
        txt_path = icon_path.replace('.png', '.txt')
        with open(txt_path, 'w') as f:
            f.write("Add your icon.png here\nPurple #6d4aff recommended\nSize: 32x32 or larger")
        return False