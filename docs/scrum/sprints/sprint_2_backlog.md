# Sprint 2 Backlog & Task Distribution

* **Sprint Period:** 2026-10-08 – 2026-10-21 (Weeks 3 – 4)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Status:** **COMPLETED** (Closed on 2026-10-22; 6 of 6 cards completed, 22 SP delivered)

---

## 1. Commitment: Sprint Goal (Why)

> *"Standardize API key and safe fallback configuration, unify the Streamlit UI and core Master Agent engine under a single canonical agent registry (`config/agents_config.json`), enforce weighted capability-based agent selection with availability filtering (`BUSY`/`OFFLINE`/`ERROR`), validate task decomposition JSON schemas, and isolate per-run scheduler and SQLite persistence states (`run_id`)."*

---

## 2. Selected Product Backlog Items & Owners (What & Who - At Sprint Planning)

During Sprint Planning on Oct 08, 2026, the Developers selected the following items from the Product Backlog, assigned primary owners, and mapped estimated hours:

| Card ID | Task Title & Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Fix API Key Config, Remove Duplicate Loaders & Enforce Safe Fallbacks (`app.py`, `.env.example`) | İrem Yılmaz (Backend Agent) | Highest | 3 | 4h | S1-06 | **Done** |
| **S2-02** | Unify Streamlit UI and Core Engine Under Canonical Registry (`config/agents_config.json`) | Kübra Hepcan (Frontend Agent) | Highest | 5 | 10h | S1-06, S2-01 | **Done** (#20) |
| **S2-03** | Weighted Task-Fitness Scoring & Availability Filtering (`src/master/capability_eval.py`) | Eren Görkem Çolak (Master Agent) | High | 3 | 6h | S2-02, S1-06 | **Done** |
| **S2-04** | Validate Task Decomposition Output & Harden Fallback Template (`src/contracts.py`) | Elif Yılmaz (Integration Agent) | High | 3 | 6h | S2-01, S2-02, S1-05 | **Done** |
| **S2-05** | Fix Scheduler Lifecycle (`run_id`) & Accurately Report Failed/Unassigned Tasks (`scheduler.py`) | Eren Görkem Çolak (Master Agent) | Highest | 3 | 8h | S2-03, S2-04 | **Done** |
| **S2-06** | Bind UI Task Assignments, Progress & Status Monitoring to Real Results (`app.py`) | Kübra Hepcan (Frontend Agent) | High | 3 | 6h | S2-02, S2-03, S2-05 | **Done** (#20, #24) |
| **S2-07** | Integrate SQLite Persistence (`db_manager.py`) with Unified Registry & `run_id` Lifecycle | Mahmut Karaalioğlu (Database Agent) | High | 2 | 4h | S1-04, S2-02, S2-05 | **Done** |

* **Total Sprint 2 Capacity:** **22 Story Points** (44 Estimated Development Hours)
* **Ownership Adjustments during Sprint:** S2-04 ownership transferred to Elif Yılmaz; S2-07 persistence task completed by Mahmut Karaalioğlu in coordination with S2-05. Berat İnan authored the comprehensive automated unit test suite (`tests/test_master_engine.py`, `tests/test_db_manager.py`).

---

## 3. Actionable Task Breakdown & Checklists (How - At Sprint Planning)

### S2-01: API Key & Fallback Standardization
- [x] Consolidate duplicate `load_api_key()` functions in `app.py` into a single central loader.
- [x] Purge hardcoded dummy credentials from source code; document `.env` usage via `.env.example`.
- [x] Implement graceful offline fallback without process crashing on HTTP 429 quota exhaustion, connection timeouts, or offline Ollama server.
- [x] Author unit tests verifying fallback behavior in `tests/test_api_config_fallback.py`.

### S2-02: Canonical Agent Registry UI Integration
- [x] Remove hardcoded 3-agent `agents_data` array in `app.py`.
- [x] Bind UI agent rendering to `config/agents_config.json`.
- [x] Display member names, assigned Ollama models, and capability dimensions accurately.

### S2-03: Weighted Capability Scoring & Status Filtering
- [x] Implement `calculate_fit_score` using category weights (Coding: 0.40, Reasoning: 0.35, Context: 0.25).
- [x] Filter out `BUSY`, `OFFLINE`, and `ERROR` agents from the candidate selection pool.
- [x] Add specialty bonus (+5.0) for matching agent domain specialties.
- [x] Write deterministic unit tests covering candidate selection logic.

### S2-04: Task Schema Validation
- [x] Define Pydantic models for decomposed subtasks (`TaskPayloadContract_v1`) in `src/contracts.py`.
- [x] Enforce standard 5-stage task structure (Requirements, DB, Backend, Frontend, Testing/Integration).
- [x] Catch empty input and malformed JSON payloads gracefully without system exception.

### S2-05: Scheduler Lifecycle & Status Integrity
- [x] Generate isolated `run_id` for every orchestrator run.
- [x] Reset scheduler state between consecutive executions on the same instance.
- [x] Never mark failed or unassigned tasks as `COMPLETED`; explicitly report `FAILED`, `BLOCKED`, or `UNASSIGNED`.

### S2-06: UI Live Status Binding
- [x] Remove manual "Start/Complete" mock buttons from `app.py`.
- [x] Connect "Analyze" button to trigger real `MasterOrchestrator` execution.
- [x] Display real-time progress indicators and backend execution states in UI.

### S2-07: SQLite Persistence Integration
- [x] Implement `runs`, `agents`, `tasks`, and `attempts` tables with WAL mode in `src/master/db_manager.py`.
- [x] Implement 3-layer protection against false `COMPLETED` records (Python check, SQLite `CHECK` constraint, database trigger).
- [x] Persist UI execution runs to `state.db`; exclude `state.db` via `.gitignore`.

---

## 4. Definition of Done Compliance
All 6 Sprint 2 deliverables were verified against the [Definition of Done](../definition_of_done.md). The automated test suite (`python -m unittest discover tests`) passed with 44/44 tests green on `main`.
