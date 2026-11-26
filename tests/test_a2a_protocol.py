"""
S5 (Eren Görkem Çolak): A2A (Agent2Agent) 1.0 layer.

Workers publish an Agent Card and accept A2A SendMessage (HTTP+JSON binding); the Master reads the
card and sends tasks as A2A messages, falling back to POST /task for workers without a card.
FastAPI TestClient stands in for the network; no Ollama, no real state.db.
"""

import os
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src import a2a_protocol as a2a
from src.agents.backend_agent import BackendAgent
from src.agents.base_agent import TaskResult
from src.agents.remote_agent import RemoteAgentProxy
from src.api.worker_server import create_worker_app

TOKEN = "a2a-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
TASK = {"task_id": "task-be-1", "run_id": "run-a2a", "title": "Book API", "description": "Books CRUD",
        "category": "BACKEND"}


def _worker(agent=None):
    return TestClient(create_worker_app(agent=agent or BackendAgent(use_ollama=False), auth_token=TOKEN))


def _transport_for(client, calls):
    """RemoteAgentProxy transport that sends its HTTP calls to a TestClient instead of the network."""
    def transport(method, url, payload, headers, timeout):
        path = urlparse(url).path
        calls.append((method, path))
        resp = client.request(method, path, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()
    return transport


class TestAgentCard(unittest.TestCase):

    def test_worker_publishes_a_valid_public_agent_card(self):
        resp = _worker().get(a2a.AGENT_CARD_PATH)  # no token: discovery is public
        self.assertEqual(resp.status_code, 200)
        card = resp.json()
        self.assertEqual(a2a.validate_agent_card(card), [])
        self.assertEqual(card["skills"][0]["id"], "backend")
        iface = card["supportedInterfaces"][0]
        self.assertEqual((iface["protocolBinding"], iface["protocolVersion"]), ("HTTP+JSON", "1.0"))
        self.assertEqual(iface["url"], "http://testserver")
        self.assertEqual(card["securitySchemes"]["bearer"]["httpAuthSecurityScheme"]["scheme"], "Bearer")
        self.assertFalse(card["capabilities"]["streaming"])
        self.assertNotIn(TOKEN, resp.text)

    def test_card_roles_and_validation(self):
        card = a2a.build_agent_card(BackendAgent(use_ollama=False), "http://100.64.0.1:8001")
        self.assertIn("backend", a2a.card_roles(card))
        self.assertNotIn("frontend", a2a.card_roles(card))
        broken = dict(card)
        del broken["skills"]
        self.assertIn("missing skills", a2a.validate_agent_card(broken))
        self.assertEqual(a2a.validate_agent_card("nope"), ["card is not a JSON object"])


class TestSendMessage(unittest.TestCase):

    def setUp(self):
        self.client = _worker()

    def test_send_message_needs_the_token(self):
        resp = self.client.post(a2a.SEND_MESSAGE_PATH, json=a2a.build_send_message_request(TASK))
        self.assertEqual(resp.status_code, 401)

    def test_send_message_returns_a_completed_task_with_files(self):
        resp = self.client.post(a2a.SEND_MESSAGE_PATH, json=a2a.build_send_message_request(TASK), headers=AUTH)
        self.assertEqual(resp.status_code, 200, resp.text)
        task = resp.json()["task"]
        self.assertEqual(task["status"]["state"], a2a.STATE_COMPLETED)
        self.assertEqual(task["contextId"], "run-a2a")
        files = [p for a in task["artifacts"] if a["name"] == "generated-files" for p in a["parts"]]
        self.assertTrue(files and files[0]["filename"].endswith(".py"))
        self.assertEqual(files[0]["mediaType"], "text/x-python")
        # GetTask returns the same task
        again = self.client.get(f"/tasks/{task['id']}", headers=AUTH)
        self.assertEqual(again.json()["id"], task["id"])
        self.assertEqual(self.client.get(f"/tasks/{task['id']}").status_code, 401)
        self.assertEqual(self.client.get("/tasks/unknown", headers=AUTH).status_code, 404)

    def test_failed_agent_gives_a_failed_task_with_the_reason(self):
        agent = BackendAgent(use_ollama=False)
        failed = TaskResult(task_id="task-be-1", agent_id=agent.agent_id, status="FAILED", output_artifacts={},
                            logs=[], execution_time_seconds=0.1, error_message="model output was empty")
        with patch.object(agent, "execute_task", return_value=failed):
            resp = _worker(agent).post(a2a.SEND_MESSAGE_PATH, json=a2a.build_send_message_request(TASK),
                                       headers=AUTH)
        status = resp.json()["task"]["status"]
        self.assertEqual(status["state"], a2a.STATE_FAILED)
        self.assertIn("model output was empty", status["message"]["parts"][0]["text"])

    def test_malformed_message_is_rejected(self):
        for body in ({}, {"message": {"messageId": "m", "role": "ROLE_USER", "parts": []}}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(a2a.SEND_MESSAGE_PATH, json=body, headers=AUTH).status_code, 400)

    def test_plain_text_message_becomes_a_task(self):
        body = {"message": {"messageId": "m-1", "role": "ROLE_USER", "parts": [{"text": "Write a book API"}]}}
        resp = self.client.post(a2a.SEND_MESSAGE_PATH, json=body, headers=AUTH)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["task"]["status"]["state"], a2a.STATE_COMPLETED)


