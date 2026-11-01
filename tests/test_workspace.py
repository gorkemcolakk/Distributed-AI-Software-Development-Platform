"""
Unit Tests for S3-04: Secure Run Workspace Writer.
Sorumlu: Mahmut Karaalioğlu (Database Agent)
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.master.workspace import (
    RunWorkspace,
    UnsafePathError,
    normalize_relative_path,
    validate_run_id,
)


class TestWorkspaceValidation(unittest.TestCase):

    def test_validate_run_id_valid(self):
        valid_ids = ["run-1234abcd", "run_2026_10", "RUN-1", "a1-b2_c3"]
        for rid in valid_ids:
            with self.subTest(run_id=rid):
                self.assertEqual(validate_run_id(rid), rid)

    def test_validate_run_id_rejects_unsafe(self):
        invalid_ids = [
            "../escape",
            "run/nested",
            "run\\nested",
            "run.id",
            "",
            "   ",
            "-leading-dash",
            "_leading-under",
            "run!special",
            None,
        ]
        for rid in invalid_ids:
            with self.subTest(run_id=rid):
                with self.assertRaises(UnsafePathError):
                    validate_run_id(rid)

    def test_normalize_valid_relative_paths(self):
        cases = [
            ("main.py", "main.py"),
            ("database/schema.sql", "database/schema.sql"),
            ("nested/dir/test.json", "nested/dir/test.json"),
            ("docs\\notes.md", "docs/notes.md"),
        ]
        for inp, expected in cases:
            with self.subTest(path=inp):
                self.assertEqual(str(normalize_relative_path(inp)), expected)

    def test_normalize_rejects_path_traversal(self):
        traversals = [
            "../outside.py",
            "../../etc/passwd.py",
            "nested/../../outside.py",
            "..\\..\\Windows\\system32.py",
            "nested/..\\../outside.py",
        ]
        for path in traversals:
            with self.subTest(path=path):
                with self.assertRaises(UnsafePathError) as ctx:
                    normalize_relative_path(path)
                self.assertIn("Yol geçişi", str(ctx.exception))

    def test_normalize_rejects_absolute_paths(self):
        absolutes = [
            "/etc/shadow.py",
            "/var/log/app.log",
            "C:\\Windows\\System32\\cmd.exe.py",
            "C:file.py",
            "\\\\network\\share\\file.py",
        ]
        for path in absolutes:
            with self.subTest(path=path):
                with self.assertRaises(UnsafePathError) as ctx:
                    normalize_relative_path(path)
                self.assertIn("Mutlak yol", str(ctx.exception))

    def test_normalize_rejects_unallowed_extensions(self):
        unallowed = [
            "run.exe",
            "setup.bat",
            "script.sh",
            "binary.dll",
            "package.bin",
            "noextension",
        ]
        for name in unallowed:
            with self.subTest(name=name):
                with self.assertRaises(UnsafePathError) as ctx:
                    normalize_relative_path(name)
                self.assertIn("İzin verilmeyen dosya uzantısı", str(ctx.exception))

    def test_normalize_rejects_reserved_device_names(self):
        reserved = ["CON.py", "PRN.sql", "AUX.txt", "NUL.json", "COM1.py", "LPT2.md"]
        for name in reserved:
            with self.subTest(name=name):
                with self.assertRaises(UnsafePathError) as ctx:
                    normalize_relative_path(name)
                self.assertIn("Ayrılmış aygıt adı", str(ctx.exception))


class TestRunWorkspaceWriting(unittest.TestCase):

    def setUp(self):
        self.temp_root = tempfile.mkdtemp(prefix="ws_root_")

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_workspace_isolation_under_run_id(self):
        ws = RunWorkspace("run-test-01", root=self.temp_root)
        self.assertEqual(ws.path, Path(self.temp_root).resolve() / "run-test-01")

        files = [
            {"filename": "database/schema.sql", "content": "CREATE TABLE t (id INT);"},
            {"filename": "backend/app.py", "content": "print('hello')"},
        ]
        written = ws.write_files(files)

        self.assertEqual(len(written), 2)
        for item in written:
            abs_p = Path(item["path"])
            self.assertTrue(abs_p.is_file())
            self.assertTrue(ws.path in abs_p.parents)
            self.assertIn("sha256", item)
            self.assertGreater(item["size_bytes"], 0)

    def test_write_files_validates_entire_batch_before_writing(self):
        ws = RunWorkspace("run-test-02", root=self.temp_root)
        files = [
            {"filename": "safe1.py", "content": "x = 1"},
            {"filename": "../evil.py", "content": "malicious = True"},
        ]

        with self.assertRaises(UnsafePathError):
            ws.write_files(files)

        safe_path = ws.path / "safe1.py"
        self.assertFalse(safe_path.exists(), "No file should be written if any entry is unsafe")

    def test_write_files_rejects_duplicate_filenames(self):
        ws = RunWorkspace("run-test-03", root=self.temp_root)
        files = [
            {"filename": "dup.py", "content": "v1"},
            {"filename": "dup.py", "content": "v2"},
        ]
        with self.assertRaises(UnsafePathError) as ctx:
            ws.write_files(files)
        self.assertIn("aynı dosya iki kez", str(ctx.exception).lower())

    def test_write_files_rejects_oversized_file(self):
        ws = RunWorkspace("run-test-04", root=self.temp_root)
        huge = "A" * (1_000_000 + 10)
        files = [{"filename": "big.txt", "content": huge}]
        with self.assertRaises(UnsafePathError) as ctx:
            ws.write_files(files)
        self.assertIn("çok büyük", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
