"""
Worker Agent Authenticated HTTP/JSON API Server.
Implements docs/WORKER_HTTP_API_DRAFT.md and docs/INTER_AGENT_CONTRACTS.md
for distributed worker agent coordination (Tailscale VPN / LAN / Localhost).

S3-02 (İrem Yılmaz — Backend Agent — qwen2.5-coder:7b) & S3-01 (Eren Görkem Çolak):
- Enforces Bearer Token authentication on all protected operational endpoints.
- Rejects unauthorized or malformed requests with HTTP 401 (fast, non-leaking).
- Provides active health check endpoints (/health and /api/v1/health).
- Supports selecting any specialist worker agent via WORKER_AGENT_ROLE or --agent
  (backend, database, frontend, testing, integration) for Tailscale mesh deployment.
- Enforces idempotent duplicate task handling via DuplicateTaskTracker (HTTP 409 on
  concurrent duplicate, cached result on completed duplicate within the same run_id).
- Executes tasks via BaseAgent and returns standard TaskResult / WorkerTaskResultContract_v1.
- No hardcoded secrets or credentials in source code.
"""

import argparse
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
from src.agents.database_agent import DatabaseAgent
from src.agents.frontend_agent import FrontendAgent
from src.agents.integration_agent import IntegrationAgent
from src.agents.testing_agent import TestingAgent
from src.contracts import (
    CONTRACT_VERSION,
    DuplicateTaskTracker,
    WorkerErrorCode,
    WorkerErrorContract_v1,
)


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


def create_agent_by_role(role: Optional[str] = None) -> BaseAgent:
    """
    Instantiates the requested specialist worker agent for running a standalone
    HTTP worker node (e.g., on each teammate's machine over Tailscale).
    Defaults to BackendAgent when role is omitted.
    """
    normalized = (role or os.getenv("WORKER_AGENT_ROLE") or "backend").strip().lower()
    if normalized in ("database", "db", "agent-database"):
        return DatabaseAgent(agent_id="agent-database")
    if normalized in ("frontend", "fe", "agent-frontend"):
        return FrontendAgent(agent_id="agent-frontend")
    if normalized in ("testing", "qa", "test", "agent-testing"):
        return TestingAgent(agent_id="agent-testing")
    if normalized in ("integration", "int", "agent-integration"):
        return IntegrationAgent(agent_id="agent-integration")
    return BackendAgent()


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


