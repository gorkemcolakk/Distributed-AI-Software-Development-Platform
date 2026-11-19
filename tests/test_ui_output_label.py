"""
The UI labels each task's output by what the agent actually returned (real model,
labelled backup template, or model-free code check), not by guessing from the agent's
source code. The old guess called every remote agent "stub" even when a real model ran.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi")))

from master_agent_projesi.app import output_label, output_source, output_summary
from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.integration_agent import IntegrationAgent


def task(category, task_id="task-x-1"):
    return {"task_id": task_id, "title": f"{category} task", "category": category,
            "description": f"Library system {category.lower()} part", "dependencies": []}


class TestOutputSource(unittest.TestCase):

    def test_real_model_modes(self):
        self.assertEqual(output_source({"generation_mode": "ollama", "model_used": "llama3.2:3b"}), "model")
        self.assertEqual(output_source({"synthesis_mode": "ollama_inference"}), "model")

    def test_backup_modes_and_fallback_reason(self):
        for art in ({"generation_mode": "template"}, {"generation_mode": "fallback"},
                    {"synthesis_mode": "safe_fallback"},
                    {"generation_mode": "ollama", "fallback_reason": "timeout"}):
            with self.subTest(art=art):
                self.assertEqual(output_source(art), "backup")

    def test_integration_review(self):
        self.assertEqual(output_source({"inspected_files": ["a.py"], "status": "APPROVED"}), "check")
        self.assertEqual(output_source({"inspected_files": ["a.py"], "model_used": "phi4-mini:3.8b"}), "model")

    def test_unknown_and_bad_input(self):
        for art in ({}, None, "text", {"status": "DONE"}):
            with self.subTest(art=art):
                self.assertIsNone(output_source(art))

    def test_real_local_agents_without_ollama_are_backup(self):
        backend = BackendAgent(use_ollama=False).execute_task(task("BACKEND"))
        database = DatabaseAgent(use_ollama=False).execute_task(task("DATABASE"))
        self.assertEqual(output_source(backend.output_artifacts), "backup")
        self.assertEqual(output_source(database.output_artifacts), "backup")

    def test_real_integration_agent_is_a_code_check(self):
        result = IntegrationAgent(use_llm=False).execute_task(
            {"task_id": "task-int-1", "run_id": "run-l", "output_artifacts": {"a.py": "x = 1\n"}})
        self.assertEqual(output_source(result.output_artifacts), "check")


class TestLabels(unittest.TestCase):

    def test_task_labels(self):
        self.assertEqual(output_label({"generation_mode": "ollama", "model_used": "qwen2.5-coder:3b"}),
                         "Ajan çıktısı · gerçek model (qwen2.5-coder:3b)")
        self.assertEqual(output_label({"generation_mode": "fallback", "fallback_reason": "timeout"}),
                         "Ajan çıktısı · yedek şablon (timeout)")
        self.assertEqual(output_label({"inspected_files": []}), "Ajan çıktısı · kod kontrolü (model kullanılmadı)")
        self.assertEqual(output_label({"inspected_files": [], "review_mode": "fallback", "fallback_reason": "TIMEOUT"}),
                         "Ajan çıktısı · kod kontrolü (model kullanılamadı: TIMEOUT)")
        self.assertEqual(output_label({}), "Ajan çıktısı")

    def test_run_summary(self):
        model = {"artifacts": {"generation_mode": "ollama"}}
        backup = {"artifacts": {"generation_mode": "template"}}
        check = {"artifacts": {"inspected_files": []}}
        self.assertEqual(output_summary({"a": model, "b": check})[0], "CANLI MOTOR · gerçek model çıktısı")
        self.assertEqual(output_summary({"a": backup, "b": check})[0], "CANLI MOTOR · yedek şablon çıktısı")
        self.assertEqual(output_summary({"a": model, "b": backup, "c": model})[0],
                         "CANLI MOTOR · 2 görev gerçek model, 1 görev yedek şablon")
        self.assertEqual(output_summary({})[0], "CANLI MOTOR")
        self.assertEqual(output_summary(None)[0], "CANLI MOTOR")


if __name__ == "__main__":
    unittest.main()
