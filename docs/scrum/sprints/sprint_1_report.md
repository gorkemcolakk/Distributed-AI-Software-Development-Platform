# Sprint 1 Review Report & Retrospective

* **Sprint Period:** September 24, 2026 – October 7, 2026 (Weeks 1 – 2)
* **Sprint Goal:** Establish foundational infrastructure, document multi-agent architecture and data model, verify local Ollama models, implement the web interface prototype, and build the initial Master Agent task decomposition pipeline.
* **Status:** **COMPLETED** (Working Prototype Increment Delivered — 24 / 24 Story Points)

---

## 1. Delivered Increment & Observable Evidence

| Card ID | Deliverable Summary | Repository Evidence | Verification Outcome |
| :--- | :--- | :--- | :--- |
| **S1-01** | Repository setup, branch workflow, and launcher scripts | `README.md`, `.gitignore`, `start.bat` | Cloned and verified across team environments. |
| **S1-02** | Streamlit Web UI Prototype for requirement input & agent monitoring | `master_agent_projesi/app.py`, `requirements.txt` | Launches locally; accepts requirements and visualizes subtasks/agents. |
| **S1-03** | Multi-Agent Architecture & Component Boundaries | `docs/ARCHITECTURE.md`, `docs/SPRINTS.md` | Reviewed against source tree; planned `src/api` explicitly distinguished. |
| **S1-04** | Initial Data Model & SQLite Persistence Prototype | `docs/DATA_MODEL.md`, `src/master/db_manager.py` | ERD documented; SQLite table initialization verified. |
| **S1-05** | System Requirements Inventory & Acceptance Criteria | `docs/SRS.md`, `docs/scrum/product_backlog.md` | Requirements mapped to observable acceptance criteria and code status. |
| **S1-06** | Local Ollama Model Research & Capability Matrix | `docs/MODEL_RESEARCH.md`, `config/agents_config.json` | Team hardware and candidate Ollama tags (`qwen2.5-coder:7b`, `deepseek-coder:6.7b`, `llama3.2:3b`, `phi4-mini:3.8b`, `qwen2.5:3b`) evaluated. |
| **S1-07** | Master-Agent Orchestrator & Task Decomposition Engine | `src/master/orchestrator.py`, `analyzer.py`, `capability_eval.py`, `scheduler.py`, `tests/test_master_engine.py` | Unit tests pass; CLI decomposes requirements into 6 subtask categories and routes to top-scoring agents. |

---

## 2. Verification & Terminal Evidence
Executing `python -m src.master.orchestrator "Develop an online library management system"` and `python -m unittest discover -s tests` confirmed the baseline orchestration loop:
* `task-req-1` (*System Specification*) ➔ Routed to **Agent B** [Reasoning: 95.0]
* `task-db-1` (*Database Schema*) ➔ Routed to **Agent A** [Context: 95.0]
* `task-be-1` (*Core Backend API*) ➔ Routed to **Agent A** [Coding: 90.0]
* `task-fe-1` (*Frontend UI*) ➔ Routed to **Agent C** [Coding: 95.0]
* `task-qa-1` (*Testing & QA*) ➔ Routed to **Agent B** [Reasoning: 85.0]
* `task-int-1` (*Integration*) ➔ Routed to **Agent C** [Coding: 82.5]

---

## 3. Sprint Retrospective

### What Went Well
* The team established clear Scrum accountabilities (Product Owner, Scrum Master, Developers) and delivered both core backend orchestration and the Streamlit UI prototype in parallel.
* Architectural documentation (`ARCHITECTURE.md`) and data modeling (`DATA_MODEL.md`) provided clear contracts before deep implementation.
* Transparent inspection of the codebase allowed the team to separate working prototype features from simulated/mock behaviors early.

### Challenges & Identified Technical Debt (Inputs to Sprint 2)
1. **UI vs. Core Registry Discrepancy:** `master_agent_projesi/app.py` currently uses a hardcoded 3-agent list (`agents_data`) and single-dimension matching (`assign_best_agent`), whereas the core engine uses `config/agents_config.json` and weighted scoring (`capability_eval.py`).
2. **Duplicate API Key Loader:** `app.py` contains two `load_api_key()` definitions and needs a unified, safe demo/fallback configuration path.
3. **Unconditional Completion Status:** `scheduler.py` retains state across runs on the same instance, and `orchestrator.py` marks tasks `COMPLETED` even if an agent is unavailable or fails.

### Action Items for Sprint 2 (`S2-01` – `S2-07`)
* **S2-01 (İrem):** Remove duplicate `load_api_key()` and enforce safe demo/fallback mode.
* **S2-02 & S2-06 (Kübra):** Unify Streamlit UI and core engine under `config/agents_config.json` and bind UI status displays to real engine execution results.
* **S2-03 & S2-05 (Eren Görkem):** Enforce weighted task-fitness scoring, filter out `BUSY`/`OFFLINE`/`ERROR` agents, and isolate scheduler state per `run_id`.
* **S2-04 (Mahmut):** Add strict JSON schema validation for decomposed tasks and clearly label fallback demo outputs.
* **S2-07 (İrem & Mahmut):** Align `src/master/db_manager.py` with the unified agent registry and `run_id` lifecycle.

---

**Prepared by:** İrem Yılmaz (Scrum Master)  