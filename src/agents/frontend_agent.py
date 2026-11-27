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

from src.agents.api_contract import contract_endpoints, off_contract, path_matches
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


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, "").strip() or default))
    except ValueError:
        return default


# S5-03 (Nov 26 test): 2048 output tokens cut the page before </body></html>.
DEFAULT_NUM_PREDICT = 4096
# The prompt (~1.5k tokens with the contract) plus 4096 output tokens must fit in the context window;
# Ollama's default window is smaller, which would cut the page again.
DEFAULT_NUM_CTX = 8192

# S5-03: the small model (qwen2.5-coder:3b) does not get the design right every time, so the agent
# owns the stylesheet. The model only writes the HTML skeleton and JS using these classes;
# the agent puts this block into <head> after validation.
BASE_CSS_ID = "app-base-css"
BASE_CSS = """:root{--bg:#f6f7fb;--surface:#fff;--text:#1f2937;--muted:#6b7280;--primary:#2563eb;--primary-dark:#1d4ed8;
--accent:#f59e0b;--danger:#dc2626;--success:#16a34a;--border:#e5e7eb;--radius:12px;--shadow:0 2px 8px rgba(0,0,0,.06)}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.5}
.app-header{background:var(--primary);color:#fff;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.app-header h1{margin:0;font-size:1.5rem}
.app-header nav{display:flex;gap:8px;flex-wrap:wrap}
.app-header nav a,.app-header nav button{color:#fff;background:rgba(255,255,255,.15);border:0;border-radius:8px;padding:6px 12px;text-decoration:none;font:inherit;cursor:pointer}
.container{max-width:1100px;margin:0 auto;padding:24px 16px}
.section{margin-bottom:32px}
.section h2{margin:0 0 12px;font-size:1.25rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px;display:flex;flex-direction:column;gap:8px}
.card h3{margin:0;font-size:1.05rem}
.price{font-weight:700;color:var(--primary)}
.muted{color:var(--muted);font-size:.9rem}
button{border:0;border-radius:8px;padding:10px 16px;font:inherit;font-weight:600;cursor:pointer;background:var(--border);color:var(--text)}
.form button[type=submit]{background:var(--primary);color:#fff}
.btn{display:inline-block;border:0;border-radius:8px;padding:10px 16px;font:inherit;font-weight:600;cursor:pointer;background:var(--border);color:var(--text)}
.btn:disabled{opacity:.6;cursor:not-allowed}
.btn-primary{background:var(--primary);color:#fff}
.btn-primary:hover{background:var(--primary-dark)}
.btn-danger{background:var(--danger);color:#fff}
.form{display:flex;flex-direction:column;gap:10px;max-width:420px}
.form label{font-weight:600;font-size:.9rem}
.form input,.form select,.form textarea{padding:10px 12px;border:1px solid var(--border);border-radius:8px;font:inherit;background:#fff}
.tabs{display:flex;gap:8px;margin-bottom:12px;border-bottom:1px solid var(--border)}
.tab{background:none;border:0;border-bottom:3px solid transparent;padding:8px 12px;font:inherit;cursor:pointer;color:var(--muted)}
.tab.active{border-color:var(--primary);color:var(--text);font-weight:600}
.hidden{display:none!important}
.alert{padding:10px 14px;border-radius:8px;margin:8px 0;background:#eff6ff;color:#1e40af}
.alert-success{background:#f0fdf4;color:#166534}
.alert-error{background:#fef2f2;color:#991b1b}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.8rem;background:var(--border)}
.list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px}
.list li{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.total{font-weight:700;text-align:right}
table{width:100%;border-collapse:collapse;background:var(--surface)}
th,td{padding:8px 12px;border-bottom:1px solid var(--border);text-align:left}
@media (max-width:600px){.app-header{padding:12px 16px}.container{padding:16px}.form{max-width:none}}"""

# Shown to the model so it uses the stylesheet instead of writing its own
CSS_CLASS_GUIDE = (
    "header.app-header (top bar: <h1> app name + <nav>), main.container (page body), section.section (+ <h2>), "
    "div.grid (responsive card grid), div.card (one item; h3, p.muted, span.price, buttons), "
    "button.btn / .btn-primary / .btn-danger, form.form (label + input stacked), div.tabs + button.tab "
    "(.active marks the open tab), .hidden (hide an element), div.alert / .alert-success / .alert-error "
    "(messages), span.badge (status), ul.list (rows: order items, cart lines), div.total (cart sum), table"
)

