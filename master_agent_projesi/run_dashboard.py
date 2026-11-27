"""
S5-03 (Kübra Hepcan): run telemetry dashboard for a selected run_id.

Shows the real task statuses, assigned agent / model, durations, attempt / retry / reassignment
counts and model / agent comparison charts of one run, read from state.db (runs, tasks, attempts).

Rules:
* Live data and demo data are never mixed: a live run gets a "CANLI" banner with its run_id,
  the engine-less demo gets a "TANITIM VERİSİ" banner and "(tanıtım)" in every chart title.
* A value that has not been collected yet (task still running, no duration recorded, no attempt
  rows) is ``None`` and shown as "henüz toplanmadı" - never as a fake 0. Charts leave those rows
  out and say how many were left out.

The data functions are pure (lists of dicts in, lists of dicts out) so they are tested without
Streamlit; ``render_run_dashboard`` only draws them.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

NOT_COLLECTED = "henüz toplanmadı"
NOT_RUN = "çalıştırılmadı"
FINISHED_STATUSES = ("COMPLETED", "FAILED")
NOT_RUN_STATUSES = ("UNASSIGNED", "BLOCKED")
STATUS_TEXT = {
    "COMPLETED": "Tamamlandı", "FAILED": "Başarısız", "PENDING": "Bekliyor", "IN_PROGRESS": "Çalışıyor",
    "UNASSIGNED": "Atanmadı", "BLOCKED": "Engellendi",
}
COLOR_OK, COLOR_FAIL, COLOR_OTHER = "#34D399", "#F87171", "#6B7280"


def _measured(value: Any) -> Optional[float]:
    """A duration that was really recorded (> 0), otherwise None. The DB default 0.0 means 'not recorded'."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 2) if number > 0 else None


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("T", " ")[:19]
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _group_attempts(attempts: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for att in attempts or []:
        grouped.setdefault(str(att.get("task_id")), []).append(att)
    for rows in grouped.values():
        rows.sort(key=lambda a: (a.get("attempt_no") or 0, a.get("attempt_id") or 0))
    return grouped


def _retry_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Same agent as the previous attempt = retry, a different agent = reassignment (same rule as review_panel)."""
    retries = reassigned = 0
    for prev, cur in zip(rows, rows[1:]):
        if (cur.get("agent_id") or cur.get("agent_name")) == (prev.get("agent_id") or prev.get("agent_name")):
            retries += 1
        else:
            reassigned += 1
    return {"retries": retries, "reassigned": reassigned}


# ---------------------------------------------------------------- data
def task_rows(tasks: Iterable[Dict[str, Any]], attempts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per task. duration / attempts are None when not collected yet."""
    by_task = _group_attempts(attempts)
    rows = []
    for task in tasks or []:
        status = str(task.get("status") or "PENDING")
        att = by_task.get(str(task.get("task_id")), [])
        duration = _measured(task.get("execution_time_seconds"))
        if duration is None and att:
            duration = _measured(sum(_measured(a.get("execution_time_seconds")) or 0 for a in att))
        if status in NOT_RUN_STATUSES:
            note = NOT_RUN
        elif status not in FINISHED_STATUSES:
            note = f"{STATUS_TEXT.get(status, status).lower()} · süre {NOT_COLLECTED}"
        elif duration is None:
            note = f"süre {NOT_COLLECTED}"
        else:
            note = ""
        counts = _retry_counts(att) if att else {"retries": None, "reassigned": None}
        rows.append({
            "task_id": task.get("task_id"),
            "title": task.get("title") or task.get("task_id"),
            "category": task.get("category") or "",
            "agent": task.get("assigned_agent_name") or task.get("assigned_agent") or None,
            "model": task.get("model_used") or None,
            "status": status,
            "duration": duration,
            "attempts": len(att) if att else None,
            "retries": counts["retries"],
            "reassigned": counts["reassigned"],
            "note": note,
        })
    return rows


def model_comparison(attempts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per model: attempts, successes, failures, success rate and mean measured duration (None if none)."""
    stats: Dict[str, Dict[str, Any]] = {}
    for att in attempts or []:
        model = att.get("model_used") or "model bilinmiyor"
        s = stats.setdefault(model, {"model": model, "attempts": 0, "success": 0, "failed": 0, "_times": []})
        s["attempts"] += 1
        if int(att.get("is_successful") or 0):
            s["success"] += 1
        else:
            s["failed"] += 1
        measured = _measured(att.get("execution_time_seconds"))
        if measured is not None:
            s["_times"].append(measured)
    out = []
    for s in sorted(stats.values(), key=lambda x: x["model"]):
        times = s.pop("_times")
        s["success_rate"] = round(100.0 * s["success"] / s["attempts"], 1)
        s["avg_duration"] = round(sum(times) / len(times), 2) if times else None
        out.append(s)
    return out


def agent_distribution(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per assigned agent: completed / failed / other task counts (unassigned tasks under 'Atanmadı')."""
    dist: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        agent = row.get("agent") or "Atanmadı"
        d = dist.setdefault(agent, {"agent": agent, "completed": 0, "failed": 0, "other": 0})
        key = {"COMPLETED": "completed", "FAILED": "failed"}.get(row.get("status"), "other")
        d[key] += 1
    return sorted(dist.values(), key=lambda d: d["agent"])


def run_summary(run: Optional[Dict[str, Any]], rows: List[Dict[str, Any]],
                attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    started, finished = _parse_ts((run or {}).get("started_at")), _parse_ts((run or {}).get("finished_at"))
    wall = round((finished - started).total_seconds(), 1) if started and finished else None
    return {
        "tasks": len(rows),
        "completed": sum(1 for r in rows if r["status"] == "COMPLETED"),
        "failed": sum(1 for r in rows if r["status"] == "FAILED"),
        "wall_seconds": wall,
        "attempts": len(attempts) if attempts else None,
        "retries": sum(r["retries"] or 0 for r in rows) if attempts else None,
        "reassigned": sum(r["reassigned"] or 0 for r in rows) if attempts else None,
        "unmeasured": sum(1 for r in rows if r["duration"] is None and r["status"] not in NOT_RUN_STATUSES),
    }


def demo_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rows for the engine-less demo report; its durations (0.0) are not real, so they stay None."""
    tasks = [{"task_id": r.get("task_id"), "title": r.get("title"), "assigned_agent_name": r.get("assigned_agent"),
              "model_used": r.get("model_used"), "status": r.get("status"), "execution_time_seconds": None}
             for r in (report or {}).get("task_assignments") or []]
    return task_rows(tasks, [])


def _fmt(value: Any, suffix: str = "") -> str:
    return NOT_COLLECTED if value is None else f"{value}{suffix}"


def table_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """Display table: missing values are written out, not shown as 0."""
    return pd.DataFrame([{
        "Görev": r["title"], "Ajan": r["agent"] or "—", "Model": r["model"] or "—",
        "Durum": STATUS_TEXT.get(r["status"], r["status"]),
        "Süre": NOT_RUN if r["status"] in NOT_RUN_STATUSES else _fmt(r["duration"], " sn"),
        "Deneme": _fmt(r["attempts"]), "Yeniden deneme": _fmt(r["retries"]), "Devir": _fmt(r["reassigned"]),
        "Not": r["note"],
    } for r in rows])


def local_time(value: Any) -> str:
    """SQLite CURRENT_TIMESTAMP is UTC; the dashboard shows the machine's local time."""
    parsed = _parse_ts(value)
    if parsed is None:
        return "?"
    return parsed.replace(tzinfo=timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M:%S")


def run_label(run: Dict[str, Any]) -> str:
    title = " ".join(str(run.get("project_title") or "").split())[:40]
    return (f"{run.get('run_id')} · {title or 'başlıksız'} · {run.get('system_status')} · "
            f"{local_time(run.get('started_at'))}")


# ---------------------------------------------------------------- drawing
def _render_body(st: Any, rows: List[Dict[str, Any]], attempts: List[Dict[str, Any]],
                 summary: Dict[str, Any], demo: bool) -> None:
    tag = " (tanıtım)" if demo else ""
    k = st.columns(5)
    k[0].metric("Görev", summary["tasks"])
    k[1].metric("Tamamlanan", summary["completed"])
    k[2].metric("Başarısız", summary["failed"])
    k[3].metric("Toplam süre", _fmt(summary["wall_seconds"], " sn"))
    k[4].metric("Deneme", _fmt(summary["attempts"]))
    if summary["attempts"] is not None:
        st.caption(f"🔁 {summary['retries']} yeniden deneme (aynı ajan) · "
                   f"↪️ {summary['reassigned']} başka ajana devir")

    st.markdown(f"**Görev durumları ve süreleri{tag}**")
    st.dataframe(table_frame(rows), use_container_width=True, hide_index=True)
    if summary["unmeasured"]:
        st.caption(f"⏳ {summary['unmeasured']} görevin süresi {NOT_COLLECTED}; tabloda böyle yazılır, "
                   "grafiklere 0 olarak girmez.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(f"**Model başarı karşılaştırması (deneme bazında){tag}**")
        models = model_comparison(attempts)
        if models:
            df = pd.DataFrame(models).set_index("model")
            st.bar_chart(df[["success", "failed"]].rename(columns={"success": "Başarılı", "failed": "Başarısız"}),
                         color=[COLOR_OK, COLOR_FAIL], stack=True, height=260)
            st.caption(" · ".join(
                f"{m['model']}: %{m['success_rate']} başarı, ort. {_fmt(m['avg_duration'], ' sn')}" for m in models))
        else:
            st.info(f"Deneme kayıtları {NOT_COLLECTED}" + (" (tanıtım kipinde deneme yapılmaz)." if demo else "."))
    with c2:
        st.markdown(f"**Ajanlara görev dağılımı{tag}**")
        dist = agent_distribution(rows)
        if dist:
            df = pd.DataFrame(dist).set_index("agent").rename(
                columns={"completed": "Tamamlandı", "failed": "Başarısız", "other": "Diğer"})
            st.bar_chart(df, color=[COLOR_OK, COLOR_FAIL, COLOR_OTHER], stack=True, height=260)
        else:
            st.info("Bu çalıştırmada görev kaydı yok.")

    measured = [r for r in rows if r["duration"] is not None]
    st.markdown(f"**Görev süreleri (sn){tag}**")
    if measured:
        st.bar_chart(pd.DataFrame({"Görev": [r["title"][:40] for r in measured],
                                   "Süre (sn)": [r["duration"] for r in measured]}).set_index("Görev"),
                     color="#4FACFE", height=240)
        left_out = len(rows) - len(measured)
        if left_out:
            st.caption(f"{left_out} görev süresi ölçülmediği için grafikte yok.")
    else:
        st.info(f"Görev süreleri {NOT_COLLECTED}.")


def render_run_dashboard(st: Any, db: Any = None, current_run_id: Optional[str] = None,
                         demo_report: Optional[Dict[str, Any]] = None) -> None:
    """
    ``db`` is ``src.master.db_manager`` (None when the engine could not be loaded).
    ``demo_report`` is the labelled demo report shown when there is no engine.
    """
    if db is None or demo_report is not None:
        st.warning("🎭 **TANITIM VERİSİ** — bu bölüm gerçek bir çalıştırma göstermiyor. Motor yüklenemediği için "
                   "örnek görev ataması kullanılıyor; süre ve deneme verisi yoktur.")
        rows = demo_rows(demo_report or {})
        _render_body(st, rows, [], run_summary(None, rows, []), demo=True)
        return

    try:
        runs = db.list_runs(limit=50)
    except Exception as exc:  # state.db missing / locked: say so, never invent numbers
        st.error(f"Çalıştırma kayıtları okunamadı (state.db): {exc}")
        return
    if not runs:
        st.info("state.db'de henüz kayıtlı çalıştırma yok. Bir gereksinim çalıştırınca burada görünür.")
        return

    ids = [r["run_id"] for r in runs]
    default = ids.index(current_run_id) if current_run_id in ids else 0
    run_id = st.selectbox("Çalıştırma (run_id)", ids, index=default,
                          format_func=lambda rid: run_label(next(r for r in runs if r["run_id"] == rid)),
                          key="telemetry-run-id")
    run = next(r for r in runs if r["run_id"] == run_id)
    tasks = db.get_tasks_for_run(run_id)
    attempts = db.get_attempts_for_run(run_id)
    rows = task_rows(tasks, attempts)

    live = run.get("system_status") == "RUNNING"
    st.success(f"🟢 **CANLI YÜRÜTME VERİSİ** · state.db · run_id `{run_id}` · durum {run.get('system_status')}"
               f" · başlangıç {local_time(run.get('started_at'))}"
               + (" (çalışma sürüyor, sayılar değişebilir)" if live else ""))
    _render_body(st, rows, attempts, run_summary(run, rows, attempts), demo=False)
