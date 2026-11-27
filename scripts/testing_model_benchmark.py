"""
S5-06 (Berat İnan): Testing Agent model benchmark + E2E check.

Every model gets the SAME fixed task set and the SAME prompts: for each scenario the TestingAgent
(src/agents/testing_agent.py, i.e. the production prompt, contract check and retry) writes pytest
tests for a fixed shared contract, with the code excerpt of a known-good reference backend as
context (like the orchestrator sends it). The accepted tests are then run against that backend
with src/master/generated_tests.py.

Measured per model:
  - duration of each generation (seconds, includes the validation retry)
  - valid output rate: share of tasks where the agent returned an accepted test file
  - first-attempt rate: share of tasks accepted without a validation retry
  - generated-test pass rate: passed / executed tests against the reference backend
These are compared with the estimated capability scores in config/agents_config.json.

--e2e runs the whole Master pipeline once on docs/model_tests/sample_requirement.md
(MASTER_SMOKE_TEST=true, so the smoke test and the generated-test pass rate are included).

Usage:
  python scripts/testing_model_benchmark.py --model deepseek-coder:6.7b
  python scripts/testing_model_benchmark.py --model deepseek-coder:6.7b --model qwen2.5-coder:3b --repeats 2
  python scripts/testing_model_benchmark.py --model deepseek-coder:6.7b --e2e

Outputs docs/model_tests/testing_benchmark_<YYYYMMDD>.json and .md.
Note: it runs model-written tests on this machine (in a temporary copy).
"""

import argparse
import json
import os
import platform
import shutil
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.testing_agent import TestingAgent  # noqa: E402
from src.master import generated_tests  # noqa: E402

EXCERPT_CHARS = 1500  # same limit the orchestrator uses (TEST_CONTEXT_MAX_CHARS)
TASK_DESCRIPTION = ("Write 3 concise pytest tests (under 40 lines) for the backend endpoints of the shared contract, "
                    "using fastapi.testclient.TestClient. Call only endpoints listed in the contract, with its request "
                    "fields, and create test data through those endpoints. The backend module is main.py "
                    "(from main import app).")

SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "books",
        "title": "Library API tests",
        "contract": {"entities": [{"name": "Book", "table": "books", "fields": ["title", "author", "year"]}],
                     "endpoints": [
                         {"method": "POST", "path": "/books", "request": ["title", "author", "year"], "response": "Book"},
                         {"method": "GET", "path": "/books", "request": [], "response": "list of Book"},
                         {"method": "GET", "path": "/books/{book_id}", "request": [], "response": "Book"},
                         {"method": "DELETE", "path": "/books/{book_id}", "request": [], "response": "ok"}]},
        "backend": '''import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY, title TEXT, author TEXT, year INTEGER)")

class Book(BaseModel):
    id: Optional[int] = None
    title: str
    author: str
    year: int

def row(r):
    return {"id": r[0], "title": r[1], "author": r[2], "year": r[3]}

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

@app.post("/books")
def create_book(book: Book):
    cur = db.execute("INSERT INTO books (title, author, year) VALUES (?, ?, ?)", (book.title, book.author, book.year))
    db.commit()
    return {"id": cur.lastrowid, "title": book.title, "author": book.author, "year": book.year}

@app.get("/books")
def list_books():
    return [row(r) for r in db.execute("SELECT * FROM books")]

@app.get("/books/{book_id}")
def get_book(book_id: int):
    r = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Book not found")
    return row(r)

@app.delete("/books/{book_id}")
def delete_book(book_id: int):
    if db.execute("DELETE FROM books WHERE id = ?", (book_id,)).rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    db.commit()
    return {"ok": True}
''',
    },
    {
        "id": "events_tickets",
        "title": "Event ticketing API tests",
        "contract": {"entities": [{"name": "Event", "table": "events", "fields": ["name", "date", "capacity"]},
                                  {"name": "Ticket", "table": "tickets", "fields": ["event_id", "buyer"]}],
                     "endpoints": [
                         {"method": "POST", "path": "/events", "request": ["name", "date", "capacity"], "response": "Event"},
                         {"method": "GET", "path": "/events", "request": [], "response": "list of Event"},
                         {"method": "POST", "path": "/tickets", "request": ["event_id", "buyer"], "response": "Ticket"},
                         {"method": "GET", "path": "/tickets", "request": [], "response": "list of Ticket"}]},
        "backend": '''import sqlite3
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, name TEXT, date TEXT, capacity INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, event_id INTEGER, buyer TEXT)")

class Event(BaseModel):
    id: Optional[int] = None
    name: str
    date: str
    capacity: int

class Ticket(BaseModel):
    id: Optional[int] = None
    event_id: int
    buyer: str

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

@app.post("/events")
def create_event(event: Event):
    cur = db.execute("INSERT INTO events (name, date, capacity) VALUES (?, ?, ?)", (event.name, event.date, event.capacity))
    db.commit()
    return {"id": cur.lastrowid, "name": event.name, "date": event.date, "capacity": event.capacity}

@app.get("/events")
def list_events():
    return [{"id": r[0], "name": r[1], "date": r[2], "capacity": r[3]} for r in db.execute("SELECT * FROM events")]

@app.post("/tickets")
def buy_ticket(ticket: Ticket):
    cur = db.execute("INSERT INTO tickets (event_id, buyer) VALUES (?, ?)", (ticket.event_id, ticket.buyer))
    db.commit()
    return {"id": cur.lastrowid, "event_id": ticket.event_id, "buyer": ticket.buyer}

@app.get("/tickets")
def list_tickets():
    return [{"id": r[0], "event_id": r[1], "buyer": r[2]} for r in db.execute("SELECT * FROM tickets")]
''',
    },
    {
        "id": "todos",
        "title": "Todo list API tests",
        "contract": {"entities": [{"name": "Todo", "table": "todos", "fields": ["title", "completed"]}],
                     "endpoints": [
                         {"method": "POST", "path": "/todos", "request": ["title", "completed"], "response": "Todo"},
                         {"method": "GET", "path": "/todos", "request": [], "response": "list of Todo"},
                         {"method": "PUT", "path": "/todos/{todo_id}", "request": ["title", "completed"], "response": "Todo"}]},
        "backend": '''import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, title TEXT, completed INTEGER)")

class Todo(BaseModel):
    id: Optional[int] = None
    title: str
    completed: bool

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

@app.post("/todos")
def create_todo(todo: Todo):
    cur = db.execute("INSERT INTO todos (title, completed) VALUES (?, ?)", (todo.title, int(todo.completed)))
    db.commit()
    return {"id": cur.lastrowid, "title": todo.title, "completed": todo.completed}

@app.get("/todos")
def list_todos():
    return [{"id": r[0], "title": r[1], "completed": bool(r[2])} for r in db.execute("SELECT * FROM todos")]

@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo: Todo):
    cur = db.execute("UPDATE todos SET title = ?, completed = ? WHERE id = ?", (todo.title, int(todo.completed), todo_id))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"id": todo_id, "title": todo.title, "completed": todo.completed}
''',
    },
]


def excerpt(code: str) -> str:
    return code[:EXCERPT_CHARS] + ("\n# ... (truncated)" if len(code) > EXCERPT_CHARS else "")


def run_case(model: str, scenario: Dict[str, Any], repeat: int, timeout: float) -> Dict[str, Any]:
    task = {
        "task_id": f"bench-{scenario['id']}-{repeat}",
        "title": scenario["title"],
        "description": TASK_DESCRIPTION,
        "category": "TESTING",
        "context_artifacts": {"shared_contract": scenario["contract"],
                              "code_under_test": {"main.py": excerpt(scenario["backend"])}},
    }
    agent = TestingAgent(model_name=model, use_ollama=True, fallback_enabled=False, timeout=timeout)
    started = time.perf_counter()
    result = agent.execute_task(task)
    duration = round(time.perf_counter() - started, 2)
    case: Dict[str, Any] = {"scenario": scenario["id"], "repeat": repeat, "duration_s": duration,
                            "status": result.status, "error": result.error_message}
    art = result.output_artifacts or {}
    if result.status != "SUCCESS":
        return case
    case.update(validation_retries=art.get("validation_retries", 0), test_functions=art.get("test_function_count"),
                endpoints_called=art.get("endpoints_called"))
    with tempfile.TemporaryDirectory(prefix="bench-") as tmp:
        ws = Path(tmp)
        (ws / "main.py").write_text(scenario["backend"], encoding="utf-8")
        (ws / "test_generated.py").write_text(art["files"][0]["content"], encoding="utf-8")
        run = generated_tests.run_generated_tests(ws)
    case["generated_tests"] = {k: run.get(k) for k in ("status", "passed", "failed", "errors", "total", "pass_rate")}
    case["failed_tests"] = [{"name": c["name"], "message": c["message"]} for c in run.get("cases") or []
                            if c["outcome"] in ("failed", "error")]
    return case


