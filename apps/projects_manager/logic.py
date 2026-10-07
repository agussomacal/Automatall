#!/usr/bin/env python3
"""Core logic for Projects Manager"""

import os
import json
import yaml
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from datetime import datetime


class ProjectsManagerLogic:
    """Handles project folder creation, management and status tracking"""

    VALID_STATUSES = [
        "inactive",
        "developing",
        "preprint",
        "in_review",
        "answering_review",
        "published",
    ]

    STATUS_LABELS = {
        "inactive": "Inactive",
        "developing": "Developing",
        "preprint": "Preprint",
        "in_review": "In Review",
        "answering_review": "Answering Review",
        "published": "Published",
    }

    STATUS_COLORS = {
        "developing": "#6d4aff",  # Purple
        "in_review": "#f39c12",  # Orange
        "answering_review": "#e67e22",  # Dark Orange
        "preprint": "#3498db",  # Blue
        "published": "#2ecc71",  # Green
        "inactive": "#95a5a6"  # Gray
    }

    PROJECT_SUBFOLDERS = [
        "Bibliography",
        "Code",
        "Notes",
        "Boards",
        "Article",
        "Blog"
    ]

    def __init__(self, settings_file: str = None):
        self.settings_file = Path(settings_file or "settings.yaml")
        self.settings = self._load_settings()
        self.default_folder = Path(os.path.expanduser(
            self.settings.get("default_project_folder", "~/Documents/Projects")
        ))

    def _load_settings(self) -> Dict:
        """Load settings from YAML file"""
        if not self.settings_file.exists():
            return {
                "default_project_folder": "~/Documents/Projects",
                "auto_save_settings": True,
                "status_tracking": True,
                "default_status": "developing"
            }

        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _save_settings(self) -> bool:
        """Save settings to YAML file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.settings, f, default_flow_style=False)
            return True
        except Exception:
            return False

    def get_setting(self, key: str, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        """Set a setting value and save"""
        self.settings[key] = value
        return self._save_settings()

    def get_default_folder(self) -> str:
        """Get current default folder"""
        return str(self.default_folder)

    def set_default_folder(self, folder_path: str) -> Tuple[bool, str]:
        """Update the default project folder"""
        path = Path(os.path.expanduser(folder_path))
        if path.is_dir():
            self.default_folder = path
            self.settings["default_project_folder"] = str(path)
            if self._save_settings():
                return True, f"Default folder set to: {path}"
            else:
                return False, "Settings could not be saved"
        else:
            return False, f"Invalid folder: {path}"

    def validate_project_name(self, name: str) -> Tuple[bool, str]:
        """Validate project name for filesystem safety"""
        if not name or not name.strip():
            return False, "Project name cannot be empty"

        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in name:
                return False, f"Name contains invalid character: '{char}'"

        if len(name.strip()) > 255:
            return False, "Project name too long (max 255 characters)"

        return True, ""

    def validate_status(self, status: str) -> bool:
        """Check if status is valid"""
        return status in self.VALID_STATUSES

    def create_project(self, name: str, folder: str = None,
                       initial_status: str = None) -> Tuple[bool, str]:
        """
        Create a new project with standard folder structure

        Args:
            name: Project name
            folder: Target folder (uses default if not specified)
            initial_status: Initial project status

        Returns:
            (success, message_or_error)
        """
        # Validate name
        is_valid, err = self.validate_project_name(name)
        if not is_valid:
            return False, err

        # Determine target folder
        target_folder = Path(os.path.expanduser(folder or str(self.default_folder)))

        # Create target folder if it doesn't exist
        if not target_folder.exists():
            try:
                target_folder.mkdir(parents=True)
            except Exception as e:
                return False, f"Cannot create target folder: {str(e)}"

        # Create project folder
        project_path = target_folder / name

        # Check if already exists
        if project_path.exists():
            return False, f"Project '{name}' already exists in {target_folder}"

        try:
            # Create main project folder
            project_path.mkdir()

            # Create subfolders
            created_subfolders = []
            for subfolder in self.PROJECT_SUBFOLDERS:
                subfolder_path = project_path / subfolder
                subfolder_path.mkdir()
                created_subfolders.append(subfolder)

            # Create project metadata file
            status = initial_status or self.settings.get("default_status", "developing")
            project_metadata = {
                "name": name,
                "path": str(project_path),
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
                "status": status,
                "subfolders": self.PROJECT_SUBFOLDERS
            }

            metadata_file = project_path / ".project_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(project_metadata, f, indent=2)

            return True, f"Project '{name}' created at:\n{project_path}\nStatus: {self.STATUS_LABELS.get(status, status)}\n\nSubfolders created:\n" + "\n".join(
                f"  - {sf}" for sf in created_subfolders)

        except Exception as e:
            return False, f"Failed to create project: {str(e)}"

    def load_project_metadata(self, project_name: str,
                              folder: str = None) -> Optional[Dict]:
        """Load metadata for a specific project"""
        target_folder = Path(os.path.expanduser(folder or str(self.default_folder)))
        metadata_file = target_folder / project_name / ".project_metadata.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def update_project_status(self, project_name: str, new_status: str,
                              folder: str = None) -> Tuple[bool, str]:
        """Update the status of a project"""
        if not self.validate_status(new_status):
            return False, f"Invalid status: {new_status}"

        target_folder = Path(os.path.expanduser(folder or str(self.default_folder)))
        metadata_file = target_folder / project_name / ".project_metadata.json"

        if not metadata_file.exists():
            return False, f"Project metadata not found: {project_name}"

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            metadata["status"] = new_status
            metadata["modified"] = datetime.now().isoformat()

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            return True, f"Status updated to: {self.STATUS_LABELS.get(new_status, new_status)}"

        except Exception as e:
            return False, f"Failed to update status: {str(e)}"

    def get_project_status(self, project_name: str,
                           folder: str = None) -> Optional[str]:
        """Get the current status of a project"""
        metadata = self.load_project_metadata(project_name, folder)
        return metadata.get("status") if metadata else None

    def list_projects(self, folder: str = None) -> Tuple[bool, List[Dict]]:
        """List all projects with their metadata in a folder"""
        target_folder = Path(os.path.expanduser(folder or str(self.default_folder)))

        if not target_folder.exists():
            return False, []

        projects = []
        try:
            for d in target_folder.iterdir():
                if d.is_dir() and not d.name.startswith('.'):
                    metadata = self.load_project_metadata(d.name, folder)
                    project_info = {
                        "name": d.name,
                        "path": str(d),
                        "status": metadata.get("status", "developing") if metadata else "developing",
                        "created": metadata.get("created", "") if metadata else "",
                        "modified": metadata.get("modified", "") if metadata else ""
                    }
                    projects.append(project_info)

            return True, sorted(projects, key=lambda x: x["name"])

        except Exception as e:
            return False, []

    def get_folder_from_drag(self, uri: str) -> str:
        """Convert URI to filesystem path"""
        if uri.startswith('file://'):
            path = uri[7:].replace('%20', ' ')
            return path
        return uri

    def delete_project(self, project_name: str, folder: str = None) -> Tuple[bool, str]:
        """Delete a project (with confirmation required)"""
        target_folder = Path(os.path.expanduser(folder or str(self.default_folder)))
        project_path = target_folder / project_name

        if not project_path.exists():
            return False, f"Project not found: {project_name}"

        try:
            import shutil
            shutil.rmtree(project_path)
            return True, f"Project '{project_name}' deleted"
        except Exception as e:
            return False, f"Failed to delete project: {str(e)}"