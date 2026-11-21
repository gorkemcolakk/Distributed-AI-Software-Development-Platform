# Sprint 2 Backlog & Task Distribution

* **Sprint Period:** 2026-10-15 – 2026-10-29 (Weeks 3 – 4)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Status:** **COMPLETED** (Closed on 2026-10-22; 6 of 6 cards completed, 22 SP delivered)

---

## 1. Commitment: Sprint Goal (Why)

> *"Standardize API key and safe fallback configuration, unify the Streamlit UI and core Master Agent engine under a single canonical agent registry (`config/agents_config.json`), enforce weighted capability-based agent selection with availability filtering (`BUSY`/`OFFLINE`/`ERROR`), validate task decomposition JSON schemas, and isolate per-run scheduler and SQLite persistence states (`run_id`)."*

---

## 2. Selected Product Backlog Items & Owners (What & Who - At Sprint Planning)

During Sprint Planning on Oct 15, 2026, the Developers selected the following 6 items from the Product Backlog (1 primary owner per team member), assigned primary owners, and mapped estimated hours:

| Card ID | Task Title & Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Standardize Backend API / Local Ollama Config & Establish Safe Fallback Logic (`app.py`, `agents_config.json`, `.env.example`) | İrem Yılmaz (Backend Agent) | Highest | 3 | 4h | S1-06 | **Done** |
| **S2-02** | Bind Streamlit UI to Canonical Agent Registry & Real Engine Status Monitoring (`app.py`, `config/agents_config.json`) | Kübra Hepcan (Frontend Agent) | Highest | 5 | 10h | S1-06, S2-01 | **Done** |
| **S2-03** | Implement Weighted Agent Selection, Availability Filtering & Scheduler Lifecycle (`capability_eval.py`, `scheduler.py`, `orchestrator.py`) | Eren Görkem Çolak (Master Agent) | Highest | 5 | 10h | S2-02, S1-06 | **Done** |
| **S2-04** | Validate Task Classification Output Against Schema & Define Inter-Agent Integration Contract (`analyzer.py`, `integration_agent.py`) | Elif Yılmaz (Integration Agent) | High | 3 | 6h | S2-01, S2-02, S1-05 | **Done** |
| **S2-05** | Integrate SQLite Persistence Layer (`db_manager.py`) with Agent Capability Profiles & `run_id` Task States (`DATA_MODEL.md`) | Mahmut Karaalioğlu (Database Agent) | High | 3 | 8h | S1-04, S2-02, S2-03 | **Done** |
| **S2-06** | Develop Automated Unit Tests (Pytest/Unittest) for Agent Selection, Schema Validation & Scheduler (`tests/test_master_engine.py`) | Berat İnan (Testing & QA Agent) | High | 3 | 6h | S2-03, S2-04, S2-05 | **Done** |

* **Total Sprint 2 Capacity:** **22 Story Points** (44 Estimated Development Hours)
* **Ownership Notes:** Each of the 6 developers owned one end-to-end deliverable card on the Trello board (`S2-01` through `S2-06`), with İrem Yılmaz supporting Mahmut Karaalioğlu on SQLite integration (`S2-05`).

---

## 3. Actionable Task Breakdown & Checklists (How - At Sprint Planning)

### S2-01: Backend API / Local Ollama Config & Safe Fallback Standardization
- [x] Consolidate duplicate `load_api_key()` functions in `app.py` into a single central configuration loader.
- [x] Purge hardcoded dummy credentials from source code; document `.env` usage via `.env.example`.
- [x] Implement graceful offline fallback without process crashing on HTTP 429 quota exhaustion, connection timeouts, or offline Ollama server.
- [x] Author unit tests verifying fallback behavior in `tests/test_api_config_fallback.py`.

### S2-02: Canonical Agent Registry UI & Live Status Monitoring Binding
- [x] Remove hardcoded 3-agent `agents_data` array in `app.py` and bind UI agent rendering to `config/agents_config.json`.
- [x] Remove manual "Start/Complete" mock buttons and connect "Analyze" button to trigger real `MasterOrchestrator` execution.
- [x] Display live agent/task statuses (`IDLE`, `BUSY`, `OFFLINE`, `COMPLETED`, `FAILED`, `BLOCKED`) and real progress indicators in UI.
- [x] Visually distinguish fallback/demo mode data from live execution results in the interface.

### S2-03: Weighted Capability Scoring, Availability Filtering & Scheduler Lifecycle
- [x] Implement `calculate_fit_score` using category weights (Coding: 0.40, Reasoning: 0.35, Context: 0.25) and specialty bonus (+5.0).
- [x] Filter out `BUSY`, `OFFLINE`, and `ERROR` agents from the candidate selection pool.
- [x] Generate isolated `run_id` for every orchestrator run and reset scheduler state between consecutive executions.
- [x] Never mark failed or unassigned tasks as `COMPLETED`; explicitly report `FAILED`, `BLOCKED`, or `UNASSIGNED`.

### S2-04: Task Classification Schema Validation & Inter-Agent Contract
- [x] Define Pydantic models and required JSON schema fields (`task_id`, `title`, `category`, `dependencies`) for decomposed subtasks in `src/contracts.py` and `analyzer.py`.
- [x] Enforce standard multi-stage task decomposition and validate with multi-paragraph requirement inputs.
- [x] Catch empty input and malformed LLM JSON payloads gracefully without system exception.
- [x] Define baseline output contract fields expected by `IntegrationAgent`.

### S2-05: SQLite Persistence Layer & `run_id` State Integration
- [x] Implement `runs`, `agents`, `tasks`, and `attempts` tables with WAL mode in `src/master/db_manager.py` aligned with `config/agents_config.json` capability profiles.
- [x] Implement 3-layer protection against false `COMPLETED` records (Python check, SQLite `CHECK` constraint, database trigger).
- [x] Verify clean initialization (`CREATE TABLE IF NOT EXISTS`) on first run and exclude `state.db` via `.gitignore`.
- [x] Synchronize `docs/DATA_MODEL.md` with updated SQLite table schemas.

### S2-06: Automated Unit Tests (Pytest/Unittest) & Local Model Verification
- [x] Write unit tests for `calculate_fit_score` weights and specialty bonus calculations in `tests/test_master_engine.py`.
- [x] Add test scenarios verifying exclusion of `BUSY` and `OFFLINE` agents during selection.
- [x] Implement negative test cases for malformed JSON inputs, empty requirements, and sequential `run_id` isolation.
- [x] Verify all tests pass offline without live API keys via `python -m unittest discover -s tests` and complete local Ollama hardware/model verification matrix.

---

## 4. Definition of Done Compliance
All 6 Sprint 2 deliverables were verified against the [Definition of Done](../definition_of_done.md). The automated test suite (`python -m unittest discover tests`) passed with 44/44 tests green on `main`.