"""
Manual model connectivity check (S2-01, cleaned up in S4-06).

Run it yourself when you want to know which model backends are reachable:

    python master_agent_projesi/test_api.py

It is NOT part of the automated test suite (the CI suite never needs a model or a key):
- Local Ollama (the primary backend) is checked with GET {OLLAMA_HOST}/api/tags.
- The optional cloud API is checked only when GEMINI_API_KEY is set AND the
  optional google-generativeai package is installed; otherwise it is reported as skipped.

No key is hardcoded or guessed here: an empty GEMINI_API_KEY simply means "not configured".
The key is never printed; error messages are masked before they are shown.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

__test__ = False  # pytest: this module is a script, not a test module

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
CLOUD_KEY_ENV = "GEMINI_API_KEY"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def mask_secret(text: str, secret: Optional[str]) -> str:
    """Removes the secret from text (e.g. an exception message that echoes the request)."""
    text = str(text)
    if secret:
        text = text.replace(secret, "***")
    return text


def check_ollama(host: Optional[str] = None, timeout: float = 3.0) -> Dict[str, Any]:
    """Returns {"ok", "host", "models", "error"} for the local Ollama server. Never raises."""
    host = (host or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
    result: Dict[str, Any] = {"ok": False, "host": host, "models": [], "error": None}
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result["models"] = sorted(m.get("name", "") for m in data.get("models", []) if isinstance(m, dict))
        result["ok"] = True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        result["error"] = f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"
    return result


def check_cloud_api(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Returns {"ok", "skipped", "models", "error"} for the optional cloud API. Never raises."""
    key = (api_key if api_key is not None else os.getenv(CLOUD_KEY_ENV, "")).strip()
    result: Dict[str, Any] = {"ok": False, "skipped": False, "models": [], "error": None}
    if not key:
        result.update(skipped=True, error=f"{CLOUD_KEY_ENV} tanımlı değil (yerel Ollama kullanılır).")
        return result
    try:
        import google.generativeai as genai
    except ImportError:
        result.update(skipped=True, error="google-generativeai paketi kurulu değil (isteğe bağlı).")
        return result
    try:
        genai.configure(api_key=key)
        result["models"] = sorted(m.name for m in genai.list_models()
                                  if "generateContent" in getattr(m, "supported_generation_methods", []))
        result["ok"] = True
    except Exception as exc:  # report, never crash
        result["error"] = mask_secret(f"{type(exc).__name__}: {exc}", key)
    return result


def main() -> int:
    # Windows consoles (cp1252) cannot encode Turkish characters; never crash on output
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass
    _load_dotenv()
    ollama = check_ollama()
    if ollama["ok"]:
        print(f"[OK] Ollama {ollama['host']}: {len(ollama['models'])} model -> {', '.join(ollama['models']) or '-'}")
    else:
        print(f"[HATA] Ollama {ollama['host']} erişilemedi: {ollama['error']}")

    cloud = check_cloud_api()
    if cloud["skipped"]:
        print(f"[ATLANDI] Bulut API: {cloud['error']}")
    elif cloud["ok"]:
        print(f"[OK] Bulut API: {len(cloud['models'])} model kullanılabilir.")
    else:
        print(f"[UYARI] Bulut API hatası: {cloud['error']}")

    # Exit code reflects the primary (local) backend only
    return 0 if ollama["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
