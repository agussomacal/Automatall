#!/usr/bin/env python3
"""Core logic for Duplicate Finder - Pure business logic, no DuplicateFinderGUI."""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass

import send2trash


@dataclass
class FileInfo:
    """Represents a file's metadata and hash."""
    path: str
    name: str
    size: int
    sha256: str
    duplicate_group_id: str = None  # Groups duplicates together

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if not isinstance(other, FileInfo):
            return False
        return self.path == other.path


class DuplicateFinderLogic:
    """Handles duplicate file detection using SHA256 hashing."""

    # Common patterns that indicate copied files
    COPY_PATTERNS = [" 1", " 2", " 3", " 4", " 5", "(1)", "(2)", "(3)"]

    def __init__(self):
        self.duplicates: Dict[str, List[FileInfo]] = {}  # hash -> list of files
        self.scan_stats = {
            "total_files": 0,
            "unique_files": 0,
            "duplicate_groups": 0,
            "potential_savings_bytes": 0,
        }

    def calculate_sha256(self, file_path: str, chunk_size: int = 8192) -> str:
        """Calculate SHA256 hash of a file efficiently."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            raise IOError(f"Cannot read file {file_path}: {str(e)}")

    def validate_folder(self, folder_path: str) -> Tuple[bool, str]:
        """Validate that folder exists and is accessible."""
        path = Path(folder_path)

        if not path.exists():
            return False, f"Folder does not exist: {folder_path}"

        if not path.is_dir():
            return False, f"Path is not a folder: {folder_path}"

        if not os.access(path, os.R_OK):
            return False, f"No read permission for folder: {folder_path}"

        return True, ""

    def scan_folder(self, folder_path: str, recursive: bool = False) -> Tuple[bool, str]:
        """
        Scan folder for duplicate files using SHA256 hashing.

        Args:
            folder_path: Absolute path to folder to scan
            recursive: Whether to scan subdirectories

        Returns:
            (success, message_or_error)
        """
        is_valid, err = self.validate_folder(folder_path)
        if not is_valid:
            return False, err

        # Reset state
        self.duplicates = {}
        self.scan_stats = {
            "total_files": 0,
            "unique_files": 0,
            "duplicate_groups": 0,
            "potential_savings_bytes": 0,
        }

        # Collect all files
        all_files = []
        folder = Path(folder_path)

        if recursive:
            iterator = folder.rglob("*")
        else:
            iterator = folder.glob("*")

        for item in iterator:
            if item.is_file() and not item.name.startswith('.'):
                all_files.append(item)

        self.scan_stats["total_files"] = len(all_files)

        if not all_files:
            return True, "No files found in folder"

        # Group files by size first (quick filter)
        size_groups: Dict[int, List[Path]] = {}
        for file_path in all_files:
            try:
                size = file_path.stat().st_size
                if size not in size_groups:
                    size_groups[size] = []
                size_groups[size].append(file_path)
            except Exception as e:
                print(f"[WARNING] Cannot read file size: {file_path} - {str(e)}")

        # For groups with same size, compute SHA256
        for size, paths in size_groups.items():
            if len(paths) < 2:
                # Unique by size, skip hashing
                self.scan_stats["unique_files"] += 1
                continue

            # Hash all files of this size
            for file_path in paths:
                try:
                    file_hash = self.calculate_sha256(str(file_path))
                    file_info = FileInfo(
                        path=str(file_path),
                        name=file_path.name,
                        size=size,
                        sha256=file_hash,
                    )

                    if file_hash not in self.duplicates:
                        self.duplicates[file_hash] = []
                    self.duplicates[file_hash].append(file_info)

                except Exception as e:
                    print(f"[ERROR] Failed to hash {file_path}: {str(e)}")

        # Filter out unique files
        filtered_duplicates = {}
        for file_hash, files in self.duplicates.items():
            if len(files) >= 2:
                # Assign group ID
                group_id = file_hash[:8]
                for f in files:
                    f.duplicate_group_id = group_id
                filtered_duplicates[file_hash] = files
                self.scan_stats["duplicate_groups"] += 1
                self.scan_stats["potential_savings_bytes"] += size * (len(files) - 1)
            else:
                self.scan_stats["unique_files"] += 1

        self.duplicates = filtered_duplicates

        # FIXED: Removed Chinese characters
        savings_mb = self.scan_stats["potential_savings_bytes"] / (1024 * 1024)
        return True, f"Found {self.scan_stats['duplicate_groups']} duplicate groups " \
                     f"(~{savings_mb:.1f} MB could be freed)"

    def get_duplicate_groups(self) -> List[Dict]:
        """
        Get all duplicate groups with their files.

        Returns list of:
        {
            "group_id": str,
            "files": [FileInfo, FileInfo, ...],
            "size": int,
            "count": int,
        }
        """
        groups = []
        for file_hash, files in self.duplicates.items():
            groups.append({
                "group_id": files[0].duplicate_group_id or file_hash[:8],
                "files": files,
                "size": files[0].size if files else 0,
                "count": len(files),
            })
        return sorted(groups, key=lambda x: x["count"], reverse=True)

    def suggest_keeps(self, group: List[FileInfo]) -> str:
        """
        Suggest which file to keep from a duplicate group.
        Uses heuristics like shorter name, earlier modification time.

        Returns path of suggested file to keep.
        """
        if not group:
            return None

        # Sort by filename length (prefer shorter names)
        sorted_files = sorted(group, key=lambda f: len(f.name))

        return sorted_files[0].path

    def delete_file(self, file_path: str) -> Tuple[bool, str]:
        """Delete a single file."""
        path = Path(file_path)
        try:
            if not path.exists():
                return False, f"File not found: {file_path}"
            send2trash.send2trash(str(path))
            # path.unlink()
            return True, f"Deleted: {file_path}"
        except Exception as e:
            return False, f"Failed to delete {file_path}: {str(e)}"

    def cleanup_duplicates(self, files_to_delete: List[str]) -> Tuple[bool, List[str]]:
        """
        Delete multiple duplicate files.

        Args:
            files_to_delete: List of file paths to delete

        Returns:
            (success, list_of_failed_files)
        """
        failed = []
        for file_path in files_to_delete:
            success, msg = self.delete_file(file_path)
            if not success:
                failed.append(file_path)

        return len(failed) == 0, failed

    def format_size(self, size_bytes: int) -> str:
        """Format byte size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
