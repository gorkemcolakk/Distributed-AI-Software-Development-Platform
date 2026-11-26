"""
A2A (Agent2Agent) protocol layer, version 1.0 (S5, Eren Görkem Çolak).

Spec: https://a2a-protocol.org/latest/specification/ (field names checked against the
official specification/a2a.proto, package lf.a2a.v1; JSON uses the proto camelCase names).

What this module covers:
- Agent Card: every worker publishes GET /.well-known/agent-card.json (public), describing who it
  is, what it can do (skills) and how to reach it (supportedInterfaces, Bearer security scheme).
- HTTP+JSON binding of SendMessage (POST /message:send) and GetTask (GET /tasks/{id}).
  Our task envelope (TaskPayloadContract_v1) travels as a `data` Part of the A2A Message; the
  worker answers with an A2A Task whose artifacts hold the generated files (one Part per file)
  and the full worker result as a `data` Part, so the Master's existing result parsing is reused.
- Streaming and push notifications are not supported (declared false in the card): tasks are
  short and synchronous, the answer comes back in the same HTTP response.

The pure functions here have no FastAPI dependency; src/api/worker_server.py mounts the routes
and src/agents/remote_agent.py uses them on the Master side.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

A2A_PROTOCOL_VERSION = "1.0"
AGENT_CARD_PATH = "/.well-known/agent-card.json"
SEND_MESSAGE_PATH = "/message:send"
PROTOCOL_BINDING = "HTTP+JSON"
BEARER_SCHEME = "bearer"
RESULT_ARTIFACT_NAME = "worker-result"
RESULT_MEDIA_TYPE = "application/json"

STATE_COMPLETED = "TASK_STATE_COMPLETED"
STATE_FAILED = "TASK_STATE_FAILED"
STATE_REJECTED = "TASK_STATE_REJECTED"
ROLE_USER = "ROLE_USER"
ROLE_AGENT = "ROLE_AGENT"

ROLES = ("backend", "frontend", "database", "testing", "integration")

# One skill per worker role; tags are what the Master matches against the role it expects.
ROLE_SKILLS: Dict[str, Dict[str, Any]] = {
    "backend": {
        "name": "Backend API",
        "description": "Writes a runnable FastAPI service for the shared contract (SQLite storage, "
                       "sign up / log in when the contract has users).",
        "tags": ["backend", "fastapi", "python", "rest"],
        "examples": ["Build the REST API for a library system"],
        "outputModes": ["text/x-python", RESULT_MEDIA_TYPE],
    },
    "database": {
        "name": "Database schema",
        "description": "Writes and validates an SQLite schema with the contract's table and column names.",
        "tags": ["database", "sql", "sqlite", "schema"],
        "examples": ["Design the tables for a restaurant ordering system"],
        "outputModes": ["application/sql", RESULT_MEDIA_TYPE],
    },
    "frontend": {
        "name": "Frontend page",
        "description": "Writes one HTML5 page that loads and sends all data through the contract's endpoints.",
        "tags": ["frontend", "html", "css", "javascript"],
        "examples": ["Build the page where users add and list tasks"],
        "outputModes": ["text/html", RESULT_MEDIA_TYPE],
    },
    "testing": {
        "name": "API tests",
        "description": "Writes pytest tests that call only the contract's endpoints of the generated backend.",
        "tags": ["testing", "pytest", "qa"],
        "examples": ["Write tests for the book endpoints"],
        "outputModes": ["text/x-python", RESULT_MEDIA_TYPE],
    },
    "integration": {
        "name": "Integration review",
        "description": "Checks syntax, conflicts and SQL of all generated files, reviews them and builds a manifest.",
        "tags": ["integration", "review", "packaging"],
        "examples": ["Review and package the generated project"],
        "outputModes": [RESULT_MEDIA_TYPE],
    },
}

MEDIA_TYPES = {".py": "text/x-python", ".sql": "application/sql", ".html": "text/html",
               ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
               ".md": "text/markdown"}


def role_of(*names: Any) -> str:
    """'agent-backend', 'Backend Architecture Agent' -> 'backend'; '' when no role word is found."""
    text = " ".join(str(n or "") for n in names).lower()
    for role in ROLES:
        if role in text:
            return role
    return ""


# ------------------------------------------------------------------------------------- Agent Card

def build_agent_card(agent: Any, base_url: str, version: str = "1.0.0") -> Dict[str, Any]:
    """A2A 1.0 AgentCard of one worker. base_url is the address the caller used (e.g. the Tailscale IP)."""
    role = role_of(getattr(agent, "agent_id", ""), getattr(agent, "name", ""))
    skill = dict(ROLE_SKILLS.get(role) or {
        "name": "Worker", "description": "General worker agent.", "tags": ["worker"],
        "outputModes": [RESULT_MEDIA_TYPE]})
    skill["id"] = role or "worker"
    capabilities = getattr(agent, "capabilities", None)
    specialties = list(getattr(capabilities, "specialties", None) or [])
    skill["tags"] = list(dict.fromkeys(skill["tags"] + specialties))
    model = getattr(agent, "model_name", "") or ""
    return {
        "name": str(getattr(agent, "name", "") or "Worker Agent"),
        "description": (f"{skill['name']} worker of the Distributed AI Software Development Platform, "
                        f"running the local model {model}. Receives one task of a run from the Master "
                        f"Agent and returns the generated files."),
        "supportedInterfaces": [{
            "url": base_url.rstrip("/"),
            "protocolBinding": PROTOCOL_BINDING,
            "protocolVersion": A2A_PROTOCOL_VERSION,
        }],
        "provider": {"organization": "CM6453 Distributed AI Software Development Platform",
                     "url": "https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform"},
        "version": version,
        "capabilities": {"streaming": False, "pushNotifications": False, "extendedAgentCard": False},
        "securitySchemes": {BEARER_SCHEME: {"httpAuthSecurityScheme": {
            "scheme": "Bearer", "description": "Shared WORKER_AUTH_TOKEN of the team"}}},
        "securityRequirements": [{"schemes": {BEARER_SCHEME: {"list": []}}}],
        "defaultInputModes": [RESULT_MEDIA_TYPE, "text/plain"],
        "defaultOutputModes": [RESULT_MEDIA_TYPE],
        "skills": [skill],
    }


def card_roles(card: Optional[Dict[str, Any]]) -> List[str]:
    """Roles an Agent Card claims through its skill ids and tags."""
    roles = []
    for skill in (card or {}).get("skills") or []:
        if not isinstance(skill, dict):
            continue
        for value in [skill.get("id")] + list(skill.get("tags") or []):
            role = role_of(value)
            if role and role not in roles:
                roles.append(role)
    return roles


def validate_agent_card(card: Any) -> List[str]:
    """Missing REQUIRED fields of an A2A 1.0 AgentCard (empty list = valid)."""
    if not isinstance(card, dict):
        return ["card is not a JSON object"]
    problems = [f"missing {key}" for key in ("name", "description", "supportedInterfaces", "version",
                                              "capabilities", "defaultInputModes", "defaultOutputModes", "skills")
                if key not in card]
    for i, iface in enumerate(card.get("supportedInterfaces") or []):
        problems += [f"supportedInterfaces[{i}] missing {k}" for k in ("url", "protocolBinding", "protocolVersion")
                     if not (isinstance(iface, dict) and iface.get(k))]
    for i, skill in enumerate(card.get("skills") or []):
        problems += [f"skills[{i}] missing {k}" for k in ("id", "name", "description", "tags")
                     if not (isinstance(skill, dict) and k in skill)]
    return problems


# ------------------------------------------------------------------------------- SendMessage / Task

def build_send_message_request(task_payload: Dict[str, Any]) -> Dict[str, Any]:
    """SendMessageRequest carrying our task envelope as a data Part (Master -> worker)."""
    return {
        "message": {
            "messageId": str(uuid.uuid4()),
            "contextId": str(task_payload.get("run_id") or ""),
            "role": ROLE_USER,
            "parts": [{"data": task_payload, "mediaType": RESULT_MEDIA_TYPE}],
            "metadata": {"contract_version": task_payload.get("contract_version")},
        },
        "configuration": {"acceptedOutputModes": [RESULT_MEDIA_TYPE], "returnImmediately": False},
    }


def task_payload_from_message(body: Any) -> Dict[str, Any]:
    """Our task dict from a SendMessageRequest: the first data Part, or the text Parts as a description."""
    if not isinstance(body, dict) or not isinstance(body.get("message"), dict):
        raise ValueError("SendMessageRequest needs a 'message' object")
    message = body["message"]
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("message.parts must be a non-empty list")
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("data"), dict):
            return dict(part["data"])
    text = "\n".join(str(p.get("text")) for p in parts if isinstance(p, dict) and p.get("text"))
    if not text.strip():
        raise ValueError("message has neither a data Part with the task nor a text Part")
    return {"task_id": str(message.get("taskId") or message.get("messageId") or uuid.uuid4()),
            "run_id": message.get("contextId") or None, "title": text.strip().splitlines()[0][:120],
            "description": text.strip()}


def _media_type(filename: str) -> str:
    name = str(filename or "").lower()
    return next((mt for ext, mt in MEDIA_TYPES.items() if name.endswith(ext)), "text/plain")


def build_task(result_payload: Dict[str, Any], context_id: Optional[str] = None) -> Dict[str, Any]:
    """A2A Task from the worker's normal /task response (worker -> Master)."""
    success = str(result_payload.get("status") or "").upper() in ("SUCCESS", "COMPLETED")
    files = (result_payload.get("output_artifacts") or {}).get("files") or []
    file_parts = [{"text": str(f.get("content", "")), "filename": str(f.get("filename") or f.get("path")),
                   "mediaType": _media_type(f.get("filename") or f.get("path"))}
                  for f in files if isinstance(f, dict) and (f.get("filename") or f.get("path"))]
    artifacts = [{"artifactId": str(uuid.uuid4()), "name": RESULT_ARTIFACT_NAME,
                  "description": "Full worker result (TaskResult contract)",
                  "parts": [{"data": result_payload, "mediaType": RESULT_MEDIA_TYPE}]}]
    if file_parts:
        artifacts.insert(0, {"artifactId": str(uuid.uuid4()), "name": "generated-files", "parts": file_parts})
    status: Dict[str, Any] = {"state": STATE_COMPLETED if success else STATE_FAILED,
                              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not success and result_payload.get("error_message"):
        status["message"] = {"messageId": str(uuid.uuid4()), "role": ROLE_AGENT,
                             "parts": [{"text": str(result_payload["error_message"])}]}
    return {"id": str(result_payload.get("task_id") or uuid.uuid4()),
            "contextId": str(context_id or result_payload.get("run_id") or ""),
            "status": status, "artifacts": artifacts}


def result_payload_from_task(response: Any) -> Dict[str, Any]:
    """The worker's normal result dict back out of a SendMessageResponse / Task (Master side)."""
    task = response.get("task") if isinstance(response, dict) and "task" in response else response
    if not isinstance(task, dict) or not isinstance(task.get("status"), dict):
        raise ValueError("A2A response has no Task with a status")
    for artifact in task.get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("name") == RESULT_ARTIFACT_NAME:
            for part in artifact.get("parts") or []:
                if isinstance(part, dict) and isinstance(part.get("data"), dict):
                    return dict(part["data"])
    # A generic A2A agent: rebuild our result from the state and the file Parts
    state = task["status"].get("state")
    files = [{"filename": p.get("filename"), "content": p.get("text", "")}
             for a in task.get("artifacts") or [] if isinstance(a, dict)
             for p in a.get("parts") or [] if isinstance(p, dict) and p.get("filename") and "text" in p]
    message_parts = ((task["status"].get("message") or {}).get("parts") or [])
    error = " ".join(str(p.get("text")) for p in message_parts if isinstance(p, dict) and p.get("text")) or None
    return {"task_id": task.get("id"), "status": "SUCCESS" if state == STATE_COMPLETED else "FAILED",
            "output_artifacts": {"files": files} if files else {}, "logs": [],
            "error_message": None if state == STATE_COMPLETED else (error or f"A2A task state {state}")}
