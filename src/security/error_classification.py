"""
S4-02: Transient / Permanent Error Classification Module.

Centralises and enriches the error classification logic that was previously
only in ``retry_policy.py`` (S4-01) so that **every layer** in the platform
(worker agents, remote proxy, master orchestrator, Streamlit UI) can:

 1. Distinguish transient errors (network, timeout, quota / 429, 503)
    from permanent errors (syntax, schema, security, bad payload).
 2. Decide whether a retry is appropriate without coupling to the retry
    policy itself (which remains in ``retry_policy.py``).
 3. Carry structured metadata (error code, http status, retryable flag,
    human message) through the entire call chain.

Hata kodları ``src/contracts.py::WorkerErrorCode`` ile birebir uyumlu.
"""

from __future__ import annotations

import re
import socket
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import ValidationError

from src.contracts import WorkerErrorCode


# =====================================================================
# 1. TRANSIENT / PERMANENT TAXONOMİSİ
# =====================================================================

class ErrorKind(str, Enum):
    """High-level bucket: does retrying the *same* operation make sense?"""
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"


# Error codes that are TRANSIENT by nature (remote network / capacity)
TRANSIENT_CODES: frozenset[str] = frozenset({
    WorkerErrorCode.TIMEOUT.value,
    WorkerErrorCode.UNREACHABLE.value,
})

# LLM / Ollama HTTP status codes treated as transient
TRANSIENT_HTTP_STATUSES: frozenset[int] = frozenset({408, 429, 502, 503, 504})

# Error codes that are always PERMANENT (retrying would yield the same failure)
PERMANENT_CODES: frozenset[str] = frozenset({
    WorkerErrorCode.UNAUTHORIZED.value,
    WorkerErrorCode.INVALID_PAYLOAD.value,
    WorkerErrorCode.DUPLICATE_TASK.value,
    WorkerErrorCode.UNSAFE_PATH.value,
    WorkerErrorCode.CONTRACT_VIOLATION.value,
})


# =====================================================================
# 2. YAPILANDIRILMIŞ SINIFLANDIRILMIŞ HATA
# =====================================================================

@dataclass(frozen=True)
class ClassifiedError:
    """
    Immutable structured representation of a classified error.

    Attributes:
        kind:          TRANSIENT or PERMANENT.
        code:          Machine-readable WorkerErrorCode value (or ``None``).
        http_status:   Originating HTTP status code (or ``None``).
        message:       Human-readable description — **never** contains secrets.
        retryable:     Explicit flag: ``True`` only for TRANSIENT.
        source_error:  Original exception type name for diagnostics.
    """
    kind: ErrorKind
    code: Optional[str] = None
    http_status: Optional[int] = None
    message: str = ""
    retryable: bool = False
    source_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "code": self.code,
            "http_status": self.http_status,
            "message": self.message,
            "retryable": self.retryable,
            "source_error": self.source_error,
        }


# =====================================================================
# 3. SINIFLANDIRMA FONKSİYONLARI
# =====================================================================

_CODE_PREFIX = re.compile(r"^\s*\[([A-Z_]+)\]")


def classify_error_code(code: Optional[str]) -> ErrorKind:
    """Classify a raw ``WorkerErrorCode`` string value."""
    if code in TRANSIENT_CODES:
        return ErrorKind.TRANSIENT
    return ErrorKind.PERMANENT


def classify_http_status(status_code: int) -> ErrorKind:
    """Classify an HTTP status code."""
    if status_code in TRANSIENT_HTTP_STATUSES:
        return ErrorKind.TRANSIENT
    return ErrorKind.PERMANENT


def extract_error_code_from_message(message: Optional[str]) -> Optional[str]:
    """
    Extract a ``[CODE]`` prefix from an error message string
    (e.g. ``"[TIMEOUT] Worker HTTP zaman aşımı"`` → ``"TIMEOUT"``).
    """
    if not message:
        return None
    match = _CODE_PREFIX.match(str(message))
    if match and match.group(1) in WorkerErrorCode.__members__:
        return match.group(1)
    return None


