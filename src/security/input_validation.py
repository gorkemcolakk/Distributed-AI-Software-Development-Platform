"""
S4-02: Input Validation & Sanitisation Module.

Centralises all backend input validation rules so that every entry point
(Streamlit UI, Worker HTTP API, MasterOrchestrator CLI) applies the same
checks:

 1. **Requirement text** — length, emptiness, and forbidden content.
 2. **Task payloads** — structural completeness (task_id, title).
 3. **File paths** — path traversal and allowed extension enforcement.
 4. **Generic strings** — null-byte injection, control chars, excessive length.

Her doğrulama hatası ``InputValidationError`` fırlatır; bu hata
``error_classification`` modülü tarafından PERMANENT olarak sınıflandırılır
(yeniden denemek aynı hatayı verir).
"""

from __future__ import annotations

import os
import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Set, Tuple


# =====================================================================
# 1. YAPILANDIRMA SABİTLERİ
# =====================================================================

# Kullanıcı gereksinim girdisi sınırları
MIN_REQUIREMENT_LENGTH = 1
MAX_REQUIREMENT_LENGTH = 50_000

# Genel dize sınırları
MAX_GENERIC_STRING_LENGTH = 10_000

# Görev alanları
MIN_TASK_ID_LENGTH = 1
MAX_TASK_ID_LENGTH = 128
MIN_TITLE_LENGTH = 2
MAX_TITLE_LENGTH = 500

# İzin verilen dosya uzantıları (ajan çıktıları)
ALLOWED_OUTPUT_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".sql", ".html", ".css", ".js", ".json", ".md", ".txt", ".yaml", ".yml",
})

# Null byte ve kontrol karakterleri (tab ve satır sonu hariç)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# =====================================================================
# 2. HATA SINIFI
# =====================================================================

class InputValidationError(ValueError):
    """
    Girdi doğrulama hatası.
    ``field``: hangi alanın başarısız olduğunu belirtir.
    ``reason``: insan okunabilir açıklama (asla hassas veri içermez).
    """

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"Girdi doğrulama hatası [{field}]: {reason}")


# =====================================================================
# 3. İLKEL DOĞRULAMA FONKSİYONLARI
# =====================================================================

def check_no_null_bytes(value: str, field: str = "input") -> None:
    """Null byte (\x00) kontrolü — her girdi için çağrılmalı."""
    if "\x00" in value:
        raise InputValidationError(field, "Girdi null byte (\\x00) içeremez.")


def check_no_control_chars(value: str, field: str = "input") -> None:
    """Tab/satır sonu dışındaki kontrol karakterlerini reddeder."""
    match = _CONTROL_CHARS.search(value)
    if match:
        raise InputValidationError(
            field,
            f"Girdi geçersiz kontrol karakteri içeriyor (0x{ord(match.group()):02x})."
        )


def check_length(
    value: str,
    field: str,
    min_len: int = 0,
    max_len: int = MAX_GENERIC_STRING_LENGTH,
) -> None:
    """Dize uzunluk kontrolü."""
    if len(value) < min_len:
        raise InputValidationError(
            field, f"En az {min_len} karakter gerekli, {len(value)} karakter verildi."
        )
    if len(value) > max_len:
        raise InputValidationError(
            field, f"En fazla {max_len} karakter kabul edilir, {len(value)} karakter verildi."
        )


def sanitize_string(value: Any, field: str = "input", max_len: int = MAX_GENERIC_STRING_LENGTH) -> str:
    """
    Genel amaçlı girdi temizleme: tür, null byte, kontrol karakteri ve uzunluk.
    Döndürülen dize güvenli kullanım için hazırdır.
    """
    if not isinstance(value, str):
        raise InputValidationError(field, f"Dize (str) bekleniyor, {type(value).__name__} alındı.")
    check_no_null_bytes(value, field)
    check_no_control_chars(value, field)
    value = value.strip()
    check_length(value, field, min_len=0, max_len=max_len)
    return value


