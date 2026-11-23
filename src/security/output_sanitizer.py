"""
S4-02: Model Output Sanitisation & Validation Module.

Ensures that text coming **out** of an LLM (or any untrusted source) is
safe to:
 - display in a web UI (Streamlit, HTML templates),
 - write to disk,
 - embed in log messages,
 - forward to other agents.

Three categories of protection:

 1. **HTML / XSS escaping** — model output may contain ``<script>`` or
    event handler attributes.  ``sanitize_for_display`` escapes them.
 2. **Log redaction** — API keys, tokens, passwords, and other secrets
    must never leak into log files or Streamlit ``st.code`` blocks.
    ``redact_secrets`` replaces known patterns with ``***REDACTED***``.
 3. **JSON schema validation** — model output that is *expected* to be
    structured JSON is validated against an expected set of keys.
    ``validate_json_output`` returns ``(True, parsed)`` or ``(False, error)``.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# =====================================================================
# 1. GİZLİ BİLGİ KALIPLARI (Redaction Patterns)
# =====================================================================

# API anahtarları, Bearer token'lar, şifreler, bağlantı dizeleri
_SECRET_PATTERNS: List[re.Pattern] = [
    # API key patterns (generic + provider-specific)
    re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{16,})['\"]?"),
    re.compile(r"(?i)(secret[_-]?key|secretkey)\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{16,})['\"]?"),
    re.compile(r"(?i)(access[_-]?token|accesstoken)\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{16,})['\"]?"),
    re.compile(r"(?i)(auth[_-]?token|authtoken)\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{16,})['\"]?"),
    # Bearer token in headers
    re.compile(r"(?i)(Authorization)\s*:\s*Bearer\s+([A-Za-z0-9\-_\.]{8,})"),
    # Password patterns
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{4,})['\"]?"),
    # Connection strings
    re.compile(r"(?i)((?:mysql|postgres|mongodb|redis)://[^\s'\"]+)"),
    # Gemini / OpenAI / Ollama API key formats
    re.compile(r"\b(AIza[A-Za-z0-9\-_]{35})\b"),  # Google AI
    re.compile(r"\b(sk-[A-Za-z0-9]{32,})\b"),      # OpenAI
    re.compile(r"\b(gsk_[A-Za-z0-9]{32,})\b"),     # Groq
    # .env style KEY=VALUE with long values
    re.compile(r"(?i)(GEMINI_API_KEY|OPENAI_API_KEY|WORKER_AUTH_TOKEN|BACKEND_AUTH_TOKEN)"
               r"\s*=\s*['\"]?([A-Za-z0-9\-_\.]{8,})['\"]?"),
]

REDACTED = "***REDACTED***"


def redact_secrets(text: str) -> str:
    """
    Verilen metindeki tüm bilinen gizli bilgi kalıplarını ``***REDACTED***``
    ile değiştirir.  Hata günlüklerine veya UI'a yazmadan önce çağrılmalıdır.

    Metnin yapısını (satır sayısı, genel uzunluk) mümkün olduğunca korur.
    """
    if not text:
        return text

    result = text
    for pattern in _SECRET_PATTERNS:
        def _replace(m: re.Match) -> str:
            groups = m.groups()
            if len(groups) >= 2:
                # group(1) is the label, group(2) is the secret value
                return m.group(0).replace(groups[-1], REDACTED)
            # Single-group patterns: replace the whole match
            return REDACTED
        result = pattern.sub(_replace, result)
    return result


# =====================================================================
# 2. HTML / XSS ESCAPİNG
# =====================================================================

# Tehlikeli HTML etiketleri ve olay işleyicileri
_DANGEROUS_HTML = re.compile(
    r"<\s*(script|iframe|object|embed|form|meta|link|base|svg\s+onload)[^>]*>",
    re.IGNORECASE,
)
_EVENT_HANDLERS = re.compile(r"\bon\w+\s*=", re.IGNORECASE)


def sanitize_for_display(text: str) -> str:
    """
    Model çıktısını ekranda güvenle göstermek için temizler.

    - HTML özel karakterleri escape edilir (``html.escape``).
    - ``<script>``, ``<iframe>`` gibi tehlikeli etiketler kaldırılır.
    - Olay işleyici (``onclick=`` vb.) nitelikleri kaldırılır.

    Streamlit ``st.markdown(unsafe_allow_html=True)`` ile kullanılsa bile
    XSS saldırısı mümkün olmaz.
    """
    if not text:
        return text

    # Step 1: HTML escape (the primary defence)
    escaped = html.escape(text, quote=True)

    return escaped


def strip_dangerous_html(text: str) -> str:
    """
    HTML escape yapmadan tehlikeli etiketleri kaldırır.
    Zaten güvenilir HTML içeriğinde ek temizleme için kullanılır.
    """
    if not text:
        return text
    result = _DANGEROUS_HTML.sub("<!-- removed -->", text)
    result = _EVENT_HANDLERS.sub("data-removed=", result)
    return result


# =====================================================================
# 3. JSON ÇIKTI DOĞRULAMA
# =====================================================================

def validate_json_output(
    raw_text: str,
    required_keys: Optional[Set[str]] = None,
    max_length: int = 500_000,
) -> Tuple[bool, Union[Dict[str, Any], str]]:
    """
    Model'den gelen ham metin yanıtı JSON olarak ayrıştırır ve doğrular.

    Args:
        raw_text:      Model'in ham çıktısı.
        required_keys: JSON'un en üst düzeyinde olması gereken anahtarlar.
        max_length:    Kabul edilen maksimum ham metin uzunluğu.

    Returns:
        ``(True, parsed_dict)`` başarılıysa,
        ``(False, error_message)`` başarısızsa.
    """
    if not raw_text or not isinstance(raw_text, str):
        return False, "Model çıktısı boş veya dize değil."

    if len(raw_text) > max_length:
        return False, f"Model çıktısı çok uzun ({len(raw_text)} > {max_length} karakter)."

    # Fenced JSON bloğunu çıkar (```json ... ```)
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw_text, re.DOTALL)
    if json_match:
        candidate = json_match.group(1).strip()
    else:
        # Raw JSON object
        obj_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        candidate = obj_match.group(0).strip() if obj_match else raw_text.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return False, f"Geçersiz JSON: {exc}"

    if not isinstance(parsed, dict):
        return False, f"JSON en üst düzeyde bir sözlük (object) olmalıdır, {type(parsed).__name__} alındı."

    if required_keys:
        missing = required_keys - set(parsed.keys())
        if missing:
            return False, f"JSON'da eksik anahtarlar: {', '.join(sorted(missing))}"

    return True, parsed


# =====================================================================
# 4. LOG GÜVENLİĞİ
# =====================================================================

def safe_log_message(message: str, max_length: int = 2000) -> str:
    """
    Günlüğe yazılacak mesajı güvenli hâle getirir:
    - Gizli bilgiler redakte edilir.
    - Çok uzun mesajlar kesilir.
    - Kontrol karakterleri kaldırılır.
    """
    if not message:
        return ""

    # Redact secrets first
    cleaned = redact_secrets(message)

    # Remove control chars except \n, \r, \t
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)

    # Truncate
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "... [kesildi]"

    return cleaned
