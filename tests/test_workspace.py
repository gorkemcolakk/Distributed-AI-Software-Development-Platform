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

from src.master.conflicts import SchemaConflictDetector
from src.agents.integration_agent import IntegrationAgent
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

    # --- S4-04: Path & Schema Conflict Resolution -------------------------
    def test_path_conflict_different_content_renames_and_preserves_both(self):
        ws = RunWorkspace("run-conflict-01", root=self.temp_root)
        r1 = ws.write_files([{"filename": "api/main.py", "content": "v = 1\n"}], owner="task-1")
        r2 = ws.write_files([{"filename": "api/main.py", "content": "v = 2\n"}], owner="task-2")

        self.assertIsNone(r1[0]["conflict"])
        self.assertEqual(r2[0]["relative_path"], "api/main.task-2.py")
        self.assertEqual(r2[0]["requested_path"], "api/main.py")
        self.assertEqual(r2[0]["conflict"]["resolution"], "RENAMED")
        self.assertEqual(r2[0]["conflict"]["other_task_id"], "task-1")
        self.assertEqual((ws.path / "api/main.py").read_text(encoding="utf-8"), "v = 1\n")
        self.assertEqual((ws.path / "api/main.task-2.py").read_text(encoding="utf-8"), "v = 2\n")
        self.assertEqual(len(ws.conflicts), 1)

    def test_path_conflict_identical_content_deduplicates(self):
        ws = RunWorkspace("run-conflict-02", root=self.temp_root)
        ws.write_files([{"filename": "database/schema.sql", "content": "CREATE TABLE t (id INT);\n"}], owner="task-1")
        r2 = ws.write_files([{"filename": "database/schema.sql", "content": "CREATE TABLE t (id INT);\n"}], owner="task-2")

        self.assertEqual(r2[0]["relative_path"], "database/schema.sql")
        self.assertEqual(r2[0]["conflict"]["resolution"], "DEDUPLICATED")
        self.assertEqual(r2[0]["conflict"]["other_task_id"], "task-1")

    def test_schema_conflict_detector_flags_different_columns_and_allows_identical(self):
        detector = SchemaConflictDetector()
        sql_a = "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);"
        sql_b_same = "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);"
        sql_b_diff = "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL);"

        self.assertEqual(detector.check("t1", "database/a.sql", sql_a), [])
        self.assertEqual(detector.check("t2", "database/b.sql", sql_b_same), [])
        conflicts = detector.check("t3", "database/c.sql", sql_b_diff)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflict_type"], "SCHEMA")
        self.assertEqual(conflicts[0]["resolution"], "REPORTED")
        self.assertEqual(conflicts[0]["table"], "users")
        self.assertEqual(conflicts[0]["other_task_id"], "t1")

    def test_integration_agent_reports_resolved_and_schema_conflicts(self):
        agent = IntegrationAgent()
        report = agent.inspect_artifacts(
            artifacts={
                "api/main.py": "x = 1\n",
                "api/main.task-2.py": "x = 2\n",
                "database/c.sql": "CREATE TABLE users (id INT);",
            },
            run_id="run-int-1",
            conflicts_log=[
                {"conflict_type": "PATH", "file_path": "api/main.py", "resolved_path": "api/main.task-2.py",
                 "resolution": "RENAMED", "detail": "renamed"},
                {"conflict_type": "SCHEMA", "file_path": "database/c.sql",
                 "resolution": "REPORTED", "detail": "schema mismatch"},
            ],
        )
        self.assertEqual(report.conflicts_resolved, 1)
        self.assertIn("api/main.py", report.conflicts_detected)
        self.assertIn("database/c.sql", report.conflicts_detected)
        self.assertEqual(report.status, "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
