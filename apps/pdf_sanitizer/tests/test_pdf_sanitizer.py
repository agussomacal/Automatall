#!/usr/bin/env python3
"""Unit tests for PDF Sanitizer logic"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path

# Import actual logic
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from logic import (
    validate_input_path,
    validate_output_path,
    generate_default_output_name,
    check_pdftoppm_available,
    check_convert_available,
    check_tools_available,
    get_quality_options,
    get_file_size_bytes,
    format_file_size,
    calculate_size_change,
)


class TestPDFSanitizerLogic(unittest.TestCase):
    """Test PDF Sanitizer business logic"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_pdf = os.path.join(self.test_dir, "test.pdf")
        Path(self.test_pdf).write_bytes(b"%PDF-1.4 test")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ========== VALIDATION TESTS ==========

    def test_validate_valid_input(self):
        is_valid, error = validate_input_path(self.test_pdf)
        self.assertTrue(is_valid)

    def test_validate_empty_input(self):
        is_valid, error = validate_input_path("")
        self.assertFalse(is_valid)
        self.assertIn("No file", error)

    def test_validate_non_pdf(self):
        txt = os.path.join(self.test_dir, "test.txt")
        Path(txt).write_text("text")
        is_valid, error = validate_input_path(txt)
        self.assertFalse(is_valid)

    def test_validate_default_output_name(self):
        result = generate_default_output_name("/path/doc.pdf")
        self.assertEqual(result, "/path/doc_sanitized.pdf")

    def test_validate_custom_suffix(self):
        result = generate_default_output_name("/path/doc.pdf", "_clean")
        self.assertEqual(result, "/path/doc_clean.pdf")

    # ========== QUALITY OPTIONS TESTS ==========

    def test_quality_options_exist(self):
        options = get_quality_options()
        self.assertIn("Low (72 DPI)", options)
        self.assertIn("Medium (150 DPI)", options)
        self.assertIn("High (300 DPI)", options)
        self.assertIn("Very High (600 DPI)", options)

    # ========== SIZE CALCULATION TESTS ==========

    def test_size_reduction(self):
        change, desc = calculate_size_change(1000, 600)
        self.assertLess(change, 0)
        self.assertIn("Reduced", desc)

    def test_size_increase(self):
        change, desc = calculate_size_change(500, 700)
        self.assertGreater(change, 0)
        self.assertIn("Increased", desc)

    # ========== TOOL CHECK TESTS ==========

    def test_check_tools_returns_tuple(self):
        ok, msg = check_tools_available()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)


def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPDFSanitizerLogic))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit(run_tests())