import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.contracts import ManifestReportContract
from src.agents.base_agent import AgentStatus
from src.agents.integration_agent import IntegrationAgent


class TestIntegrationAgentManifest(unittest.TestCase):
    def setUp(self):
        self.agent = IntegrationAgent(use_llm=False)
        self.run_id = "test_sprint3_05"

    def test_generate_manifest_success(self):
        artifacts = {
            "src/main.py": "print('Hello World')",
            "docs/readme.md": "# Readme Content",
        }

        report = self.agent.generate_artifact_manifest(self.run_id, artifacts)

        self.assertEqual(report.catalog_status, "COMPLETED")
        self.assertEqual(len(report.manifests), 2)
        self.assertEqual(len(report.missing_or_empty_files), 0)

        main_manifest = next(m for m in report.manifests if m.file_name == "main.py")
        self.assertGreater(main_manifest.size_bytes, 0)
        self.assertEqual(len(main_manifest.sha256_hash), 64)

    def test_generate_manifest_with_empty_files(self):
        artifacts = {
            "src/main.py": "print('Hello World')",
            "src/empty.py": "",
            "src/spaces.py": "   ",
        }

        report = self.agent.generate_artifact_manifest(self.run_id, artifacts)

        self.assertEqual(report.catalog_status, "REVIEW_REQUIRED")
        self.assertEqual(len(report.manifests), 1)
        self.assertIn("src/empty.py", report.missing_or_empty_files)
        self.assertIn("src/spaces.py", report.missing_or_empty_files)

    @patch("src.agents.integration_agent.requests.post")
    def test_llm_code_review_with_phi4_mini_and_agent_status_preserved(self, mock_post):
        """S4-05: phi4-mini:3.8b ile kod inceleme bulgularının rapora eklendiğini ve status'un AgentStatus kaldığını doğrular."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": (
                '{"summary": "Tablo ve endpoint uyumu incelendi.", '
                '"findings": [{"file_path": "backend.py", "severity": "WARNING", '
                '"issue": "users tablosu sorgusu eksik", '
                '"actionable_suggestion": "schema.sql içindeki users tablosunu kullanın."}]}'
            )
        }
        mock_post.return_value = mock_response

        result = self.agent.execute_task(
            {
                "task_id": "task-int-llm",
                "run_id": "run_sprint4_05",
                "description": "Review backend and database integration",
                "use_llm": True,
                "output_artifacts": {
                    "schema.sql": "CREATE TABLE users (id INT PRIMARY KEY);",
                    "backend.py": "def get_items():\n    return []\n",
                    "index.html": "<html><body><h1>App</h1></body></html>",
                },
            }
        )

        self.assertIsInstance(self.agent.status, AgentStatus)
        self.assertEqual(self.agent.status, AgentStatus.IDLE)

        mock_post.assert_called_once()
        called_payload = mock_post.call_args.kwargs.get("json") or {}
        self.assertEqual(called_payload.get("model"), "phi4-mini:3.8b")

        out = result.output_artifacts
        self.assertEqual(out["status"], "REVIEW_REQUIRED")
        self.assertIn("Tablo ve endpoint uyumu incelendi.", out["llm_review_summary"])
        self.assertTrue(any("users tablosu" in f["issue"] for f in out["findings"]))
        self.assertEqual(out["artifact_manifest"]["catalog_status"], "COMPLETED")

    @patch("src.agents.integration_agent.requests.post")
    def test_llm_code_review_graceful_fallback_when_ollama_offline(self, mock_post):
        """S4-05: Ollama kapalıyken veya bağlantı hatası olduğunda ajanın çökmeden statik analizle devam ettiğini doğrular."""
        mock_post.side_effect = ConnectionError("Ollama connection refused")

        report = self.agent.inspect_artifacts(
            artifacts={"app.py": "def ok():\n    return True\n"},
            run_id="run_fallback",
            use_llm=True,
        )

        self.assertEqual(report.status, "APPROVED")
        self.assertIn("statik analiz uygulandı", report.llm_review_summary)

    def test_s4_05_python_sql_ui_checks_and_package_path_only_when_created(self):
        """S4-05 Checklist 1-4: Python/SQL/UI denetimi ve package_path'in yalnızca paket gerçekten oluşturulduğunda raporlanması."""
        temp_dir = tempfile.mkdtemp(dir=self.agent.workspace_root)
        pkg_target = os.path.join(temp_dir, "merged_pkg")
        try:
            # 1. Hatalı UI/CSS dosyası varsa REJECTED dönmeli ve package_path kesinlikle None kalmalı
            bad_ui_report = self.agent.inspect_artifacts(
                artifacts={
                    "app.py": "def main():\n    return 1\n",
                    "styles.css": "body { color: red; ",  # Kapanmamış süslü parantez
                },
                run_id="run_bad_ui",
                create_package_dir=pkg_target,
                use_llm=False,
            )
            self.assertEqual(bad_ui_report.status, "REJECTED")
            self.assertIsNone(bad_ui_report.package_path)
            self.assertFalse(os.path.exists(pkg_target))
            self.assertTrue(any(f.file_path == "styles.css" for f in bad_ui_report.findings))

            # 2. Tüm Python, SQL ve UI dosyaları geçerliyse APPROVED dönmeli ve birleştirilmiş paket gerçekten oluşturulmalı
            ok_report = self.agent.inspect_artifacts(
                artifacts={
                    "app.py": "def main():\n    return 1\n",
                    "schema.sql": "CREATE TABLE items (id INT PRIMARY KEY);",
                    "index.html": "<!DOCTYPE html><html><body><h1>OK</h1></body></html>",
                },
                run_id="run_ok_pkg",
                create_package_dir=pkg_target,
                use_llm=False,
            )
            self.assertEqual(ok_report.status, "APPROVED")
            self.assertIsNotNone(ok_report.package_path)
            self.assertTrue(os.path.isdir(ok_report.package_path))
            self.assertTrue(os.path.isfile(os.path.join(ok_report.package_path, "app.py")))
            self.assertTrue(os.path.isfile(os.path.join(ok_report.package_path, "schema.sql")))
            self.assertTrue(os.path.isfile(os.path.join(ok_report.package_path, "index.html")))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestReviewModeIsVisible(unittest.TestCase):
    """The report says whether phi4-mini really reviewed the files (model_used / review_mode / fallback_reason)."""

    FILES = {"app.py": "def ok():\n    return True\n"}

    def _ok_response(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"response": '{"summary": "Uyumlu.", "findings": []}'}
        return response

    @patch("src.agents.integration_agent.requests.post")
    def test_successful_review_reports_the_model(self, mock_post):
        mock_post.return_value = self._ok_response()
        report = IntegrationAgent(use_llm=True).inspect_artifacts(self.FILES, run_id="r1")
        self.assertEqual((report.review_mode, report.model_used, report.fallback_reason),
                         ("llm", "phi4-mini:3.8b", None))

    @patch("src.agents.integration_agent.requests.post")
    def test_unreachable_model_is_labelled_fallback(self, mock_post):
        mock_post.side_effect = ConnectionError("refused")
        report = IntegrationAgent(use_llm=True).inspect_artifacts(self.FILES, run_id="r2")
        self.assertEqual((report.review_mode, report.model_used, report.fallback_reason),
                         ("fallback", None, "CONNECTION_ERROR"))
        self.assertEqual(report.status, "APPROVED")

    @patch("src.agents.integration_agent.requests.post")
    def test_http_error_is_labelled_fallback(self, mock_post):
        mock_post.return_value = MagicMock(status_code=404)
        report = IntegrationAgent(use_llm=True).inspect_artifacts(self.FILES, run_id="r3")
        self.assertEqual((report.review_mode, report.fallback_reason), ("fallback", "HTTP_404"))

    @patch("src.agents.integration_agent.requests.post")
    def test_model_off_means_static_check_and_no_call(self, mock_post):
        report = IntegrationAgent(use_llm=False).inspect_artifacts(self.FILES, run_id="r4")
        mock_post.assert_not_called()
        self.assertEqual((report.review_mode, report.model_used), ("static", None))

    def test_env_switch_like_the_other_agents(self):
        with patch.dict(os.environ, {"INTEGRATION_AGENT_USE_OLLAMA": "false"}):
            self.assertFalse(IntegrationAgent().use_llm)
        with patch.dict(os.environ, {"INTEGRATION_AGENT_USE_OLLAMA": "true"}):
            self.assertTrue(IntegrationAgent().use_llm)

    @patch("src.agents.integration_agent.requests.post")
    def test_no_files_means_no_model_call(self, mock_post):
        result = IntegrationAgent(use_llm=True).execute_task(
            {"task_id": "task-int-1", "run_id": "r5", "description": "Review the build"})
        mock_post.assert_not_called()
        self.assertEqual(result.output_artifacts["status"], "REVIEW_REQUIRED")

    def test_project_text_in_context_is_not_taken_as_a_file(self):
        agent = IntegrationAgent(use_llm=False)
        files = agent._extract_artifacts_from_task({"context_artifacts": {
            "project_title": "Kutuphane", "requirement": "uye kaydi ve kitap arama",
            "code_under_test": {"backend_task_be_1.py": "x = 1\n"}}})
        self.assertEqual(files, {"backend_task_be_1.py": "x = 1\n"})


if __name__ == "__main__":
    unittest.main()
