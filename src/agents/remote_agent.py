"""
Remote Agent HTTP Proxy for Distributed Execution (S3-01 — Eren Görkem Çolak).

Allows the Master Orchestrator to dispatch tasks over HTTP/JSON (e.g., across a
Tailscale VPN mesh, LAN, or local ports) to remote worker servers running
`src/api/worker_server.py` without changing the orchestrator's BaseAgent interface.

Features:
- Subclasses `BaseAgent` so `CapabilityEvaluator`, `MasterOrchestrator`, `db_manager`,
  and the Streamlit UI treat remote and local agents identically.
- Wraps every outgoing task in a validated `TaskPayloadContract_v1` envelope
  including `contract_version="1.0"`, `run_id`, `task_id`, `envelope_id`,
  `timeout_seconds`, and `context_artifacts`.
- Validates the worker's response with `WorkerTaskResultContract_v1` and normalizes
  `"COMPLETED"` / `"SUCCESS"` into `TaskResult(status="SUCCESS")`.
- Enforces per-task HTTP timeouts and classifies network / HTTP errors
  (`TIMEOUT`, `UNAUTHORIZED`, `DUPLICATE_TASK`, `INVALID_PAYLOAD`, `UNREACHABLE`).
- Supports optional fallback to an in-process local agent when `fallback_to_local=True`.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from pydantic import ValidationError

from src.agents.base_agent import (
    AgentCapabilityProfile,
    AgentStatus,
    BaseAgent,
    TaskResult,
)
from src.contracts import (
    CONTRACT_VERSION,
    DEFAULT_TASK_TIMEOUT_SECONDS,
    TaskPayloadContract_v1,
    WorkerErrorCode,
    WorkerErrorContract_v1,
    WorkerTaskResultContract_v1,
    build_task_envelope,
    normalize_worker_status,
)

# Maps canonical agent IDs / roles to their environment variable for Tailscale/remote URLs
AGENT_URL_ENV_VARS: Dict[str, str] = {
    "agent-backend": "BACKEND_AGENT_URL",
    "backend": "BACKEND_AGENT_URL",
    "agent-database": "DATABASE_AGENT_URL",
    "database": "DATABASE_AGENT_URL",
    "agent-frontend": "FRONTEND_AGENT_URL",
    "frontend": "FRONTEND_AGENT_URL",
    "agent-testing": "TESTING_AGENT_URL",
    "testing": "TESTING_AGENT_URL",
    "agent-integration": "INTEGRATION_AGENT_URL",
    "integration": "INTEGRATION_AGENT_URL",
}


def get_remote_auth_token(override_token: Optional[str] = None) -> str:
    """Resolves Bearer token for worker communication from explicit value or environment."""
    if override_token is not None:
        return override_token.strip()
    return (os.getenv("WORKER_AUTH_TOKEN") or os.getenv("BACKEND_AUTH_TOKEN") or "").strip()


def get_agent_endpoint_url(agent_id_or_role: str, config_url: Optional[str] = None) -> Optional[str]:
    """
    Returns the configured remote HTTP endpoint URL (e.g. Tailscale `http://100.x.y.z:8001`)
    for a given agent ID or role if set via environment variable or config; otherwise None.
    """
    key = (agent_id_or_role or "").strip().lower()
    env_var = AGENT_URL_ENV_VARS.get(key)
    if env_var:
        env_val = (os.getenv(env_var) or "").strip()
        if env_val:
            return env_val.rstrip("/")
    if config_url and str(config_url).strip():
        return str(config_url).strip().rstrip("/")
    return None


class RemoteAgentProxy(BaseAgent):
    """
    BaseAgent-compatible proxy that dispatches tasks to a remote Worker HTTP server
    (e.g., over Tailscale VPN or LAN) using versioned v1.0 contracts and Bearer auth.
    """

    def __init__(
        self,
        endpoint_url: str,
        agent_id: Optional[str] = None,
        name: str = "Remote Worker Agent",
        model_name: str = "remote-ollama",
        capability_profile: Optional[AgentCapabilityProfile] = None,
        local_agent: Optional[BaseAgent] = None,
        auth_token: Optional[str] = None,
        timeout: Optional[float] = None,
        task_path: str = "/task",
        health_path: str = "/health",
        fallback_to_local: bool = False,
        transport: Optional[Callable[[str, str, Optional[Dict[str, Any]], Dict[str, str], float], Dict[str, Any]]] = None,
    ):
        if local_agent is not None:
            agent_id = agent_id or local_agent.agent_id
            name = name if name != "Remote Worker Agent" else local_agent.name
            model_name = model_name if model_name != "remote-ollama" else local_agent.model_name
            capability_profile = capability_profile or local_agent.capabilities

        profile = capability_profile or AgentCapabilityProfile(
            coding_score=85.0,
            reasoning_score=85.0,
            context_capacity=85.0,
            specialties=["backend", "frontend", "database", "testing", "integration"],
        )
        super().__init__(
            agent_id=agent_id or "agent-remote",
            name=name,
            model_name=model_name,
            capability_profile=profile,
        )
        self.endpoint_url = (endpoint_url or "").strip().rstrip("/")
        if not self.endpoint_url:
            raise ValueError("RemoteAgentProxy requires a non-empty endpoint_url.")

        self.local_agent = local_agent
        self.auth_token = get_remote_auth_token(auth_token)
        self.timeout = float(
            timeout
            if timeout is not None
            else os.getenv("WORKER_HTTP_TIMEOUT", str(DEFAULT_TASK_TIMEOUT_SECONDS))
        )
        self.task_path = task_path if task_path.startswith("/") else f"/{task_path}"
        self.health_path = health_path if health_path.startswith("/") else f"/{health_path}"
        self.fallback_to_local = fallback_to_local
        self._transport = transport or self._default_http_transport
        self.last_envelope: Optional[Dict[str, Any]] = None
        self.last_error_contract: Optional[WorkerErrorContract_v1] = None

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Contract-Version": CONTRACT_VERSION,
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    @staticmethod
    def _default_http_transport(
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]],
        headers: Dict[str, str],
        timeout: float,
    ) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def check_health(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Probes the remote worker's /health endpoint and updates local agent status."""
        url = f"{self.endpoint_url}{self.health_path}"
        try:
            data = self._transport("GET", url, None, {"Accept": "application/json"}, timeout)
            remote_status = str(data.get("agent_status", "IDLE")).upper()
            if remote_status in AgentStatus.__members__:
                self.status = AgentStatus[remote_status]
            else:
                self.status = AgentStatus.IDLE
            return data
        except Exception as exc:
            self.status = AgentStatus.OFFLINE
            return {"status": "OFFLINE", "error": str(exc), "endpoint": url}

    def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """
        Packages the task into a versioned `TaskPayloadContract_v1` envelope and
        dispatches it over HTTP to the remote worker endpoint.
        """
        self.status = AgentStatus.BUSY
        start_time = time.time()

        try:
            envelope: TaskPayloadContract_v1 = build_task_envelope(
                task,
                run_id=task.get("run_id"),
                timeout_seconds=float(task.get("timeout_seconds", self.timeout)),
            )
        except ValidationError as exc:
            self.status = AgentStatus.ERROR
            err = WorkerErrorContract_v1(
                run_id=task.get("run_id"),
                task_id=str(task.get("task_id") or "unknown"),
                agent_id=self.agent_id,
                error_code=WorkerErrorCode.INVALID_PAYLOAD,
                message=f"Görev zarfı sözleşme doğrulamasından geçemedi: {exc}",
                retryable=False,
            )
            self.last_error_contract = err
            return TaskResult(
                task_id=str(task.get("task_id") or "unknown"),
                agent_id=self.agent_id,
                status="FAILED",
                output_artifacts={"error_contract": err.model_dump()},
                logs=[f"[{self.name}] Envelope validation failed: {err.message}"],
                execution_time_seconds=round(time.time() - start_time, 2),
                error_message=err.message,
            )

        task_id = envelope.task_id
        self.current_tasks.append(task_id)
        payload_dict = envelope.model_dump()
        # Preserve extra integration keys (output_artifacts, artifact_sources, package_dir) if present
        for extra_key in ("output_artifacts", "artifact_sources", "package_dir"):
            if extra_key in task and extra_key not in payload_dict:
                payload_dict[extra_key] = task[extra_key]

        self.last_envelope = payload_dict
        effective_timeout = min(float(envelope.timeout_seconds), float(self.timeout))
        url = f"{self.endpoint_url}{self.task_path}"
        logs = [
            f"[{self.name}] Dispatching task '{task_id}' (run_id='{envelope.run_id}', "
            f"contract v{envelope.contract_version}) to {url}..."
        ]

        try:
            raw_response = self._transport(
                "POST",
                url,
                payload_dict,
                self._headers(),
                effective_timeout,
            )
            result_contract = WorkerTaskResultContract_v1(
                contract_version=str(raw_response.get("contract_version", CONTRACT_VERSION)),
                run_id=raw_response.get("run_id", envelope.run_id),
                task_id=raw_response.get("task_id", task_id),
                agent_id=raw_response.get("agent_id", self.agent_id),
                status=raw_response.get("status", "FAILED"),
                output_artifacts=raw_response.get("output_artifacts") or {},
                logs=list(raw_response.get("logs") or []),
                error_message=raw_response.get("error_message"),
                execution_time_seconds=float(
                    raw_response.get("execution_time_seconds", round(time.time() - start_time, 2))
                ),
            )
            combined_logs = logs + result_contract.logs
            norm_status = result_contract.normalized_status()
            if norm_status == "SUCCESS":
                self.status = AgentStatus.IDLE
                if task_id in self.current_tasks:
                    self.current_tasks.remove(task_id)
                self.last_error_contract = None
                return TaskResult(
                    task_id=result_contract.task_id,
                    agent_id=self.agent_id,
                    status="SUCCESS",
                    output_artifacts=result_contract.output_artifacts,
                    logs=combined_logs,
                    execution_time_seconds=result_contract.execution_time_seconds,
                    error_message=None,
                )
            else:
                err_msg = result_contract.error_message or f"Remote worker reported status '{result_contract.status.value}'"
                raise RuntimeError(err_msg)

        except Exception as exc:
            elapsed = round(time.time() - start_time, 2)
            if task_id in self.current_tasks:
                self.current_tasks.remove(task_id)

            error_contract = self._classify_exception(exc, envelope.run_id, task_id)
            self.last_error_contract = error_contract
            logs.append(f"[{self.name}] Remote dispatch error ({error_contract.error_code.value}): {error_contract.message}")

            if self.fallback_to_local and self.local_agent is not None:
                logs.append(f"[{self.name}] [REMOTE_FALLBACK] Falling back to local in-process agent '{self.local_agent.name}'.")
                local_res = self.local_agent.execute_task(payload_dict)
                self.status = self.local_agent.status
                return TaskResult(
                    task_id=local_res.task_id,
                    agent_id=self.agent_id,
                    status=normalize_worker_status(local_res.status),
                    output_artifacts=local_res.output_artifacts,
                    logs=logs + list(local_res.logs or []),
                    execution_time_seconds=round(time.time() - start_time, 2),
                    error_message=local_res.error_message,
                )

            self.status = AgentStatus.ERROR
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status="FAILED",
                output_artifacts={"error_contract": error_contract.model_dump()},
                logs=logs,
                execution_time_seconds=elapsed,
                error_message=f"[{error_contract.error_code.value}] {error_contract.message}",
            )

    def _classify_exception(
        self,
        exc: Exception,
        run_id: Optional[str],
        task_id: str,
    ) -> WorkerErrorContract_v1:
        """Maps HTTP, socket, timeout, and validation exceptions into `WorkerErrorContract_v1`."""
        if isinstance(exc, urllib.error.HTTPError):
            code = exc.code
            detail = exc.reason
            try:
                body = json.loads(exc.read().decode("utf-8", errors="ignore"))
                if isinstance(body, dict) and body.get("detail"):
                    detail = str(body["detail"])
            except Exception:
                pass
            if code == 401:
                return WorkerErrorContract_v1(
                    run_id=run_id,
                    task_id=task_id,
                    agent_id=self.agent_id,
                    error_code=WorkerErrorCode.UNAUTHORIZED,
                    message=f"HTTP 401 Yetkisiz erişim ({detail})",
                    retryable=False,
                )
            if code == 409:
                return WorkerErrorContract_v1(
                    run_id=run_id,
                    task_id=task_id,
                    agent_id=self.agent_id,
                    error_code=WorkerErrorCode.DUPLICATE_TASK,
                    message=f"HTTP 409 Mükerrer görev reddedildi ({detail})",
                    retryable=False,
                )
            if code in (400, 422):
                return WorkerErrorContract_v1(
                    run_id=run_id,
                    task_id=task_id,
                    agent_id=self.agent_id,
                    error_code=WorkerErrorCode.INVALID_PAYLOAD,
                    message=f"HTTP {code} Geçersiz görev verisi ({detail})",
                    retryable=False,
                )
            if code in (408, 504):
                return WorkerErrorContract_v1(
                    run_id=run_id,
                    task_id=task_id,
                    agent_id=self.agent_id,
                    error_code=WorkerErrorCode.TIMEOUT,
                    message=f"HTTP {code} Uzak ajan zaman aşımı ({detail})",
                    retryable=True,
                )
            return WorkerErrorContract_v1(
                run_id=run_id,
                task_id=task_id,
                agent_id=self.agent_id,
                error_code=WorkerErrorCode.EXECUTION_ERROR,
                message=f"HTTP {code} Uzak sunucu hatası ({detail})",
                retryable=code >= 500,
            )

        if isinstance(exc, urllib.error.URLError):
            reason = exc.reason
            if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower():
                return WorkerErrorContract_v1(
                    run_id=run_id,
                    task_id=task_id,
                    agent_id=self.agent_id,
                    error_code=WorkerErrorCode.TIMEOUT,
                    message=f"Worker HTTP bağlantı/okuma zaman aşımı ({self.timeout}s)",
                    retryable=True,
                )
            return WorkerErrorContract_v1(
                run_id=run_id,
                task_id=task_id,
                agent_id=self.agent_id,
                error_code=WorkerErrorCode.UNREACHABLE,
                message=f"Worker sunucusuna ulaşılamadı ({self.endpoint_url}): {reason}",
                retryable=True,
            )

        if isinstance(exc, (socket.timeout, TimeoutError)):
            return WorkerErrorContract_v1(
                run_id=run_id,
                task_id=task_id,
                agent_id=self.agent_id,
                error_code=WorkerErrorCode.TIMEOUT,
                message=f"Worker HTTP zaman aşımı ({self.timeout}s)",
                retryable=True,
            )

        if isinstance(exc, ValidationError):
            return WorkerErrorContract_v1(
                run_id=run_id,
                task_id=task_id,
                agent_id=self.agent_id,
                error_code=WorkerErrorCode.CONTRACT_VIOLATION,
                message=f"Worker yanıtı sözleşme şemasına uymuyor: {exc}",
                retryable=False,
            )

        return WorkerErrorContract_v1(
            run_id=run_id,
            task_id=task_id,
            agent_id=self.agent_id,
            error_code=WorkerErrorCode.EXECUTION_ERROR,
            message=str(exc),
            retryable=False,
        )


def wrap_agent_if_remote(
    agent: BaseAgent,
    endpoint_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: Optional[float] = None,
    fallback_to_local: Optional[bool] = None,
) -> BaseAgent:
    """
    If a remote URL (e.g., Tailscale IP `http://100.x.y.z:8001`) is configured for `agent`
    via parameter or environment variable (`BACKEND_AGENT_URL`, `DATABASE_AGENT_URL`, etc.),
    wraps `agent` in a `RemoteAgentProxy`. Otherwise returns `agent` unchanged.
    """
    resolved_url = get_agent_endpoint_url(agent.agent_id, endpoint_url)
    if not resolved_url:
        return agent

    if fallback_to_local is None:
        raw_fb = (os.getenv("REMOTE_FALLBACK_TO_LOCAL") or "").strip().lower()
        fallback_to_local = raw_fb in ("1", "true", "yes", "on")

    return RemoteAgentProxy(
        endpoint_url=resolved_url,
        local_agent=agent,
        auth_token=auth_token,
        timeout=timeout,
        fallback_to_local=fallback_to_local,
    )

