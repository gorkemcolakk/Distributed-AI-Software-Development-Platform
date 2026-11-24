"""
Requirements Analyzer & Task Decomposition Engine.

S4-07 (Eren Görkem Çolak): the Master model (qwen2.5:7b on local Ollama) reads the
requirement and returns
  - the tasks for this requirement (category, title, description, dependencies), and
  - a shared contract (entities with table / field names, API endpoints) that every
    worker agent receives, so the generated files use the same names and fit together.

The model output is normalised and checked before use (known categories only, at most
MAX_LLM_TASKS tasks, unique ids, no cycles; an INTEGRATION task is always added last).
If the model is switched off, unreachable or returns something unusable, the fixed
6-task template below is used and the result says so (decomposition_mode="template"
plus fallback_reason) - the run never silently pretends the model planned it.

The model is only asked when use_llm is True (the Streamlit UI turns it on, or
MASTER_ANALYZER_USE_OLLAMA=true). The default stays the template, so unit tests and
scripts never call Ollama by accident.
"""

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.agents.base_agent import TaskCategory

MAX_LLM_TASKS = 10  # raw model tasks accepted (same-category tasks are merged afterwards)
# One task per worker role: every agent writes one file, all from the same contract.
# A model that splits e.g. the backend into 3 tasks would otherwise get 3 separate FastAPI apps (seen with
# qwen2.5:7b on 19.11.2026), and a missing role (no FRONTEND task) would leave that agent idle.
CORE_CATEGORIES = ("DATABASE", "BACKEND", "FRONTEND", "TESTING")
# REQUIREMENTS tasks from the model are dropped: the Master already did that work by writing the shared
# contract, and a separate "architecture skeleton" task produced a second FastAPI app on the backend agent.
CATEGORY_ORDER = CORE_CATEGORIES
DEFAULT_TASKS = {
    "DATABASE": ("Database schema", "Create the tables of the shared contract."),
    "BACKEND": ("Backend API", "Implement every endpoint of the shared contract."),
    "FRONTEND": ("User interface", "Build the page that uses every endpoint of the shared contract."),
    "TESTING": ("API tests", "Test the main endpoints of the shared contract."),
}
DEFAULT_MODEL = "qwen2.5:7b"

CATEGORY_ALIASES = {
    "REQUIREMENTS": "REQUIREMENTS", "ARCHITECTURE": "REQUIREMENTS", "DESIGN": "REQUIREMENTS",
    "DATABASE": "DATABASE", "DB": "DATABASE", "SQL": "DATABASE", "SCHEMA": "DATABASE",
    "BACKEND": "BACKEND", "API": "BACKEND", "SERVER": "BACKEND",
    "FRONTEND": "FRONTEND", "UI": "FRONTEND", "WEB": "FRONTEND", "CLIENT": "FRONTEND",
    "TESTING": "TESTING", "TEST": "TESTING", "TESTS": "TESTING", "QA": "TESTING",
}
SPECIALTY = {
    "REQUIREMENTS": "architecture", "DATABASE": "database", "BACKEND": "backend",
    "FRONTEND": "frontend", "TESTING": "testing", "INTEGRATION": "integration",
}
ID_PREFIX = {"REQUIREMENTS": "req", "DATABASE": "db", "BACKEND": "be", "FRONTEND": "fe",
             "TESTING": "qa", "INTEGRATION": "int"}
# Short rules appended to every description: the worker models are small (3B-7B) and
# these limits keep them inside their timeout and away from SQL they get wrong (#41).
CATEGORY_RULES = {
    "REQUIREMENTS": "Keep it a concise FastAPI skeleton (under 45 lines) that follows the shared contract.",
    "DATABASE": ("Use SQLite 3 with only CREATE TABLE IF NOT EXISTS and CREATE INDEX statements; "
                 "no CHECK constraints, triggers or subqueries. Use the table and column names of the shared contract."),
    "BACKEND": ("Write a concise FastAPI service (under 60 lines) with /health and every endpoint of the shared contract "
                "(same method, path and request fields), using Pydantic models with the contract's field names; "
                "give each model an optional id field instead of adding attributes later."),
    "FRONTEND": ("Write one concise HTML5 page that calls the shared contract's endpoints and uses its field names "
                 "in forms and lists."),
    "TESTING": ("Write 3 concise pytest tests (under 40 lines) for the backend endpoints of the shared contract, "
                "using fastapi.testclient.TestClient. Call only endpoints listed in the contract, with its request "
                "fields, and create test data through those endpoints."),
}

