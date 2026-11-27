"""
Testing Specialist Agent implementation.
Generates unit tests with a local Ollama model (default: deepseek-coder:6.7b).

S3-06 (Berat İnan):
- The task description / context artifacts are sent to the local Ollama model.
- The model reply is parsed and validated (must be valid Python with at least one test_ function).
- Broken model output raises ModelOutputError -> BaseAgent marks the task FAILED.
- When Ollama is unreachable the agent returns a labelled template (FALLBACK_ENABLED=true).
- Output file names coming from the task payload are checked against path traversal (../).

S5-06 (Berat İnan):
- When the task context has a shared_contract, the prompt lists its endpoints as the only ones
  the tests may call, and every client.get/post/... call in the reply is checked against it.
  A call outside the contract is a validation error: the model is asked once more with the
  rejected calls listed (TESTING_AGENT_VALIDATION_RETRIES, default 1), then the task FAILS.
- (27 Nov) The prompt shows a valid example body per POST/PUT endpoint (types from the generated
  backend's Pydantic models when its code is in the context) and says 422 is expected only for a body
  that leaves out a required field. Status-code assertions that contradict the body actually sent
  (422 for a complete body, 200 for a body missing a field) are rejected like off-contract calls.
"""

import ast
import json
import os
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Any, List, Optional, Callable, Tuple

from src.agents.base_agent import BaseAgent, AgentCapabilityProfile


class ModelOutputError(ValueError):
    """The model answered, but the answer is not a usable Python test file."""


class OllamaCallError(RuntimeError):
    """Ollama could not be reached or returned an HTTP / protocol error."""

    def __init__(self, message: str, error_type: str = "UNKNOWN", status_code: Optional[int] = None):
        super().__init__(message)
        self.error_type = error_type  # TIMEOUT, CONNECTION_REFUSED, NOT_FOUND, HTTP_ERROR, INVALID_RESPONSE
        self.status_code = status_code


class UnsafePathError(ValueError):
    """A requested output path would escape the agent's output directory."""


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def resolve_safe_output_path(base_dir: str, filename: str) -> Path:
    """
    Returns base_dir/filename as an absolute path, or raises UnsafePathError if the
    name is absolute, has a drive letter, contains '..', or resolves outside base_dir.
    Only .py files may be written.
    """
    if not filename or not isinstance(filename, str) or "\x00" in filename:
        raise UnsafePathError("Çıktı dosya adı boş veya geçersiz.")

    normalized = filename.strip().replace("\\", "/")
    if PureWindowsPath(filename).drive or PureWindowsPath(filename).anchor or normalized.startswith("/"):
        raise UnsafePathError(f"Mutlak yol kabul edilmez: '{filename}'")

    parts = PurePosixPath(normalized).parts
    if not parts or any(p in ("..", "") for p in parts):
        raise UnsafePathError(f"Yol geçişi (..) tespit edildi: '{filename}'")
    if not normalized.endswith(".py"):
        raise UnsafePathError(f"Yalnızca .py test dosyaları yazılabilir: '{filename}'")

    base = Path(base_dir).resolve()
    candidate = base.joinpath(*parts).resolve()
    if candidate != base and base not in candidate.parents:
        raise UnsafePathError(f"Çıktı dizini dışına yazma girişimi: '{filename}'")
    return candidate


