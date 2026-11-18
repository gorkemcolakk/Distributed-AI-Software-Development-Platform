"""
Bounded retry policy for failed task attempts (S4-01 — Eren Görkem Çolak).

A failed attempt is either TRANSIENT or PERMANENT:

- TRANSIENT: the remote worker did not answer in time (``TIMEOUT``) or could not be
  reached (``UNREACHABLE``). The same agent is tried again, at most ``max_retries``
  times, after a short pause. A network blip should not cost the task its best agent.
- PERMANENT: everything else (agent exception, invalid output, unsafe path,
  unauthorized, contract violation, duplicate task, ...). Trying the same agent
  again would give the same answer, so the task goes straight to the next candidate.

The error code comes from the structured worker error (``WorkerErrorContract_v1``)
that ``RemoteAgentProxy`` puts into ``output_artifacts["error_contract"]`` and into
the ``"[CODE] message"`` prefix of ``error_message``. Local in-process agents handle
their own Ollama timeouts (labelled backup mode), so their failures are PERMANENT.
"""

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from src.contracts import WorkerErrorCode

TRANSIENT = "TRANSIENT"
PERMANENT = "PERMANENT"

TRANSIENT_CODES = frozenset({WorkerErrorCode.TIMEOUT.value, WorkerErrorCode.UNREACHABLE.value})

_CODE_PREFIX = re.compile(r"^\s*\[([A-Z_]+)\]")


def failure_code(result: Any, error_message: Optional[str] = None) -> Optional[str]:
    """Structured worker error code of a failed attempt, or None if there is none."""
    artifacts = getattr(result, "output_artifacts", None) or {}
    contract = artifacts.get("error_contract") if isinstance(artifacts, dict) else None
    if isinstance(contract, dict) and contract.get("error_code"):
        return str(getattr(contract["error_code"], "value", contract["error_code"]))
    message = error_message if error_message is not None else getattr(result, "error_message", None)
    match = _CODE_PREFIX.match(str(message or ""))
    if match and match.group(1) in WorkerErrorCode.__members__:
        return match.group(1)
    return None


def classify_failure(result: Any, error_message: Optional[str] = None) -> str:
    """TRANSIENT for remote timeout / unreachable, PERMANENT for everything else."""
    return TRANSIENT if failure_code(result, error_message) in TRANSIENT_CODES else PERMANENT


def _env_number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RetryPolicy:
    """How often and how patiently a TRANSIENT failure is retried on the same agent."""

    max_retries: int = 1
    backoff_seconds: float = 2.0

    def __post_init__(self):
        object.__setattr__(self, "max_retries", max(0, int(self.max_retries)))
        object.__setattr__(self, "backoff_seconds", max(0.0, float(self.backoff_seconds)))

    @classmethod
    def from_env(cls) -> "RetryPolicy":
        """MASTER_MAX_RETRIES (default 1) and MASTER_RETRY_BACKOFF seconds (default 2)."""
        return cls(
            max_retries=int(_env_number("MASTER_MAX_RETRIES", 1)),
            backoff_seconds=_env_number("MASTER_RETRY_BACKOFF", 2.0),
        )

    def delay_for(self, retry_no: int) -> float:
        """Pause before retry number ``retry_no`` (1-based): linear backoff."""
        return self.backoff_seconds * max(1, retry_no)
