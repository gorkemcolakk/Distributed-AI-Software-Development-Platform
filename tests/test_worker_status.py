"""
S3-03 (Kübra Hepcan): the Streamlit panel shows whether remote/local worker agents are ONLINE/OFFLINE.

A tiny stub server plays the worker's /health endpoint; no real worker or Ollama is needed.
"""

import json
import os
import re
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi")))

from master_agent_projesi.app import agent_endpoint, probe_worker, probe_workers, machine_label


class _Health(BaseHTTPRequestHandler):
    body = {"status": "HEALTHY", "agent_status": "IDLE"}
    raw = None

    def do_GET(self):
        payload = self.raw if self.raw is not None else json.dumps(self.body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def _closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestProbeWorker(unittest.TestCase):

    def setUp(self):
        _Health.body = {"status": "HEALTHY", "agent_status": "IDLE"}
        _Health.raw = None
        self.server = HTTPServer(("127.0.0.1", 0), _Health)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_healthy_worker_is_online_with_its_own_status(self):
        _Health.body = {"status": "HEALTHY", "agent_status": "busy"}
        result = probe_worker(self.url, timeout=5)
        self.assertTrue(result["online"])
        self.assertEqual(result["agent_status"], "BUSY")

    def test_unhealthy_worker_is_offline(self):
        _Health.body = {"status": "DEGRADED"}
        result = probe_worker(self.url, timeout=5)
        self.assertFalse(result["online"])
        self.assertEqual(result["agent_status"], "OFFLINE")

    def test_garbage_reply_is_offline_and_never_raises(self):
        for raw in (b"not json", b"[]", b""):
            with self.subTest(raw=raw):
                _Health.raw = raw
                self.assertFalse(probe_worker(self.url, timeout=5)["online"])

    def test_closed_port_and_bad_url_are_offline(self):
        for url in (f"http://127.0.0.1:{_closed_port()}", "not a url", ""):
            with self.subTest(url=url):
                self.assertFalse(probe_worker(url, timeout=15)["online"])

    def test_probe_workers_checks_each_url(self):
        dead = f"http://127.0.0.1:{_closed_port()}"
        result = probe_workers((self.url, dead))
        self.assertTrue(result[self.url]["online"])
        self.assertFalse(result[dead]["online"])
        self.assertEqual(probe_workers(()), {})


class TestMachineLabel(unittest.TestCase):

    def setUp(self):
        self._old = os.environ.pop("FRONTEND_AGENT_URL", None)

    def tearDown(self):
        os.environ.pop("FRONTEND_AGENT_URL", None)
        if self._old is not None:
            os.environ["FRONTEND_AGENT_URL"] = self._old

    def test_agent_without_url_is_local_and_has_no_machine_line(self):
        agent = {"id": "agent-frontend", "endpoint_url": ""}
        self.assertIsNone(agent_endpoint(agent))
        self.assertEqual(machine_label(agent), "")

    def test_env_url_marks_agent_as_remote(self):
        os.environ["FRONTEND_AGENT_URL"] = "http://100.64.0.7:8003/"
        agent = {"id": "agent-frontend", "endpoint_url": ""}
        self.assertEqual(agent_endpoint(agent), "http://100.64.0.7:8003")
        self.assertEqual(machine_label(agent), "🖥 100.64.0.7:8003")


class _Tags(BaseHTTPRequestHandler):
    """Fake Ollama: only qwen2.5-coder:3b (Frontend) and llama3.2:3b (Database) are installed."""

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"models": [{"name": "qwen2.5-coder:3b"}, {"name": "llama3.2:3b"}]}).encode())

    def log_message(self, *args):
        pass


_AGENT_URL_VARS = tuple(f"{r}_AGENT_URL" for r in ("INTEGRATION", "FRONTEND", "BACKEND", "DATABASE", "TESTING"))


class TestAgentCardStatus(unittest.TestCase):
    """Each card shows one status. Local agents always work (backup mode if the model is missing); only an unreachable remote worker is OFFLINE."""

    def setUp(self):
        import streamlit as st
        self.server = HTTPServer(("127.0.0.1", 0), _Tags)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self._env = {k: os.environ.get(k) for k in ("OLLAMA_HOST",) + _AGENT_URL_VARS}
        os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{self.server.server_address[1]}"
        # app.py loads .env on every run; an empty value here keeps a local .env (real Tailscale
        # worker addresses) from turning these local agents into remote ones during the test.
        for k in _AGENT_URL_VARS:
            os.environ[k] = ""
        st.cache_data.clear()

    def tearDown(self):
        import streamlit as st
        self.server.shutdown()
        self.server.server_close()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        st.cache_data.clear()

    def _cards(self):
        """{agent name: (status, has_backup_note)} read from the sidebar cards."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", "master_agent_projesi", "app.py"),
                               default_timeout=60).run()
        self.assertFalse(at.exception)
        html = " ".join(m.value for m in at.sidebar.markdown)
        cards = {}
        for card in html.split('<div class="agent-card"')[1:]:
            found = re.search(r'dot"></span>(\w+) Agent.*?● ([\w -]+)</span>', card)
            if found:
                cards[found.group(1)] = (found.group(2), "yedek mod" in card)
        return cards

    def test_local_agents_never_show_offline_missing_model_shows_backup_note(self):
        cards = self._cards()
        for name in ("Integration", "Frontend", "Backend", "Database", "Testing"):
            self.assertEqual(cards[name][0], "ONLINE - IDLE", name)
        self.assertFalse(cards["Frontend"][1])
        self.assertFalse(cards["Database"][1])
        for name in ("Integration", "Backend", "Testing"):
            self.assertTrue(cards[name][1], name)

    def test_ollama_down_local_agents_still_online_in_backup_mode(self):
        os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{_closed_port()}"
        cards = self._cards()
        for name, (status, backup) in cards.items():
            self.assertEqual(status, "ONLINE - IDLE", name)
            self.assertTrue(backup, name)

    def test_unreachable_remote_worker_is_offline_even_if_model_is_installed(self):
        os.environ["FRONTEND_AGENT_URL"] = f"http://127.0.0.1:{_closed_port()}"
        cards = self._cards()
        self.assertEqual(cards["Frontend"], ("OFFLINE", False))
        self.assertEqual(cards["Database"][0], "ONLINE - IDLE")


if __name__ == "__main__":
    unittest.main()
