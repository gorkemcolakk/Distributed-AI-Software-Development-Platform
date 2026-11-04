"""
Frontend Specialist Agent implementation.
Generates a self-contained HTML/CSS/JS page with local Ollama inference
(default: qwen2.5-coder:3b).

S3-03 (Kübra Hepcan):
- Sends a structured prompt to local Ollama and expects one ```html code block.
- Validates the reply before the task can succeed: empty, prose-only, malformed or
  truncated (no closing </html>) output makes the task FAILED, never "successful".
- When Ollama is unreachable, an optional, clearly labelled fallback template is returned
  (generation_mode="fallback"); with fallback disabled the task fails instead.
- Returns the generated file in ``files`` so the Master writes it under workspaces/{run_id}/.
- No hardcoded secrets or tokens.
"""

import html
import json
import os
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.agents.base_agent import BaseAgent, AgentCapabilityProfile
from src.master.workspace import normalize_relative_path


class ModelOutputError(ValueError):
    """The model answered, but the reply is not usable HTML (empty, prose-only, malformed, truncated)."""


class OllamaCallError(RuntimeError):
    """Ollama could not be reached or returned an HTTP/protocol error."""

    def __init__(self, message: str, error_type: str = "UNKNOWN", status_code: Optional[int] = None):
        super().__init__(message)
        self.error_type = error_type  # TIMEOUT, CONNECTION_REFUSED, NOT_FOUND, HTTP_ERROR, INVALID_RESPONSE
        self.status_code = status_code


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


_CODE_BLOCK = re.compile(r"```[ \t]*(?:html|htm)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_html_code(raw_response: str) -> str:
    """Takes the fenced html code block from the model reply, or the whole reply if nothing is fenced."""
    if not raw_response or not raw_response.strip():
        raise ModelOutputError("Model boş yanıt döndürdü.")
    blocks = [b.strip() for b in _CODE_BLOCK.findall(raw_response) if b.strip()]
    if blocks:
        return max(blocks, key=len)
    return raw_response.strip()


_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
                        "param", "source", "track", "wbr"})
# Tags that do not show anything to the user; they do not count as UI elements.
_NON_VISIBLE = frozenset({"html", "head", "title", "meta", "link", "style", "script", "body"})
_COMPONENT_TAGS = ("nav", "header", "main", "section", "form", "table", "button", "input",
                   "select", "textarea", "ul", "ol", "footer", "canvas", "svg")
MIN_UI_ELEMENTS = 3


class _HtmlInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.start_tags: Dict[str, int] = {}
        self.end_tags: Dict[str, int] = {}
        self.visible_elements = 0

    def handle_starttag(self, tag, attrs):
        self.start_tags[tag] = self.start_tags.get(tag, 0) + 1
        if tag not in _NON_VISIBLE:
            self.visible_elements += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.end_tags[tag] = self.end_tags.get(tag, 0) + 1

    def handle_endtag(self, tag):
        self.end_tags[tag] = self.end_tags.get(tag, 0) + 1


def validate_ui_code(code: str) -> Tuple[int, List[str]]:
    """
    Checks that the reply is a complete HTML document with real UI elements.
    Returns (visible_element_count, detected_components). Raises ModelOutputError otherwise.
    """
    if not code or not code.strip():
        raise ModelOutputError("Model çıktısı boş.")

    inspector = _HtmlInspector()
    try:
        inspector.feed(code)
        inspector.close()
    except Exception as exc:  # HTMLParser rarely raises, but never trust model output
        raise ModelOutputError(f"Model çıktısı HTML olarak okunamadı: {exc}") from exc

    starts, ends = inspector.start_tags, inspector.end_tags
    if "html" not in starts or "body" not in starts:
        raise ModelOutputError("Model çıktısı geçerli bir HTML sayfası değil (<html> / <body> yok).")
    if not ends.get("html") or not ends.get("body"):
        raise ModelOutputError("Model çıktısı yarım kalmış (</body> veya </html> yok).")
    for tag in ("script", "style"):
        if starts.get(tag, 0) > ends.get(tag, 0):
            raise ModelOutputError(f"Model çıktısında kapatılmamış <{tag}> bloğu var.")
    if inspector.visible_elements < MIN_UI_ELEMENTS:
        raise ModelOutputError(
            f"Model çıktısında yeterli arayüz öğesi yok ({inspector.visible_elements} < {MIN_UI_ELEMENTS}).")

    components = [tag for tag in _COMPONENT_TAGS if starts.get(tag)]
    return inspector.visible_elements, components


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_").lower()
    return slug or "generated"


