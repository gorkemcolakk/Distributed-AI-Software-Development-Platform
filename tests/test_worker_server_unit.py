"""
Comprehensive Unit Tests for S3-02:
Worker Agent Authenticated HTTP/JSON API and BackendAgent Local Ollama Code Generation.
Sorumlu: İrem Yılmaz (Backend Agent — qwen2.5-coder:7b / Scrum Master)
"""

import ast
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.agents.backend_agent import (
    BackendAgent,
    ModelOutputError,
    OllamaCallError,
    UnsafePathError,
    extract_python_code,
    validate_backend_code,
    resolve_safe_output_path,
)
from src.api.worker_server import create_worker_app, WorkerHttpClient
from src.contracts import TaskPayloadContract_v1


class TestWorkerServerEndpoints(unittest.TestCase):
    """Tests the authenticated worker HTTP API server endpoints with TestClient."""

    def setUp(self):
        self.test_token = "test-secret-token-12345"
        self.agent = BackendAgent(use_ollama=False)  # deterministic fallback for fast unit tests
        self.app = create_worker_app(agent=self.agent, auth_token=self.test_token)
        self.client = TestClient(self.app)

    def test_health_endpoint_200(self):
        """GET /health and GET /api/v1/health should return 200 with status HEALTHY."""
        for path in ("/health", "/api/v1/health"):
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertEqual(data["status"], "HEALTHY")
                self.assertEqual(data["service"], "Worker Agent HTTP API")
                self.assertEqual(data["agent_name"], "Backend Architecture Agent")
                self.assertNotIn(self.test_token, resp.text)

    def test_unauthorized_missing_token(self):
        """Requests without Authorization header must be rejected with 401."""
        for path in ("/task", "/api/v1/tasks", "/api/v1/tasks/execute"):
            with self.subTest(path=path):
                resp = self.client.post(path, json={"task_id": "task-be-1"})
                self.assertEqual(resp.status_code, 401)
                self.assertIn("Missing Authorization header", resp.json()["detail"])

    def test_unauthorized_malformed_header(self):
        """Requests with malformed Authorization headers must be rejected with 401."""
        bad_headers = [
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer "},
            {"Authorization": f"Basic {self.test_token}"},
            {"Authorization": f"Token {self.test_token}"},
            {"Authorization": self.test_token},
            {"Authorization": "Bearer   "},
        ]
        for header in bad_headers:
            with self.subTest(header=header):
                resp = self.client.post("/task", json={"task_id": "task-be-1"}, headers=header)
                self.assertEqual(resp.status_code, 401)

    def test_unauthorized_invalid_token(self):
        """Requests with wrong Bearer token must be rejected with 401 without echoing the token."""
        wrong_token = "wrong-token-attempt-987"
        resp = self.client.post(
            "/task",
            json={"task_id": "task-be-1"},
            headers={"Authorization": f"Bearer {wrong_token}"}
        )
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn(wrong_token, resp.text)

    def test_task_execution_invalid_payload(self):
        """Valid token with malformed or missing required task fields must return 422."""
        headers = {"Authorization": f"Bearer {self.test_token}"}
        
        # Missing task_id
        resp = self.client.post("/task", json={"title": "Missing ID"}, headers=headers)
        self.assertEqual(resp.status_code, 422)

        # Empty task_id
        resp = self.client.post("/task", json={"task_id": ""}, headers=headers)
        self.assertEqual(resp.status_code, 422)

    def test_task_execution_valid_request(self):
        """Valid token with valid TaskPayloadContract_v1 returns 200 with result."""
        headers = {"Authorization": f"Bearer {self.test_token}"}
        payload = {
            "task_id": "task-be-101",
            "title": "Online Book Catalog REST API",
            "category": "BACKEND",
            "description": "Develop catalog endpoints with CRUD support",
            "required_specialty": "backend"
        }
        resp = self.client.post("/task", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["task_id"], "task-be-101")
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("output_artifacts", data)
        self.assertIn("endpoints_created", data["output_artifacts"])
        self.assertIn("generated_code", data["output_artifacts"])

    def test_agent_registration_endpoint(self):
        """POST /api/v1/agents/register creates registration session with valid token."""
        headers = {"Authorization": f"Bearer {self.test_token}"}
        resp = self.client.post(
            "/api/v1/agents/register",
            json={"agent_id": "agent-backend", "name": "Backend Agent"},
            headers=headers
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["agent_id"], "agent-backend")
        self.assertIn("session_token", data)

    def test_heartbeat_endpoint(self):
        """POST /api/v1/agents/heartbeat acknowledges agent health signal."""
        headers = {"Authorization": f"Bearer {self.test_token}"}
        resp = self.client.post(
            "/api/v1/agents/heartbeat",
            json={"agent_id": "agent-backend", "status": "IDLE"},
            headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["acknowledged"])