def extract_error_code_from_result(result: Any) -> Optional[str]:
    """
    Attempts to find a structured ``WorkerErrorCode`` from a task result object
    or its ``output_artifacts["error_contract"]``.
    """
    artifacts = getattr(result, "output_artifacts", None) or {}
    contract = artifacts.get("error_contract") if isinstance(artifacts, dict) else None
    if isinstance(contract, dict) and contract.get("error_code"):
        return str(getattr(contract["error_code"], "value", contract["error_code"]))
    # Fallback: parse from error_message
    error_message = getattr(result, "error_message", None)
    return extract_error_code_from_message(error_message)


def classify_exception(exc: Exception) -> ClassifiedError:
    """
    Maps a raw Python exception to a ``ClassifiedError``.

    Covers network errors, HTTP errors, timeouts, validation errors,
    and generic exceptions — mirrors the per-class logic that was
    previously inlined in ``RemoteAgentProxy._classify_exception``.
    """
    if isinstance(exc, urllib.error.HTTPError):
        status_code = exc.code
        kind = classify_http_status(status_code)
        if status_code == 401:
            code = WorkerErrorCode.UNAUTHORIZED.value
        elif status_code == 409:
            code = WorkerErrorCode.DUPLICATE_TASK.value
        elif status_code in (400, 422):
            code = WorkerErrorCode.INVALID_PAYLOAD.value
        elif status_code in (408, 504):
            code = WorkerErrorCode.TIMEOUT.value
        elif status_code == 429:
            code = WorkerErrorCode.TIMEOUT.value  # quota → transient
            kind = ErrorKind.TRANSIENT
        else:
            code = WorkerErrorCode.EXECUTION_ERROR.value
        return ClassifiedError(
            kind=kind,
            code=code,
            http_status=status_code,
            message=f"HTTP {status_code} hatası: {exc.reason}",
            retryable=(kind == ErrorKind.TRANSIENT),
            source_error=type(exc).__name__,
        )

    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower():
            return ClassifiedError(
                kind=ErrorKind.TRANSIENT,
                code=WorkerErrorCode.TIMEOUT.value,
                message=f"Bağlantı zaman aşımı: {reason}",
                retryable=True,
                source_error=type(exc).__name__,
            )
        return ClassifiedError(
            kind=ErrorKind.TRANSIENT,
            code=WorkerErrorCode.UNREACHABLE.value,
            message=f"Sunucuya ulaşılamadı: {reason}",
            retryable=True,
            source_error=type(exc).__name__,
        )

    if isinstance(exc, (socket.timeout, TimeoutError)):
        return ClassifiedError(
            kind=ErrorKind.TRANSIENT,
            code=WorkerErrorCode.TIMEOUT.value,
            message=f"Zaman aşımı: {exc}",
            retryable=True,
            source_error=type(exc).__name__,
        )

    if isinstance(exc, ValidationError):
        return ClassifiedError(
            kind=ErrorKind.PERMANENT,
            code=WorkerErrorCode.CONTRACT_VIOLATION.value,
            message=f"Şema doğrulama hatası: {exc}",
            retryable=False,
            source_error=type(exc).__name__,
        )

    if isinstance(exc, (SyntaxError, ValueError, TypeError)):
        return ClassifiedError(
            kind=ErrorKind.PERMANENT,
            code=WorkerErrorCode.INVALID_PAYLOAD.value,
            message=f"Kalıcı hata: {exc}",
            retryable=False,
            source_error=type(exc).__name__,
        )

    # Default: unknown exceptions are permanent (retrying would not help)
    return ClassifiedError(
        kind=ErrorKind.PERMANENT,
        code=WorkerErrorCode.EXECUTION_ERROR.value,
        message=f"Bilinmeyen hata: {exc}",
        retryable=False,
        source_error=type(exc).__name__,
    )


def classify_task_result(result: Any, error_message: Optional[str] = None) -> ClassifiedError:
    """
    Takes a TaskResult (or dict-like) and returns a ClassifiedError.
    Compatible with the existing ``retry_policy.classify_failure`` interface.
    """
    code = extract_error_code_from_result(result)
    if code is None and error_message:
        code = extract_error_code_from_message(error_message)

    kind = classify_error_code(code) if code else ErrorKind.PERMANENT
    msg = error_message or getattr(result, "error_message", None) or "Bilinmeyen hata"
    return ClassifiedError(
        kind=kind,
        code=code,
        message=str(msg),
        retryable=(kind == ErrorKind.TRANSIENT),
        source_error="TaskResult",
    )
