#!/usr/bin/env python3
"""Unit tests for PDF Compressor logic"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path

# Import actual logic from the app
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from logic import (
    validate_input_path,
    validate_output_path,
    generate_default_output_name,
    check_ghostscript_available,
    get_preset_description,
    get_file_size_bytes,
    format_file_size,
    calculate_compression_ratio,
)


class TestPDFCompressorLogic(unittest.TestCase):
    """Test PDF Compressor business logic"""

    def setUp(self):
        """Create temp directory with test files"""
        self.test_dir = tempfile.mkdtemp()
        self.test_pdf = os.path.join(self.test_dir, "test.pdf")

        # Create a dummy PDF (just text for testing validation)
        Path(self.test_pdf).write_bytes(b"%PDF-1.4 dummy pdf content")

    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ========== INPUT VALIDATION TESTS ==========

    def test_validate_valid_pdf(self):
        """Test validation with valid PDF"""
        is_valid, error = validate_input_path(self.test_pdf)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_validate_empty_path(self):
        """Test validation with empty path"""
        is_valid, error = validate_input_path("")
        self.assertFalse(is_valid)
        self.assertIn("No file selected", error)

    def test_validate_nonexistent_file(self):
        """Test validation with non-existent file"""
        is_valid, error = validate_input_path("/nonexistent/file.pdf")
        self.assertFalse(is_valid)
        self.assertIn("does not exist", error)

    def test_validate_not_pdf_extension(self):
        """Test validation with non-PDF extension"""
        txt_file = os.path.join(self.test_dir, "test.txt")
        Path(txt_file).write_text("text file")

        is_valid, error = validate_input_path(txt_file)
        self.assertFalse(is_valid)
        self.assertIn("PDF", error)

    def test_validate_directory_instead_of_file(self):
        """Test validation when path is directory"""
        is_valid, error = validate_input_path(self.test_dir)
        self.assertFalse(is_valid)
        self.assertIn("Not a file", error)

    # ========== OUTPUT VALIDATION TESTS ==========

    def test_validate_valid_output(self):
        """Test validation with valid output path"""
        output = os.path.join(self.test_dir, "output.pdf")
        is_valid, error = validate_output_path(output, self.test_pdf)
        self.assertTrue(is_valid)

    def test_validate_output_no_extension(self):
        """Test validation without .pdf extension"""
        output = os.path.join(self.test_dir, "output")
        is_valid, error = validate_output_path(output, self.test_pdf)
        self.assertFalse(is_valid)
        self.assertIn(".pdf", error)

    def test_validate_output_invalid_directory(self):
        """Test validation with invalid output directory"""
        output = "/nonexistent/dir/output.pdf"
        is_valid, error = validate_output_path(output, self.test_pdf)
        self.assertFalse(is_valid)

    # ========== OUTPUT NAME GENERATION TESTS ==========

    def test_generate_output_name_basic(self):
        """Test default output name generation"""
        result = generate_default_output_name("/path/to/document.pdf")
        self.assertEqual(result, "/path/to/document_compressed.pdf")

    def test_generate_output_name_with_spaces(self):
        """Test with spaces in filename"""
        result = generate_default_output_name("/path/to/my file.pdf")
        self.assertEqual(result, "/path/to/my file_compressed.pdf")

    def test_generate_output_name_with_uppercase(self):
        """Test with uppercase letters"""
        result = generate_default_output_name("/path/to/DOCUMENT.PDF")
        self.assertEqual(result, "/path/to/DOCUMENT_compressed.pdf")

    def test_generate_output_name_empty_input(self):
        """Test with empty input"""
        result = generate_default_output_name("")
        self.assertEqual(result, "")

    # ========== PRESET DESCRIPTION TESTS ==========

    def test_get_preset_descriptions(self):
        """Test all preset descriptions"""
        self.assertIn("quality", get_preset_description("/screen"))
        self.assertIn("quality", get_preset_description("/ebook"))
        self.assertIn("quality", get_preset_description("/printer"))
        self.assertIn("quality", get_preset_description("/prepress"))
        self.assertIn("settings", get_preset_description("/default"))

    def test_get_unknown_preset(self):
        """Test with unknown preset"""
        desc = get_preset_description("/unknown")
        self.assertEqual(desc, "Custom settings")

    # ========== FILE SIZE TESTS ==========

    def test_format_file_size_bytes(self):
        """Test formatting in bytes"""
        self.assertEqual(format_file_size(500), "500.0 B")

    def test_format_file_size_kb(self):
        """Test formatting in KB"""
        self.assertEqual(format_file_size(1536), "1.5 KB")

    def test_format_file_size_mb(self):
        """Test formatting in MB"""
        self.assertEqual(format_file_size(1572864), "1.5 MB")

    def test_calculate_compression_ratio_reduction(self):
        """Test compression ratio calculation (reduction)"""
        ratio = calculate_compression_ratio(1000, 600)
        self.assertAlmostEqual(ratio, 40.0, places=1)

    def test_calculate_compression_ratio_expansion(self):
        """Test compression ratio (negative would be expansion)"""
        # If compressed is larger than original
        ratio = calculate_compression_ratio(500, 700)
        self.assertEqual(ratio, 0.0)  # Clamped to 0

    def test_calculate_compression_ratio_zero_original(self):
        """Test with zero original size"""
        ratio = calculate_compression_ratio(0, 0)
        self.assertEqual(ratio, 0.0)

    # ========== GHOSTSCRIPT CHECK TEST ==========

    def test_check_ghostscript_available(self):
        """Test Ghostscript availability check"""
        available, msg = check_ghostscript_available()
        # Just verify it returns a tuple
        self.assertIsInstance(available, bool)
        self.assertIsInstance(msg, str)


class TestEndToEndWorkflow(unittest.TestCase):
    """Test complete compression workflow"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_validation_workflow(self):
        """Test complete validation before compression"""
        # Setup
        test_pdf = os.path.join(self.test_dir, "input.pdf")
        output_pdf = os.path.join(self.test_dir, "input_compressed.pdf")
        Path(test_pdf).write_bytes(b"%PDF-1.4 test")

        # 1. Validate input
        is_valid, error = validate_input_path(test_pdf)
        self.assertTrue(is_valid)

        # 2. Validate output
        is_valid, error = validate_output_path(output_pdf, test_pdf)
        self.assertTrue(is_valid)

        # 3. Generate default name
        default_output = generate_default_output_name(test_pdf)
        self.assertEqual(default_output, output_pdf.replace("_compressed", "_compressed"))


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPDFCompressorLogic))
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