class TestBackendAgentOllamaAndFallback(unittest.TestCase):
    """Unit tests for BackendAgent Ollama code synthesis and safe fallback handling."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.task = {
            "task_id": "task-be-users",
            "title": "User Authentication API",
            "category": "BACKEND",
            "description": "FastAPI endpoints for user signup, login, and JWT validation.",
            "context_artifacts": {"database": "SQLite / PostgreSQL"}
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(BackendAgent, "_call_ollama")
    def test_real_ollama_code_generation_success(self, mock_call):
        """Simulates successful qwen2.5-coder:7b code generation and validates syntax."""
        mock_reply = '''Here is the FastAPI implementation:

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI(title="User Authentication API")

class UserLogin(BaseModel):
    username: str
    password: str

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

@app.post("/api/v1/auth/login", status_code=status.HTTP_200_OK)
def login(user: UserLogin):
    if user.username == "admin" and user.password == "secret":
        return {"access_token": "token-xyz", "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
```
'''
        mock_call.return_value = mock_reply

        agent = BackendAgent(use_ollama=True, output_dir=self.temp_dir)
        result = agent.execute_task(self.task)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["synthesis_mode"], "ollama_inference")
        self.assertEqual(result.output_artifacts["model_used"], "qwen2.5-coder:7b")
        self.assertIn("POST /api/v1/auth/login", result.output_artifacts["endpoints_created"])

        # Validate that the generated file was safely written
        written_files = result.output_artifacts["files"]
        self.assertEqual(len(written_files), 1)
        self.assertTrue(os.path.exists(written_files[0]["path"]))
        self.assertIn("FastAPI", written_files[0]["content"])

    @patch.object(BackendAgent, "_call_ollama")
    def test_ollama_offline_fallback_enabled(self, mock_call):
        """When Ollama is offline and fallback_enabled=True, agent returns safe code without crashing."""
        mock_call.side_effect = OllamaCallError("Connection refused to Ollama", error_type="CONNECTION_REFUSED")

        agent = BackendAgent(use_ollama=True, fallback_enabled=True, output_dir=self.temp_dir)
        result = agent.execute_task(self.task)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["synthesis_mode"], "safe_fallback")
        self.assertIn("[FALLBACK]", " ".join(result.logs))

        # Check that the fallback code parses as valid Python
        code = result.output_artifacts["generated_code"]
        tree = ast.parse(code)
        self.assertIsNotNone(tree)
        self.assertIn("app = FastAPI", code)

    @patch.object(BackendAgent, "_call_ollama")
    def test_ollama_offline_fallback_disabled_raises(self, mock_call):
        """When Ollama is offline and fallback_enabled=False, BaseAgent marks task FAILED."""
        mock_call.side_effect = OllamaCallError("Ollama offline", error_type="CONNECTION_REFUSED")

        agent = BackendAgent(use_ollama=True, fallback_enabled=False)
        result = agent.execute_task(self.task)

        self.assertEqual(result.status, "FAILED")
        self.assertIn("Ollama offline", result.error_message)

    def test_path_traversal_protection(self):
        """resolve_safe_output_path must reject attempts to escape output directory."""
        with self.assertRaises(UnsafePathError):
            resolve_safe_output_path(self.temp_dir, "../escaped.py")

        with self.assertRaises(UnsafePathError):
            resolve_safe_output_path(self.temp_dir, "/absolute/path.py")

        with self.assertRaises(UnsafePathError):
            resolve_safe_output_path(self.temp_dir, "malicious.sh")

        safe = resolve_safe_output_path(self.temp_dir, "safe_service.py")
        self.assertTrue(str(safe).startswith(os.path.abspath(self.temp_dir)))


class TestLiveWorkerHttpLoopback(unittest.TestCase):
    """Tests real HTTP loopback over a live socket using uvicorn and urllib."""

    @classmethod
    def setUpClass(cls):
        import uvicorn
        cls.token = "loopback-secret-token"
        cls.agent = BackendAgent(use_ollama=False)
        cls.app = create_worker_app(agent=cls.agent, auth_token=cls.token)

        # Find a free local port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]

        cls.base_url = f"http://127.0.0.1:{cls.port}"
        
        # Start uvicorn server in a background daemon thread
        config = uvicorn.Config(cls.app, host="127.0.0.1", port=cls.port, log_level="warning")
        cls.server = uvicorn.Server(config)
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()

        # Wait until server is reachable
        client = WorkerHttpClient(base_url=cls.base_url, auth_token=cls.token)
        ready = False
        for _ in range(30):
            try:
                data = client.health_check()
                if data.get("status") == "HEALTHY":
                    ready = True
                    break
            except Exception:
                time.sleep(0.1)

        if not ready:
            raise RuntimeError(f"Could not connect to live test worker server at {cls.base_url}")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=2.0)

    def test_live_health_check(self):
        client = WorkerHttpClient(base_url=self.base_url, auth_token=self.token)
        data = client.health_check()
        self.assertEqual(data["status"], "HEALTHY")

    def test_live_task_execution_with_token(self):
        client = WorkerHttpClient(base_url=self.base_url, auth_token=self.token)
        task = {
            "task_id": "task-be-live-1",
            "title": "Live API Test",
            "category": "BACKEND",
            "description": "Integration verification"
        }
        res = client.execute_task(task, path="/task")
        self.assertEqual(res["task_id"], "task-be-live-1")
        self.assertEqual(res["status"], "SUCCESS")

    def test_live_unauthorized_rejection(self):
        bad_client = WorkerHttpClient(base_url=self.base_url, auth_token="wrong-token")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            bad_client.execute_task({"task_id": "task-1"}, path="/task")
        self.assertEqual(ctx.exception.code, 401)


if __name__ == "__main__":
    unittest.main()