_HEAD_OPEN = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
_HEAD_CLOSE = re.compile(r"</head\s*>", re.IGNORECASE)
_HTML_OPEN = re.compile(r"<html\b[^>]*>", re.IGNORECASE)


def apply_base_css(code: str) -> str:
    """
    Puts the agent's stylesheet at the end of <head>: after <meta charset> (which must stay in the first
    1024 bytes) and before <body>. The model is told not to write its own <style>.
    """
    if f'id="{BASE_CSS_ID}"' in code:
        return code
    block = f'<style id="{BASE_CSS_ID}">\n{BASE_CSS}\n</style>\n'
    match = _HEAD_CLOSE.search(code)
    if match:
        return f"{code[:match.start()]}{block}{code[match.start():]}"
    match = _HEAD_OPEN.search(code)
    if match:
        return f"{code[:match.end()]}\n{block}{code[match.end():]}"
    match = _HTML_OPEN.search(code)
    if match:  # validate_ui_code does not require <head>
        return f"{code[:match.end()]}\n<head>\n{block}\n</head>{code[match.end():]}"
    return code


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


# Tags whose end tag HTML lets the author leave out; a missing </li> or </p> is not a mistake.
_OPTIONAL_END = frozenset({"li", "p", "td", "th", "tr", "thead", "tbody", "tfoot", "option", "optgroup",
                           "dt", "dd", "colgroup", "rt", "rp", "caption"})
# Text of these elements is what the user reads (used for the English label warning)
_LABEL_TAGS = frozenset({"button", "label", "h1", "h2", "h3", "a", "th", "legend", "option"})
MAX_REPORTED_TAG_ISSUES = 5


class _HtmlInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.start_tags: Dict[str, int] = {}
        self.end_tags: Dict[str, int] = {}
        self.visible_elements = 0
        self.stack: List[Tuple[str, int]] = []   # (tag, line) of elements still open
        self.tag_issues: List[str] = []           # S5-03: unclosed / stray tags
        self.title_text = ""
        self.h1_text = ""
        self.label_texts: List[str] = []
        self.placeholders: List[str] = []
        self.scripts: List[str] = []
        self._text_target: Optional[str] = None
        self._text_buf: List[str] = []

    def _count_start(self, tag, attrs):
        self.start_tags[tag] = self.start_tags.get(tag, 0) + 1
        if tag not in _NON_VISIBLE:
            self.visible_elements += 1
        for name, value in attrs:
            if name == "placeholder" and value:
                self.placeholders.append(value.strip())

    def handle_starttag(self, tag, attrs):
        self._count_start(tag, attrs)
        if tag in _VOID_TAGS:
            return
        self.stack.append((tag, self.getpos()[0]))
        if self._text_target is None and (tag in ("title", "h1", "script") or tag in _LABEL_TAGS):
            self._text_target, self._text_buf = tag, []

    def handle_startendtag(self, tag, attrs):
        # <div/> counts as opened and closed; it never stays on the stack
        self._count_start(tag, attrs)
        if tag not in _VOID_TAGS:
            self.end_tags[tag] = self.end_tags.get(tag, 0) + 1

    def handle_data(self, data):
        if self._text_target is not None:
            self._text_buf.append(data)

    def handle_endtag(self, tag):
        self.end_tags[tag] = self.end_tags.get(tag, 0) + 1
        if tag in _VOID_TAGS:
            return
        if self._text_target == tag:
            self._store_text(tag, "".join(self._text_buf))
            self._text_target = None
        if not any(open_tag == tag for open_tag, _ in self.stack):
            self.tag_issues.append(f"</{tag}> açılmadan kapatılmış (satır {self.getpos()[0]})")
            return
        while self.stack:
            open_tag, line = self.stack.pop()
            if open_tag == tag:
                break
            if open_tag not in _OPTIONAL_END:
                self.tag_issues.append(f"<{open_tag}> (satır {line}) kapatılmamış")

    def _store_text(self, tag, text):
        if tag == "script":
            self.scripts.append(text)
            return
        text = " ".join(text.split())
        if tag == "title" and not self.title_text:
            self.title_text = text
        elif tag == "h1" and not self.h1_text:
            self.h1_text = text
        if tag in _LABEL_TAGS and text:
            self.label_texts.append(text)

    def finish(self):
        for open_tag, line in self.stack:
            if open_tag not in _OPTIONAL_END:
                self.tag_issues.append(f"<{open_tag}> (satır {line}) kapatılmamış")
        self.stack = []