_CODE_BLOCK = re.compile(r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_python_code(raw_response: str) -> str:
    """Takes the first fenced code block from the model reply, or the whole reply if there is none."""
    if not raw_response or not raw_response.strip():
        raise ModelOutputError("Model boş yanıt döndürdü.")
    blocks = [b.strip() for b in _CODE_BLOCK.findall(raw_response) if b.strip()]
    if blocks:
        return max(blocks, key=len)
    return raw_response.strip()


def validate_test_code(code: str) -> Tuple[int, int]:
    """
    Checks that the code parses and defines at least one test function.
    Returns (test_function_count, assertion_count).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ModelOutputError(f"Model çıktısı geçerli Python değil (satır {exc.lineno}: {exc.msg}).") from exc

    test_functions = 0
    assertions = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            test_functions += 1
        elif isinstance(node, ast.Assert):
            assertions += 1
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr.startswith("assert")):
            assertions += 1

    if test_functions == 0:
        raise ModelOutputError("Model çıktısında hiçbir test_ fonksiyonu bulunamadı.")
    return test_functions, assertions


HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
# The backend rule (analyzer.CATEGORY_RULES) always adds these even though the contract does not list them
ALWAYS_ALLOWED_ENDPOINTS = (("GET", "/health"), ("GET", "/"))


def contract_endpoints(context: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """(METHOD, path) pairs of the shared contract in the task context; empty when there is none."""
    contract = (context or {}).get("shared_contract") or {}
    endpoints = []
    for ep in contract.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        method = str(ep.get("method") or "").upper()
        path = str(ep.get("path") or "").strip()
        if method in HTTP_METHODS and path.startswith("/"):
            endpoints.append((method, path))
    return endpoints


def _is_param(segment: str) -> bool:
    return (segment.startswith("{") and segment.endswith("}")) or segment.startswith(":")


def _split_path(path: str) -> List[str]:
    return [s for s in path.split("?", 1)[0].split("#", 1)[0].split("/") if s != ""]


def path_matches(template: str, called: str) -> bool:
    """'/books/{book_id}' matches '/books/1' and '/books/{x}'; fixed segments must be equal."""
    t, c = _split_path(template), _split_path(called)
    if len(t) != len(c):
        return False
    return all(_is_param(ts) or ts == cs or _is_param(cs) for ts, cs in zip(t, c))


def _literal_path(node: ast.AST) -> Optional[str]:
    """The URL of a call argument: a plain string, or an f-string with each {expr} kept as '{}'."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return None


def find_endpoint_calls(code: str) -> List[Tuple[str, str]]:
    """(METHOD, path) of every client.get('/x') / client.request('POST', '/x') style call with a literal URL."""
    calls = []
    for node in ast.walk(ast.parse(code)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        attr = node.func.attr.lower()
        if attr.upper() in HTTP_METHODS and node.args:
            method, url_node = attr.upper(), node.args[0]
        elif attr == "request" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
            method, url_node = str(node.args[0].value).upper(), node.args[1]
        else:
            continue
        path = _literal_path(url_node)
        if path is None:
            continue
        if "://" in path:  # http://testserver/books -> /books
            path = "/" + path.split("://", 1)[1].partition("/")[2]
        if path.startswith("/"):
            calls.append((method, path))
    return calls


def find_off_contract_calls(code: str, endpoints: List[Tuple[str, str]]) -> List[str]:
    """Calls in the test code that the contract does not define ('POST /orders'), in order, without duplicates."""
    allowed = list(endpoints) + list(ALWAYS_ALLOWED_ENDPOINTS)
    off = []
    for method, path in find_endpoint_calls(code):
        if any(m == method and path_matches(p, path) for m, p in allowed):
            continue
        label = f"{method} {path}"
        if label not in off:
            off.append(label)
    return off


# --------------------------------------------------------------------------------------------------
# S5-06 (27 Nov finding): "invalid request" tests must expect what the contract really defines.
# FastAPI answers 422 only when the JSON body fails Pydantic validation (a required field is missing or
# a value has the wrong type). An empty string or a past date is still a valid str, so the backend
# answers 200 (test_invalid_events expected 422); a body without a required field is rejected with
# 422 (test_tickets expected 200). The agent now shows a valid example body per endpoint and checks
# every status-code assertion against the body that was actually sent.
# --------------------------------------------------------------------------------------------------
BODY_METHODS = ("POST", "PUT", "PATCH")
_MODEL_RE = re.compile(r"^class\s+(\w+)\s*\(\s*(?:pydantic\.)?BaseModel\s*\)\s*:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)", re.M)
_FIELD_RE = re.compile(r"^[ \t]+(\w+)\s*:\s*([^=\n#]+?)\s*(=[^\n#]*)?[ \t]*(?:#[^\n]*)?$", re.M)
_ROUTE_RE = re.compile(
    r"@\w+\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"'][^\n]*\n(?:[ \t]*@[^\n]*\n)*"
    r"[ \t]*(?:async[ \t]+)?def[ \t]+\w+[ \t]*\(([^)]*)\)", re.I)


def _type_kind(annotation: str) -> str:
    """'number', 'bool', 'str' or 'any' for a Pydantic field annotation."""
    a = annotation.replace(" ", "").lower()
    for wrapper in ("optional[", "typing.optional["):
        if a.startswith(wrapper):
            a = a[len(wrapper):-1]
    a = a.split("|")[0]
    if a in ("int", "float", "decimal", "conint", "confloat", "positiveint"):
        return "number"
    if a == "bool":
        return "bool"
    if a in ("str", "emailstr", "constr", "date", "datetime", "time"):
        return "str"
    return "any"


def parse_body_models(code: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    {(METHOD, path): {"fields": {name: kind}, "required": [names]}} for each route of the generated
    backend that takes a Pydantic body. Uses regexes, so it also works on a truncated code excerpt.
    """
    models: Dict[str, Dict[str, Any]] = {}
    for match in _MODEL_RE.finditer(code or ""):
        fields, required = {}, []
        for f in _FIELD_RE.finditer(match.group(2)):
            name, annotation, default = f.group(1), f.group(2), f.group(3)
            if name in ("model_config", "Config") or annotation.startswith(("ClassVar", "class")):
                continue
            fields[name] = _type_kind(annotation)
            optional = default is not None or "optional" in annotation.lower() or "none" in annotation.lower()
            if not optional:
                required.append(name)
        models[match.group(1)] = {"fields": fields, "required": required}

    routes: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for route in _ROUTE_RE.finditer(code or ""):
        method, path, params = route.group(1).upper(), route.group(2), route.group(3)
        for param in params.split(","):
            if ":" not in param:
                continue
            annotation = param.split(":", 1)[1].split("=")[0].strip()
            if annotation in models:
                routes[(method, path)] = models[annotation]
                break
    return routes


def endpoint_body_schemas(context: Optional[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Body schema of every POST/PUT/PATCH endpoint of the contract: field types and required fields from the
    generated backend when its code is in the context, otherwise the contract's request fields (all
    required, types unknown), as the backend rule asks for Pydantic models with exactly those fields.
    """
    context = context or {}
    code = "\n".join(str(v) for v in (context.get("code_under_test") or {}).values())
    from_code = parse_body_models(code)
    contract = context.get("shared_contract") or {}
    schemas: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for ep in contract.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        method, path = str(ep.get("method") or "").upper(), str(ep.get("path") or "")
        if method not in BODY_METHODS:
            continue
        found = next((s for (m, p), s in from_code.items() if m == method and path_matches(p, path)), None)
        if found is not None:
            schemas[(method, path)] = dict(found, source="code")
            continue
        names = [str(n) for n in ep.get("request") or [] if str(n) and str(n) != "id"]
        if names:
            schemas[(method, path)] = {"fields": {n: "any" for n in names}, "required": names, "source": "contract"}
    return schemas


def sample_value(name: str, kind: str) -> Any:
    """A value that passes validation for the field (used in the prompt's example bodies)."""
    lowered = name.lower()
    if kind == "number" or (kind == "any" and (lowered == "id" or lowered.endswith(("_id", "_count")) or lowered in (
            "price", "amount", "quantity", "year", "age", "capacity", "seats", "count", "total", "rating"))):
        return 1
    if kind == "bool" or (kind == "any" and lowered.startswith(("is_", "has_")) or lowered in ("done", "completed")):
        return True
    if "email" in lowered:
        return "user@example.com"
    if "date" in lowered:
        return "2026-12-01"
    if "password" in lowered:
        return "secret123"
    return f"test {lowered}"


def _value_fits(value: Any, kind: str) -> bool:
    if kind == "number":
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        return isinstance(value, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", value) is not None
    if kind == "bool":
        return isinstance(value, bool) or value in (0, 1, "true", "false", "True", "False", "yes", "no")
    if kind == "str":
        return isinstance(value, str)
    return value is not None


def _field_kind(name: str, schema: Dict[str, Any]) -> str:
    """The field's type; without backend code it is guessed from the name (event_id, capacity -> number)."""
    kind = schema["fields"].get(name, "any")
    if kind != "any":
        return kind
    sample = sample_value(name, "any")
    if isinstance(sample, bool):
        return "bool"
    return "number" if isinstance(sample, int) else "any"


_UNKNOWN = object()


def _call_info(call: ast.Call) -> Optional[Dict[str, Any]]:
    """Method, path and JSON body (when it is a dict literal) of a client.get/post/... call."""
    if not isinstance(call.func, ast.Attribute):
        return None
    attr = call.func.attr.lower()
    if attr.upper() in HTTP_METHODS and call.args:
        method, url_node = attr.upper(), call.args[0]
    elif attr == "request" and len(call.args) >= 2 and isinstance(call.args[0], ast.Constant):
        method, url_node = str(call.args[0].value).upper(), call.args[1]
    else:
        return None
    path = _literal_path(url_node)
    if path is None or not path.startswith("/"):
        return None
    body: Any = None
    for kw in call.keywords:
        if kw.arg == "json":
            if isinstance(kw.value, ast.Dict) and all(isinstance(k, ast.Constant) for k in kw.value.keys):
                body = {k.value: (v.value if isinstance(v, ast.Constant) else _UNKNOWN)
                        for k, v in zip(kw.value.keys, kw.value.values)}
            else:
                body = _UNKNOWN
    return {"method": method, "path": path, "body": body}


def _expected_codes(compare: ast.Compare) -> Optional[set]:
    """{422} for `x.status_code == 422`, {200, 201} for `x.status_code in (200, 201)`."""
    if len(compare.ops) != 1 or len(compare.comparators) != 1:
        return None
    op, right = compare.ops[0], compare.comparators[0]
    if isinstance(op, ast.Eq) and isinstance(right, ast.Constant) and isinstance(right.value, int):
        return {right.value}
    if isinstance(op, ast.In) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
        codes = {e.value for e in right.elts if isinstance(e, ast.Constant) and isinstance(e.value, int)}
        return codes if codes and len(codes) == len(right.elts) else None
    return None


def find_wrong_status_expectations(code: str, schemas: Dict[Tuple[str, str], Dict[str, Any]]) -> List[str]:
    """
    Status-code assertions that cannot hold for the body the test sends:
    - 4xx expected although every required field is sent with a valid type (the backend answers 200);
    - 2xx expected although a required field is missing or has the wrong type (FastAPI answers 422).
    Calls whose body is not a dict literal, or endpoints without a known schema, are not judged.
    """
    if not schemas:
        return []
    problems: List[str] = []
    tree = ast.parse(code)
    for func in ast.walk(tree):
        if not (isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) and func.name.startswith("test")):
            continue
        responses: Dict[str, Dict[str, Any]] = {}
        nodes = sorted((n for n in ast.walk(func) if hasattr(n, "lineno")),
                       key=lambda n: (n.lineno, n.col_offset))
        for node in nodes:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                info = _call_info(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if info:
                            responses[target.id] = info
                        else:
                            responses.pop(target.id, None)
            if not isinstance(node, ast.Compare):
                continue
            left = node.left
            if not (isinstance(left, ast.Attribute) and left.attr == "status_code"):
                continue
            if isinstance(left.value, ast.Name):
                info = responses.get(left.value.id)
            elif isinstance(left.value, ast.Call):
                info = _call_info(left.value)
            else:
                info = None
            codes = _expected_codes(node)
            if not info or not codes or info["method"] not in BODY_METHODS or info["body"] is _UNKNOWN:
                continue
            schema = next((s for (m, p), s in schemas.items()
                           if m == info["method"] and path_matches(p, info["path"])), None)
            if schema is None:
                continue
            body = info["body"] or {}
            missing = [f for f in schema["required"] if f not in body]
            wrong_type = [f for f, v in body.items()
                          if v is not _UNKNOWN and f in schema["fields"] and not _value_fits(v, _field_kind(f, schema))]
            label = f"{func.name}: {info['method']} {info['path']}"
            expected = "/".join(str(c) for c in sorted(codes))
            if all(400 <= c < 500 for c in codes) and not missing and not wrong_type:
                problems.append(f"{label} tüm zorunlu alanları geçerli tiple gönderiyor, uç nokta 200 döner "
                                f"ama test {expected} bekliyor (geçersiz istek için zorunlu bir alanı çıkar)")
            elif all(200 <= c < 300 for c in codes) and (missing or wrong_type):
                why = ", ".join([f"eksik alan '{f}'" for f in missing] + [f"'{f}' alanının tipi yanlış" for f in wrong_type])
                problems.append(f"{label} için {why}: FastAPI 422 döner ama test {expected} bekliyor")
    return problems


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_").lower()
    return slug or "generated"


class TestingAgent(BaseAgent):
    """Specialized Agent for Quality Assurance & Automated Testing."""

    __test__ = False  # not a test class, despite the name (keeps pytest collection quiet)

    def __init__(self, agent_id: str = None, name: str = "Automated Testing Agent", model_name: str = "deepseek-coder:6.7b",
                 use_ollama: Optional[bool] = None, ollama_host: Optional[str] = None, timeout: Optional[float] = None,
                 output_dir: Optional[str] = None, fallback_enabled: Optional[bool] = None,
                 llm_client: Optional[Callable[[str], str]] = None):
        profile = AgentCapabilityProfile(
            coding_score=85.0,
            reasoning_score=90.0,
            context_capacity=85.0,
            specialties=["testing", "pytest", "unit_testing", "integration_testing"]
        )
        super().__init__(agent_id=agent_id, name=name, model_name=model_name, capability_profile=profile)
        self.use_ollama = _env_flag("TESTING_AGENT_USE_OLLAMA", True) if use_ollama is None else use_ollama
        self.ollama_host = (ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = float(timeout if timeout is not None else os.getenv("OLLAMA_TIMEOUT", "180"))
        self.output_dir = output_dir if output_dir is not None else (os.getenv("TESTING_AGENT_OUTPUT_DIR") or None)
        self.fallback_enabled = _env_flag("FALLBACK_ENABLED", True) if fallback_enabled is None else fallback_enabled
        try:
            self.max_validation_retries = max(0, int(os.getenv("TESTING_AGENT_VALIDATION_RETRIES", "1")))
        except ValueError:
            self.max_validation_retries = 1
        # Injectable for tests; defaults to a real HTTP call to Ollama
        self.llm_client = llm_client or self._call_ollama

    def _process(self, task: Dict[str, Any], logs: List[str]) -> Dict[str, Any]:
        filename = self._target_filename(task)
        if self.output_dir:
            # Fail before spending model time if the payload asks for an unsafe path
            resolve_safe_output_path(self.output_dir, filename)

        if not self.use_ollama:
            logs.append(f"[{self.name}] Ollama disabled (TESTING_AGENT_USE_OLLAMA=false); returning template suite.")
            return self._template_result(filename, generation_mode="template")

        endpoints = contract_endpoints(task.get("context_artifacts"))
        schemas = endpoint_body_schemas(task.get("context_artifacts")) if endpoints else {}
        prompt = self.build_prompt(task)
        total_attempts = 1 + self.max_validation_retries
        logs.append(f"[{self.name}] Sending test generation prompt to local Ollama model '{self.model_name}'...")
        for attempt in range(1, total_attempts + 1):
            try:
                raw = self.llm_client(prompt)
            except OllamaCallError as exc:
                if not self.fallback_enabled:
                    raise
                logs.append(f"[{self.name}] Ollama unavailable ({exc.error_type}): {exc}. Using labelled fallback template.")
                return self._template_result(filename, generation_mode="fallback", fallback_reason=exc.error_type)

            code = None
            try:
                code = extract_python_code(raw)
                test_count, assertion_count = validate_test_code(code)
                if endpoints:
                    off_contract = find_off_contract_calls(code, endpoints)
                    if off_contract:
                        raise ModelOutputError(
                            "Testler sözleşmede olmayan uç noktaları çağırıyor: " + ", ".join(off_contract))
                    wrong_expectations = find_wrong_status_expectations(code, schemas)
                    if wrong_expectations:
                        raise ModelOutputError(
                            "Testlerin durum kodu beklentisi sözleşmeye uymuyor: " + "; ".join(wrong_expectations))
            except ModelOutputError as exc:
                if attempt < total_attempts:
                    logs.append(f"[{self.name}] Test doğrulama hatası (deneme {attempt}/{total_attempts}): {exc} "
                                f"Düzeltilmiş testler yeniden isteniyor...")
                    prompt = self.build_retry_prompt(task, code or raw or "", str(exc))
                    continue
                raise
            break
        logs.append(f"[{self.name}] Model output validated: {test_count} test functions, {assertion_count} assertions"
                    + (f", all endpoint calls inside the shared contract ({len(endpoints)} endpoints)." if endpoints else "."))

        written_path = None
        if self.output_dir:
            target = resolve_safe_output_path(self.output_dir, filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code + "\n", encoding="utf-8")
            written_path = str(target)
            logs.append(f"[{self.name}] Test file written to {written_path}")

        return {
            "files": [{"filename": filename, "content": code}],
            "test_files_generated": [filename],
            "test_function_count": test_count,
            "total_assertions": assertion_count,
            "model_used": self.model_name,
            "generation_mode": "ollama",
            "validation_retries": attempt - 1,
            "contract_checked": bool(endpoints),
            "endpoints_called": sorted({f"{m} {p}" for m, p in find_endpoint_calls(code)}),
            "written_path": written_path,
            "status": "TEST_SUITE_GENERATED"
        }

    def build_prompt(self, task: Dict[str, Any]) -> str:
        context = task.get("context_artifacts") or {}
        context_text = json.dumps(context, ensure_ascii=False, indent=2)[:6000] if context else "(yok)"
        return (
            "You are a senior QA engineer. Write a single self-contained Python pytest test file.\n"
            "Rules:\n"
            "- Reply with exactly one ```python code block and nothing else.\n"
            "- Define at least three test functions whose names start with test_.\n"
            "- Use plain assert statements; mock any network, database or file system access.\n"
            "- Cover the normal case, an invalid input case and an edge case.\n\n"
            f"Task title: {task.get('title', '')}\n"
            f"Task description: {task.get('description', '')}\n"
            f"Context artifacts from upstream agents:\n{context_text}\n"
            f"{self._contract_rules(task)}"
        )

    @staticmethod
    def _contract_rules(task: Dict[str, Any]) -> str:
        endpoints = contract_endpoints(task.get("context_artifacts"))
        if not endpoints:
            return ""
        schemas = endpoint_body_schemas(task.get("context_artifacts"))
        lines = []
        for m, p in endpoints:
            schema = schemas.get((m, p))
            if schema:
                example = {f: sample_value(f, schema["fields"].get(f, "any")) for f in schema["fields"]
                           if f in schema["required"] or f != "id"}
                lines.append(f"  - {m} {p}  valid body: json={json.dumps(example, ensure_ascii=False)}")
            else:
                lines.append(f"  - {m} {p}")
        rules = (
            "\nAPI CONTRACT — the tests may call ONLY these endpoints (plus GET /health), with exactly this\n"
            "method and path; replace {param} parts with an id created earlier in the same test:\n"
            + "\n".join(lines) + "\n"
            "Do not invent other paths, versions (/api/v1/...) or methods.\n"
        )
        if schemas:
            rules += (
                "STATUS CODES:\n"
                "- A valid request sends EVERY field of the valid body above with the same value types;\n"
                "  assert r.status_code in (200, 201).\n"
                "- The only invalid request the contract defines is a body that LEAVES OUT a required field\n"
                "  (or sends a text where a number is expected); FastAPI answers it with 422:\n"
                "  assert r.status_code == 422.\n"
                "- Never expect 400/422 for empty strings, negative numbers, past dates or unknown ids:\n"
                "  the contract does not forbid them, so the backend answers 200.\n"
            )
        return rules

    def build_retry_prompt(self, task: Dict[str, Any], previous_output: str, error: str) -> str:
        """Follow-up prompt asking the model to fix a rejected reply (e.g. calls outside the contract)."""
        snippet = (previous_output or "").strip()[:2500]
        return (
            f"{self.build_prompt(task)}\n"
            "IMPORTANT — your previous reply was REJECTED:\n"
            f"- Reason: {error}\n"
            "- Rewrite the complete test file inside exactly one ```python block, fixing this.\n"
            f"Previous rejected output:\n```python\n{snippet}\n```\n"
        )

    def _target_filename(self, task: Dict[str, Any]) -> str:
        context = task.get("context_artifacts") or {}
        requested = task.get("output_filename") or context.get("output_filename")
        if requested:
            return str(requested)
        return f"test_{_safe_slug(task.get('task_id', 'generated'))}.py"

    def _template_result(self, filename: str, generation_mode: str, fallback_reason: Optional[str] = None) -> Dict[str, Any]:
        result = {
            "test_files_generated": [filename],
            "total_assertions": 0,
            "model_used": None,
            "generation_mode": generation_mode,
            "status": "TEST_SUITE_TEMPLATE" if generation_mode == "template" else "TEST_SUITE_FALLBACK"
        }
        if fallback_reason:
            result["fallback_reason"] = fallback_reason
        return result

    def _call_ollama(self, prompt: str) -> str:
        """POSTs the prompt to Ollama /api/generate and returns the 'response' text."""
        body = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "seed": 42, "num_predict": 1024}
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
