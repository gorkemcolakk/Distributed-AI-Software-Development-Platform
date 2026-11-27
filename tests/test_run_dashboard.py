"""
S5-03 (Kübra Hepcan): run telemetry dashboard (master_agent_projesi/run_dashboard.py).

Checks that the dashboard reads a selected run_id's real task statuses, durations and attempts
from state.db, that values not collected yet are never shown as 0, and that demo data is labelled.
Uses a temporary state.db; no Ollama and no Streamlit server.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from master_agent_projesi import run_dashboard as rd
from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.frontend_agent import FrontendAgent
from src.agents.integration_agent import IntegrationAgent
from src.agents.testing_agent import TestingAgent
from src.master import db_manager
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class _Col:
    def __init__(self, st):
        self.st = st

    def metric(self, label, value):
        self.st.calls.append(("metric", f"{label}={value}"))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSt:
    def __init__(self):
        self.calls = []
        self.charts = []
        self.frames = []

    def __getattr__(self, name):  # markdown, caption, info, warning, success, error
        def record(text="", *args, **kwargs):
            self.calls.append((name, str(text)))
        return record

    def columns(self, spec, **kwargs):
        return [_Col(self) for _ in range(spec if isinstance(spec, int) else len(spec))]

    def dataframe(self, df, **kwargs):
        self.frames.append(df)

    def bar_chart(self, df, **kwargs):
        self.charts.append(df)

    def selectbox(self, label, options, index=0, **kwargs):
        self.calls.append(("selectbox", label))
        return options[index]

    def text(self):
        return " ".join(c[1] for c in self.calls)


TASKS = [
    {"task_id": "t-db", "title": "Veritabanı", "assigned_agent_name": "DB Agent", "model_used": "llama3.2:3b",
     "status": "COMPLETED", "execution_time_seconds": 4.5},
    {"task_id": "t-fe", "title": "Arayüz", "assigned_agent_name": "FE Agent", "model_used": "qwen2.5-coder:3b",
     "status": "COMPLETED", "execution_time_seconds": 0.0},
    {"task_id": "t-be", "title": "API", "assigned_agent_name": "BE Agent", "model_used": "qwen2.5-coder:7b",
     "status": "IN_PROGRESS", "execution_time_seconds": 0.0},
    {"task_id": "t-qa", "title": "Test", "assigned_agent_name": None, "model_used": None,
     "status": "BLOCKED", "execution_time_seconds": 0.0},
]
ATTEMPTS = [
    {"task_id": "t-fe", "agent_id": "be", "attempt_no": 1, "is_successful": 0, "execution_time_seconds": 2.0,
     "model_used": "qwen2.5-coder:7b"},
    {"task_id": "t-fe", "agent_id": "be", "attempt_no": 2, "is_successful": 0, "execution_time_seconds": 0.0,
     "model_used": "qwen2.5-coder:7b"},
    {"task_id": "t-fe", "agent_id": "fe", "attempt_no": 3, "is_successful": 1, "execution_time_seconds": 6.0,
     "model_used": "qwen2.5-coder:3b"},
    {"task_id": "t-db", "agent_id": "db", "attempt_no": 1, "is_successful": 1, "execution_time_seconds": 4.5,
     "model_used": "llama3.2:3b"},
]


class TestDashboardData(unittest.TestCase):

    def setUp(self):
        self.rows = {r["task_id"]: r for r in rd.task_rows(TASKS, ATTEMPTS)}

    def test_durations_come_from_records_and_missing_ones_stay_none(self):
        self.assertEqual(self.rows["t-db"]["duration"], 4.5)
        self.assertEqual(self.rows["t-fe"]["duration"], 8.0)  # task total missing -> sum of measured attempts
        self.assertIsNone(self.rows["t-be"]["duration"])       # still running: not 0
        self.assertIn(rd.NOT_COLLECTED, self.rows["t-be"]["note"])
        self.assertEqual(self.rows["t-qa"]["note"], rd.NOT_RUN)

    def test_attempt_retry_and_reassignment_counts(self):
        fe = self.rows["t-fe"]
        self.assertEqual((fe["attempts"], fe["retries"], fe["reassigned"]), (3, 1, 1))
        self.assertIsNone(self.rows["t-be"]["attempts"])  # no attempt rows yet

    def test_model_comparison_uses_attempts(self):
        models = {m["model"]: m for m in rd.model_comparison(ATTEMPTS)}
        self.assertEqual((models["qwen2.5-coder:7b"]["success"], models["qwen2.5-coder:7b"]["failed"]), (0, 2))
        self.assertEqual(models["qwen2.5-coder:7b"]["avg_duration"], 2.0)  # the 0.0 attempt is not averaged in
        self.assertEqual(models["qwen2.5-coder:3b"]["success_rate"], 100.0)
        self.assertEqual(rd.model_comparison([]), [])

    def test_agent_distribution(self):
        dist = {d["agent"]: d for d in rd.agent_distribution(self.rows.values())}
        self.assertEqual(dist["FE Agent"]["completed"], 1)
        self.assertEqual(dist["BE Agent"]["other"], 1)
        self.assertEqual(dist["Atanmadı"]["other"], 1)

    def test_table_writes_out_missing_values(self):
        df = rd.table_frame(list(self.rows.values()))
        be = df[df["Görev"] == "API"].iloc[0]
        self.assertEqual(be["Süre"], rd.NOT_COLLECTED)
        self.assertEqual(be["Deneme"], rd.NOT_COLLECTED)
        self.assertEqual(df[df["Görev"] == "Test"].iloc[0]["Süre"], rd.NOT_RUN)
        self.assertNotIn("0.0 sn", " ".join(df["Süre"]))

    def test_utc_timestamps_are_shown_in_local_time(self):
        from datetime import datetime, timezone
        expected = datetime(2026, 11, 27, 19, 0, 50, tzinfo=timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M:%S")
        self.assertEqual(rd.local_time("2026-11-27 19:00:50"), expected)
        self.assertEqual(rd.local_time(None), "?")

    def test_summary_wall_time_and_unmeasured(self):
        run = {"started_at": "2026-11-27 10:00:00", "finished_at": "2026-11-27 10:01:30"}
        summary = rd.run_summary(run, list(self.rows.values()), ATTEMPTS)
        self.assertEqual(summary["wall_seconds"], 90.0)
        self.assertEqual(summary["unmeasured"], 1)
        self.assertIsNone(rd.run_summary({"started_at": "2026-11-27 10:00:00"}, [], [])["wall_seconds"])


class TestDashboardWithStateDb(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "state.db")
        self.old_env = os.environ.get("STATE_DB_PATH")
        os.environ["STATE_DB_PATH"] = self.db_path
        db_manager.init_db(self.db_path, verbose=False)

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("STATE_DB_PATH", None)
        else:
            os.environ["STATE_DB_PATH"] = self.old_env
        self.tmp.cleanup()

    def _run_engine(self, title):
        agents = [FrontendAgent(use_ollama=False), BackendAgent(use_ollama=False), DatabaseAgent(use_ollama=False),
                  TestingAgent(use_ollama=False), IntegrationAgent(use_llm=False)]
        orch = MasterOrchestrator(evaluator=CapabilityEvaluator(agents), db_path=self.db_path)
        return orch.process_requirement("Kütüphane sistemi", title)

    def test_list_runs_and_attempts_for_run(self):
        first = self._run_engine("Birinci")
        second = self._run_engine("İkinci")
        ids = [r["run_id"] for r in db_manager.list_runs(db_path=self.db_path)]
        self.assertEqual(set(ids), {first["run_id"], second["run_id"]})
        attempts = db_manager.get_attempts_for_run(first["run_id"], self.db_path)
        self.assertTrue(attempts)
        self.assertTrue(all(a["run_id"] == first["run_id"] for a in attempts))

    def test_render_selected_run_is_labelled_live(self):
        report = self._run_engine("Kütüphane")
        st = FakeSt()
        rd.render_run_dashboard(st, db_manager, current_run_id=report["run_id"])
        text = st.text()
        self.assertIn("CANLI YÜRÜTME VERİSİ", text)
        self.assertIn(report["run_id"], text)
        self.assertNotIn("TANITIM", text)
        self.assertEqual(len(st.frames[0]), report["total_tasks_processed"])
        self.assertGreaterEqual(len(st.charts), 2)  # model comparison + agent distribution

    def test_empty_db_says_no_runs(self):
        st = FakeSt()
        rd.render_run_dashboard(st, db_manager)
        self.assertIn("henüz kayıtlı çalıştırma yok", st.text())
        self.assertEqual(st.frames, [])


class TestDemoIsLabelled(unittest.TestCase):

    def test_demo_report_is_marked_and_has_no_fake_zero_durations(self):
        report = {"run_id": "demo", "task_assignments": [
            {"task_id": "a", "title": "Demo görev", "assigned_agent": "FE", "model_used": "m",
             "status": "COMPLETED", "execution_time_seconds": 0.0}]}
        st = FakeSt()
        rd.render_run_dashboard(st, None, demo_report=report)
        text = st.text()
        self.assertIn("TANITIM VERİSİ", text)
        self.assertIn("(tanıtım)", text)
        self.assertNotIn("CANLI", text)
        self.assertEqual(st.frames[0].iloc[0]["Süre"], rd.NOT_COLLECTED)


if __name__ == "__main__":
    unittest.main()