class FrontendAgent(BaseAgent):
    """Specialized Agent for Frontend UI/UX development."""

    def __init__(self, agent_id: str = None, name: str = "Frontend Specialist Agent",
                 model_name: str = "qwen2.5-coder:3b", use_ollama: Optional[bool] = None,
                 ollama_host: Optional[str] = None, timeout: Optional[float] = None,
                 fallback_enabled: Optional[bool] = None,
                 llm_client: Optional[Callable[[str], str]] = None):
        profile = AgentCapabilityProfile(
            coding_score=98.0,
            reasoning_score=88.0,
            context_capacity=95.0,
            specialties=["frontend", "ui_ux", "react", "css_design_system"]
        )
        super().__init__(agent_id=agent_id, name=name, model_name=model_name, capability_profile=profile)
        self.use_ollama = _env_flag("FRONTEND_AGENT_USE_OLLAMA", True) if use_ollama is None else use_ollama
        self.ollama_host = (ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = float(timeout if timeout is not None else os.getenv("OLLAMA_TIMEOUT", "180"))
        self.fallback_enabled = _env_flag("FALLBACK_ENABLED", True) if fallback_enabled is None else fallback_enabled
        # Injectable for tests; defaults to a real HTTP call to Ollama
        self.llm_client = llm_client or self._call_ollama

    # ------------------------------------------------------------------ task processing
    def _process(self, task: Dict[str, Any], logs: List[str]) -> Dict[str, Any]:
        filename = self._target_filename(task)
        # Fail before spending model time if the payload asks for an unsafe path
        normalize_relative_path(filename)  # raises UnsafePathError -> task FAILED

        logs.append(f"[{self.name}] Analyzing UI/UX requirements for '{task.get('title', '')}'...")

        if not self.use_ollama:
            logs.append(f"[{self.name}] [TEMPLATE] FRONTEND_AGENT_USE_OLLAMA is false; returning labelled template page.")
            return self._template_result(task, filename, generation_mode="template")

        prompt = self.build_prompt(task)
        logs.append(f"[{self.name}] Sending UI prompt to local Ollama model '{self.model_name}' at {self.ollama_host}...")
        try:
            raw = self.llm_client(prompt)
        except OllamaCallError as exc:
            if not self.fallback_enabled:
                logs.append(f"[{self.name}] Ollama call failed and fallback is disabled: {exc}")
                raise
            logs.append(f"[{self.name}] [FALLBACK] Ollama unavailable ({exc.error_type}): {exc}. "
                        "Returning labelled fallback page, not model output.")
            return self._template_result(task, filename, generation_mode="fallback", fallback_reason=exc.error_type)

        code = extract_html_code(raw)
        element_count, components = validate_ui_code(code)
        logs.append(f"[{self.name}] Model output validated: {len(code.splitlines())} lines, "
                    f"{element_count} UI elements ({', '.join(components) or 'no component tags'}).")

        return {
            "files": [{"filename": filename, "content": code, "language": "html"}],
            "ui_files_generated": [filename],
            "ui_element_count": element_count,
            "components_detected": components,
            "model_used": self.model_name,
            "generation_mode": "ollama",
            "status": "FRONTEND_UI_GENERATED"
        }

    def build_prompt(self, task: Dict[str, Any]) -> str:
        context = task.get("context_artifacts") or {}
        context_text = json.dumps(context, ensure_ascii=False, indent=2)[:4000] if context else "(none)"
        return (
            "You are a senior frontend engineer. Build ONE complete, self-contained web page.\n"
            "Rules:\n"
            "- Reply with exactly one ```html code block and nothing else.\n"
            "- The page must be a full HTML document: <!DOCTYPE html>, <html>, <head>, <body>, closed with </html>.\n"
            "- Put all CSS in one <style> block and all JavaScript in one <script> block. No external files, "
            "no CDN links, no frameworks.\n"
            "- Use semantic elements (header, main, form, button, table or ul) and a responsive layout.\n"
            "- Do not invent backend URLs; keep any data in JavaScript variables.\n\n"
            f"Task title: {task.get('title', '')}\n"
            f"Task description: {task.get('description', '')}\n"
            f"Context from upstream agents:\n{context_text}\n"
        )

    def _target_filename(self, task: Dict[str, Any]) -> str:
        context = task.get("context_artifacts") or {}
        requested = task.get("output_filename") or context.get("output_filename")
        if requested:
            return str(requested)
        return f"ui_{_safe_slug(task.get('task_id', 'generated'))}.html"

    def _template_result(self, task: Dict[str, Any], filename: str, generation_mode: str,
                         fallback_reason: Optional[str] = None) -> Dict[str, Any]:
        title = html.escape(str(task.get("title") or "Generated UI"))
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            f"<title>{title}</title>\n"
            "<style>body{font-family:sans-serif;margin:2rem}main{max-width:40rem}</style>\n</head>\n<body>\n"
            f"<header><h1>{title}</h1></header>\n"
            "<main>\n<p>Placeholder page. This file was NOT written by the model.</p>\n</main>\n"
            "</body>\n</html>\n"
        )
        result = {
            "files": [{"filename": filename, "content": content, "language": "html"}],
            "ui_files_generated": [filename],
            "ui_element_count": 3,
            "components_detected": ["header", "main"],
            "model_used": None,
            "generation_mode": generation_mode,
            "status": "FRONTEND_UI_TEMPLATE" if generation_mode == "template" else "FRONTEND_UI_FALLBACK"
        }
        if fallback_reason:
            result["fallback_reason"] = fallback_reason
        return result

    # ------------------------------------------------------------------ Ollama client
    def _call_ollama(self, prompt: str) -> str:
        """POSTs the prompt to Ollama /api/generate and returns the 'response' text."""
        body = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "seed": 42, "num_predict": 2048}
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
