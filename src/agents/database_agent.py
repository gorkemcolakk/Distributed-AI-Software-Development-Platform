"""
Database Specialist Agent implementation.
Designs database schemas, migrations, indices, and data persistence models
with a local Ollama model (default: llama3.2:3b).

S3-04 (Mahmut Karaalioğlu):
- The task description and project context are sent to the local Ollama model.
- The SQL in the reply is extracted and executed against a throw-away in-memory
  SQLite database. Only replies that really create at least one table pass.
- ATTACH / DETACH / VACUUM / PRAGMA / load_extension are refused, so a model
  reply can never create or touch a file on disk while being validated.
- Broken model output raises ModelOutputError -> BaseAgent marks the task FAILED.
- When Ollama is unreachable the agent returns a clearly labelled fallback schema
  (FALLBACK_ENABLED=true); with fallback disabled the task fails.
- The agent never writes to disk itself: the generated .sql file is returned in
  output_artifacts["files"] and the Master Orchestrator writes it into
  workspaces/{run_id}/ through src/master/workspace.py.
"""

import json
import os
import re
import socket
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional, Callable

from src.agents.base_agent import BaseAgent, AgentCapabilityProfile


class ModelOutputError(ValueError):
    """The model answered, but the answer is not a usable SQL schema."""


class OllamaCallError(RuntimeError):
    """Ollama could not be reached or returned an HTTP / protocol error."""

    def __init__(self, message: str, error_type: str = "UNKNOWN", status_code: Optional[int] = None):
        super().__init__(message)
        self.error_type = error_type  # TIMEOUT, CONNECTION_REFUSED, NOT_FOUND, HTTP_ERROR, INVALID_RESPONSE
        self.status_code = status_code


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _is_ollama_reachable(host: str, timeout: float = 1.0) -> bool:
    """Quick TCP check so an offline Ollama fails fast instead of waiting for the full timeout."""
    try:
        parsed = urllib.parse.urlparse(host)
        hostname = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((hostname, port), timeout=timeout):
            return True
    except OSError:
        return False


_SQL_BLOCK = re.compile(r"```[ \t]*(?:sql|sqlite|postgresql|postgres)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
_FORBIDDEN_SQL = re.compile(r"\b(ATTACH|DETACH|VACUUM|PRAGMA|LOAD_EXTENSION)\b", re.IGNORECASE)
_SQL_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
SQL_VALIDATION_TIMEOUT_SECONDS = 5.0


def extract_sql(raw_response: str) -> str:
    """Takes the longest fenced SQL block from the model reply, or the whole reply if none is fenced."""
    if not raw_response or not raw_response.strip():
        raise ModelOutputError("Model boş yanıt döndürdü.")
    blocks = [b.strip() for b in _SQL_BLOCK.findall(raw_response) if b.strip()]
    if blocks:
        return max(blocks, key=len)
    return raw_response.strip()


def _deny_dangerous(action, arg1, arg2, db_name, trigger):
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def validate_sql_schema(sql: str) -> Dict[str, List[str]]:
    """
    Executes the script in an isolated in-memory SQLite database and returns the
    objects it created: {"tables": [...], "indexes": [...], "views": [...], "triggers": [...]}.
    Raises ModelOutputError if the script is not valid SQL or creates no table.
    """
    if not sql or not sql.strip():
        raise ModelOutputError("SQL çıktısı boş.")
    without_comments = _SQL_COMMENT.sub(" ", sql)
    forbidden = _FORBIDDEN_SQL.search(without_comments)
    if forbidden:
        raise ModelOutputError(f"SQL çıktısında izin verilmeyen ifade var: {forbidden.group(1).upper()}")

    conn = sqlite3.connect(":memory:")
    deadline = time.monotonic() + SQL_VALIDATION_TIMEOUT_SECONDS
    try:
        conn.set_authorizer(_deny_dangerous)
        # Abort runaway scripts (e.g. an endless WITH RECURSIVE) instead of hanging the agent
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            conn.executescript(sql)
        except sqlite3.Error as exc:
            if time.monotonic() > deadline:
                raise ModelOutputError(
                    f"SQL doğrulaması {SQL_VALIDATION_TIMEOUT_SECONDS} saniyede tamamlanamadı.") from exc
            raise ModelOutputError(f"Model çıktısı geçerli SQLite SQL değil: {exc}") from exc
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)
        rows = conn.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
    finally:
        conn.close()

    objects: Dict[str, List[str]] = {"tables": [], "indexes": [], "views": [], "triggers": []}
    plural = {"table": "tables", "index": "indexes", "view": "views", "trigger": "triggers"}
    for obj_type, name in rows:
        if obj_type in plural:
            objects[plural[obj_type]].append(name)
    if not objects["tables"]:
        raise ModelOutputError("SQL çıktısı hiçbir tablo oluşturmuyor (CREATE TABLE bulunamadı).")
    return objects


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_").lower()
    return slug or "generated"


