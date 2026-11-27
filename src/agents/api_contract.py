"""
Shared API contract helpers (S4-07 contract, used by the Testing and Frontend agents).

Moved out of testing_agent.py in S5-03 so the Frontend agent can check its fetch() calls
with the same rules the Testing agent uses for its client calls.
"""

from typing import Any, Dict, List, Optional, Tuple

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


def off_contract(calls: List[Tuple[str, str]], endpoints: List[Tuple[str, str]]) -> List[str]:
    """Calls the contract does not define ('POST /orders'), in order, without duplicates."""
    allowed = list(endpoints) + list(ALWAYS_ALLOWED_ENDPOINTS)
    off = []
    for method, path in calls:
        if any(m == method and path_matches(p, path) for m, p in allowed):
            continue
        label = f"{method} {path}"
        if label not in off:
            off.append(label)
    return off
