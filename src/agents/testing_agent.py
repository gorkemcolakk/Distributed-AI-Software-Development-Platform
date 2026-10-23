"""
Testing Specialist Agent implementation.
Generates unit tests with a local Ollama model (default: deepseek-coder:6.7b).

S3-06 (Berat İnan):
- The task description / context artifacts are sent to the local Ollama model.
- The model reply is parsed and validated (must be valid Python with at least one test_ function).
- Broken model output raises ModelOutputError -> BaseAgent marks the task FAILED.
- When Ollama is unreachable the agent returns a labelled template (FALLBACK_ENABLED=true).
- Output file names coming from the task payload are checked against path traversal (../).
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

        prompt = self.build_prompt(task)
        logs.append(f"[{self.name}] Sending test generation prompt to local Ollama model '{self.model_name}'...")
        try:
            raw = self.llm_client(prompt)
        except OllamaCallError as exc:
            if not self.fallback_enabled:
                raise
            logs.append(f"[{self.name}] Ollama unavailable ({exc.error_type}): {exc}. Using labelled fallback template.")
            return self._template_result(filename, generation_mode="fallback", fallback_reason=exc.error_type)

        code = extract_python_code(raw)
        test_count, assertion_count = validate_test_code(code)
        logs.append(f"[{self.name}] Model output validated: {test_count} test functions, {assertion_count} assertions.")

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
