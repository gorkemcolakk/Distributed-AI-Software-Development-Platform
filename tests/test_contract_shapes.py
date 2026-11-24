"""
Sprint 5 (Eren Görkem Çolak): endpoints of the shared contract carry their request fields and
response, so Testing only calls what Backend serves (24 Nov: tests called a POST /books that was
not in the contract). Pure functions only; no Ollama.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.master.analyzer import CATEGORY_RULES, PROMPT, RequirementsAnalyzer


class TestContractShapes(unittest.TestCase):

    def test_request_and_response_are_kept_and_cleaned(self):
        contract = RequirementsAnalyzer.normalize_contract({
            "entities": [{"name": "Dish", "table": "dishes", "fields": ["name", "price"]}],
            "endpoints": [{"method": "post", "path": "/dishes", "description": "add a dish",
                           "request": ["Name", "unit price", 7, ""], "response": "Dish"}]})
        ep = contract["endpoints"][0]
        self.assertEqual(ep["method"], "POST")
        self.assertEqual(ep["request"], ["name", "unit_price"])
        self.assertEqual(ep["response"], "Dish")

    def test_endpoints_without_shape_still_work(self):
        contract = RequirementsAnalyzer.normalize_contract({
            "endpoints": [{"method": "GET", "path": "/dishes", "description": "list"}]})
        self.assertEqual(contract["endpoints"], [{"method": "GET", "path": "/dishes", "description": "list"}])

    def test_request_list_is_capped(self):
        contract = RequirementsAnalyzer.normalize_contract({
            "endpoints": [{"method": "GET", "path": "/x", "request": [f"f{i}" for i in range(30)]}]})
        self.assertEqual(len(contract["endpoints"][0]["request"]), 10)

    def test_prompt_asks_for_create_endpoints_and_shapes(self):
        self.assertIn('"request"', PROMPT)
        self.assertIn('"response"', PROMPT)
        self.assertIn("POST (or PUT)", PROMPT)
        PROMPT.format(max_tasks=10, title="t", requirement="r")  # braces still escaped correctly

    def test_testing_rule_limits_tests_to_contract_endpoints(self):
        self.assertIn("only endpoints listed in the contract", CATEGORY_RULES["TESTING"])
        self.assertIn("every endpoint of the shared contract", CATEGORY_RULES["BACKEND"])


if __name__ == "__main__":
    unittest.main()
