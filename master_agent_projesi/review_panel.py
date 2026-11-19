"""
S4-03 (Kübra Hepcan): Streamlit panels for retried / reassigned tasks, Integration Agent
code-review findings and conflict / syntax-error warnings.

Everything here is a pure function over data the engine already produces, so it is easy to test
and does not touch app.py. Inputs:

* ``history``   - ``orch.execution_history``: one TaskResult per attempt, in execution order
                  (failed attempts included, unlike ``state.artifacts`` which keeps SUCCESS only).
* ``report``    - the dict returned by ``MasterOrchestrator.process_requirement``
                  (``task_assignments`` with ``attempted_agents``, plus ``conflicts``).
* ``agents``    - optional list of agent objects, used to turn ``agent_id`` into a readable name.

Rules used to label an attempt (same as the engine):
* the first attempt of a task        -> FIRST
* same agent as the previous attempt -> RETRYING   (S4-01 retries TIMEOUT / UNREACHABLE on the same agent)
* a different agent                  -> REASSIGNED (failover to the next candidate)
"""

import html
import re
from typing import Any, Dict, Iterable, List, Optional

ATTEMPT_STYLE = {  # label -> (Turkish text, color)
    "FIRST": ("İlk deneme", "#6B7280"),
    "RETRYING": ("YENİDEN DENENDİ", "#FBBF24"),
    "REASSIGNED": ("BAŞKA AJANA DEVREDİLDİ", "#F97316"),
}
REVIEW_STYLE = {  # Integration Agent status -> (Turkish text, color)
    "APPROVED": ("ONAYLANDI", "#34D399"),
    "REVIEW_REQUIRED": ("İNCELEME GEREKLİ", "#FBBF24"),
    "REJECTED": ("REDDEDİLDİ", "#F87171"),
    "PENDING": ("BEKLEMEDE", "#6B7280"),
}
SEVERITY_STYLE = {"CRITICAL": "#F87171", "WARNING": "#FBBF24", "INFO": "#60A5FA"}
ERROR_CODE_TEXT = {
    "TIMEOUT": "ajan zamanında yanıt vermedi",
    "UNREACHABLE": "ajana ulaşılamadı",
}
_PSEUDO_PATHS = ("", "NONE", "WORKSPACE")  # Integration Agent uses these when there is no real file
_REVIEW_ORDER = {"APPROVED": 0, "PENDING": 0, "REVIEW_REQUIRED": 1, "REJECTED": 2}


def esc(x: Any) -> str:
    return html.escape(str(x))


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# --------------------------------------------------------------------------------------
# 1. Retried / reassigned tasks
# --------------------------------------------------------------------------------------
_CODE_PREFIX = re.compile(r"^\s*\[([A-Z_]+)\]")


def _error_code(result: Any) -> Optional[str]:
    artifacts = _get(result, "output_artifacts") or {}
    contract = artifacts.get("error_contract") if isinstance(artifacts, dict) else None
    if isinstance(contract, dict) and contract.get("error_code"):
        code = contract["error_code"]
        return str(getattr(code, "value", code))
    match = _CODE_PREFIX.match(str(_get(result, "error_message") or ""))
    return match.group(1) if match else None


