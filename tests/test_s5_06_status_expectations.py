"""
S5-06 (Berat İnan) finding of 27 November: generated "invalid request" tests must expect what the
contract defines. In the run, test_invalid_events expected 422 but the endpoint answered 200, and
test_tickets expected 200 but got 422.

The backend below is the shape the Backend Agent writes for an events/tickets contract. The tests
check the static validator, the agent's retry and, end to end, that the corrected tests really pass
against the backend (run with pytest through src.master.generated_tests).
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.testing_agent import (
    TestingAgent,
    endpoint_body_schemas,
    find_wrong_status_expectations,
    parse_body_models,
    sample_value,
)
from src.master import generated_tests

BACKEND = '''
import sqlite3
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, name TEXT, date TEXT, capacity INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, event_id INTEGER, buyer TEXT)")

class Event(BaseModel):
    id: Optional[int] = None
    name: str
    date: str
    capacity: int

class Ticket(BaseModel):
    id: Optional[int] = None
    event_id: int
    buyer: str

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

@app.post("/events")
def create_event(event: Event):
    cur = db.execute("INSERT INTO events (name, date, capacity) VALUES (?, ?, ?)",
                     (event.name, event.date, event.capacity))
    db.commit()
    return {"id": cur.lastrowid, "name": event.name, "date": event.date, "capacity": event.capacity}

@app.get("/events")
def list_events():
    return [{"id": r[0], "name": r[1]} for r in db.execute("SELECT id, name FROM events")]

@app.post("/tickets")
def buy_ticket(ticket: Ticket):
    cur = db.execute("INSERT INTO tickets (event_id, buyer) VALUES (?, ?)", (ticket.event_id, ticket.buyer))
    db.commit()
    return {"id": cur.lastrowid, "event_id": ticket.event_id, "buyer": ticket.buyer}
'''

CONTRACT = {
    "entities": [{"name": "Event", "table": "events", "fields": ["name", "date", "capacity"]},
                 {"name": "Ticket", "table": "tickets", "fields": ["event_id", "buyer"]}],
    "endpoints": [
        {"method": "POST", "path": "/events", "request": ["name", "date", "capacity"], "response": "Event"},
        {"method": "GET", "path": "/events", "request": [], "response": "list of Event"},
        {"method": "POST", "path": "/tickets", "request": ["event_id", "buyer"], "response": "Ticket"},
    ],
}
CONTEXT = {"shared_contract": CONTRACT, "code_under_test": {"backend/main.py": BACKEND}}
TASK = {"task_id": "task-qa-events", "title": "API tests", "description": "Test the contract endpoints.",
        "category": "TESTING", "context_artifacts": CONTEXT}

# What the model wrote in the failing run (simplified)
WRONG = '''
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_invalid_events():
    r = client.post("/events", json={"name": "", "date": "not-a-date", "capacity": -5})
    assert r.status_code == 422

def test_tickets():
    r = client.post("/tickets", json={"event_id": 1})
    assert r.status_code == 200
'''

FIXED = '''
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_event():
    r = client.post("/events", json={"name": "Concert", "date": "2026-12-01", "capacity": 100})
    assert r.status_code in (200, 201)

def test_invalid_events():
    r = client.post("/events", json={"name": "Concert", "date": "2026-12-01"})
    assert r.status_code == 422

def test_tickets():
    event_id = client.post("/events", json={"name": "A", "date": "2026-12-01", "capacity": 1}).json()["id"]
    r = client.post("/tickets", json={"event_id": event_id, "buyer": "Ali"})
    assert r.status_code in (200, 201)

def test_ticket_wrong_type():
    assert client.post("/tickets", json={"event_id": "abc", "buyer": "Ali"}).status_code == 422
'''


def scripted(*replies):
    calls = []

    def client(prompt):
        calls.append(prompt)
        return "```python\n" + replies[min(len(calls), len(replies)) - 1] + "\n```"

    client.calls = calls
    return client


class TestBodySchemas(unittest.TestCase):

    def test_models_are_read_from_backend_code(self):
        routes = parse_body_models(BACKEND)
        self.assertEqual(routes[("POST", "/events")]["required"], ["name", "date", "capacity"])
        self.assertEqual(routes[("POST", "/events")]["fields"]["capacity"], "number")
        self.assertNotIn("id", routes[("POST", "/tickets")]["required"])

    def test_truncated_excerpt_still_gives_models(self):
        cut = BACKEND[:BACKEND.index("def buy_ticket")]
        self.assertIn(("POST", "/events"), parse_body_models(cut))

    def test_contract_is_used_when_there_is_no_code(self):
        schemas = endpoint_body_schemas({"shared_contract": CONTRACT})
        self.assertEqual(schemas[("POST", "/tickets")]["required"], ["event_id", "buyer"])
        self.assertEqual(schemas[("POST", "/tickets")]["source"], "contract")
        self.assertNotIn(("GET", "/events"), schemas)

    def test_sample_values_pass_validation(self):
        self.assertEqual(sample_value("capacity", "number"), 1)
        self.assertEqual(sample_value("event_id", "any"), 1)
        self.assertEqual(sample_value("date", "str"), "2026-12-01")


class TestStatusExpectations(unittest.TestCase):

    def test_the_27_november_tests_are_rejected(self):
        problems = find_wrong_status_expectations(WRONG, endpoint_body_schemas(CONTEXT))
        self.assertEqual(len(problems), 2)
        self.assertIn("test_invalid_events", problems[0])
        self.assertIn("200 döner", problems[0])
        self.assertIn("test_tickets", problems[1])
        self.assertIn("eksik alan 'buyer'", problems[1])

    def test_correct_expectations_are_accepted(self):
        self.assertEqual(find_wrong_status_expectations(FIXED, endpoint_body_schemas(CONTEXT)), [])

    def test_same_rules_without_backend_code(self):
        schemas = endpoint_body_schemas({"shared_contract": CONTRACT})
        self.assertEqual(len(find_wrong_status_expectations(WRONG, schemas)), 2)
        self.assertEqual(find_wrong_status_expectations(FIXED, schemas), [])

    def test_bodies_built_in_variables_are_not_judged(self):
        code = ('def test_x():\n    payload = {"event_id": 1}\n'
                '    r = client.post("/tickets", json=payload)\n    assert r.status_code == 200\n')
        self.assertEqual(find_wrong_status_expectations(code, endpoint_body_schemas(CONTEXT)), [])


class TestAgentRetriesWrongExpectations(unittest.TestCase):

    def test_prompt_shows_valid_bodies_and_the_422_rule(self):
        prompt = TestingAgent(use_ollama=True, llm_client=scripted(FIXED)).build_prompt(TASK)
        self.assertIn('POST /events  valid body: json={"name": "test name", "date": "2026-12-01", "capacity": 1}', prompt)
        self.assertIn("LEAVES OUT a required field", prompt)
        self.assertIn("Never expect 400/422 for empty strings", prompt)

    def test_wrong_reply_is_retried_then_accepted(self):
        client = scripted(WRONG, FIXED)
        result = TestingAgent(use_ollama=True, llm_client=client).execute_task(TASK)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["validation_retries"], 1)
        self.assertIn("durum kodu beklentisi", client.calls[1])
        self.assertIn("test_invalid_events", client.calls[1])

    def test_wrong_reply_twice_fails_the_task(self):
        result = TestingAgent(use_ollama=True, llm_client=scripted(WRONG)).execute_task(TASK)
        self.assertEqual(result.status, "FAILED")
        self.assertIn("durum kodu beklentisi", result.error_message)


@unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest is needed to run generated tests")
class TestEndToEndAgainstBackend(unittest.TestCase):
    """The rule matches reality: the wrong tests fail and the accepted tests pass on the real backend."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s5-06-status-")
        self.ws = Path(self.tmp)
        (self.ws / "backend").mkdir()
        (self.ws / "tests").mkdir()
        (self.ws / "backend" / "main.py").write_text(BACKEND, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tests(self, code):
        (self.ws / "tests" / "test_api.py").write_text(code, encoding="utf-8")
        return generated_tests.run_generated_tests(self.ws)

    def test_wrong_tests_fail_like_on_27_november(self):
        result = self.run_tests(WRONG)
        self.assertEqual((result["passed"], result["failed"]), (0, 2))

    def test_accepted_tests_all_pass(self):
        result = self.run_tests(FIXED)
        self.assertEqual(result["status"], "PASSED", result.get("cases"))
        self.assertEqual(result["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
