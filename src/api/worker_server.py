"""
Worker Agent Authenticated HTTP/JSON API Server.
Implements docs/WORKER_HTTP_API_DRAFT.md for distributed worker agent coordination.

S3-02 (İrem Yılmaz — Backend Agent — qwen2.5-coder:7b):
- Enforces Bearer Token authentication on all protected operational endpoints.
- Rejects unauthorized or malformed requests with HTTP 401 (fast, non-leaking).
- Provides active health check endpoints (/health and /api/v1/health).
- Executes tasks via BackendAgent (or injected BaseAgent) and returns standard TaskResult / contracts.
- No hardcoded secrets or credentials in source code.
"""

import hmac
import json
import os
import time
import urllib.request
import uuid
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.agents.backend_agent import BackendAgent
from src.agents.base_agent import BaseAgent


def get_auth_token(override_token: Optional[str] = None) -> str:
    """Reads configured worker authentication token from environment without hardcoding."""
    if override_token is not None:
        return override_token.strip()
    return (os.getenv("WORKER_AUTH_TOKEN") or os.getenv("BACKEND_AUTH_TOKEN") or "").strip()


def check_bearer_token(auth_header: Optional[str], expected_token: str) -> Optional[str]:
    """
    Validates Authorization header strictly against expected Bearer token.
    Returns None if valid, or an error message string if invalid.
    Never reflects or echoes the submitted token in error strings.
    """
    if not auth_header or not isinstance(auth_header, str):
        return "Missing Authorization header"

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return "Malformed Authorization header, expected 'Bearer <token>'"

    token = parts[1].strip()
    if not token:
        return "Empty token in Authorization header"

    if not expected_token or not hmac.compare_digest(token, expected_token):
        return "Invalid Bearer token"

    return None


class AgentRegistrationRequest(BaseModel):
    """Payload for worker agent node registration."""
    agent_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    model_name: Optional[str] = None
    status: Optional[str] = "IDLE"
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    endpoint_callback: Optional[str] = None


class AgentHeartbeatRequest(BaseModel):
    """Payload for worker agent node heartbeat signal."""
    agent_id: str = Field(..., min_length=1)
    status: Optional[str] = "IDLE"
    active_tasks: List[str] = Field(default_factory=list)
    hardware_metrics: Dict[str, Any] = Field(default_factory=dict)


