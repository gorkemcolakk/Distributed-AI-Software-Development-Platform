"""
S5-06 (Berat İnan): scripts/testing_model_benchmark.py without Ollama.
Checks the metrics, the comparison with config/agents_config.json and the Markdown report.
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("testing_model_benchmark", ROOT / "scripts" / "testing_model_benchmark.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

CASES = [
    {"scenario": "books", "repeat": 1, "duration_s": 40.0, "status": "SUCCESS", "error": None, "validation_retries": 0,
     "generated_tests": {"status": "PASSED", "passed": 3, "failed": 0, "errors": 0, "total": 3, "pass_rate": 1.0}},
    {"scenario": "events_tickets", "repeat": 1, "duration_s": 90.0, "status": "SUCCESS", "error": None,
     "validation_retries": 1,
     "generated_tests": {"status": "FAILED", "passed": 1, "failed": 2, "errors": 0, "total": 3, "pass_rate": 0.3333}},
    {"scenario": "todos", "repeat": 1, "duration_s": 60.0, "status": "FAILED", "error": "geçerli Python değil"},
]


class TestBenchmarkMetrics(unittest.TestCase):

    def test_summary(self):
        s = bench.summarize("deepseek-coder:6.7b", CASES)
        self.assertEqual(s["tasks"], 3)
        self.assertAlmostEqual(s["valid_output_rate"], 0.6667, places=4)
        self.assertAlmostEqual(s["first_attempt_rate"], 0.3333, places=4)
        self.assertEqual(s["median_duration_s"], 60.0)
        self.assertEqual((s["generated_tests_passed"], s["generated_tests_total"]), (4, 6))
        self.assertEqual(s["fully_passing_suites"], 1)

    def test_comparison_uses_the_config_scores(self):
        c = bench.compare_with_config(bench.summarize("deepseek-coder:6.7b", CASES))
        self.assertEqual(c["estimated"]["agent"], "Testing Agent")
        self.assertEqual(c["estimated"]["capabilities"]["coding"], 88.0)
        self.assertAlmostEqual(c["measured"]["coding_proxy"], round(100 * (2 / 3) * (4 / 6), 1), places=1)
        self.assertAlmostEqual(c["difference"]["reasoning"], round(33.3 - 95.0, 1), places=1)

    def test_unknown_model_has_no_estimate(self):
        self.assertIsNone(bench.compare_with_config(bench.summarize("no-such-model", CASES))["estimated"])

    def test_every_scenario_backend_fits_the_context_excerpt(self):
        for s in bench.SCENARIOS:
            with self.subTest(s["id"]):
                self.assertIn("BaseModel", bench.excerpt(s["backend"]))

    def test_markdown_report(self):
        tmp = tempfile.mkdtemp()
        try:
            summary = [bench.summarize("deepseek-coder:6.7b", CASES)]
            data = {"date": "2026-11-27", "repeats": 1, "hardware": "test", "summary": summary,
                    "config_comparison": [bench.compare_with_config(summary[0])],
                    "cases": {"deepseek-coder:6.7b": CASES}, "test_suite": "516 test OK", "limitations": ["tek model"]}
            path = Path(tmp) / "report.md"
            bench.write_markdown(path, data)
            text = path.read_text(encoding="utf-8")
            self.assertIn("| deepseek-coder:6.7b | 3 | %67 | %33 | 60.0 sn | %67 (4/6) | 1 |", text)
            self.assertIn("88.0 → 44.4", text)
            self.assertIn("geçerli Python değil", text)
            self.assertIn("- tek model", text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
