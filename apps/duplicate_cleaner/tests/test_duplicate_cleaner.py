import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Assuming your core module is named `duplicate_finder.py`
# Adjust the import line below to match your actual module name.

# Ensure parent dir is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from DuplicateFinderLogic.logic import DuplicateFinderLogic, FileInfo


class TestFileInfo(unittest.TestCase):
    """Test suite for FileInfo dataclass."""

    def test_equality_same_path(self):
        f1 = FileInfo(path="/tmp/a.txt", name="a.txt", size=100, sha256="abc")
        f2 = FileInfo(path="/tmp/a.txt", name="a.txt", size=100, sha256="abc")
        self.assertEqual(f1, f2)

    def test_inequality_different_path(self):
        f1 = FileInfo(path="/tmp/a.txt", name="a.txt", size=100, sha256="abc")
        f2 = FileInfo(path="/tmp/b.txt", name="b.txt", size=100, sha256="abc")
        self.assertNotEqual(f1, f2)

    def test_inequality_different_type(self):
        f1 = FileInfo(path="/tmp/a.txt", name="a.txt", size=100, sha256="abc")
        self.assertNotEqual(f1, "/tmp/a.txt")

    def test_hash_based_on_path(self):
        f1 = FileInfo(path="/tmp/a.txt", name="a.txt", size=100, sha256="abc")
        f2 = FileInfo(path="/tmp/a.txt", name="different_name.txt", size=200, sha256="xyz")
        self.assertEqual(hash(f1), hash(f2))