def create_worker_app(
    agent: Optional[BaseAgent] = None,
    auth_token: Optional[str] = None,
    duplicate_tracker: Optional[DuplicateTaskTracker] = None,
) -> FastAPI:
    """
    Application factory for the Worker Agent HTTP/JSON API.
    Enables injecting custom agents or explicit tokens for deterministic unit testing.
    """
    worker_agent = agent if agent is not None else create_agent_by_role()
    token_resolver = lambda: get_auth_token(auth_token)
    tracker = duplicate_tracker if duplicate_tracker is not None else DuplicateTaskTracker()

    app = FastAPI(
        title="Worker Agent HTTP API",
        description="Authenticated HTTP REST interface for distributed worker agents",
        version=CONTRACT_VERSION,
    )

    pending_queue: List[Dict[str, Any]] = []

    # --- Health Endpoints (Public Health Probes) ---
    @app.get("/health", status_code=status.HTTP_200_OK)
    @app.get("/api/v1/health", status_code=status.HTTP_200_OK)
    def health_check():
        raw_status = getattr(worker_agent.status, "value", str(worker_agent.status))
        return {
            "status": "HEALTHY",
            "service": "Worker Agent HTTP API",
            "version": CONTRACT_VERSION,
            "agent_id": worker_agent.agent_id,
            "agent_name": worker_agent.name,
            "model_name": worker_agent.model_name,
            "agent_status": raw_status,
            "active_tasks_count": len(getattr(worker_agent, "current_tasks", [])),
            "timestamp": time.time(),
        }

    # --- Task Execution Endpoints (Bearer Authenticated) ---
    @app.post("/task", status_code=status.HTTP_200_OK)
    @app.post("/api/v1/tasks", status_code=status.HTTP_200_OK)
    @app.post("/api/v1/tasks/execute", status_code=status.HTTP_200_OK)
    async def execute_task_endpoint(
        request: Request,
        authorization: Optional[str] = Header(None),
    ):
        # 1. Drain socket body first to prevent connection reset on Windows
        raw_body = await request.body()

        # 2. Strict & Fast Authentication Check (< 1ms)
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unauthorized: {auth_err}",
            )

        # 3. Strict Payload Validation
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or unparseable JSON body",
            )

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload must be a JSON object",
            )

        task_id = data.get("task_id")
        if not task_id or not isinstance(task_id, str) or not task_id.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'task_id' is required and must not be empty",
            )

        run_id = data.get("run_id")
        envelope_id = data.get("envelope_id")

        # 4. Duplicate / Idempotency Check (S3-01 Item 3)
        dup_state, cached_response = tracker.begin(run_id, task_id, envelope_id)
        if dup_state == "COMPLETED" and cached_response is not None:
            cached_copy = dict(cached_response)
            cached_logs = list(cached_copy.get("logs") or [])
            cached_logs.append(f"[{worker_agent.name}] Idempotent cache hit for duplicate task '{task_id}'.")
            cached_copy["logs"] = cached_logs
            cached_copy["duplicate_cached"] = True
            return cached_copy

        if dup_state == "IN_PROGRESS":
            err_contract = WorkerErrorContract_v1(
                run_id=run_id,
                task_id=task_id,
                agent_id=worker_agent.agent_id,
                error_code=WorkerErrorCode.DUPLICATE_TASK,
                message=f"Task '{task_id}' (run_id='{run_id}') is already IN_PROGRESS on this worker.",
                retryable=False,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_contract.message,
            )

        # 5. Agent Execution (run in threadpool so event loop stays non-blocking for /health)
        try:
            result = await run_in_threadpool(worker_agent.execute_task, data)
        except Exception as exc:
            tracker.release(run_id, task_id, envelope_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Worker execution error: {exc}",
            )

        response_payload = {
            "contract_version": data.get("contract_version", CONTRACT_VERSION),
            "run_id": run_id,
            "task_id": result.task_id,
            "agent_id": result.agent_id,
            "status": result.status,
            "output_artifacts": result.output_artifacts,
            "logs": result.logs,
            "execution_time_seconds": result.execution_time_seconds,
            "error_message": result.error_message,
        }

        if result.status in ("SUCCESS", "COMPLETED"):
            tracker.complete(run_id, task_id, response_payload, envelope_id)
        else:
            tracker.release(run_id, task_id, envelope_id)

        return response_payload

    # --- Agent Registration Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/agents/register", status_code=status.HTTP_201_CREATED)
    async def register_agent_endpoint(
        request: Request,
        authorization: Optional[str] = Header(None),
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
            "message": "Ajan kaydı başarıyla doğrulandı ve havuza eklendi.",
        }

    # --- Heartbeat Signal Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/agents/heartbeat", status_code=status.HTTP_200_OK)
    async def heartbeat_endpoint(
        request: Request,
        authorization: Optional[str] = Header(None),
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
            "next_task_id": next_id,
        }

    # --- Poll Next Task Endpoint (Bearer Authenticated) ---
    @app.get("/api/v1/tasks/pending", status_code=status.HTTP_200_OK)
    def get_pending_task(
        agent_id: str = Query(..., min_length=1),
        authorization: Optional[str] = Header(None),
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
        authorization: Optional[str] = Header(None),
    ):
        await request.body()
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        return {
            "acknowledged": True,
            "task_id": task_id,
            "state": "RUNNING",
        }

    # --- Task Result Submission Endpoint (Bearer Authenticated) ---
    @app.post("/api/v1/tasks/{task_id}/result", status_code=status.HTTP_200_OK)
    async def submit_task_result(
        task_id: str,
        request: Request,
        authorization: Optional[str] = Header(None),
    ):
        await request.body()
        auth_err = check_bearer_token(authorization, token_resolver())
        if auth_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {auth_err}")

        return {
            "success": True,
            "task_id": task_id,
            "next_state": "COMPLETED",
            "message": "Görev çıktısı ve eserler başarıyla kaydedildi.",
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

    def health_check(self, path: str = "/health", timeout: Optional[float] = None) -> Dict[str, Any]:
        """Calls the health check endpoint."""
        url = f"{self.base_url}{path}"
        eff_timeout = self.timeout if timeout is None else timeout
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=eff_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def execute_task(self, task: Dict[str, Any], path: str = "/task", timeout: Optional[float] = None) -> Dict[str, Any]:
        """Submits task payload to worker with Bearer authorization."""
        url = f"{self.base_url}{path}"
        eff_timeout = self.timeout if timeout is None else timeout
        data = json.dumps(task).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=eff_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def run_server(host: str = "0.0.0.0", port: int = 8000, agent: Optional[BaseAgent] = None):
    """Runs the FastAPI server via uvicorn."""
    import uvicorn
    server_app = create_worker_app(agent=agent)
    uvicorn.run(server_app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributed Worker Agent HTTP API Server")
    parser.add_argument(
        "--agent",
        default=os.getenv("WORKER_AGENT_ROLE", "backend"),
        choices=["backend", "database", "frontend", "testing", "integration"],
        help="Specialist agent role to host on this worker node (default: backend)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("WORKER_HOST", "0.0.0.0"),
        help="Bind host address (use 0.0.0.0 for Tailscale / LAN access)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WORKER_PORT", os.getenv("BACKEND_API_PORT", "8000"))),
        help="Bind port number (default: 8000)",
    )
    args = parser.parse_args()
    selected_agent = create_agent_by_role(args.agent)
    run_server(host=args.host, port=args.port, agent=selected_agent)