def summarize(model: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [c for c in cases if c["status"] == "SUCCESS"]
    passed = sum(c["generated_tests"]["passed"] or 0 for c in ok)
    total = sum(c["generated_tests"]["total"] or 0 for c in ok)
    return {
        "model": model,
        "tasks": len(cases),
        "valid_output_rate": round(len(ok) / len(cases), 4) if cases else None,
        "first_attempt_rate": round(sum(1 for c in ok if c.get("validation_retries") == 0) / len(cases), 4) if cases else None,
        "median_duration_s": round(statistics.median(c["duration_s"] for c in cases), 2) if cases else None,
        "generated_tests_passed": passed,
        "generated_tests_total": total,
        "generated_test_pass_rate": round(passed / total, 4) if total else None,
        "fully_passing_suites": sum(1 for c in ok if c["generated_tests"]["status"] == "PASSED"),
    }


def estimated_scores(model: str) -> Optional[Dict[str, Any]]:
    config = json.loads((ROOT / "config" / "agents_config.json").read_text(encoding="utf-8"))
    for agent in config.get("agents", []):
        if agent.get("model") == model:
            return {"agent": agent["name"], "capabilities": agent.get("capabilities"),
                    "provenance": agent.get("capability_provenance")}
    return None


def compare_with_config(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Measured proxies on the 0-100 scale next to the estimated scores (not written back to the config)."""
    est = estimated_scores(summary["model"])
    rate = summary["generated_test_pass_rate"]
    measured = {
        # coding: does the code the model writes run and pass against a correct backend?
        "coding_proxy": None if rate is None else round(100 * (summary["valid_output_rate"] or 0) * rate, 1),
        # reasoning: does it follow the contract and status rules without being corrected?
        "reasoning_proxy": None if summary["first_attempt_rate"] is None else round(100 * summary["first_attempt_rate"], 1),
    }
    out = {"model": summary["model"], "estimated": est, "measured": measured}
    if est and est.get("capabilities"):
        caps = est["capabilities"]
        out["difference"] = {
            "coding": None if measured["coding_proxy"] is None else round(measured["coding_proxy"] - caps["coding"], 1),
            "reasoning": None if measured["reasoning_proxy"] is None else round(measured["reasoning_proxy"] - caps["reasoning"], 1),
        }
    return out


def run_e2e(requirement_path: Path, testing_model: str) -> Dict[str, Any]:
    """One full Master run with the smoke test and generated-test pass rate switched on."""
    from src.agents.backend_agent import BackendAgent
    from src.agents.database_agent import DatabaseAgent
    from src.agents.frontend_agent import FrontendAgent
    from src.agents.integration_agent import IntegrationAgent
    from src.master.capability_eval import CapabilityEvaluator
    from src.master.orchestrator import MasterOrchestrator
    os.environ["MASTER_SMOKE_TEST"] = "true"
    text = requirement_path.read_text(encoding="utf-8")
    # The five local agents with their default models (agents_config.json); a model that is not
    # installed falls back to its labelled template, the Testing Agent runs on the benchmarked model.
    evaluator = CapabilityEvaluator()
    for agent in (FrontendAgent(), BackendAgent(), DatabaseAgent(), TestingAgent(model_name=testing_model),
                  IntegrationAgent()):
        evaluator.register_agent(agent)
    with tempfile.TemporaryDirectory(prefix="bench-e2e-") as tmp:
        started = time.perf_counter()
        orch = MasterOrchestrator(evaluator=evaluator, db_path=os.path.join(tmp, "state.db"),
                                  workspace_root=os.path.join(tmp, "ws"), write_artifacts=True)
        report = orch.process_requirement(text, "Sample requirement (S5-06 E2E)")
        duration = round(time.perf_counter() - started, 2)
    decomposition = report.get("decomposition") or {}
    tasks = [{"task_id": a["task_id"], "status": a["status"], "agent": a.get("assigned_agent"),
              "model": a.get("model_used"), "seconds": a.get("execution_time_seconds"),
              "reason": None if a["status"] == "COMPLETED" else a.get("reason")}
             for a in report["task_assignments"]]
    smoke = report.get("smoke_test") or {}
    gen = report.get("generated_tests") or {}
    return {"requirement": str(requirement_path.relative_to(ROOT)).replace("\\", "/"), "duration_s": duration,
            "system_status": report["system_status"], "status_counts": report["status_counts"],
            "decomposition_mode": decomposition.get("mode"),
            "shared_contract": bool(decomposition.get("shared_contract")), "tasks": tasks,
            "smoke_test": {"status": smoke.get("status"), "reason": smoke.get("reason"),
                           "checks": [f"{c['method']} {c['path']} -> {c['status_code']}" for c in smoke.get("checks") or []]},
            "generated_tests": dict({k: gen.get(k) for k in ("status", "reason", "passed", "total", "pass_rate", "model_used")},
                                    failed_tests=[{"name": c["name"], "message": c["message"]} for c in gen.get("cases") or []
                                                  if c["outcome"] in ("failed", "error")])}


def pct(value: Optional[float]) -> str:
    return "—" if value is None else f"%{value * 100:.0f}"


def write_markdown(path: Path, data: Dict[str, Any]):
    lines = [f"# Testing Agent model kıyaslaması ({data['date']})", "",
             f"Betik: `scripts/testing_model_benchmark.py` · Görev kümesi: {len(SCENARIOS)} senaryo × "
             f"{data['repeats']} tekrar · Donanım: {data['hardware']}", "",
             "## Özet", "",
             "| Model | Görev | Geçerli çıktı | İlk denemede kabul | Medyan süre | Üretilen test geçme oranı | Tamamı geçen paket |",
             "|---|---|---|---|---|---|---|"]
    for s in data["summary"]:
        lines.append(f"| {s['model']} | {s['tasks']} | {pct(s['valid_output_rate'])} | {pct(s['first_attempt_rate'])} | "
                     f"{s['median_duration_s']} sn | {pct(s['generated_test_pass_rate'])} "
                     f"({s['generated_tests_passed']}/{s['generated_tests_total']}) | {s['fully_passing_suites']} |")
    lines += ["", "## Tahmini puanlarla karşılaştırma (config/agents_config.json)", "",
              "Ölçülen değerler 0-100 ölçeğine çevrilmiş vekil metriklerdir: kodlama ≈ geçerli çıktı oranı × test "
              "geçme oranı, akıl yürütme ≈ ilk denemede kabul oranı (sözleşme ve durum kodu kurallarına "
              "düzeltme gerekmeden uyma). Yapılandırmadaki puanlar değiştirilmedi.", "",
              "| Model | Kodlama (tahmini → ölçülen) | Fark | Akıl yürütme (tahmini → ölçülen) | Fark |",
              "|---|---|---|---|---|"]
    for c in data["config_comparison"]:
        est = (c.get("estimated") or {}).get("capabilities") or {}
        diff = c.get("difference") or {}
        lines.append(f"| {c['model']} | {est.get('coding', '—')} → {c['measured']['coding_proxy']} | {diff.get('coding', '—')} | "
                     f"{est.get('reasoning', '—')} → {c['measured']['reasoning_proxy']} | {diff.get('reasoning', '—')} |")
    lines += ["", "## Görev ayrıntıları", "",
              "| Model | Senaryo | Tekrar | Durum | Süre | Yeniden deneme | Testler (geçen/çalışan) | Not |",
              "|---|---|---|---|---|---|---|---|"]
    for model, cases in data["cases"].items():
        for c in cases:
            gen = c.get("generated_tests") or {}
            note = (c.get("error") or "")[:120] or "; ".join(f"{f['name']}: {(f['message'] or '')[:80]}"
                                                            for f in c.get("failed_tests") or [])[:160]
            lines.append(f"| {model} | {c['scenario']} | {c['repeat']} | {c['status']} | {c['duration_s']} sn | "
                         f"{c.get('validation_retries', '—')} | {gen.get('passed', '—')}/{gen.get('total', '—')} | "
                         f"{note.replace('|', '/')} |")
    if data.get("e2e"):
        e = data["e2e"]
        lines += ["", "## Uçtan uca (E2E) doğrulama", "",
                  f"Gereksinim: `{e['requirement']}` · Süre: {e['duration_s']} sn · Sistem durumu: **{e['system_status']}** · "
                  f"Ayrıştırma: {e['decomposition_mode']}", "",
                  f"- Görev durumları: {e['status_counts']}",
                  f"- Ortak sözleşme: {'var' if e.get('shared_contract') else 'yok (sabit şablon ayrıştırma sözleşme üretmez)'}",
                  f"- Duman testi: {e['smoke_test']['status']} ({e['smoke_test']['reason']})"
                  + (f": {', '.join(e['smoke_test'].get('checks') or [])}" if e['smoke_test'].get('checks') else ""),
                  f"- Üretilen testler: {e['generated_tests']['status']} ({e['generated_tests']['reason']}), "
                  f"test modeli: {e['generated_tests']['model_used']}"]
        for f in e["generated_tests"].get("failed_tests") or []:
            lines.append(f"  - `{f['name']}`: {(f['message'] or '').replace('|', '/')[:200]}")
        lines += ["",
                  "| Görev | Durum | Ajan | Model | Süre (sn) | Not |", "|---|---|---|---|---|---|"]
        for t in e["tasks"]:
            lines.append(f"| {t['task_id']} | {t['status']} | {t['agent']} | {t['model']} | {t['seconds']} | "
                         f"{(t['reason'] or '').replace('|', '/')[:120]} |")
    if data.get("test_suite"):
        lines += ["", "## Otomatik test paketi", "", data["test_suite"]]
    lines += ["", "## Sınırlar", ""] + [f"- {n}" for n in data["limitations"]] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", required=True, help="Ollama model tag (repeatable)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("OLLAMA_TIMEOUT", "300")))
    parser.add_argument("--e2e", action="store_true", help="also run one full Master pipeline")
    parser.add_argument("--requirement", default=str(ROOT / "docs" / "model_tests" / "sample_requirement.md"))
    parser.add_argument("--test-suite", default="", help="one-line result of the unittest suite to include")
    parser.add_argument("--note", action="append", default=[], help="extra limitation line for the report")
    parser.add_argument("--out", default=None, help="output path without extension")
    args = parser.parse_args()

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    cases: Dict[str, List[Dict[str, Any]]] = {}
    for model in args.model:
        cases[model] = []
        for scenario in SCENARIOS:
            for repeat in range(1, args.repeats + 1):
                print(f"[{model}] {scenario['id']} #{repeat} ...", flush=True)
                case = run_case(model, scenario, repeat, args.timeout)
                gen = case.get("generated_tests") or {}
                print(f"    {case['status']} in {case['duration_s']}s, retries={case.get('validation_retries')}, "
                      f"tests {gen.get('passed')}/{gen.get('total')} {case.get('error') or ''}", flush=True)
                cases[model].append(case)

    summary = [summarize(m, c) for m, c in cases.items()]
    data = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "script": "scripts/testing_model_benchmark.py",
        "repeats": args.repeats,
        "hardware": f"{platform.system()} {platform.release()}, {os.cpu_count()} mantıksal çekirdek, Python {platform.python_version()}",
        "ollama_options": {"temperature": 0.1, "seed": 42, "num_predict": 1024},
        "scenarios": [s["id"] for s in SCENARIOS],
        "summary": summary,
        "config_comparison": [compare_with_config(s) for s in summary],
        "cases": cases,
        "test_suite": args.test_suite,
        "limitations": [
            "temperature 0.1 + seed 42: aynı makinede sonuçlar büyük ölçüde tekrarlanabilir, farklı donanımda süreler değişir.",
            "Ölçülen vekil metrikler yalnızca test yazma görevini kapsar; yapılandırmadaki genel yetenek puanlarının yerine geçmez.",
        ] + args.note,
    }
    if args.e2e:
        print("[e2e] running the Master pipeline ...", flush=True)
        data["e2e"] = run_e2e(Path(args.requirement), args.model[0])
        print(f"    {data['e2e']['system_status']} in {data['e2e']['duration_s']}s", flush=True)

    out = Path(args.out) if args.out else ROOT / "docs" / "model_tests" / f"testing_benchmark_{date}"
    out.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(out.with_suffix(".md"), data)
    print(f"Wrote {out.with_suffix('.json')} and {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