PROMPT = """You are the Master Agent of a multi-agent software team. Plan the work for the requirement below.

Return ONLY a JSON object with this shape:
{{
  "contract": {{
    "entities": [{{"name": "Book", "table": "books", "fields": [{{"name": "id", "type": "integer"}}, {{"name": "title", "type": "text"}}]}}],
    "endpoints": [{{"method": "POST", "path": "/books", "description": "add a book", "request": ["title"], "response": "Book"}},
                  {{"method": "GET", "path": "/books", "description": "list or search books", "request": ["title"], "response": "list of Book"}}]
  }},
  "tasks": [
    {{"id": "t1", "category": "DATABASE", "title": "short title", "description": "what to build for THIS requirement", "depends_on": []}}
  ]
}}

Rules:
- category is one of: DATABASE, BACKEND, FRONTEND, TESTING.
- Exactly one task per category: one DATABASE, one BACKEND, one FRONTEND, one TESTING.
  Each task covers ALL features of the requirement for its layer.
- depends_on lists ids of tasks that must finish first. FRONTEND only needs the contract, not the backend code.
  TESTING depends on BACKEND.
- The contract is shared by every agent: 1 to 4 entities, snake_case table and field names, 3 to 8 endpoints
  that cover every feature in the requirement. Every entity users create or change has a POST (or PUT) endpoint,
  every list or search has a GET endpoint. "request" lists the body or query field names, "response" names what comes back.
- Descriptions name the concrete entities, fields and endpoints. No code in the JSON.

Project: {title}
Requirement:
{requirement}
"""