class TestMasterSide(unittest.TestCase):

    def _proxy(self, client, calls):
        return RemoteAgentProxy(endpoint_url="http://100.64.0.1:8001", agent_id="agent-backend",
                                name="Backend Agent", auth_token=TOKEN, transport=_transport_for(client, calls))

    def test_master_reads_the_card_and_sends_the_task_over_a2a(self):
        calls = []
        proxy = self._proxy(_worker(), calls)
        with patch.dict(os.environ, {"MASTER_A2A_DISPATCH": "true"}):
            proxy.use_a2a = True
            self.assertIsNotNone(proxy.fetch_agent_card())
            result = proxy.execute_task(dict(TASK))
        self.assertEqual(result.status, "SUCCESS", result.error_message)
        self.assertTrue(result.output_artifacts.get("files"))
        self.assertIn(("POST", a2a.SEND_MESSAGE_PATH), calls)
        self.assertNotIn(("POST", "/task"), calls)

    def test_switch_off_keeps_the_old_task_route(self):
        calls = []
        proxy = self._proxy(_worker(), calls)
        proxy.use_a2a = False
        proxy.fetch_agent_card()
        self.assertEqual(proxy.execute_task(dict(TASK)).status, "SUCCESS")
        self.assertIn(("POST", "/task"), calls)

    def test_worker_without_a_card_keeps_the_old_task_route(self):
        calls = []
        proxy = self._proxy(_worker(), calls)
        real = proxy._transport

        def old_worker(method, url, payload, headers, timeout):  # a worker that has not pulled the A2A change
            if url.endswith(a2a.AGENT_CARD_PATH):
                raise RuntimeError("HTTP 404")
            return real(method, url, payload, headers, timeout)
        proxy._transport = old_worker
        proxy.use_a2a = True
        self.assertIsNone(proxy.fetch_agent_card())
        self.assertEqual(proxy.execute_task(dict(TASK)).status, "SUCCESS")
        self.assertIn(("POST", "/task"), calls)

    def test_failed_a2a_task_is_a_failed_result(self):
        agent = BackendAgent(use_ollama=False)
        failed = TaskResult(task_id="task-be-1", agent_id=agent.agent_id, status="FAILED", output_artifacts={},
                            logs=[], execution_time_seconds=0.1, error_message="model output was empty")
        calls = []
        proxy = self._proxy(_worker(agent), calls)
        proxy.use_a2a = True
        proxy.fetch_agent_card()
        with patch.object(agent, "execute_task", return_value=failed):
            result = proxy.execute_task(dict(TASK))
        self.assertEqual(result.status, "FAILED")
        self.assertIn("model output was empty", result.error_message)

    def test_generic_a2a_task_without_our_result_artifact_is_understood(self):
        task = {"id": "t1", "status": {"state": a2a.STATE_COMPLETED},
                "artifacts": [{"artifactId": "a", "parts": [{"text": "print(1)", "filename": "main.py"}]}]}
        payload = a2a.result_payload_from_task({"task": task})
        self.assertEqual(payload["status"], "SUCCESS")
        self.assertEqual(payload["output_artifacts"]["files"], [{"filename": "main.py", "content": "print(1)"}])
        failed = a2a.result_payload_from_task({"id": "t2", "status": {"state": a2a.STATE_REJECTED}})
        self.assertEqual(failed["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
