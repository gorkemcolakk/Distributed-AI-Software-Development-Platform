"""
Zip export of a run: all generated files in one download named after the project.
Pure functions, no Streamlit needed.
"""

import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from master_agent_projesi.run_export import build_run_zip, safe_project_name


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


if __name__ == "__main__":
    unittest.main()
