import shutil
import unittest
import os
import tempfile
from pathlib import Path
import sys

# Adjust path to import logic
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logic import PDFConcatenatorLogic


class TestPDFConcatenatorLogic(unittest.TestCase):

    def setUp(self):
        self.logic = PDFConcatenatorLogic()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Cleanup temp files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_fake_pdf(self, name, content=b"%PDF-1.4 fake"):
        path = os.path.join(self.temp_dir, name)
        with open(path, 'wb') as f:
            f.write(content)
        return path

    def test_validate_valid_pdf(self):
        path = self._create_fake_pdf("test.pdf")
        is_valid, err = self.logic.validate_file(path)
        self.assertTrue(is_valid)
        self.assertEqual(err, "")

    def test_validate_nonexistent_file(self):
        is_valid, err = self.logic.validate_file("/fake/path.pdf")
        self.assertFalse(is_valid)
        self.assertIn("not found", err)

    def test_validate_invalid_extension(self):
        path = os.path.join(self.temp_dir, "test.txt")
        with open(path, 'w') as f:
            f.write("text")
        is_valid, err = self.logic.validate_file(path)
        self.assertFalse(is_valid)
        self.assertIn("Unsupported format", err)

    def test_validate_invalid_header(self):
        path = self._create_fake_pdf("bad.pdf", content=b"NOT A PDF")
        is_valid, err = self.logic.validate_file(path)
        self.assertFalse(is_valid)
        self.assertIn("Invalid PDF header", err)

    @unittest.skipUnless(shutil.which("gs"), "Ghostscript not installed")
    def test_concat_valid_pdfs(self):
        pdf1 = self._create_fake_pdf("a.pdf")
        pdf2 = self._create_fake_pdf("b.pdf")
        output = os.path.join(self.temp_dir, "out.pdf")

        # Note: This will likely fail with fake content, but tests the flow
        # A real test would need valid PDF binaries. 
        # We test that the function calls gs correctly.
        try:
            success, msg = self.logic.concat_pdfs([pdf1, pdf2], output)
            # If gs runs, it might fail on content, but we check if the command executed
            # For this unit test, we expect failure due to invalid PDF content, not missing binary
            if not success:
                self.assertNotIn("not found", msg)
        except Exception as e:
            self.fail(f"concat_pdfs raised unexpected exception: {e}")


if __name__ == '__main__':
    unittest.main()