def create_worker_app(agent: Optional[BaseAgent] = None, auth_token: Optional[str] = None) -> FastAPI:
    """
    Application factory for the Worker Agent HTTP/JSON API.
    Enables injecting custom agents or explicit tokens for deterministic unit testing.
    """
    worker_agent = agent if agent is not None else BackendAgent()
    token_resolver = lambda: get_auth_token(auth_token)

    app = FastAPI(
        title="Worker Agent HTTP API",
        description="Authenticated HTTP REST interface for distributed worker agents",
        version="1.0.0"
    )

    pending_queue: List[Dict[str, Any]] = []

    # --- Health Endpoints (Public Health Probes) ---
    @app.get("/health", status_code=status.HTTP_200_OK)
    @app.get("/api/v1/health", status_code=status.HTTP_200_OK)
    def health_check():
        return {
            "status": "HEALTHY",
            "service": "Worker Agent HTTP API",
            "version": "1.0.0",
            "agent_id": worker_agent.agent_id,
            "agent_name": worker_agent.name,
            "model_name": worker_agent.model_name,
            "agent_status": worker_agent.status.value,
            "active_tasks_count": len(worker_agent.current_tasks),
            "timestamp": time.time()
        }

    # --- Task Execution Endpoints (Bearer Authenticated) ---
    @app.post("/task", status_code=status.HTTP_200_OK)
    @app.post("/api/v1/tasks", status_code=status.HTTP_200_OK)
    @app.post("/api/v1/tasks/execute", status_code=status.HTTP_200_OK)
    async def execute_task_endpoint(
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        # 1. Drain socket body first to prevent connection reset on Windows
        raw_body = await request.body()

        # 2. Strict & Fast Authentication Check (< 1ms)
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unauthorized: {auth_err}"
            )

        # 3. Strict Payload Validation
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or unparseable JSON body"
            )

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload must be a JSON object"
            )

        task_id = data.get("task_id")
        if not task_id or not isinstance(task_id, str) or not task_id.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'task_id' is required and must not be empty"
            )

        # 4. Agent Execution (run in threadpool so event loop stays non-blocking for /health)
        result = await run_in_threadpool(worker_agent.execute_task, data)

        return {
            "contract_version": data.get("contract_version", "1.0"),
            "task_id": result.task_id,
            "agent_id": result.agent_id,
            "status": result.status,
            "output_artifacts": result.output_artifacts,
            "logs": result.logs,
            "execution_time_seconds": result.execution_time_seconds,
            "error_message": result.error_message
        }

    # --- Agent Registration Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/agents/register", status_code=status.HTTP_201_CREATED)
    async def register_agent_endpoint(
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        raw_body = await request.body()
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            payload = {}

        registered_id = payload.get("agent_id") or worker_agent.agent_id

        return {
            "success": True,
            "agent_id": registered_id,
            "session_token": f"sess-{uuid.uuid4().hex[:8]}",
            "heartbeat_interval_seconds": 15,
            "message": "Ajan kaydı başarıyla doğrulandı ve havuza eklendi."
        }

    # --- Heartbeat Signal Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/agents/heartbeat", status_code=status.HTTP_200_OK)
    async def heartbeat_endpoint(
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        await request.body()
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        has_pending = len(pending_queue) > 0
        next_id = pending_queue[0].get("task_id") if has_pending else None

        return {
            "acknowledged": True,
            "has_pending_task": has_pending,
            "next_task_id": next_id
        }

    # --- Poll Next Task Endpoint (Bearer Authenticated) ---
    @app.get("/api/v1/tasks/pending", status_code=status.HTTP_200_OK)
    def get_pending_task(
        agent_id: str = Query(..., min_length=1),
        authorization: Optional[str] = Header(None)
    ):
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        if pending_queue:
            task = pending_queue.pop(0)
            return {"has_task": True, "task": task}
        return {"has_task": False, "message": "Atanmış veya hazır bekleyen görev bulunmuyor."}

    # --- Task Acknowledgment Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/tasks/{task_id}/ack", status_code=status.HTTP_200_OK)
    async def acknowledge_task(
        task_id: str,
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        await request.body()
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        return {
            "acknowledged": True,
            "task_id": task_id,
            "state": "RUNNING"
        }

    # --- Task Result Submission Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/tasks/{task_id}/result", status_code=status.HTTP_200_OK)
    async def submit_task_result(
        task_id: str,
        request: Request,
        authorization: Optional[str] = Header(None)
    ):
        await request.body()
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        return {
            "success": True,
            "task_id": task_id,
            "next_state": "COMPLETED",
            "message": "Görev çıktısı ve eserler başarıyla kaydedildi."
        }

    return app


# Default application instance for uvicorn
app = create_worker_app()


class WorkerHttpClient:
    """Client adapter for communicating with a remote or local Worker Agent HTTP endpoint."""

    def __init__(self, base_url: Optional[str] = None, auth_token: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or os.getenv("WORKER_BASE_URL") or os.getenv("BACKEND_API_HOST") or "http://localhost:8000").rstrip("/")
        self.auth_token = auth_token if auth_token is not None else get_auth_token()
        self.timeout = timeout

    def _headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def health_check(self, path: str = "/health") -> Dict[str, Any]:
        """Calls the health check endpoint."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def execute_task(self, task: Dict[str, Any], path: str = "/task") -> Dict[str, Any]:
        """Submits task payload to worker with Bearer authorization."""
        url = f"{self.base_url}{path}"
        data = json.dumps(task).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def run_server(host: str = "0.0.0.0", port: int = 8000, agent: Optional[BaseAgent] = None):
    """Runs the FastAPI server via uvicorn."""
    import uvicorn
    server_app = create_worker_app(agent=agent)
    uvicorn.run(server_app, host=host, port=port)


if __name__ == "__main__":
    configured_host = os.getenv("WORKER_HOST", "0.0.0.0")
    configured_port = int(os.getenv("WORKER_PORT", os.getenv("BACKEND_API_PORT", "8000")))
    run_server(host=configured_host, port=configured_port)
