#!/usr/bin/env python3
"""Unit tests for App Generator logic"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path

# Import actual logic
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from logic import (
    validate_app_name,
    validate_category,
    parse_tags,
    validate_icon_url,
    generate_config_yaml,
    create_app_structure,
)


class TestAppGeneratorLogic(unittest.TestCase):
    """Test App Generator business logic"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ========== APP NAME VALIDATION ==========

    def test_validate_valid_name(self):
        is_valid, result = validate_app_name("PDF Compressor")
        self.assertTrue(is_valid)
        self.assertEqual(result, "pdf_compressor")

    def test_validate_name_with_spaces(self):
        is_valid, result = validate_app_name("Hello World")
        self.assertTrue(is_valid)
        self.assertEqual(result, "hello_world")

    def test_validate_name_lowercase(self):
        is_valid, result = validate_app_name("MyAPP")
        self.assertTrue(is_valid)
        self.assertEqual(result, "myapp")

    def test_validate_empty_name(self):
        is_valid, error = validate_app_name("")
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())

    def test_validate_special_characters_removed(self):
        is_valid, result = validate_app_name("File@#$%Processor")
        self.assertTrue(is_valid)
        self.assertEqual(result, "fileprocessor")

    def test_validate_underscore_boundaries(self):
        is_valid, error = validate_app_name("_invalid")
        self.assertFalse(is_valid)

    def test_validate_consecutive_underscores(self):
        is_valid, error = validate_app_name("bad__name")
        self.assertFalse(is_valid)

    # ========== CATEGORY VALIDATION ==========

    def test_validate_valid_category(self):
        is_valid, result = validate_category("Media")
        self.assertTrue(is_valid)
        self.assertEqual(result, "media")

    def test_validate_empty_category(self):
        is_valid, error = validate_category("")
        self.assertFalse(is_valid)

    def test_validate_invalid_chars(self):
        is_valid, error = validate_category("my-cat!")
        self.assertFalse(is_valid)

    # ========== TAG PARSING ==========

    def test_parse_multiple_tags(self):
        tags = parse_tags("tool, utility, files")
        self.assertEqual(tags, ["tool", "utility", "files"])

    def test_parse_single_tag(self):
        tags = parse_tags("example")
        self.assertEqual(tags, ["example"])

    def test_parse_empty_string(self):
        tags = parse_tags("")
        self.assertEqual(tags, [])

    def test_parse_extra_whitespace(self):
        tags = parse_tags("  tag1  ,  tag2  ,  tag3  ")
        self.assertEqual(tags, ["tag1", "tag2", "tag3"])

    # ========== ICON URL VALIDATION ==========

    def test_validate_http_url(self):
        is_valid, msg, _ = validate_icon_url("http://example.com/icon.png")
        self.assertTrue(is_valid)

    def test_validate_https_url(self):
        is_valid, msg, _ = validate_icon_url("https://example.com/icon.png")
        self.assertTrue(is_valid)

    def test_validate_invalid_scheme(self):
        is_valid, msg, code = validate_icon_url("ftp://example.com/icon.png")
        self.assertFalse(is_valid)
        self.assertEqual(code, "INVALID_SCHEME")

    def test_validate_empty_url(self):
        is_valid, msg, _ = validate_icon_url("")
        self.assertTrue(is_valid)

    # ========== CONFIG GENERATION ==========

    def test_generate_config_yaml(self):
        yaml_content = generate_config_yaml("pdf_compressor", "an app", "media", ["pdf", "compression"])

        self.assertIn('name:', yaml_content)
        self.assertIn('category: "media"', yaml_content)
        self.assertIn("tags:", yaml_content)
        self.assertIn("'pdf'", yaml_content)
        self.assertIn("'compression'", yaml_content)

    # ========== STRUCTURE CREATION ==========

    def test_create_app_structure(self):
        success, msg, path = create_app_structure(
            self.test_dir,
            "test_app",
            "tools",
            ["test"],
            None
        )

        self.assertTrue(success)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(os.path.join(path, "config.yaml")))
        self.assertTrue(os.path.exists(os.path.join(path, "logic.py")))
        self.assertTrue(os.path.exists(os.path.join(path, "app.py")))
        self.assertTrue(os.path.exists(os.path.join(path, "icon.png")))
        self.assertTrue(os.path.exists(os.path.join(path, "tests/")))

    def test_create_app_already_exists(self):
        # Create first
        create_app_structure(self.test_dir, "duplicate", "tools", [], None)

        # Try to create again
        success, msg, _ = create_app_structure(self.test_dir, "duplicate", "tools", [], None)
        self.assertFalse(success)
        self.assertIn("already exists", msg)


def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAppGeneratorLogic))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit(run_tests())