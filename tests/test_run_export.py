"""
Zip export of a run: all generated files in one download named after the project.
Pure functions, no Streamlit needed.
"""

import csv
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from master_agent_projesi.run_export import (
    build_agent_telemetry_csv_export,
    build_run_history_csv_export,
    build_run_zip,
    build_telemetry_json_export,
    safe_project_name,
)
from src.master import db_manager


class TestProjectName(unittest.TestCase):

    def test_turkish_letters_and_spaces(self):
        self.assertEqual(safe_project_name("Restoran Sipariş Sistemi"), "restoran-siparis-sistemi")
        self.assertEqual(safe_project_name("İçecek Şirketi Öğrenci Çözümü"), "icecek-sirketi-ogrenci-cozumu")

    def test_symbols_are_removed(self):
        self.assertEqual(safe_project_name("  Kütüphane: Kitap/Üye (v2)!  "), "kutuphane-kitap-uye-v2")

    def test_empty_name_uses_fallback(self):
        self.assertEqual(safe_project_name(""), "proje")
        self.assertEqual(safe_project_name(None, "run-1234"), "run-1234")
        self.assertEqual(safe_project_name("!!!"), "proje")

    def test_name_is_shortened_without_trailing_dash(self):
        name = safe_project_name("a" * 39 + " bbbbbbbbb")
        self.assertLessEqual(len(name), 40)
        self.assertFalse(name.endswith("-"))

    def test_path_characters_never_reach_the_name(self):
        name = safe_project_name("../../etc/passwd")
        self.assertNotIn("/", name)
        self.assertNotIn(".", name)


class TestBuildRunZip(unittest.TestCase):

    def open(self, data):
        return zipfile.ZipFile(io.BytesIO(data))

    def test_files_are_zipped_under_the_project_folder(self):
        rows = [{"file": "ui_task_fe.html", "content": "<html>ğ</html>"},
                {"file": "backend/app.py", "content": "print('hi')"}]
        name, data, count = build_run_zip("Restoran Sipariş Sistemi", rows)
        self.assertEqual(name, "restoran-siparis-sistemi.zip")
        self.assertEqual(count, 2)
        with self.open(data) as z:
            self.assertEqual(sorted(z.namelist()), ["restoran-siparis-sistemi/backend/app.py",
                                                    "restoran-siparis-sistemi/ui_task_fe.html"])
            self.assertEqual(z.read("restoran-siparis-sistemi/ui_task_fe.html").decode("utf-8"), "<html>ğ</html>")
            self.assertIsNone(z.testzip())

    def test_windows_separators_are_normalised(self):
        _, data, count = build_run_zip("P", [{"file": "backend\\app.py", "content": "x"}])
        self.assertEqual(count, 1)
        with self.open(data) as z:
            self.assertEqual(z.namelist(), ["p/backend/app.py"])

    def test_unsafe_paths_are_skipped(self):
        rows = [{"file": "../evil.py", "content": "x"}, {"file": "a/../../evil.py", "content": "x"},
                {"file": "/etc/passwd", "content": "x"}, {"file": "C:\\win\\x.py", "content": "x"},
                {"file": "", "content": "x"}, {"file": "ok.py", "content": "x"}]
        _, data, count = build_run_zip("P", rows)
        self.assertEqual(count, 1)
        with self.open(data) as z:
            self.assertEqual(z.namelist(), ["p/ok.py"])

    def test_rows_without_text_content_are_skipped(self):
        rows = [{"file": "a.py", "content": None}, {"file": "b.py", "content": b"bytes"},
                {"file": "c.py", "content": ""}, {"file": "d.py", "content": "x"}]
        _, data, count = build_run_zip("P", rows)
        self.assertEqual(count, 2)  # an empty string is still a real (empty) file
        with self.open(data) as z:
            self.assertEqual(sorted(z.namelist()), ["p/c.py", "p/d.py"])

    def test_same_file_twice_is_written_once(self):
        rows = [{"file": "a.py", "content": "one"}, {"file": "./a.py", "content": "two"}]
        _, data, count = build_run_zip("P", rows)
        self.assertEqual(count, 1)
        with self.open(data) as z:
            self.assertEqual(z.read("p/a.py"), b"one")

    def test_no_files_gives_empty_count(self):
        name, data, count = build_run_zip("P", [])
        self.assertEqual((name, count), ("p.zip", 0))
        with self.open(data) as z:
            self.assertEqual(z.namelist(), [])


class TestTelemetryExports(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "telemetry.db")
        db_manager.init_db(self.db_path, verbose=False)
        db_manager.create_run("run-exp-1", "Kütüphane Sistemi", total_tasks=1, db_path=self.db_path)
        db_manager.save_task_result(
            "run-exp-1",
            {"task_id": "t-db", "title": "DB", "category": "DATABASE", "dependencies": []},
            {
                "task_id": "t-db", "title": "DB", "assigned_agent": "Database Agent",
                "model_used": "llama3.2:3b", "fit_score": 90.0, "execution_time_seconds": 4.5,
                "status": "COMPLETED", "agent_result_status": "SUCCESS",
                "reason": "ok", "attempted_agents": ["Database Agent"],
                "output_files": ["database/schema.sql"],
            },
            attempts=[{
                "agent_id": "agent-database", "agent_name": "Database Agent",
                "model_used": "llama3.2:3b", "is_successful": True, "execution_time_seconds": 4.5,
            }],
            db_path=self.db_path,
        )
        db_manager.finish_run("run-exp-1", "COMPLETED", {"COMPLETED": 1}, db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_telemetry_json_and_csv_exports_are_repeatable(self):
        j_name, j_bytes_1, j_count = build_telemetry_json_export("Kütüphane Sistemi", db_path=self.db_path)
        _, j_bytes_2, _ = build_telemetry_json_export("Kütüphane Sistemi", db_path=self.db_path)
        self.assertEqual(j_name, "kutuphane-sistemi-telemetry.json")
        self.assertEqual(j_count, 1)
        self.assertEqual(j_bytes_1, j_bytes_2)
        self.assertEqual(json.loads(j_bytes_1.decode("utf-8"))["runs"][0]["run_id"], "run-exp-1")

        a_name, a_bytes, a_count = build_agent_telemetry_csv_export("Kütüphane Sistemi", db_path=self.db_path)
        self.assertEqual(a_name, "kutuphane-sistemi-agent-telemetry.csv")
        self.assertEqual(a_count, 1)
        a_rows = list(csv.DictReader(io.StringIO(a_bytes.decode("utf-8"))))
        self.assertEqual(a_rows[0]["agent_name"], "Database Agent")
        self.assertEqual(a_rows[0]["avg_attempt_duration_seconds"], "4.5")

        r_name, r_bytes, r_count = build_run_history_csv_export("Kütüphane Sistemi", db_path=self.db_path)
        self.assertEqual(r_name, "kutuphane-sistemi-run-history.csv")
        self.assertEqual(r_count, 1)
        r_rows = list(csv.DictReader(io.StringIO(r_bytes.decode("utf-8"))))
        self.assertEqual(r_rows[0]["run_id"], "run-exp-1")


if __name__ == "__main__":
    unittest.main()
