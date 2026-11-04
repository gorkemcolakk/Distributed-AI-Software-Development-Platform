"""
S3-03 (Kübra Hepcan): the Streamlit UI lists the files the Master wrote into workspaces/{run_id}/.

Only the pure helper is tested here; importing app.py runs it in bare mode (same as test_api_config_fallback).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi")))

from master_agent_projesi.app import generated_file_rows, GEN_MODE_LABELS


def _record(task_id, title, agent, output_files):
    return {"task_id": task_id, "title": title, "assigned_agent": agent, "output_files": output_files}


class TestGeneratedFileRows(unittest.TestCase):

    def test_lists_written_files_with_path_mode_and_content(self):
        report = {"workspace_path": os.path.join("work", "run-1"), "task_assignments": [
            _record("task-req-1", "Spec", "Integration Agent", []),
            _record("task-fe-1", "UI", "Frontend Agent", ["ui_task_fe_1.html"]),
        ]}
        artifacts = {"task-fe-1": {"artifacts": {
            "files": [{"filename": "ui_task_fe_1.html", "content": "<html></html>"}],
            "generation_mode": "ollama"}}}

        rows = generated_file_rows(report, artifacts)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["file"], "ui_task_fe_1.html")
        self.assertEqual(row["agent"], "Frontend Agent")
        self.assertEqual(row["mode"], "ollama")
        self.assertEqual(row["content"], "<html></html>")
        self.assertEqual(row["path"], os.path.join("work", "run-1", "ui_task_fe_1.html"))

    def test_task_without_files_and_missing_artifacts_do_not_crash(self):
        report = {"workspace_path": None, "task_assignments": [
            _record("task-fe-1", "UI", None, ["ui.html"]),
            _record("task-be-1", "API", "Backend Agent", []),
        ]}
        rows = generated_file_rows(report, {})

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "ui.html")
        self.assertEqual(rows[0]["agent"], "-")
        self.assertIsNone(rows[0]["content"])
        self.assertIsNone(rows[0]["mode"])

    def test_nested_and_windows_style_names_match_their_content(self):
        report = {"workspace_path": "w", "task_assignments": [
            _record("task-db-1", "DB", "Database Agent", ["database/schema.sql"])]}
        artifacts = {"task-db-1": {"artifacts": {
            "files": [{"filename": "database\\schema.sql", "content": "CREATE TABLE t(id INT);"}],
            "synthesis_mode": "safe_fallback"}}}

        row = generated_file_rows(report, artifacts)[0]
        self.assertEqual(row["content"], "CREATE TABLE t(id INT);")
        self.assertEqual(row["mode"], "safe_fallback")

    def test_fallback_and_template_modes_are_never_labelled_as_model_output(self):
        for mode in ("fallback", "safe_fallback", "template"):
            self.assertNotEqual(GEN_MODE_LABELS[mode][0], GEN_MODE_LABELS["ollama"][0])
            self.assertIn("model çıktısı değil" if mode != "template" else "Şablon", GEN_MODE_LABELS[mode][0])


if __name__ == "__main__":
    unittest.main()