def inspect_html(code: str) -> _HtmlInspector:
    inspector = _HtmlInspector()
    try:
        inspector.feed(code)
        inspector.close()
    except Exception as exc:  # HTMLParser rarely raises, but never trust model output
        raise ModelOutputError(f"Model çıktısı HTML olarak okunamadı: {exc}") from exc
    inspector.finish()
    return inspector


def validate_ui_code(code: str) -> Tuple[int, List[str]]:
    """
    Checks that the reply is a complete HTML document with real UI elements and balanced tags.
    Returns (visible_element_count, detected_components). Raises ModelOutputError otherwise.
    """
    if not code or not code.strip():
        raise ModelOutputError("Model çıktısı boş.")

    inspector = inspect_html(code)
    starts, ends = inspector.start_tags, inspector.end_tags
    if "html" not in starts or "body" not in starts:
        raise ModelOutputError("Model çıktısı geçerli bir HTML sayfası değil (<html> / <body> yok).")
    if not ends.get("html") or not ends.get("body"):
        raise ModelOutputError("Model çıktısı yarım kalmış (</body> veya </html> yok).")
    for tag in ("script", "style"):
        if starts.get(tag, 0) > ends.get(tag, 0):
            raise ModelOutputError(f"Model çıktısında kapatılmamış <{tag}> bloğu var.")
    if inspector.tag_issues:
        shown = inspector.tag_issues[:MAX_REPORTED_TAG_ISSUES]
        more = len(inspector.tag_issues) - len(shown)
        raise ModelOutputError("Model çıktısında uyumsuz etiketler var: " + "; ".join(shown)
                               + (f" (+{more} daha)" if more > 0 else ""))
    if inspector.visible_elements < MIN_UI_ELEMENTS:
        raise ModelOutputError(
            f"Model çıktısında yeterli arayüz öğesi yok ({inspector.visible_elements} < {MIN_UI_ELEMENTS}).")

    components = [tag for tag in _COMPONENT_TAGS if starts.get(tag)]
    return inspector.visible_elements, components


# ---------------------------------------------------------------- S5-03: app name and Turkish labels
GENERIC_TITLES = frozenset({
    "", "frontend", "frontend interface", "frontend ui", "frontend ui/ux", "frontend page", "ui", "user interface",
    "web app", "web application", "web page", "app", "application", "my app", "document", "untitled", "home",
    "generated ui", "index", "kullanıcı arayüzü", "arayüz", "uygulama", "ana sayfa",
})


def check_app_title(code: str, task: Dict[str, Any]) -> str:
    """<title> (and <h1>, if any) must name the application, not 'Frontend Interface' or the task. Returns it."""
    inspector = inspect_html(code)
    task_title = " ".join(str(task.get("title") or "").split()).lower()
    for label, text in (("<title>", inspector.title_text), ("<h1>", inspector.h1_text)):
        norm = text.lower().strip(" -|:")
        if label == "<h1>" and not norm:
            continue  # a page without <h1> is allowed; the title still names the app
        if norm in GENERIC_TITLES or (task_title and norm == task_title) or "frontend" in norm:
            raise ModelOutputError(f"Sayfa başlığı uygulamanın adı değil ({label}: '{text or '(boş)'}'). "
                                   "Gereksinimden kısa bir Türkçe uygulama adı kullanılmalı.")
    return inspector.title_text


ENGLISH_LABELS = frozenset({
    "login", "log in", "sign in", "register", "sign up", "logout", "log out", "submit", "add", "add to cart",
    "cart", "shopping cart", "my orders", "orders", "order", "place order", "checkout", "products", "menu",
    "password", "email", "username", "name", "price", "quantity", "total", "delete", "remove", "save", "cancel",
    "edit", "update", "search", "welcome", "home", "create", "send", "back", "next", "items", "description",
})