def attempt_rows(history: Iterable[Any], agents: Optional[Iterable[Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """task_id -> ordered attempt rows built from the engine's execution history."""
    names = {getattr(a, "agent_id", None): getattr(a, "name", None) for a in (agents or [])}
    rows: Dict[str, List[Dict[str, Any]]] = {}
    for result in history or []:
        task_id = _get(result, "task_id")
        if not task_id:
            continue
        agent_id = _get(result, "agent_id")
        agent = names.get(agent_id) or agent_id or "-"
        task_rows = rows.setdefault(task_id, [])
        if not task_rows:
            kind = "FIRST"
        else:
            kind = "RETRYING" if task_rows[-1]["agent"] == agent else "REASSIGNED"
        ok = str(_get(result, "status", "")).upper() == "SUCCESS"
        task_rows.append({
            "no": len(task_rows) + 1,
            "agent": agent,
            "kind": kind,
            "ok": ok,
            "code": None if ok else _error_code(result),
            "message": None if ok else _get(result, "error_message"),
            "seconds": _get(result, "execution_time_seconds", 0.0),
        })
    return rows


def rows_from_attempted_agents(attempted: Iterable[str]) -> List[Dict[str, Any]]:
    """Fallback when only the record's ``attempted_agents`` list is known (no history)."""
    out: List[Dict[str, Any]] = []
    for name in attempted or []:
        if not out:
            kind = "FIRST"
        else:
            kind = "RETRYING" if out[-1]["agent"] == name else "REASSIGNED"
        out.append({"no": len(out) + 1, "agent": name, "kind": kind, "ok": None,
                    "code": None, "message": None, "seconds": None})
    return out


def task_flags(rows: List[Dict[str, Any]]) -> List[str]:
    """Which badges a task needs: any of RETRYING / REASSIGNED (empty = ran once, no drama)."""
    return [k for k in ("RETRYING", "REASSIGNED") if any(r["kind"] == k for r in rows)]


def retry_summary(rows: List[Dict[str, Any]]) -> str:
    """One short sentence, e.g. 'Frontend Agent 2 kez yeniden denendi → Backend Agent'a devredildi'."""
    if not rows:
        return ""
    retries = sum(1 for r in rows if r["kind"] == "RETRYING")
    handovers = [r["agent"] for r in rows if r["kind"] == "REASSIGNED"]
    parts = []
    if retries:
        parts.append(f"aynı ajan {retries} kez yeniden denendi")
    if handovers:
        parts.append("devredilen ajan(lar): " + ", ".join(dict.fromkeys(handovers)))
    return " · ".join(parts)


def attempt_flow_html(rows: List[Dict[str, Any]]) -> str:
    """Compact HTML: a badge per RETRYING / REASSIGNED plus a step list of all attempts."""
    flags = task_flags(rows)
    if not flags:
        return ""
    chips = "".join(
        f'<span class="chip chip-cx" style="--c:{ATTEMPT_STYLE[k][1]};margin-right:6px">'
        f'{"↻" if k == "RETRYING" else "⇄"} {ATTEMPT_STYLE[k][0]}</span>' for k in flags)
    steps = []
    for r in rows:
        text, color = ATTEMPT_STYLE[r["kind"]]
        if r["ok"] is True:
            state = '<span style="color:#34D399">✔ başarılı</span>'
        elif r["ok"] is False:
            why = ERROR_CODE_TEXT.get(r["code"] or "", "")
            tail = f" ({esc(why)})" if why else ""
            msg = (" — " + esc(" ".join(str(r["message"]).split())[:140])) if r["message"] else ""
            state = f'<span style="color:#F87171">✖ başarısız{tail}{msg}</span>'
        else:
            state = ""
        steps.append(
            f'<div style="padding:3px 0;font-size:.85rem">{r["no"]}. <b>{esc(r["agent"])}</b> '
            f'<span style="color:{color}">· {esc(text)}</span> {state}</div>')
    return (f'<div style="margin:6px 0 2px">{chips}<span class="task-desc">{esc(retry_summary(rows))}</span>'
            f'{"".join(steps)}</div>')


# --------------------------------------------------------------------------------------
# 2. Integration Agent code review
# --------------------------------------------------------------------------------------
def _is_review_report(art: Any) -> bool:
    return isinstance(art, dict) and art.get("status") in REVIEW_STYLE and (
        "findings" in art or "inspected_files" in art)


def find_review_report(history: Iterable[Any]) -> Optional[Dict[str, Any]]:
    """Last IntegrationReportContract_v1 found in the history (FAILED / REJECTED reports included)."""
    found = None
    for result in history or []:
        art = _get(result, "output_artifacts")
        if _is_review_report(art):
            found = art
    return found


def _finding(f: Any) -> Dict[str, str]:
    return {"file_path": str(_get(f, "file_path", "") or ""),
            "severity": str(_get(f, "severity", "INFO") or "INFO").upper(),
            "issue": str(_get(f, "issue", "") or ""),
            "suggestion": str(_get(f, "actionable_suggestion", "") or "")}


def file_review_status(path: str, findings: List[Dict[str, str]]) -> str:
    """Same rule the orchestrator stores in output_files.review_status."""
    status = "APPROVED"
    for f in findings:
        if f["file_path"] != path:
            continue
        if f["severity"] == "CRITICAL":
            return "REJECTED"
        if f["severity"] == "WARNING":
            status = "REVIEW_REQUIRED"
    return status


def review_view(report: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Turn an IntegrationReportContract dict into: overall status, summary, per-file rows, findings."""
    if not _is_review_report(report):
        return None
    findings = [_finding(f) for f in report.get("findings") or []]
    paths = list(dict.fromkeys(list(report.get("inspected_files") or []) + [f["file_path"] for f in findings
                                                                          if f["file_path"] not in _PSEUDO_PATHS]))
    files = []
    for p in paths:
        own = [f for f in findings if f["file_path"] == p]
        files.append({"file": p, "status": file_review_status(p, findings), "findings": own})
    files.sort(key=lambda r: -_REVIEW_ORDER.get(r["status"], 0))
    counts = {s: sum(1 for r in files if r["status"] == s) for s in ("APPROVED", "REVIEW_REQUIRED", "REJECTED")}
    return {"status": report["status"], "summary": report.get("summary") or "", "files": files,
            "findings": findings, "counts": counts}


def review_table_html(view: Dict[str, Any]) -> str:
    status_txt, status_color = REVIEW_STYLE.get(view["status"], REVIEW_STYLE["PENDING"])
    c = view["counts"]
    head = (f'<div style="margin-bottom:8px"><span class="chip chip-cx" style="--c:{status_color}">'
            f'Kod incelemesi: {status_txt}</span> '
            f'<span class="chip">✔ {c["APPROVED"]} onaylı</span> '
            f'<span class="chip">⚠ {c["REVIEW_REQUIRED"]} inceleme gerekli</span> '
            f'<span class="chip">✖ {c["REJECTED"]} reddedildi</span></div>')
    if view["summary"]:
        head += f'<div class="task-desc">{esc(view["summary"])}</div>'
    td = "padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top;"
    body = ""
    for r in view["files"]:
        txt, color = REVIEW_STYLE.get(r["status"], REVIEW_STYLE["PENDING"])
        notes = "".join(
            f'<div style="margin-bottom:4px"><span style="color:{SEVERITY_STYLE.get(f["severity"], "#6B7280")};'
            f'font-weight:600">{esc(f["severity"])}</span> {esc(f["issue"])}'
            + (f'<div class="task-desc">💡 {esc(f["suggestion"])}</div>' if f["suggestion"] else "") + '</div>'
            for f in r["findings"]) or '<span class="task-desc">Bulgu yok</span>'
        body += (f'<tr><td style="{td}white-space:nowrap;font-weight:600">{esc(r["file"])}</td>'
                 f'<td style="{td}white-space:nowrap"><span class="chip chip-cx" style="--c:{color}">{txt}</span></td>'
                 f'<td style="{td}">{notes}</td></tr>')
    if not body:
        return head + '<div class="task-desc" style="margin-top:8px">İncelenen dosya yok.</div>'
    th = "text-align:left;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.2);"
    return (head + '<div style="overflow-x:auto;margin-top:8px"><table style="border-collapse:collapse;width:100%">'
            f'<thead><tr><th style="{th}">Dosya</th><th style="{th}">Durum</th><th style="{th}">Bulgular</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


# --------------------------------------------------------------------------------------
# 3. Warning cards: syntax errors, unsafe / empty files, path & schema conflicts
# --------------------------------------------------------------------------------------
def _finding_kind(issue: str) -> str:
    low = issue.lower()
    if "çakışma" in low:
        return "PATH"
    if "syntax" in low or "sözdizimi" in low:
        return "SYNTAX"
    if "güvensiz" in low or "dışına" in low:
        return "UNSAFE_PATH"
    if "boş" in low or "bulunamadı" in low:
        return "EMPTY"
    return "OTHER"


_KIND_TITLE = {
    "SYNTAX": "Sözdizimi (syntax) hatası",
    "UNSAFE_PATH": "Güvensiz dosya yolu",
    "EMPTY": "Boş veya eksik dosya",
    "OTHER": "Kod incelemesi uyarısı",
    "PATH": "Dosya yolu çakışması",
    "SCHEMA": "Veritabanı şeması çakışması",
}
_KIND_ICON = {"SYNTAX": "🐛", "UNSAFE_PATH": "⛔", "EMPTY": "📄", "OTHER": "⚠", "PATH": "📁", "SCHEMA": "🗄"}
_RESOLUTION_TEXT = {
    "RENAMED": "Dosya yeniden adlandırılarak ikisi de korundu.",
    "DEDUPLICATED": "İçerik aynı olduğu için tekrar yazılmadı.",
    "REPORTED": "Otomatik çözülmedi; ilk tanım geçerli kabul edildi, elle kontrol edin.",
}


def warning_cards(view: Optional[Dict[str, Any]], conflicts: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """One card per CRITICAL / WARNING finding and per file conflict, most severe first."""
    cards: List[Dict[str, Any]] = []
    for f in (view or {}).get("findings", []):
        if f["severity"] not in ("CRITICAL", "WARNING"):
            continue
        kind = _finding_kind(f["issue"])
        cards.append({"kind": kind, "severity": f["severity"], "title": _KIND_TITLE[kind], "file": f["file_path"],
                      "message": f["issue"], "hint": f["suggestion"]})
    for c in conflicts or []:
        kind = c.get("conflict_type") if c.get("conflict_type") in ("PATH", "SCHEMA") else "OTHER"
        resolution = c.get("resolution")
        hint = _RESOLUTION_TEXT.get(resolution, "")
        if kind == "PATH" and resolution == "RENAMED" and c.get("resolved_path"):
            hint = f"Yeni yol: {c['resolved_path']}. " + hint
        cards.append({"kind": kind, "severity": "CRITICAL" if resolution == "REPORTED" else "WARNING",
                      "title": _KIND_TITLE[kind], "file": c.get("file_path") or "",
                      "message": c.get("detail") or "Aynı dosya iki görev tarafından üretildi.", "hint": hint})
    cards.sort(key=lambda c: 0 if c["severity"] == "CRITICAL" else 1)
    return cards


def warning_card_html(card: Dict[str, Any]) -> str:
    color = SEVERITY_STYLE.get(card["severity"], "#FBBF24")
    file_chip = f' <span class="chip">{esc(card["file"])}</span>' if card["file"] else ""
    hint = f'<div class="task-desc" style="margin-top:4px">💡 {esc(card["hint"])}</div>' if card["hint"] else ""
    return (f'<div style="border-left:4px solid {color};background:rgba(255,255,255,.04);border-radius:8px;'
            f'padding:10px 14px;margin:8px 0">'
            f'<div style="font-weight:600;color:{color}">{_KIND_ICON.get(card["kind"], "⚠")} '
            f'{esc(card["title"])}{file_chip}</div>'
            f'<div style="margin-top:4px">{esc(card["message"])}</div>{hint}</div>')


# --------------------------------------------------------------------------------------
# 4. Streamlit entry points (called from app.py)
# --------------------------------------------------------------------------------------
def render_task_attempts(st: Any, task_id: str, rows_by_task: Dict[str, List[Dict[str, Any]]],
                         fallback_attempted: Optional[List[str]] = None) -> None:
    """Under a task card: show RETRYING / REASSIGNED details (nothing if the task ran once)."""
    rows = rows_by_task.get(task_id) or rows_from_attempted_agents(fallback_attempted or [])
    markup = attempt_flow_html(rows)
    if markup:
        st.markdown(markup, unsafe_allow_html=True)


def render_review_panel(st: Any, report: Dict[str, Any], history: Iterable[Any]) -> None:
    """Section 'Kod inceleme sonuçları': Integration findings table + warning cards."""
    view = review_view(find_review_report(history))
    cards = warning_cards(view, (report or {}).get("conflicts"))
    st.markdown('<div class="section-title">Kod inceleme sonuçları</div>', unsafe_allow_html=True)
    if view is None:
        st.caption("Bu çalıştırmada Integration Agent incelemesi yapılmadı (ya da sonucu alınamadı).")
    else:
        st.markdown(review_table_html(view), unsafe_allow_html=True)
    if cards:
        st.markdown(f'<div class="section-title">Uyarılar ({len(cards)})</div>', unsafe_allow_html=True)
        for card in cards:
            st.markdown(warning_card_html(card), unsafe_allow_html=True)
    elif view is not None:
        st.success("Sözdizimi hatası ya da dosya çakışması bulunmadı.")