class DecompositionError(Exception):
    """The model answer could not be turned into a usable plan (reason in .reason)."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _short(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _snake(text: Any) -> str:
    return re.sub(r"[^a-z0-9_]", "", re.sub(r"[\s\-]+", "_", str(text or "").strip().lower()))[:40]


class RequirementsAnalyzer:
    """Decomposes high-level requirements into execution tasks for worker agents."""

    def __init__(self, use_llm: Optional[bool] = None, model: Optional[str] = None,
                 host: Optional[str] = None, timeout: Optional[float] = None,
                 llm_client: Optional[Callable[[str], str]] = None):
        self.use_llm = _env_flag("MASTER_ANALYZER_USE_OLLAMA", False) if use_llm is None else bool(use_llm)
        self.model = model or os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL
        self.host = (host or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self.timeout = float(timeout or os.getenv("MASTER_ANALYZER_TIMEOUT") or 180)
        self._llm_client = llm_client

    # ------------------------------------------------------------------ public
    def decompose(self, requirement_text: str, project_title: str = "Generated Software System") -> Dict[str, Any]:
        """
        Returns {requirement_id, project_title, raw_requirement, total_tasks, tasks,
        decomposition_mode ("llm" | "template"), decomposition_label, fallback_reason, shared_contract}.
        """
        req_id = f"req-{uuid.uuid4().hex[:6]}"
        tasks, contract, reason = None, None, "DISABLED"
        if self.use_llm:
            try:
                tasks, contract = self._plan_with_model(requirement_text, project_title)
                reason = None
            except DecompositionError as exc:
                reason = exc.reason
        if tasks is None:
            tasks = self._template_tasks(project_title)
            mode, label = "template", f"Sabit şablon ({reason})"
        else:
            mode, label = "llm", f"Yerel Ollama ({self.model})"
        return {
            "requirement_id": req_id,
            "project_title": project_title,
            "raw_requirement": requirement_text,
            "total_tasks": len(tasks),
            "tasks": tasks,
            "decomposition_mode": mode,
            "decomposition_label": label,
            "fallback_reason": reason,
            "shared_contract": contract,
        }

    # ------------------------------------------------------------------ model
    def _plan_with_model(self, requirement_text: str, project_title: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        prompt = PROMPT.format(max_tasks=MAX_LLM_TASKS, title=_short(project_title, 120),
                               requirement=str(requirement_text or "")[:4000])
        raw = self._llm_client(prompt) if self._llm_client else self._call_ollama(prompt)
        data = self._parse_json(raw)
        tasks = self.normalize_tasks(data.get("tasks"))
        contract = self.normalize_contract(data.get("contract"))
        return tasks, contract

    def _call_ollama(self, prompt: str) -> str:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "format": "json",
                           "options": {"temperature": 0.1, "seed": 42}}).encode("utf-8")
        req = urllib.request.Request(f"{self.host}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8")).get("response", "")
        except urllib.error.HTTPError as exc:
            raise DecompositionError(f"HTTP_{exc.code}") from exc
        except (TimeoutError, OSError) as exc:  # URLError is an OSError
            text = str(getattr(exc, "reason", exc)).lower()
            raise DecompositionError("TIMEOUT" if "timed out" in text or isinstance(exc, TimeoutError)
                                     else "CONNECTION_REFUSED", str(exc)) from exc
        except ValueError as exc:
            raise DecompositionError("INVALID_RESPONSE", str(exc)) from exc

    @staticmethod
    def _parse_json(raw: Any) -> Dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            raise DecompositionError("EMPTY_RESPONSE")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        try:
            data = json.loads(match.group(0) if match else text)
        except ValueError as exc:
            raise DecompositionError("INVALID_JSON", str(exc)) from exc
        if not isinstance(data, dict):
            raise DecompositionError("INVALID_JSON", "top level is not an object")
        return data

    # ------------------------------------------------------------------ normalisation
    @staticmethod
    def normalize_tasks(raw_tasks: Any) -> List[Dict[str, Any]]:
        """Model tasks -> engine tasks with our ids, specialties, rules and a final INTEGRATION task."""
        if not isinstance(raw_tasks, list):
            raise DecompositionError("INVALID_TASKS", "tasks is not a list")
        picked = []
        for item in raw_tasks:
            if not isinstance(item, dict):
                continue
            category = CATEGORY_ALIASES.get(str(item.get("category", "")).strip().upper())
            if category is None or category not in CORE_CATEGORIES:
                continue  # INTEGRATION is added by the analyzer; REQUIREMENTS = the contract itself
            picked.append((item, category))
        if len(picked) < 2:
            raise DecompositionError("INVALID_TASKS", f"only {len(picked)} usable tasks")
        if len(picked) > MAX_LLM_TASKS:
            raise DecompositionError("INVALID_TASKS", f"{len(picked)} tasks (max {MAX_LLM_TASKS})")

        # Merge same-category tasks into one (keeps every model id pointing at the merged task)
        groups: Dict[str, Dict[str, Any]] = {}
        id_map: Dict[str, str] = {}
        for item, category in picked:
            group = groups.setdefault(category, {"titles": [], "descriptions": [], "raw_deps": []})
            title = _short(item.get("title"), 80)
            description = _short(item.get("description"), 400)
            if title and title not in group["titles"]:
                group["titles"].append(title)
            if description and description not in group["descriptions"]:
                group["descriptions"].append(description)
            deps = item.get("depends_on", item.get("dependencies", item.get("dependson", [])))
            group["raw_deps"].extend(deps if isinstance(deps, list) else [deps] if deps else [])
            new_id = f"task-{ID_PREFIX[category]}-1"
            id_map[str(item.get("id") or item.get("task_id") or new_id)] = new_id

        # Every worker role gets a task, even if the model forgot one
        for category in CORE_CATEGORIES:
            if category not in groups:
                title, description = DEFAULT_TASKS[category]
                groups[category] = {"titles": [title], "descriptions": [description], "raw_deps": []}

        tasks = []
        for category in CATEGORY_ORDER:
            if category not in groups:
                continue
            group = groups[category]
            task_id = f"task-{ID_PREFIX[category]}-1"
            title = " + ".join(group["titles"])[:120] or DEFAULT_TASKS.get(category, (f"{category.title()} task",))[0]
            description = " ".join(d if d.endswith(".") else d + "." for d in group["descriptions"])[:900]
            deps = []
            for dep in group["raw_deps"]:
                mapped = id_map.get(str(dep))
                if mapped and mapped != task_id and mapped not in deps:
                    deps.append(mapped)
            tasks.append({
                "task_id": task_id,
                "title": title if len(title) >= 2 else f"{category.title()} task",
                "category": category,
                "description": f"{description} {CATEGORY_RULES[category]}",
                "dependencies": deps,
                "required_specialty": SPECIALTY[category],
            })

        # TESTING needs the backend code it tests (code_under_test only comes from finished tasks)
        backend_ids = [t["task_id"] for t in tasks if t["category"] == "BACKEND"]
        for task in tasks:
            if task["category"] == "TESTING":
                for be in backend_ids:
                    if be not in task["dependencies"]:
                        task["dependencies"].append(be)

        from src.master.scheduler import TaskScheduler  # local import: scheduler imports nothing from here
        if TaskScheduler().find_cycles(tasks):
            raise DecompositionError("CYCLE", "the model's dependencies contain a cycle")

        tasks.append({
            "task_id": "task-int-1",
            "title": "Code Review, Integration & Deployment Package",
            "category": TaskCategory.INTEGRATION.value,
            "description": ("Review all generated files against the shared contract, report syntax errors and "
                            "conflicts, assemble the final package."),
            "dependencies": [t["task_id"] for t in tasks],
            "required_specialty": "integration",
        })
        return tasks

    @staticmethod
    def normalize_contract(raw: Any) -> Optional[Dict[str, Any]]:
        """Small, predictable contract: up to 4 entities (10 fields each) and 10 endpoints."""
        if not isinstance(raw, dict):
            return None
        entities = []
        for ent in raw.get("entities") or []:
            if not isinstance(ent, dict):
                continue
            name = _short(ent.get("name"), 40)
            table = _snake(ent.get("table") or name)
            fields = []
            for f in ent.get("fields") or []:
                if isinstance(f, dict) and _snake(f.get("name")):
                    fields.append({"name": _snake(f.get("name")), "type": _short(f.get("type") or "text", 20).lower()})
                elif isinstance(f, str) and _snake(f):
                    fields.append({"name": _snake(f), "type": "text"})
            if name and table and fields:
                entities.append({"name": name, "table": table, "fields": fields[:10]})
        endpoints = []
        for ep in raw.get("endpoints") or []:
            if not isinstance(ep, dict):
                continue
            method = str(ep.get("method") or "GET").strip().upper()
            path = str(ep.get("path") or "").strip()
            if method in ("GET", "POST", "PUT", "PATCH", "DELETE") and path.startswith("/"):
                entry = {"method": method, "path": path[:80], "description": _short(ep.get("description"), 120)}
                request = [_snake(f) for f in (ep.get("request") or []) if isinstance(f, str) and _snake(f)]
                if request:  # S5: request/response shape so tests call what the backend really serves
                    entry["request"] = request[:10]
                if ep.get("response"):
                    entry["response"] = _short(ep.get("response"), 60)
                endpoints.append(entry)
        if not entities and not endpoints:
            return None
        return {"entities": entities[:4], "endpoints": endpoints[:10]}

    # ------------------------------------------------------------------ template
    @staticmethod
    def _template_tasks(project_title: str) -> List[Dict[str, Any]]:
        """Fixed 6-task chain used when the model is off or its answer is unusable."""
        return [
            {
                "task_id": "task-req-1",
                "title": "System Specification & Architecture Design",
                "category": TaskCategory.REQUIREMENTS.value,
                "description": (
                    f"Analyze requirement spec for '{project_title}' and generate a concise "
                    "FastAPI architecture skeleton with /health and 2 core resource endpoints (under 45 lines)."
                ),
                "dependencies": [],
                "required_specialty": "architecture"
            },
            {
                "task_id": "task-db-1",
                "title": "Database Schema & Migration Definition",
                "category": TaskCategory.DATABASE.value,
                "description": (
                    "Design simple SQLite 3 tables, relationships, and indexes based on architecture spec. "
                    "IMPORTANT: Do NOT use CHECK constraints, triggers, or subqueries; "
                    "use only simple CREATE TABLE IF NOT EXISTS and CREATE INDEX statements."
                ),
                "dependencies": ["task-req-1"],
                "required_specialty": "database"
            },
            {
                "task_id": "task-be-1",
                "title": "Core Backend API Implementation",
                "category": TaskCategory.BACKEND.value,
                "description": (
                    "Implement a concise FastAPI service (under 50 lines) with /health, "
                    "GET and POST endpoints using Pydantic BaseModel and in-memory dict storage."
                ),
                "dependencies": ["task-db-1"],
                "required_specialty": "backend"
            },
            {
                "task_id": "task-fe-1",
                "title": "Frontend User Interface & Components",
                "category": TaskCategory.FRONTEND.value,
                "description": (
                    "Develop a concise responsive HTML5 UI page with header, main, form, input, button, and ul."
                ),
                "dependencies": ["task-be-1"],
                "required_specialty": "frontend"
            },
            {
                "task_id": "task-qa-1",
                "title": "Automated Testing & Quality Assurance",
                "category": TaskCategory.TESTING.value,
                "description": (
                    "Write 3 concise, self-contained pytest unit test functions (test_normal, test_invalid, "
                    "test_edge, under 35 lines total) using simple assert statements."
                ),
                "dependencies": ["task-fe-1"],
                "required_specialty": "testing"
            },
            {
                "task_id": "task-int-1",
                "title": "Code Review, Integration & Deployment Package",
                "category": TaskCategory.INTEGRATION.value,
                "description": "Review code quality, resolve integration conflicts, assemble final build package and documentation.",
                "dependencies": ["task-qa-1"],
                "required_specialty": "integration"
            }
        ]