def find_english_labels(code: str) -> List[str]:
    """Visible button/label/heading texts and placeholders that are plain English words (warning only)."""
    inspector = inspect_html(code)
    found = []
    for text in inspector.label_texts + inspector.placeholders:
        if text.lower().strip(" :!?.*") in ENGLISH_LABELS and text not in found:
            found.append(text)
    return found


# ---------------------------------------------------------------- S5-03: fetch() calls vs. the shared contract
_FETCH = re.compile(r"\bfetch\s*\(\s*")
_STRING = re.compile(r"""(['"`])((?:\\.|(?!\1).)*)\1""", re.DOTALL)
_BASE_PLUS = re.compile(r"[A-Za-z_$][\w$.]*\s*\+\s*")
_METHOD = re.compile(r"""\bmethod\s*:\s*(['"`])(\w+)\1""", re.IGNORECASE)


def _call_args(text: str, start: int) -> str:
    """Text of the fetch( ... ) arguments, up to the parenthesis that closes the call."""
    depth, i, quote = 1, start, None
    while i < len(text) and depth:
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return text[start:i - 1] if not depth else text[start:i]


def _normalize_fetch_path(url: str, has_tail: bool) -> Optional[str]:
    url = re.sub(r"\$\{[^}]*\}", "{}", url.strip())
    if "://" in url:
        url = "/" + url.split("://", 1)[1].partition("/")[2]
    if url.startswith("{}/"):        # `${API_BASE}/orders`
        url = url[2:]
    if has_tail:                      # '/orders/' + id
        url = url.rstrip("/") + "/{}"
    if not url or url.startswith("{}"):
        return None                   # fully dynamic URL: cannot be checked
    if not url.startswith("/"):
        url = "/" + url.lstrip("./")
    return url.split("?", 1)[0].split("#", 1)[0]


def find_fetch_calls(code: str) -> List[Tuple[str, str]]:
    """(METHOD, path) of every fetch() whose URL is a literal, a template string or BASE + literal."""
    calls = []
    for match in _FETCH.finditer(code):
        head = _call_args(code, match.end())
        base = _BASE_PLUS.match(head)
        if base:
            head = head[base.end():]
        literal = _STRING.match(head)
        if not literal:
            continue
        rest = head[literal.end():]
        path = _normalize_fetch_path(literal.group(2), has_tail=rest.lstrip().startswith("+"))
        if path is None:
            continue
        method = _METHOD.search(rest)
        calls.append(((method.group(2).upper() if method else "GET"), path))
    return calls


def check_fetch_against_contract(code: str, endpoints: List[Tuple[str, str]]) -> Dict[str, Any]:
    """Warnings, never a failure: fetch calls outside the contract and contract endpoints the page never calls."""
    calls = find_fetch_calls(code)
    warnings = [f"Sözleşmede olmayan çağrı: {label}" for label in off_contract(calls, endpoints)]
    if not calls:
        warnings.append("Sayfa sözleşmedeki hiçbir uç noktayı fetch ile çağırmıyor.")
    unused = [f"{m} {p}" for m, p in endpoints
              if not any(cm == m and path_matches(p, cp) for cm, cp in calls)]
    return {"fetch_calls": sorted({f"{m} {p}" for m, p in calls}), "contract_warnings": warnings,
            "unused_endpoints": unused}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_").lower()
    return slug or "generated"