class DatabaseAgent(BaseAgent):
    """Specialized Agent for Database Schema Design & Migrations."""

    def __init__(self, agent_id: str = None, name: str = "Database Schema Agent", model_name: str = "llama3.2:3b",
                 use_ollama: Optional[bool] = None, ollama_host: Optional[str] = None,
                 timeout: Optional[float] = None, fallback_enabled: Optional[bool] = None,
                 llm_client: Optional[Callable[[str], str]] = None):
        profile = AgentCapabilityProfile(
            coding_score=94.0,
            reasoning_score=90.0,
            context_capacity=88.0,
            specialties=["database", "sql", "migrations", "indexing", "orm"]
        )
        super().__init__(agent_id=agent_id, name=name, model_name=model_name, capability_profile=profile)
        self.use_ollama = _env_flag("DATABASE_AGENT_USE_OLLAMA", True) if use_ollama is None else use_ollama
        self.ollama_host = (ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = float(timeout if timeout is not None else os.getenv("OLLAMA_TIMEOUT", "180"))
        self.fallback_enabled = _env_flag("FALLBACK_ENABLED", True) if fallback_enabled is None else fallback_enabled
        # Injectable for tests; defaults to a real HTTP call to Ollama
        self.llm_client = llm_client or self._call_ollama

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------
    def _process(self, task: Dict[str, Any], logs: List[str]) -> Dict[str, Any]:
        task_id = task.get("task_id", "task-db")
        filename = f"database/schema_{_safe_slug(task_id)}.sql"
        logs.append(f"[{self.name}] Analyzing entity relationships and relational integrity for '{task_id}'...")

        if not self.use_ollama:
            logs.append(f"[{self.name}] Ollama disabled (DATABASE_AGENT_USE_OLLAMA=false); using labelled template schema.")
            return self._build_result(task, self._fallback_schema(task), filename,
                                      generation_mode="template", model_used=None)

        prompt = self.build_prompt(task)
        logs.append(f"[{self.name}] Sending schema prompt to local Ollama model '{self.model_name}' at {self.ollama_host}...")
        try:
            raw = self.llm_client(prompt)
        except OllamaCallError as exc:
            if not self.fallback_enabled:
                logs.append(f"[{self.name}] Ollama call failed and fallback is disabled: {exc}")
                raise
            logs.append(f"[{self.name}] [FALLBACK] Ollama unavailable ({exc.error_type}): {exc}. Using labelled fallback schema.")
            return self._build_result(task, self._fallback_schema(task), filename,
                                      generation_mode="fallback", model_used=None, fallback_reason=exc.error_type)

        sql = extract_sql(raw)
        objects = validate_sql_schema(sql)
        logs.append(f"[{self.name}] Model SQL validated in in-memory SQLite: "
                    f"{len(objects['tables'])} tables, {len(objects['indexes'])} indexes.")
        return self._build_result(task, sql, filename, generation_mode="ollama",
                                  model_used=self.model_name, objects=objects)

    # ------------------------------------------------------------------
    # Prompt / result helpers
    # ------------------------------------------------------------------
    def build_prompt(self, task: Dict[str, Any]) -> str:
        context = task.get("context_artifacts") or {}
        context_text = json.dumps(context, ensure_ascii=False, indent=2)[:6000] if context else "(none)"
        return (
            "You are a senior database engineer. Design a relational database schema.\n"
            "Rules:\n"
            "- Reply with exactly one ```sql code block and nothing else.\n"
            "- The SQL must run unchanged on SQLite 3 (no SERIAL, no ENUM, no schema names).\n"
            "- Use CREATE TABLE IF NOT EXISTS with INTEGER PRIMARY KEY, NOT NULL, UNIQUE,\n"
            "  CHECK and FOREIGN KEY ... REFERENCES constraints where they make sense.\n"
            "- Add CREATE INDEX statements for foreign keys and frequently searched columns.\n"
            "- Do not use PRAGMA, ATTACH, DETACH or VACUUM.\n\n"
            f"Task title: {task.get('title', '')}\n"
            f"Task description: {task.get('description', '')}\n"
            f"Project context:\n{context_text}\n"
        )

    def _build_result(self, task: Dict[str, Any], sql: str, filename: str, generation_mode: str,
                      model_used: Optional[str], objects: Optional[Dict[str, List[str]]] = None,
                      fallback_reason: Optional[str] = None) -> Dict[str, Any]:
        objects = objects or validate_sql_schema(sql)
        result = {
            "files": [{"filename": filename, "content": sql.rstrip() + "\n", "language": "sql"}],
            "generated_sql": sql,
            "tables_designed": objects["tables"],
            "indexes_created": objects["indexes"],
            "database_engine": "SQLite",
            "migration_version": f"001_{_safe_slug(task.get('task_id', 'schema'))}",
            "model_used": model_used,
            "generation_mode": generation_mode,
            "status": "DATABASE_SCHEMA_GENERATED" if generation_mode == "ollama" else "DATABASE_SCHEMA_FALLBACK",
        }
        if fallback_reason:
            result["fallback_reason"] = fallback_reason
        return result

    def _fallback_schema(self, task: Dict[str, Any]) -> str:
        """Deterministic, valid SQLite schema used only when the model cannot be reached."""
        task_id = task.get("task_id", "task-db")
        return f"""-- FALLBACK SCHEMA (generated without a model; Ollama was not used)
-- Task: {_safe_slug(task_id)}

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects (owner_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id);
"""

    # ------------------------------------------------------------------
    # Ollama transport
    # ------------------------------------------------------------------
    def _call_ollama(self, prompt: str) -> str:
        """POSTs the prompt to Ollama /api/generate and returns the 'response' text."""
        if not _is_ollama_reachable(self.ollama_host, timeout=1.0):
            raise OllamaCallError(f"Ollama sunucusuna bağlanılamadı ({self.ollama_host}).",
                                  error_type="CONNECTION_REFUSED")
        body = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "seed": 42, "num_predict": 1536}
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.ollama_host}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise OllamaCallError(f"Model '{self.model_name}' Ollama üzerinde bulunamadı (HTTP 404).",
                                      error_type="NOT_FOUND", status_code=404)
            raise OllamaCallError(f"Ollama HTTP {e.code} hatası döndürdü.", error_type="HTTP_ERROR", status_code=e.code)
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)) or "timed out" in str(e.reason).lower():
                raise OllamaCallError(f"Ollama isteği zaman aşımına uğradı ({self.timeout}s).", error_type="TIMEOUT")
            raise OllamaCallError(f"Ollama sunucusuna bağlanılamadı ({self.ollama_host}).", error_type="CONNECTION_REFUSED")
        except (socket.timeout, TimeoutError):
            raise OllamaCallError(f"Ollama isteği zaman aşımına uğradı ({self.timeout}s).", error_type="TIMEOUT")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise OllamaCallError("Ollama yanıtı JSON değil.", error_type="INVALID_RESPONSE")
        if not isinstance(data, dict) or not isinstance(data.get("response"), str):
            raise OllamaCallError("Ollama yanıtında 'response' alanı yok.", error_type="INVALID_RESPONSE")
        return data["response"]
