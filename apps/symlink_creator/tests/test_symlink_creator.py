#!/usr/bin/env python3
"""Real tests that import and test the actual app.py code"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path

# Import the ACTUAL logic module from app.py
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from logic import (
    extract_paths_from_selection,
    auto_fill_link_name,
    validate_paths,
    prepare_link_path,
    check_link_exists,
    create_symlink,
    verify_symlink_created,
)


class TestActualLogicModule(unittest.TestCase):
    """Test the REAL logic.py from app.py - NOT mocks"""

    def setUp(self):
        """Create temp directory for tests"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_paths_empty(self):
        """Test ACTUAL function with empty data"""
        result = extract_paths_from_selection(b"")
        self.assertEqual(result, [])

    def test_extract_paths_single_file_uri(self):
        """Test ACTUAL function with file:// URI"""
        uri = b"file:///home/user/test.txt\n"
        result = extract_paths_from_selection(uri)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "/home/user/test.txt")

    def test_extract_paths_with_spaces(self):
        """Test ACTUAL function with URL-encoded spaces"""
        uri = b"file:///home/user/my%20file.txt\n"
        result = extract_paths_from_selection(uri)
        self.assertEqual(result[0], "/home/user/my file.txt")

    def test_auto_fill_from_file(self):
        """Test ACTUAL function extracting filename"""
        result = auto_fill_link_name("/path/to/document.pdf")
        self.assertEqual(result, "document.pdf")

    def test_auto_fill_from_folder(self):
        """Test ACTUAL function extracting folder name"""
        result = auto_fill_link_name("/path/to/folder/")
        self.assertEqual(result, "folder")

    def test_validate_valid_paths(self):
        """Test ACTUAL validation with valid paths"""
        test_file = os.path.join(self.test_dir, "test.txt")
        Path(test_file).touch()

        is_valid, errors = validate_paths(test_file, self.test_dir)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_validate_missing_target(self):
        """Test ACTUAL validation catches missing target"""
        is_valid, errors = validate_paths("/nonexistent/file.txt", self.test_dir)
        self.assertFalse(is_valid)
        self.assertTrue(any("does not exist" in e for e in errors))

    def test_validate_destination_not_folder(self):
        """Test ACTUAL validation rejects file as destination"""
        test_file = os.path.join(self.test_dir, "test.txt")
        Path(test_file).touch()

        is_valid, errors = validate_paths(test_file, test_file)  # File as dest
        self.assertFalse(is_valid)
        self.assertTrue(any("not a folder" in e for e in errors))

    def test_prepare_link_path(self):
        """Test ACTUAL path preparation"""
        result = prepare_link_path("/dest/folder", "link_name")
        self.assertEqual(result, os.path.join("/dest/folder", "link_name"))

    def test_check_link_exists_true(self):
        """Test ACTUAL existence check"""
        link_path = os.path.join(self.test_dir, "link")
        target = os.path.join(self.test_dir, "target")
        Path(target).touch()
        os.symlink(target, link_path)

        self.assertTrue(check_link_exists(link_path))

    def test_check_link_exists_false(self):
        """Test ACTUAL existence check returns False for missing"""
        self.assertFalse(check_link_exists("/nonexistent/path"))

    def test_create_symlink_success(self):
        """Test ACTUAL symlink creation"""
        target = os.path.join(self.test_dir, "target.txt")
        link = os.path.join(self.test_dir, "link.txt")
        Path(target).touch()

        success, error = create_symlink(target, link)

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertTrue(os.path.islink(link))

    def test_create_symlink_permission_error(self):
        """Test ACTUAL permission error handling"""
        target = os.path.join(self.test_dir, "target.txt")
        Path(target).touch()

        # Try to create in read-only location (will fail)
        success, error = create_symlink(target, "/root/test_link")

        self.assertFalse(success)
        self.assertIsNotNone(error)

    def test_verify_symlink_correct(self):
        """Test ACTUAL verification of correct symlink"""
        target = os.path.join(self.test_dir, "target.txt")
        link = os.path.join(self.test_dir, "link.txt")
        Path(target).touch()
        os.symlink(target, link)

        valid, msg = verify_symlink_created(link, target)

        self.assertTrue(valid)
        self.assertIn("verified", msg.lower())

    def test_verify_symlink_wrong_target(self):
        """Test ACTUAL detection of wrong symlink target"""
        target1 = os.path.join(self.test_dir, "target1.txt")
        target2 = os.path.join(self.test_dir, "target2.txt")
        link = os.path.join(self.test_dir, "link.txt")
        Path(target1).touch()
        Path(target2).touch()
        os.symlink(target1, link)

        valid, msg = verify_symlink_created(link, target2)

        self.assertFalse(valid)
        self.assertIn("wrong", msg.lower())


class TestEndToEndWorkflow(unittest.TestCase):
    """Test complete workflows using actual logic functions"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_complete_create_workflow(self):
        """Test complete symlink creation from start to finish"""
        # Setup
        target = os.path.join(self.test_dir, "source_file.txt")
        dest = os.path.join(self.test_dir, "destination")
        Path(target).touch()
        os.makedirs(dest)

        # 1. Validate paths
        is_valid, errors = validate_paths(target, dest)
        self.assertTrue(is_valid, f"Validation failed: {errors}")

        # 2. Prepare link name
        link_name = auto_fill_link_name(target)
        self.assertEqual(link_name, "source_file.txt")

        # 3. Prepare full path
        link_path = prepare_link_path(dest, link_name)
        expected = os.path.join(dest, "source_file.txt")
        self.assertEqual(link_path, expected)

        # 4. Create symlink
        success, error = create_symlink(target, link_path)
        self.assertTrue(success, f"Creation failed: {error}")

        # 5. Verify
        valid, msg = verify_symlink_created(link_path, target)
        self.assertTrue(valid, f"Verification failed: {msg}")

    def test_dnd_workflow_simulation(self):
        """Test simulated drag-and-drop workflow"""
        # Setup
        source = os.path.join(self.test_dir, "dropped.txt")
        Path(source).touch()

        # Simulate DND data from file manager
        dnd_bytes = f"file://{source}\n".encode()

        # Extract path (calls actual logic function)
        paths = extract_paths_from_selection(dnd_bytes)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], source)

        # Rest of workflow
        dest = os.path.join(self.test_dir, "dest")
        os.makedirs(dest)

        link_name = auto_fill_link_name(source)
        link_path = prepare_link_path(dest, link_name)

        success, error = create_symlink(source, link_path)
        self.assertTrue(success)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestActualLogicModule))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflow))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'=' * 60}")
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit(run_tests())