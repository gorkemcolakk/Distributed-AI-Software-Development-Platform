"""
S4-03 (Kübra Hepcan): the Streamlit UI shows retried / reassigned tasks, Integration Agent code-review
results and clear warning cards for file conflicts and syntax errors.

The tests feed review_panel.py with the output of the REAL MasterOrchestrator (worker doubles, no Ollama,
no network, no SQLite), so a change in the engine's data shape breaks them instead of the demo.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi")))

from src.agents.base_agent import AgentCapabilityProfile, AgentStatus, BaseAgent, TaskResult
from src.agents.integration_agent import IntegrationAgent
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator
from src.master.retry_policy import RetryPolicy

from master_agent_projesi import review_panel as rp


class Worker(BaseAgent):
    """Test double. `script` items: None = success, "TIMEOUT"/"UNREACHABLE" = remote error, other = crash."""

    def __init__(self, agent_id, name, score, script=(), files=None, specialties=("backend",), fail_integration=False):
        profile = AgentCapabilityProfile(coding_score=score, reasoning_score=score,
                                         context_capacity=score, specialties=list(specialties))
        super().__init__(agent_id=agent_id, name=name, model_name=f"{agent_id}:1b", capability_profile=profile)
        self.script = list(script)
        self.files = files or {}
        self.fail_integration = fail_integration

    def execute_task(self, task):
        tid = task["task_id"]
        if self.fail_integration and task.get("category") == "INTEGRATION":
            return TaskResult(task_id=tid, agent_id=self.agent_id, status="FAILED", output_artifacts={},
                              logs=[], execution_time_seconds=0.0, error_message="not an integration agent")
        outcome = self.script.pop(0) if self.script else None
        if outcome is None:
            return TaskResult(task_id=tid, agent_id=self.agent_id, status="SUCCESS",
                              output_artifacts={"files": [dict(f) for f in self.files.get(tid, [])]},
                              logs=[], execution_time_seconds=0.5)
        if outcome in ("TIMEOUT", "UNREACHABLE"):
            return TaskResult(task_id=tid, agent_id=self.agent_id, status="FAILED",
                              output_artifacts={"error_contract": {"error_code": outcome, "message": "x"}},
                              logs=[], execution_time_seconds=1.0, error_message=f"[{outcome}] worker problem")
        return TaskResult(task_id=tid, agent_id=self.agent_id, status="FAILED", output_artifacts={},
                          logs=[], execution_time_seconds=0.1, error_message="model crashed")


def task(tid, category="BACKEND", specialty="backend", deps=()):
    return {"task_id": tid, "title": f"Task {tid}", "category": category, "description": f"desc {tid}",
            "dependencies": list(deps), "required_specialty": specialty}


def run(agents, tasks):
    evaluator = CapabilityEvaluator()
    for a in agents:
        evaluator.register_agent(a)
    orch = MasterOrchestrator(evaluator=evaluator, persist=False,
                              retry_policy=RetryPolicy(max_retries=1, backoff_seconds=0.0), sleep=lambda s: None)
    orch.analyzer.decompose = lambda text, title: {
        "requirement_id": "req", "project_title": title, "raw_requirement": text,
        "total_tasks": len(tasks), "tasks": [dict(t) for t in tasks]}
    report = orch.process_requirement("s4-03", "S4-03")
    return orch, report, {r["task_id"]: r for r in report["task_assignments"]}


class TestRetriedAndReassignedTasks(unittest.TestCase):

    def test_timeout_then_success_on_same_agent_is_retrying(self):
        primary = Worker("p", "Primary", 90, script=["TIMEOUT", None])
        backup = Worker("b", "Backup", 60)
        orch, _, _ = run([primary, backup], [task("t1")])

        rows = rp.attempt_rows(orch.execution_history, [primary, backup])["t1"]

        self.assertEqual([r["kind"] for r in rows], ["FIRST", "RETRYING"])
        self.assertEqual([r["agent"] for r in rows], ["Primary", "Primary"])
        self.assertEqual([r["ok"] for r in rows], [False, True])
        self.assertEqual(rows[0]["code"], "TIMEOUT")
        self.assertEqual(rp.task_flags(rows), ["RETRYING"])
        markup = rp.attempt_flow_html(rows)
        self.assertIn("YENİDEN DENENDİ", markup)
        self.assertNotIn("BAŞKA AJANA", markup)
        self.assertIn("zamanında yanıt vermedi", markup)

    def test_crash_goes_to_another_agent_and_is_reassigned(self):
        primary = Worker("p", "Primary", 90, script=["CRASH"])
        backup = Worker("b", "Backup", 60)
        orch, _, by_id = run([primary, backup], [task("t1")])

        rows = rp.attempt_rows(orch.execution_history, [primary, backup])["t1"]

        self.assertEqual([r["kind"] for r in rows], ["FIRST", "REASSIGNED"])
        self.assertEqual(rows[1]["agent"], "Backup")
        self.assertIn("model crashed", rows[0]["message"])
        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Backup"])
        self.assertIn("Backup", rp.retry_summary(rows))
        self.assertIn("BAŞKA AJANA DEVREDİLDİ", rp.attempt_flow_html(rows))

    def test_retry_then_reassignment_shows_both_badges(self):
        primary = Worker("p", "Primary", 90, script=["TIMEOUT", "TIMEOUT"])
        backup = Worker("b", "Backup", 60)
        orch, _, _ = run([primary, backup], [task("t1")])

        rows = rp.attempt_rows(orch.execution_history, [primary, backup])["t1"]

        self.assertEqual([r["kind"] for r in rows], ["FIRST", "RETRYING", "REASSIGNED"])
        self.assertEqual(rp.task_flags(rows), ["RETRYING", "REASSIGNED"])
        self.assertIn("1 kez yeniden denendi", rp.retry_summary(rows))

    def test_task_that_ran_once_shows_nothing(self):
        orch, _, _ = run([Worker("p", "Primary", 90)], [task("t1")])
        rows = rp.attempt_rows(orch.execution_history)["t1"]
        self.assertEqual(rp.task_flags(rows), [])
        self.assertEqual(rp.attempt_flow_html(rows), "")

    def test_fallback_uses_attempted_agents_when_history_is_missing(self):
        rows = rp.rows_from_attempted_agents(["A", "A", "B"])
        self.assertEqual([r["kind"] for r in rows], ["FIRST", "RETRYING", "REASSIGNED"])
        self.assertEqual(rp.rows_from_attempted_agents([]), [])
        self.assertEqual(rp.rows_from_attempted_agents(["A"])[0]["kind"], "FIRST")

    def test_error_text_is_escaped(self):
        rows = [{"no": 1, "agent": "<b>X</b>", "kind": "FIRST", "ok": False, "code": None,
                 "message": "<script>alert(1)</script>", "seconds": 0},
                {"no": 2, "agent": "Y", "kind": "REASSIGNED", "ok": True, "code": None, "message": None, "seconds": 0}]
        markup = rp.attempt_flow_html(rows)
        self.assertNotIn("<script>", markup)
        self.assertNotIn("<b>X</b>", markup)


def pipeline(backend_files, frontend_files, extra_backend=None):
    backend = Worker("be", "Backend Double", 80, files={"t-be": backend_files}, fail_integration=True)
    frontend = Worker("fe", "Frontend Double", 80, specialties=("frontend",), files={"t-fe": frontend_files},
                      fail_integration=True)
    integration = IntegrationAgent(workspace_root=tempfile.gettempdir(), use_llm=False)  # no Ollama in tests
    tasks = [task("t-be"), task("t-fe", "FRONTEND", "frontend"),
             task("t-int", "INTEGRATION", "integration", deps=["t-be", "t-fe"])]
    orch, report, by_id = run([backend, frontend, integration], tasks)
    return orch, report, by_id


class TestIntegrationReview(unittest.TestCase):

    def test_approved_review_lists_every_file_as_approved(self):
        orch, report, by_id = pipeline([{"filename": "api.py", "content": "X = 1\n"}],
                                       [{"filename": "ui.html", "content": "<html></html>"}])
        view = rp.review_view(rp.find_review_report(orch.execution_history))

        self.assertEqual(by_id["t-int"]["status"], "COMPLETED")
        self.assertEqual(view["status"], "APPROVED")
        self.assertEqual({r["file"]: r["status"] for r in view["files"]},
                         {"api.py": "APPROVED", "ui.html": "APPROVED"})
        self.assertEqual(view["counts"], {"APPROVED": 2, "REVIEW_REQUIRED": 0, "REJECTED": 0})
        self.assertEqual(rp.warning_cards(view, report["conflicts"]), [])
        self.assertIn("ONAYLANDI", rp.review_table_html(view))

    def test_review_required_for_warning_findings(self):
        orch, report, by_id = pipeline([{"filename": "schema.sql", "content": "-- nothing here\n"}],
                                       [{"filename": "ui.html", "content": "<html></html>"}])
        view = rp.review_view(rp.find_review_report(orch.execution_history))

        self.assertEqual(by_id["t-int"]["status"], "COMPLETED")  # REVIEW_REQUIRED still counts as success
        self.assertEqual(view["status"], "REVIEW_REQUIRED")
        self.assertEqual({r["file"]: r["status"] for r in view["files"]}["schema.sql"], "REVIEW_REQUIRED")
        cards = rp.warning_cards(view)
        self.assertEqual([c["severity"] for c in cards], ["WARNING"])
        self.assertIn("İNCELEME GEREKLİ", rp.review_table_html(view))

    def test_syntax_error_is_rejected_and_gets_its_own_card_even_though_the_task_failed(self):
        orch, report, by_id = pipeline([{"filename": "api.py", "content": "def broken(:\n    pass\n"}],
                                       [{"filename": "ui.html", "content": "<html></html>"}])
        # A REJECTED review makes the task FAILED, so it is NOT in the SUCCESS-only artifacts dict...
        self.assertEqual(by_id["t-int"]["status"], "FAILED")
        success_only = [r for r in orch.execution_history if r.status == "SUCCESS" and rp._is_review_report(r.output_artifacts)]
        self.assertEqual(success_only, [])
        # ...but the full execution history still has the report
        view = rp.review_view(rp.find_review_report(orch.execution_history))

        self.assertEqual(view["status"], "REJECTED")
        files = {r["file"]: r["status"] for r in view["files"]}
        self.assertEqual(files, {"api.py": "REJECTED", "ui.html": "APPROVED"})
        self.assertEqual(view["files"][0]["file"], "api.py")  # worst first
        cards = rp.warning_cards(view)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["kind"], "SYNTAX")
        self.assertEqual(cards[0]["severity"], "CRITICAL")
        self.assertEqual(cards[0]["file"], "api.py")
        self.assertIn("Satır 1", cards[0]["message"])
        markup = rp.warning_card_html(cards[0])
        self.assertIn("Sözdizimi (syntax) hatası", markup)
        self.assertIn("api.py", markup)
        self.assertIn("REDDEDİLDİ", rp.review_table_html(view))

    def test_two_agents_writing_the_same_path_make_a_conflict_card(self):
        orch, report, by_id = pipeline([{"filename": "app/main.py", "content": "API = 1\n"}],
                                       [{"filename": "app/main.py", "content": "UI = 1\n"}])
        view = rp.review_view(rp.find_review_report(orch.execution_history))
        cards = rp.warning_cards(view, report["conflicts"])

        self.assertEqual(view["status"], "REJECTED")
        self.assertTrue(cards)
        self.assertEqual(cards[0]["kind"], "PATH")
        self.assertEqual(cards[0]["title"], "Dosya yolu çakışması")
        self.assertIn("Backend Double", cards[0]["message"])
        self.assertIn("Frontend Double", cards[0]["message"])

    def test_no_review_report_means_none(self):
        orch, _, _ = run([Worker("p", "Primary", 90)], [task("t1")])
        self.assertIsNone(rp.find_review_report(orch.execution_history))
        self.assertIsNone(rp.review_view(None))
        self.assertEqual(rp.warning_cards(None, None), [])

    def test_pseudo_paths_do_not_become_file_rows(self):
        view = rp.review_view({"status": "REJECTED", "inspected_files": [], "summary": "s", "findings": [
            {"file_path": "WORKSPACE", "severity": "CRITICAL", "issue": "İncelenecek hiçbir çıktı yok",
             "actionable_suggestion": "x"}]})
        self.assertEqual(view["files"], [])
        self.assertEqual(len(rp.warning_cards(view)), 1)
        self.assertIn("İncelenen dosya yok", rp.review_table_html(view))

    def test_general_model_finding_is_a_card_not_a_file_row(self):
        view = rp.review_view({"status": "REVIEW_REQUIRED", "inspected_files": ["api.py"], "summary": "s", "findings": [
            {"file_path": "GENERAL", "severity": "WARNING", "issue": "Genel tasarım notu",
             "actionable_suggestion": "x"}]})
        self.assertEqual([r["file"] for r in view["files"]], ["api.py"])
        self.assertEqual(view["files"][0]["status"], "APPROVED")
        self.assertEqual(len(rp.warning_cards(view)), 1)

    def test_review_mode_says_who_reviewed(self):
        base = {"status": "APPROVED", "inspected_files": ["a.py"], "findings": []}
        llm = rp.review_view(dict(base, review_mode="llm", model_used="phi4-mini:3.8b"))
        self.assertEqual(rp.review_mode_text(llm)[0], "Model incelemesi: phi4-mini:3.8b")
        self.assertIn("phi4-mini:3.8b", rp.review_table_html(llm))
        fb = rp.review_view(dict(base, review_mode="fallback", fallback_reason="CONNECTION_REFUSED"))
        self.assertIn("Model kullanılamadı", rp.review_mode_text(fb)[0])
        self.assertIn("CONNECTION_REFUSED", rp.review_mode_text(fb)[0])
        static = rp.review_view(dict(base))  # old reports without the S4-05 fields
        self.assertIn("statik", rp.review_mode_text(static)[0])
        # "llm" without a model name must not be presented as a model review
        self.assertNotIn("Model incelemesi", rp.review_mode_text(rp.review_view(dict(base, review_mode="llm")))[0])

    def test_real_integration_review_reports_static_mode_when_model_is_off(self):
        orch, _, _ = pipeline([{"filename": "api.py", "content": "X = 1\n"}],
                              [{"filename": "ui.html", "content": "<html></html>"}])
        view = rp.review_view(rp.find_review_report(orch.execution_history))
        self.assertEqual(view["mode"], "static")
        self.assertIn("statik", rp.review_table_html(view))

    def test_user_controlled_text_is_escaped(self):
        view = rp.review_view({"status": "REJECTED", "inspected_files": ["<img src=x>.py"], "summary": "<i>s</i>",
                               "findings": [{"file_path": "<img src=x>.py", "severity": "CRITICAL",
                                             "issue": "<script>1</script>", "actionable_suggestion": "<b>fix</b>"}]})
        for markup in (rp.review_table_html(view), rp.warning_card_html(rp.warning_cards(view)[0])):
            self.assertNotIn("<script>", markup)
            self.assertNotIn("<img", markup)
            self.assertNotIn("<b>fix</b>", markup)


class TestConflictCards(unittest.TestCase):

    def test_schema_conflict_is_reported_card(self):
        cards = rp.warning_cards(None, [{
            "conflict_type": "SCHEMA", "file_path": "db/b.sql", "resolution": "REPORTED", "table": "users",
            "detail": "'users' tablosu 'db/a.sql' dosyasında farklı tanımlanmış."}])
        self.assertEqual(cards[0]["kind"], "SCHEMA")
        self.assertEqual(cards[0]["severity"], "CRITICAL")
        self.assertIn("db/a.sql", cards[0]["message"])

    def test_renamed_path_conflict_shows_new_path_as_warning(self):
        cards = rp.warning_cards(None, [{
            "conflict_type": "PATH", "file_path": "app.py", "resolution": "RENAMED",
            "resolved_path": "t2/app.py", "detail": "Aynı yol, farklı içerik."}])
        self.assertEqual(cards[0]["severity"], "WARNING")
        self.assertIn("t2/app.py", cards[0]["hint"])

    def test_critical_cards_come_first(self):
        view = {"findings": [{"file_path": "a.sql", "severity": "WARNING", "issue": "w", "suggestion": ""},
                             {"file_path": "b.py", "severity": "CRITICAL", "issue": "Python sözdizimi (syntax) hatası",
                              "suggestion": ""},
                             {"file_path": "c.py", "severity": "INFO", "issue": "i", "suggestion": ""}]}
        cards = rp.warning_cards(view)
        self.assertEqual([c["severity"] for c in cards], ["CRITICAL", "WARNING"])


class FakeSt:
    def __init__(self):
        self.calls = []

    def markdown(self, text, unsafe_allow_html=False):
        self.calls.append(("markdown", text))

    def caption(self, text):
        self.calls.append(("caption", text))

    def success(self, text):
        self.calls.append(("success", text))


class TestRenderEntryPoints(unittest.TestCase):

    def test_render_review_panel_with_rejected_review(self):
        orch, report, _ = pipeline([{"filename": "api.py", "content": "def broken(:\n"}],
                                   [{"filename": "ui.html", "content": "<html></html>"}])
        st = FakeSt()
        rp.render_review_panel(st, report, orch.execution_history)
        text = " ".join(c[1] for c in st.calls)
        self.assertIn("Kod inceleme sonuçları", text)
        self.assertIn("REDDEDİLDİ", text)
        self.assertIn("Uyarılar (1)", text)
        self.assertIn("Sözdizimi (syntax) hatası", text)

    def test_render_review_panel_clean_run_says_so(self):
        orch, report, _ = pipeline([{"filename": "api.py", "content": "X = 1\n"}],
                                   [{"filename": "ui.html", "content": "<html></html>"}])
        st = FakeSt()
        rp.render_review_panel(st, report, orch.execution_history)
        self.assertEqual(st.calls[-1][0], "success")

    def test_render_review_panel_without_integration_review(self):
        orch, report, _ = run([Worker("p", "Primary", 90)], [task("t1")])
        st = FakeSt()
        rp.render_review_panel(st, report, orch.execution_history)
        self.assertEqual(st.calls[-1][0], "caption")

    def test_render_task_attempts_only_writes_for_retried_tasks(self):
        primary = Worker("p", "Primary", 90, script=["CRASH"])
        backup = Worker("b", "Backup", 60)
        orch, _, _ = run([primary, backup], [task("t1"), task("t2")])
        rows = rp.attempt_rows(orch.execution_history, [primary, backup])
        st = FakeSt()
        rp.render_task_attempts(st, "t1", rows)
        rp.render_task_attempts(st, "t2", rows)
        self.assertEqual(len(st.calls), 1)


if __name__ == "__main__":
    unittest.main()