# =====================================================================
# 4. GEREKSİNİM METNİ DOĞRULAMA
# =====================================================================

def validate_requirement_text(text: Any) -> str:
    """
    Kullanıcının gereksinim metnini doğrular ve temizler.

    - Boş veya çok kısa metinler reddedilir.
    - Aşırı uzun metinler reddedilir.
    - Null byte ve kontrol karakterleri reddedilir.

    Döndürülen metin güvenli ve strip edilmiştir.
    """
    if not isinstance(text, str):
        raise InputValidationError("requirement", f"Dize (str) bekleniyor, {type(text).__name__} alındı.")

    check_no_null_bytes(text, "requirement")
    check_no_control_chars(text, "requirement")

    cleaned = text.strip()
    check_length(cleaned, "requirement", MIN_REQUIREMENT_LENGTH, MAX_REQUIREMENT_LENGTH)

    return cleaned


# =====================================================================
# 5. GÖREV YÜKÜ DOĞRULAMA
# =====================================================================

def validate_task_payload(payload: Any) -> Dict[str, Any]:
    """
    Worker'a gönderilecek görev payload'ını doğrular.

    Zorunlu alanlar: ``task_id`` (str, boş olmayan).
    İsteğe bağlı ama doğrulanan: ``title``, ``description``, ``category``.

    Döndürülen sözlük güvenli kullanım için hazırdır.
    """
    if not isinstance(payload, dict):
        raise InputValidationError("payload", "Görev verisi bir sözlük (dict) olmalıdır.")

    # task_id: zorunlu
    task_id = payload.get("task_id")
    if not task_id or not isinstance(task_id, str) or not task_id.strip():
        raise InputValidationError("task_id", "Görev kimliği (task_id) boş olamaz.")
    task_id = sanitize_string(task_id, "task_id", MAX_TASK_ID_LENGTH)
    payload["task_id"] = task_id

    # title: isteğe bağlı ama varsa doğrulanır
    title = payload.get("title")
    if title is not None:
        payload["title"] = sanitize_string(str(title), "title", MAX_TITLE_LENGTH)

    # description: isteğe bağlı
    desc = payload.get("description")
    if desc is not None:
        payload["description"] = sanitize_string(str(desc), "description", MAX_REQUIREMENT_LENGTH)

    return payload


# =====================================================================
# 6. DOSYA YOLU DOĞRULAMA
# =====================================================================

def validate_output_path(
    filename: Any,
    allowed_extensions: Optional[frozenset[str]] = None,
) -> str:
    """
    Ajan çıktı dosya yolunu doğrular.
    - Boş, null byte, mutlak yol, path traversal (..) reddedilir.
    - İzin verilmeyen uzantılar reddedilir.

    Döndürülen yol normalize edilmiş göreli bir yoldur.
    """
    exts = allowed_extensions if allowed_extensions is not None else ALLOWED_OUTPUT_EXTENSIONS

    if not filename or not isinstance(filename, str):
        raise InputValidationError("filename", "Dosya adı boş veya geçersiz.")

    check_no_null_bytes(filename, "filename")

    normalized = filename.strip().replace("\\", "/")

    # Mutlak yol kontrolü
    if PureWindowsPath(filename).drive or PureWindowsPath(filename).anchor or normalized.startswith("/"):
        raise InputValidationError("filename", f"Mutlak yol kabul edilmez: '{filename}'")

    # Path traversal kontrolü
    parts = PurePosixPath(normalized).parts
    if not parts or any(p in ("..", "") for p in parts):
        raise InputValidationError("filename", f"Yol geçişi (..) tespit edildi: '{filename}'")

    # Uzantı kontrolü
    suffix = PurePosixPath(normalized).suffix.lower()
    if exts and suffix not in exts:
        raise InputValidationError(
            "filename",
            f"İzin verilmeyen dosya uzantısı '{suffix}'. "
            f"İzin verilenler: {', '.join(sorted(exts))}"
        )

    return normalized
