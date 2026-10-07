#!/usr/bin/env python3
"""Unit tests for Projects Manager with Status Tracking"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logic import ProjectsManagerLogic


class TestProjectsManagerLogic(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.logic = ProjectsManagerLogic()
        self.logic.default_folder = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_empty_name(self):
        is_valid, err = self.logic.validate_project_name("")
        self.assertFalse(is_valid)
        self.assertIn("empty", err)

    def test_validate_invalid_chars(self):
        is_valid, err = self.logic.validate_project_name("my<project>")
        self.assertFalse(is_valid)
        self.assertIn("invalid character", err)

    def test_validate_valid_name(self):
        is_valid, err = self.logic.validate_project_name("My_Project-2024")
        self.assertTrue(is_valid)
        self.assertEqual(err, "")

    def test_create_project(self):
        success, msg = self.logic.create_project("test_project")
        self.assertTrue(success)

        project_path = Path(self.temp_dir) / "test_project"
        self.assertTrue(project_path.exists())

        # Check metadata file
        metadata_file = project_path / ".project_metadata.json"
        self.assertTrue(metadata_file.exists())

        with open(metadata_file) as f:
            metadata = json.load(f)
        self.assertEqual(metadata["name"], "test_project")
        self.assertIn("status", metadata)

    def test_update_project_status(self):
        self.logic.create_project("status_test")
        success, msg = self.logic.update_project_status("status_test", "published")
        self.assertTrue(success)

        status = self.logic.get_project_status("status_test")
        self.assertEqual(status, "published")

    def test_invalid_status(self):
        success, msg = self.logic.update_project_status("nonexistent", "invalid_status")
        self.assertFalse(success)
        self.assertIn("Invalid status", msg)

    def test_list_projects(self):
        self.logic.create_project("proj1", initial_status="developing")
        self.logic.create_project("proj2", initial_status="published")

        success, projects = self.logic.list_projects()
        self.assertTrue(success)
        self.assertEqual(len(projects), 2)

        statuses = {p["name"]: p["status"] for p in projects}
        self.assertEqual(statuses["proj1"], "developing")
        self.assertEqual(statuses["proj2"], "published")

    def test_delete_project(self):
        self.logic.create_project("to_delete")
        success, msg = self.logic.delete_project("to_delete")
        self.assertTrue(success)

        # Verify deletion
        success, projects = self.logic.list_projects()
        self.assertNotIn("to_delete", [p["name"] for p in projects])


if __name__ == '__main__':
    unittest.main()