class FrontendAgent(BaseAgent):
    """Specialized Agent for Frontend UI/UX development."""

    def __init__(self, agent_id: str = None, name: str = "Frontend Specialist Agent",
                 model_name: str = "qwen2.5-coder:3b", use_ollama: Optional[bool] = None,
                 ollama_host: Optional[str] = None, timeout: Optional[float] = None,
                 fallback_enabled: Optional[bool] = None,
                 llm_client: Optional[Callable[[str], str]] = None,
                 num_predict: Optional[int] = None, num_ctx: Optional[int] = None):
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
        self.num_predict = num_predict or _env_int("FRONTEND_NUM_PREDICT", DEFAULT_NUM_PREDICT, minimum=256)
        self.num_ctx = num_ctx or _env_int("FRONTEND_NUM_CTX", DEFAULT_NUM_CTX, minimum=1024)
        self.max_validation_retries = _env_int("FRONTEND_VALIDATION_RETRIES", 1, minimum=0)
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

        endpoints = contract_endpoints(task.get("context_artifacts"))
        prompt = self.build_prompt(task)
        total_attempts = 1 + self.max_validation_retries
        logs.append(f"[{self.name}] Sending UI prompt to local Ollama model '{self.model_name}' at {self.ollama_host} "
                    f"(num_predict={self.num_predict}, num_ctx={self.num_ctx})...")
        for attempt in range(1, total_attempts + 1):
            try:
                raw = self.llm_client(prompt)
            except OllamaCallError as exc:
                if not self.fallback_enabled:
                    logs.append(f"[{self.name}] Ollama call failed and fallback is disabled: {exc}")
                    raise
                logs.append(f"[{self.name}] [FALLBACK] Ollama unavailable ({exc.error_type}): {exc}. "
                            "Returning labelled fallback page, not model output.")
                return self._template_result(task, filename, generation_mode="fallback",
                                             fallback_reason=exc.error_type)

            code = None
            try:
                code = extract_html_code(raw)
                element_count, components = validate_ui_code(code)
                app_title = check_app_title(code, task)
                # S5-03 (Nov 27 app test): the 3b model left "// JavaScript code will be added here".
                # A page that calls no endpoint is asked for once more; if it is still empty it is
                # kept with a warning (check_fetch_against_contract) instead of failing the task.
                if endpoints and not find_fetch_calls(code) and attempt < total_attempts:
                    raise ModelOutputError(
                        "Sayfanın JavaScript'i hiçbir API uç noktasını fetch ile çağırmıyor (boş ya da yer tutucu "
                        "yorum). Formları, ürün listesini, sepeti ve siparişleri sözleşmedeki uç noktalara bağlayan "
                        "çalışan kodu yazın.")
            except ModelOutputError as exc:
                if attempt < total_attempts:
                    logs.append(f"[{self.name}] Sayfa doğrulama hatası (deneme {attempt}/{total_attempts}): {exc} "
                                "Düzeltilmiş sayfa yeniden isteniyor...")
                    prompt = self.build_retry_prompt(task, code or raw or "", str(exc))
                    continue
                raise
            break
        logs.append(f"[{self.name}] Model output validated: {len(code.splitlines())} lines, "
                    f"{element_count} UI elements ({', '.join(components) or 'no component tags'}), "
                    f"app name '{app_title}'.")

        # Warnings only: the page is still usable, the reviewer sees them on the task card
        english = find_english_labels(code)
        if english:
            logs.append(f"[{self.name}] [UYARI] İngilizce etiketler: {', '.join(english)}")
        contract = check_fetch_against_contract(code, endpoints) if endpoints else {
            "fetch_calls": sorted({f"{m} {p}" for m, p in find_fetch_calls(code)}),
            "contract_warnings": [], "unused_endpoints": []}
        for warning in contract["contract_warnings"]:
            logs.append(f"[{self.name}] [UYARI] {warning}")
        if contract["unused_endpoints"]:
            logs.append(f"[{self.name}] Sayfanın çağırmadığı sözleşme uç noktaları: "
                        f"{', '.join(contract['unused_endpoints'])}")

        code = apply_base_css(code)
        logs.append(f"[{self.name}] Base stylesheet (#{BASE_CSS_ID}) added to <head>.")

        return {
            "files": [{"filename": filename, "content": code, "language": "html"}],
            "ui_files_generated": [filename],
            "ui_element_count": element_count,
            "components_detected": components,
            "app_title": app_title,
            "validation_retries": attempt - 1,
            "contract_checked": bool(endpoints),
            "fetch_calls": contract["fetch_calls"],
            "contract_warnings": contract["contract_warnings"],
            "unused_endpoints": contract["unused_endpoints"],
            "english_labels": english,
            "model_used": self.model_name,
            "generation_mode": "ollama",
            "status": "FRONTEND_UI_GENERATED"
        }

    def build_prompt(self, task: Dict[str, Any]) -> str:
        context = task.get("context_artifacts") or {}
        context_text = json.dumps(context, ensure_ascii=False, indent=2)[:4000] if context else "(none)"
        requirement = str(context.get("requirement") or "").strip()[:1500]
        return (
            "You are a senior frontend engineer. Build ONE complete web page for the application below.\n"
            "Rules:\n"
            "- Reply with exactly one ```html code block and nothing else.\n"
            "- Full HTML document: <!DOCTYPE html>, <html lang=\"tr\">, <head> with <meta charset=\"utf-8\">, "
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> and <title>, then <body>, "
            "ending with </body></html>. Close every tag you open.\n"
            "- APP NAME: pick a short Turkish name for the application from the requirement (for example "
            "\"Kafe Sipariş\" or \"Kütüphane\"). Use it in <title> and in the <h1> of the header. Never use "
            "\"Frontend Interface\", \"Frontend UI\", \"Web App\" or the task title.\n"
            "- LANGUAGE: every visible text (headings, labels, buttons, placeholders, messages) is Turkish, "
            "e.g. Giriş Yap, Kayıt Ol, Sepete Ekle, Sepet, Siparişi Ver, Siparişlerim, Çıkış.\n"
            "- STYLE: the page already gets a ready stylesheet. Do NOT write a <style> block, style=\"...\" "
            "attributes, CDN links or CSS frameworks. Use ONLY these classes:\n"
            f"  {CSS_CLASS_GUIDE}.\n"
            "- LAYOUT: <header class=\"app-header\"> with <h1> and <nav>; <main class=\"container\"> with one "
            "<section class=\"section\"> (and an <h2>) per feature:\n"
            "  * if the API has /register or /login: one section with div.tabs (two button.tab: Giriş Yap / "
            "Kayıt Ol) switching between two form.form; hide the inactive form with .hidden;\n"
            "  * every list the API returns (products, books, items...): a div.grid filled with div.card "
            "elements built from the API data (name in h3, details in p.muted, price in span.price, an action "
            "button.btn-primary);\n"
            "  * if the app has orders or a basket: a 'Sepet' section (ul.list of chosen items, div.total, "
            "a 'Siparişi Ver' button) and a 'Siparişlerim' section listing the user's orders;\n"
            "  * show the result of every action in a div.alert-success or div.alert-error.\n"
            "- JS: one <script> at the end of <body>. Load and send data only with fetch on relative paths "
            "(fetch('/items')), never hard-coded sample data. After login keep the token in localStorage and "
            "send it as the header Authorization: 'Bearer ' + token. Write the complete working code (tab "
            "switching, form submit handlers, rendering cards, cart and orders) - never a placeholder comment "
            "like '// JavaScript code will be added here'.\n"
            "- Keep it compact (about 200 lines), no comments.\n\n"
            f"{self._contract_rules(task)}"
            + (f"Requirement: {requirement}\n" if requirement else "")
            + f"Task title: {task.get('title', '')}\n"
            f"Task description: {task.get('description', '')}\n"
            f"Context from upstream agents:\n{context_text}\n"
        )

    @staticmethod
    def _contract_rules(task: Dict[str, Any]) -> str:
        endpoints = contract_endpoints(task.get("context_artifacts"))
        if not endpoints:
            return ""
        listed = "\n".join(f"  - {m} {p}" for m, p in endpoints)
        return (
            "API CONTRACT - fetch may call ONLY these endpoints, with exactly this method and path "
            "(replace {param} with the real id):\n"
            f"{listed}\n"
            "Do not invent other paths, prefixes (/api/v1/...) or methods.\n\n"
        )

    def build_retry_prompt(self, task: Dict[str, Any], previous_output: str, error: str) -> str:
        """Follow-up prompt asking the model to fix a rejected page (unclosed tags, generic title...)."""
        snippet = (previous_output or "").strip()[:6000]
        return (
            f"{self.build_prompt(task)}\n"
            "IMPORTANT - your previous page was REJECTED:\n"
            f"- Reason: {error}\n"
            "- Rewrite the complete page inside exactly one ```html block, fixing this. "
            "Every <div>, <section>, <form>, <ul>, <button> and <span> you open must be closed in the right order.\n"
            f"Previous rejected page:\n```html\n{snippet}\n```\n"
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
            "<!DOCTYPE html>\n<html lang=\"tr\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{title}</title>\n"
            "</head>\n<body>\n"
            f"<header class=\"app-header\"><h1>{title}</h1></header>\n"
            "<main class=\"container\">\n<div class=\"alert\">Yer tutucu sayfa: bu dosya model tarafından "
            "YAZILMADI.</div>\n</main>\n"
            "</body>\n</html>\n"
        )
        content = apply_base_css(content)
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
            "options": {"temperature": 0.2, "seed": 42, "num_predict": self.num_predict, "num_ctx": self.num_ctx}
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
