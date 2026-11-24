"""
S5 (İrem Yılmaz, Eren Görkem Çolak): a worker that answers on the wrong role/port, without a token or
with a different token is shown with a warning AND gets no task from the engine.

A small stub server plays the worker's /health and token-protected heartbeat; no real worker or Ollama.
"""

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi")))

from master_agent_projesi.app import probe_worker, remote_start_problem
from src.agents.base_agent import AgentStatus
from src.agents.remote_agent import RemoteAgentProxy


class _Worker(BaseHTTPRequestHandler):
    health = {}
    token = "right-token"

    def _send(self, code, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self._send(200, self.health)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.headers.get("Authorization") != f"Bearer {self.token}":
            self._send(401, {"detail": "Unauthorized"})
        else:
            self._send(200, {"acknowledged": True})

    def log_message(self, *args):
        pass


def _health(agent_id="agent-backend", name="Backend Agent", token_configured=True):
    return {"status": "HEALTHY", "agent_status": "IDLE", "agent_id": agent_id, "agent_name": name,
            "token_configured": token_configured}


class TestWorkerConfigWarnings(unittest.TestCase):

    def setUp(self):
        _Worker.health = _health()
        self.server = HTTPServer(("127.0.0.1", 0), _Worker)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.env = patch.dict(os.environ, {"WORKER_AUTH_TOKEN": "right-token"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()

    def test_right_role_and_token_is_online_without_warning(self):
        result = probe_worker(self.url, "backend", timeout=5)
        self.assertTrue(result["online"])
        self.assertEqual(result["warning"], "")

    def test_wrong_role_on_the_port_is_offline_with_warning(self):
        _Worker.health = _health("agent-frontend", "Frontend Agent")  # 24 Nov: wrong worker on a port
        result = probe_worker(self.url, "backend", timeout=5)
        self.assertFalse(result["online"])
        self.assertIn("Yanlış rol/port", result["warning"])

    def test_worker_without_token_is_offline_with_warning(self):
        _Worker.health = _health(token_configured=False)
        result = probe_worker(self.url, "backend", timeout=5)
        self.assertFalse(result["online"])
        self.assertIn("WORKER_AUTH_TOKEN", result["warning"])

    def test_different_token_is_offline_with_401_warning(self):
        with patch.dict(os.environ, {"WORKER_AUTH_TOKEN": "other-token"}):
            result = probe_worker(self.url, "backend", timeout=5)
        self.assertFalse(result["online"])
        self.assertIn("401", result["warning"])

    def test_engine_does_not_send_tasks_to_a_wrong_role_worker(self):
        _Worker.health = _health("agent-frontend", "Frontend Agent")
        proxy = RemoteAgentProxy(endpoint_url=self.url, agent_id="backend", name="Backend Agent")
        problem = remote_start_problem(proxy)
        self.assertIn("Yanlış rol/port", problem)
        self.assertEqual(proxy.status, AgentStatus.OFFLINE)  # the orchestrator skips OFFLINE agents

    def test_engine_keeps_a_correct_worker_online(self):
        proxy = RemoteAgentProxy(endpoint_url=self.url, agent_id="backend", name="Backend Agent")
        self.assertEqual(remote_start_problem(proxy), "")
        self.assertEqual(proxy.status, AgentStatus.IDLE)

    def test_engine_reports_an_unreachable_worker(self):
        self.server.shutdown()
        self.server.server_close()
        proxy = RemoteAgentProxy(endpoint_url=self.url, agent_id="backend", name="Backend Agent")
        self.assertEqual(remote_start_problem(proxy), "yanıt vermiyor")
        self.assertEqual(proxy.status, AgentStatus.OFFLINE)
        self.server = HTTPServer(("127.0.0.1", 0), _Worker)  # tearDown shuts down a running server
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


if __name__ == "__main__":
    unittest.main()
