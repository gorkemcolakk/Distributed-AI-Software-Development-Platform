# Sprint 5 Backlog & Task Distribution
## Distributed AI Software Development Platform (CM6453)

* **Document Owner:** İrem Yılmaz (Scrum Master & Developer)
* **Application Scope:** Distributed AI Software Development Platform — Sprint 5 Planning & Final Release
* **Framework:** Scrum (2020 Scrum Guide, 5 Sprints × 2 Weeks = 10 Weeks)
* **Sprint Number:** Sprint 5 (Final Sprint)
* **Sprint Period:** 2026-11-26 – 2026-12-10 (Weeks 9 – 10)
* **Sprint Planning Date:** 2026-11-26
* **Sprint Status:** **ACTIVE / IN PROGRESS**
* **Scrum Team Roster & Accountabilities:**
  - **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
  - **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - **Developers:**
    - Eren Görkem Çolak (Master Agent — `qwen2.5:7b`)
    - Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`)
    - Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`)
    - Berat İnan (Testing Agent — `deepseek-coder:6.7b`)
    - İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
    - Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`)

---

## 1. Commitment: Sprint Goal (Topic One: Why is this Sprint valuable?)

> *"Orchestrate an end-to-end distributed software generation pipeline with live SQLite telemetry and CSV/JSON export, render empirical local Ollama model benchmarks and run metrics in the Streamlit dashboard, harmonize all system documentation with the verified codebase, and validate the complete platform through end-to-end tests, a final project report, and a live demonstration."*

---

## 2. Selected Product Backlog Items & Owners (Topic Two: What can be done this Sprint?)

During Sprint Planning on November 26, 2026, the Developers selected 6 technical Product Backlog Items from Epic 5 (`S5-01` – `S5-06`) alongside 2 final course submission deliverables (`S5-07` and `S5-08`) with zero carry-over from Sprint 4, committing to a total capacity of **27 Story Points**:

| Card ID | PBI Title & Technical Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Initial Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S5-01** | End-to-End Distributed Workflow & Telemetry Logging (`src/master/orchestrator.py`) | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | Highest | 3 | 6h | S4-01, S4-05, S4-07 | Sprint Backlog |
| **S5-02** | Documentation & System Harmonization (`README.md`, `docs/*`, `docs/scrum/*`) | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | High | 3 | 6h | S5-01, S5-04 | Sprint Backlog |
| **S5-03** | Live Telemetry & Model Benchmark Visualizer Dashboard (`master_agent_projesi/app.py`) | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | High | 3 | 6h | S5-01, S5-04 | Sprint Backlog |
| **S5-04** | SQLite Telemetry & Benchmark Data Export (`src/master/db_manager.py`, `master_agent_projesi/run_export.py`) | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | High | 3 | 6h | S4-04, S5-01 | Sprint Backlog |
| **S5-05** | Final Demonstration Scenario & Acceptance Verification (`docs/model_tests/sample_requirement.md`) | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | Highest | 3 | 6h | S5-01, S5-03 | Sprint Backlog |
| **S5-06** | Empirical Ollama Benchmark & E2E Test Suite Validation (`scripts/master_model_benchmark.py`, `tests/`) | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | Highest | 5 | 10h | S5-01, S5-04 | Sprint Backlog |
| **S5-07** | Comprehensive Final Project Report (CM6453 Course Deliverable) | Elif Yılmaz (Lead) & Mahmut Karaalioğlu | Highest | 4 | 9h | S5-01, S5-02, S5-04, S5-06 | Sprint Backlog |
| **S5-08** | Final Project Presentation Deck & Live Demo Walkthrough | Kübra Hepcan (Lead) & Eren Görkem Çolak | Highest | 3 | 7h | S5-03, S5-05, S5-06 | Sprint Backlog |

* **Total Sprint 5 Committed Capacity:** **27 Story Points** (~56 Estimated Development & Documentation Hours)
  - **Carry-over Work:** 0 Story Points (All Sprint 4 cards `S4-01` – `S4-07` / 29 SP completed)
  - **Core Technical & Integration PBIs (`S5-01` – `S5-06`):** 20 Story Points (~40h)
  - **Final Report & Presentation Deliverables (`S5-07` – `S5-08`):** 7 Story Points (~16h)

---

## 3. Actionable Task Breakdown & Checklists (Topic Three: How will the chosen work get done?)

### S5-01: End-to-End Distributed Workflow & Telemetry Logging
- [ ] 1. Verify full end-to-end execution in `src/master/orchestrator.py` from requirement prompt through LLM decomposition, parallel worker dispatch, AST/SQL review, and workspace packaging (`workspaces/{run_id}/`).
- [ ] 2. Record per-task start/finish timestamps, execution durations, and retry/reassignment metadata cleanly in SQLite (`state.db`).
- [ ] 3. Verify distributed worker execution over HTTP REST (`src/api/worker_server.py` and `src/agents/remote_agent.py`) with Bearer Token authentication.

### S5-02: Documentation & System Harmonization
- [ ] 1. Synchronize [`README.md`](../../../README.md), [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md), [`docs/DATA_MODEL.md`](../../DATA_MODEL.md), and [`docs/SRS.md`](../../SRS.md) with the actual repository file tree and local Ollama model tags in `config/agents_config.json`.
- [ ] 2. Align [`docs/scrum/definition_of_done.md`](../definition_of_done.md), [`docs/scrum/product_backlog.md`](../product_backlog.md), and [`docs/scrum/scrum_calendar.md`](../scrum_calendar.md) with Sprint 4 completion metrics (99 SP) and Sprint 5 scope (27 SP).
- [ ] 3. Ensure all internal Markdown links point strictly to verified repository files.

### S5-03: Live Telemetry & Model Benchmark Visualizer Dashboard
- [ ] 1. Render real execution runs (`run_id`), task durations, retry/reassignment counts, and agent comparison charts in [`master_agent_projesi/app.py`](../../../master_agent_projesi/app.py).
- [ ] 2. Clearly distinguish live SQLite run telemetry from static/offline benchmark data in the UI.
- [ ] 3. Wire the run export and review panels (`master_agent_projesi/review_panel.py`, `master_agent_projesi/run_export.py`) for smooth demo navigation.

### S5-04: SQLite Telemetry & Benchmark Data Export
- [ ] 1. Implement analytical queries in [`src/master/db_manager.py`](../../../src/master/db_manager.py) aggregating run durations, agent success rates, attempt counts, and conflict records across `runs`, `tasks`, `attempts`, and `file_conflicts`.
- [ ] 2. Expose CSV and JSON export helpers in [`master_agent_projesi/run_export.py`](../../../master_agent_projesi/run_export.py) for UI download and final report tables.
- [ ] 3. Verify export integrity and schema safety with deterministic unit tests in `tests/test_run_export.py` and `tests/test_db_manager.py`.

### S5-05: Final Demonstration Scenario & Acceptance Verification
- [ ] 1. Rehearse a multi-paragraph software requirement scenario using [`docs/model_tests/sample_requirement.md`](../../model_tests/sample_requirement.md) and inspect generated artifacts in `workspaces/{run_id}/`.
- [ ] 2. Verify negative failure and recovery paths (worker timeout/offline fallback, AST syntax rejection, and file conflict handling).
- [ ] 3. Confirm all Sprint 5 acceptance criteria against the Definition of Done prior to Sprint Review.

### S5-06: Empirical Ollama Benchmark & E2E Test Suite Validation
- [ ] 1. Execute standardized local Ollama model benchmarks via [`scripts/master_model_benchmark.py`](../../../scripts/master_model_benchmark.py) and [`scripts/model_smoke_test.py`](../../../scripts/model_smoke_test.py) across team models (`qwen2.5:7b`, `qwen2.5-coder:7b`, `qwen2.5-coder:3b`, `llama3.2:3b`, `deepseek-coder:6.7b`, `phi4-mini:3.8b`).
- [ ] 2. Record empirical latency, syntax validity, and pass/fail metrics under `docs/model_tests/`.
- [ ] 3. Verify the full deterministic offline test suite (**495+ tests** across 30 test modules via `python -m unittest discover -s tests`) and green CI status in [`.github/workflows/tests.yml`](../../../.github/workflows/tests.yml).

### S5-07: Comprehensive Final Project Report (CM6453 Course Deliverable)
- [ ] 1. Compile the final engineering and academic project report covering: *Problem Statement, Multi-Agent Architecture, Versioned Contracts, DAG Scheduling, Fault Recovery & AST/SQL QA, SQLite Persistence, Empirical Benchmarks, and 5-Sprint Scrum Metrics*.
- [ ] 2. Include verified architecture diagrams, SQLite schema v5 documentation, empirical benchmark tables (`S5-04`, `S5-06`), and cumulative Scrum velocity metrics (**126 SP** across 5 sprints).
- [ ] 3. Review formatting, repository file references, and accuracy across all 6 team members before submission.

### S5-08: Final Project Presentation Deck & Live Demo Walkthrough
- [ ] 1. Prepare the final presentation slide deck covering system motivation, distributed local-LLM architecture, fault-tolerance and AST code-review highlights, telemetry/benchmark results, and Scrum process reflection.
- [ ] 2. Prepare a timed live demo walkthrough using [`docs/model_tests/sample_requirement.md`](../../model_tests/sample_requirement.md) and [`master_agent_projesi/app.py`](../../../master_agent_projesi/app.py).
- [ ] 3. Coordinate presentation speaking sections across all 6 team members for the final demonstration session.

---

## 4. Capacity & Workload Allocation Matrix

| Developer | Student ID | Agent & Model | Assigned Cards | Total SP | Est. Hours | Primary Technical & Deliverable Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | S5-01, S5-08 (Co) | 4.5 SP | 9.5h | End-to-end orchestrator telemetry & presentation technical walkthrough |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | S5-02 | 3 SP | 6h | Documentation/Scrum harmonization & Scrum Master facilitation |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | S5-03, S5-08 (Lead) | 4.5 SP | 9.5h | Streamlit telemetry visualizer & **Presentation Deck Lead** |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | S5-04, S5-07 (Co) | 5 SP | 10.5h | SQLite telemetry queries/export & **Final Project Report Co-Owner** |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | S5-06 | 5 SP | 10h | Empirical Ollama model benchmarks & full E2E test suite validation |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | S5-05, S5-07 (Lead) | 5 SP | 10.5h | Demo acceptance verification & **Final Project Report Lead** |

---

## 5. Definition of Done Compliance & Verification Strategy

All selected items must satisfy the [Definition of Done](../definition_of_done.md) before presentation at the Sprint 5 Review:
- [ ] **Working Software:** Complete end-to-end pipeline executes cleanly and writes verified artifacts to `workspaces/{run_id}/`.
- [ ] **Deterministic Testing:** All **495+ offline unit and integration tests** pass (`python -m unittest discover -s tests`).
- [ ] **CI Quality Gate:** GitHub Actions workflow ([`.github/workflows/tests.yml`](../../../.github/workflows/tests.yml)) passes cleanly on `main` and all feature/docs branches.
- [ ] **Honest Reporting & Sandboxing:** Live vs. fallback data clearly labeled in the UI; file writes strictly confined to `workspaces/{run_id}/`; zero hardcoded secrets.
- [ ] **Course Deliverables Completed:** Final Project Report (`S5-07`) and Presentation Deck (`S5-08`) reviewed by all team members and ready for final submission.

---

**Plan Created By:** Scrum Team at Sprint 5 Planning (Nov 26, 2026)  
**Facilitated By:** İrem Yılmaz (Scrum Master)