class TestDuplicateFinderLogic(unittest.TestCase):
    """Test suite for DuplicateFinderLogic class."""

    def setUp(self):
        self.finder = DuplicateFinderLogic()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- Helper methods ---

    def create_file(self, relative_path: str, content: bytes) -> Path:
        file_path = self.temp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path

    # --- Unit Tests ---

    def test_calculate_sha256_success(self):
        file_path = self.create_file("test.txt", b"hello world")
        # SHA256 of 'hello world' is b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
        expected_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        file_hash = self.finder.calculate_sha256(str(file_path))
        self.assertEqual(file_hash, expected_hash)

    def test_calculate_sha256_nonexistent_file(self):
        with self.assertRaises(IOError):
            self.finder.calculate_sha256(str(self.temp_path / "nonexistent.txt"))

    def test_validate_folder_valid(self):
        is_valid, msg = self.finder.validate_folder(str(self.temp_path))
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_validate_folder_nonexistent(self):
        non_existent = self.temp_path / "missing_folder"
        is_valid, msg = self.finder.validate_folder(str(non_existent))
        self.assertFalse(is_valid)
        self.assertIn("does not exist", msg)

    def test_validate_folder_not_a_directory(self):
        file_path = self.create_file("regular_file.txt", b"content")
        is_valid, msg = self.finder.validate_folder(str(file_path))
        self.assertFalse(is_valid)
        self.assertIn("not a folder", msg)

    @patch("os.access", return_value=False)
    def test_validate_folder_no_read_permission(self, mock_access):
        is_valid, msg = self.finder.validate_folder(str(self.temp_path))
        self.assertFalse(is_valid)
        self.assertIn("No read permission", msg)

    def test_scan_folder_empty_directory(self):
        success, msg = self.finder.scan_folder(str(self.temp_path))
        self.assertTrue(success)
        self.assertEqual(msg, "No files found in folder")
        self.assertEqual(self.finder.scan_stats["total_files"], 0)

    def test_scan_folder_ignores_hidden_files(self):
        self.create_file(".hidden_file", b"content")
        self.create_file("visible_file.txt", b"content")

        success, _ = self.finder.scan_folder(str(self.temp_path))
        self.assertTrue(success)
        self.assertEqual(self.finder.scan_stats["total_files"], 1)

    def test_scan_folder_non_recursive(self):
        self.create_file("root.txt", b"root content")
        self.create_file("sub/nested.txt", b"nested content")

        success, _ = self.finder.scan_folder(str(self.temp_path), recursive=False)
        self.assertTrue(success)
        self.assertEqual(self.finder.scan_stats["total_files"], 1)

    def test_scan_folder_recursive(self):
        self.create_file("root.txt", b"root content")
        self.create_file("sub/nested.txt", b"nested content")

        success, _ = self.finder.scan_folder(str(self.temp_path), recursive=True)
        self.assertTrue(success)
        self.assertEqual(self.finder.scan_stats["total_files"], 2)

    def test_scan_folder_detects_duplicates(self):
        content = b"duplicate content payload"
        file1 = self.create_file("dir1/file1.txt", content)
        file2 = self.create_file("dir2/file2.txt", content)
        self.create_file("unique.txt", b"unique content")

        success, msg = self.finder.scan_folder(str(self.temp_path), recursive=True)
        self.assertTrue(success)
        self.assertIn("Found 1 duplicate groups", msg)

        # Verify scan statistics
        self.assertEqual(self.finder.scan_stats["total_files"], 3)
        self.assertEqual(self.finder.scan_stats["duplicate_groups"], 1)
        self.assertEqual(self.finder.scan_stats["potential_savings_bytes"], len(content))

        # Verify duplicate groupings
        groups = self.finder.get_duplicate_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["size"], len(content))

    def test_get_duplicate_groups_sorted_by_count(self):
        content_a = b"Group A content"
        content_b = b"Group B content"

        # Group 1: 2 files
        self.create_file("a1.txt", content_a)
        self.create_file("a2.txt", content_a)

        # Group 2: 3 files
        self.create_file("b1.txt", content_b)
        self.create_file("b2.txt", content_b)
        self.create_file("b3.txt", content_b)

        self.finder.scan_folder(str(self.temp_path), recursive=False)
        groups = self.finder.get_duplicate_groups()

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["count"], 3)  # Larger group should be first
        self.assertEqual(groups[1]["count"], 2)

    def test_suggest_keeps(self):
        f1 = FileInfo(path="/path/to/very_long_filename.txt", name="very_long_filename.txt", size=10, sha256="abc")
        f2 = FileInfo(path="/path/to/short.txt", name="short.txt", size=10, sha256="abc")
        f3 = FileInfo(path="/path/to/medium_name.txt", name="medium_name.txt", size=10, sha256="abc")

        suggested = self.finder.suggest_keeps([f1, f2, f3])
        self.assertEqual(suggested, "/path/to/short.txt")

    def test_suggest_keeps_empty_group(self):
        self.assertIsNone(self.finder.suggest_keeps([]))

    @patch("send2trash.send2trash")
    def test_delete_file_success(self, mock_send2trash):
        file_path = self.create_file("to_delete.txt", b"delete me")

        success, msg = self.finder.delete_file(str(file_path))
        self.assertTrue(success)
        self.assertIn("Deleted:", msg)
        mock_send2trash.assert_called_once_with(str(file_path))

    def test_delete_file_not_found(self):
        non_existent = str(self.temp_path / "missing.txt")
        success, msg = self.finder.delete_file(non_existent)
        self.assertFalse(success)
        self.assertIn("File not found", msg)

    @patch("send2trash.send2trash", side_effect=PermissionError("Permission denied"))
    def test_delete_file_failure(self, mock_send2trash):
        file_path = self.create_file("locked.txt", b"data")
        success, msg = self.finder.delete_file(str(file_path))
        self.assertFalse(success)
        self.assertIn("Failed to delete", msg)

    @patch.object(DuplicateFinderLogic, "delete_file")
    def test_cleanup_duplicates(self, mock_delete):
        mock_delete.side_effect = [
            (True, "Deleted f1"),
            (False, "Failed f2"),
            (True, "Deleted f3"),
        ]

        files = ["/f1.txt", "/f2.txt", "/f3.txt"]
        all_succeeded, failed = self.finder.cleanup_duplicates(files)

        self.assertFalse(all_succeeded)
        self.assertEqual(failed, ["/f2.txt"])

    def test_format_size(self):
        self.assertEqual(self.finder.format_size(500), "500.0 B")
        self.assertEqual(self.finder.format_size(1024), "1.0 KB")
        self.assertEqual(self.finder.format_size(1048576), "1.0 MB")
        self.assertEqual(self.finder.format_size(1073741824), "1.0 GB")
        self.assertEqual(self.finder.format_size(1099511627776), "1.0 TB")


if __name__ == "__main__":
    unittest.main()
