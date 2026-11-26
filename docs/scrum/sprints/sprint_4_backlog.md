# Sprint 4 Backlog & Task Distribution

* **Sprint Period:** 2026-11-12 – 2026-11-26 (Weeks 7 – 8)
* **Sprint Planning Date:** 2026-11-12
* **Sprint Review Date:** 2026-11-26
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Status:** **COMPLETED (7 of 7 Done — 29 / 29 SP)**

---

## 1. Commitment: Sprint Goal (Topic One: Why is this Sprint valuable?)

> *"Implement bounded task retry and automatic failover reassignment for failed tasks, build automated Python AST syntax and LLM code review into the Integration Agent, resolve file path and schema conflicts with SQLite attempt history persistence, and enforce a deterministic CI quality gate on GitHub Actions."*

---

## 2. Selected Product Backlog Items & Owners (Topic Two: What can be done this Sprint?)

During Sprint Planning on November 12, 2026, the Developers selected 6 Product Backlog Items from Epic 4 (no carry-over from Sprint 3), committed to an initial capacity of **24 Story Points**, and later accepted **S4-07** (5 SP) mid-sprint to connect the Master Agent analyzer to local Ollama (`qwen2.5:7b`) with parallel task dispatch:

| Card ID | PBI Title & Technical Scope | Primary Assignee | Priority | Story Points | Est. Hours | Final Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S4-01** | Bounded Retry Mechanism & Automatic Alternative Agent Reassignment | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | Highest | 5 | 8h | **Done** |
| **S4-02** | Error Detection, Transient/Permanent Error Classification & Security Hardening | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | High | 3 | 8h | **Done** |
| **S4-03** | UI Display of Code Review Findings, Conflict Alerts & Reassignment History | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | High | 3 | 8h | **Done** |
| **S4-04** | File Path/Schema Conflict Resolution & SQLite Attempt History Persistence | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | High | 3 | 8h | **Done** |
| **S4-05** | Automated Python AST Syntax / Code Review & Integrated Packaging | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | Highest | 5 | 10h | **Done** |
| **S4-06** | Automated Test Expansion, Generated Code Tests & GitHub Actions CI Quality Gate | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | Highest | 5 | 10h | **Done** |
| **S4-07** | Master Agent Local Model Task Decomposition & Inter-Agent Shared Contract | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | Highest | 5 | 10h | **Done** |

* **Total Sprint 4 Delivered Velocity:** **29 Story Points** (~62 Estimated Development Hours — 100% of committed & accepted scope)
  - **Initial Sprint 4 Committed Capacity:** 24 Story Points (S4-01 to S4-06, ~52h)
  - **Mid-Sprint Added Scope (S4-07):** 5 Story Points (10h)

---

## 3. Actionable Task Breakdown & Completed Checklists (Topic Three: How did the chosen work get done?)

### S4-01: Bounded Retry & Automatic Task Reassignment (`Done`)
- [x] 1. Configure retry limit (`max_retries`) on `orchestrator.py` and `retry_policy.py`; if exceeded, fail over the task to a backup agent.
- [x] 2. Verify alternative worker availability (`IDLE`) and calculate fit score before reassigning.
- [x] 3. If no eligible alternative exists or all retries are exhausted, honestly report the task as `FAILED`.
- [x] 4. Hold dependent downstream tasks in `BLOCKED` status without premature execution.

### S4-02: Error Classification & Security Hardening (`Done`)
- [x] 1. Separate transient errors (network timeout, quota 429) from permanent errors (syntax error, schema violation) in `src/security/error_classification.py` to prevent futile retries.
- [x] 2. Validate input requirement string length, empty input, and malformed characters on backend (`src/security/input_validation.py`).
- [x] 3. Sanitize and escape model outputs before rendering in UI or writing to disk (`src/security/output_sanitizer.py`).
- [x] 4. Verify that error logs and SQLite attempt records are purged of API keys or sensitive authorization tokens.

### S4-03: UI Code Review Display & Reassignment Badges (`Done`)
- [x] 1. Visually indicate retried (`RETRYING`) and reassigned (`REASSIGNED`) tasks with status badges in Streamlit (`master_agent_projesi/review_panel.py`).
- [x] 2. Render file-by-file code review verdicts (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`) produced by the Integration Agent.
- [x] 3. Present informative warning cards when file conflicts or syntax errors occur.

### S4-04: File Path Conflict Resolution & SQLite Attempt History (`Done`)
- [x] 1. Detect and report duplicate or conflicting target write paths and SQL schema mismatches in the same workspace directory (`src/master/conflicts.py`).
- [x] 2. Record every task attempt (attempt number, assigned agent, error message, duration, model used) in SQLite `attempts` table.
- [x] 3. Record generated file metadata (path, size, SHA-256 hash, review status, conflict resolution) in SQLite `output_files` and `file_conflicts` tables.

### S4-05: Integration Agent AST Syntax Review & Packaging (`Done`)
- [x] 1. Integration Agent reads real output files from `workspaces/{run_id}/` and executes Python AST and SQLite DDL syntax validation (`src/agents/integration_agent.py`).
- [x] 2. Provide actionable review findings with specific file path and line numbers for any syntax defect.
- [x] 3. Issue `APPROVED` when mandatory checks pass; otherwise issue `REVIEW_REQUIRED` or `REJECTED`.
- [x] 4. Generate the assembled project archive package only when all mandatory checks pass.

### S4-06: Automated Test Expansion & GitHub Actions CI Gate (`Done`)
- [x] 1. Author deterministic mock-based unit tests for retry, reassignment, and conflict detection (`tests/test_s4_failover_and_conflicts.py`).
- [x] 2. Expand `.github/workflows/tests.yml` to execute the full test suite automatically on every Pull Request.
- [x] 3. Enforce that any failing test unconditionally blocks the Pull Request merge.
- [x] 4. Purge dummy key assumptions and obsolete constants in `master_agent_projesi/test_api.py`.

### S4-07: Master Agent Local Model Decomposition & Inter-Agent Shared Contract (`Done`)
- [x] 1. Connect `src/master/analyzer.py` static 6-task decomposition to the local Ollama model (`qwen2.5:7b`); extract dynamic subtasks and dependencies from requirements.
- [x] 2. Extract a shared domain contract (`contract`: entities/tables, fields, and REST endpoints) and inject it into all worker task envelopes so generated files fit together.
- [x] 3. Validate and normalize model output (enforce `MAX_LLM_TASKS` limit, valid categories, acyclic DAG, and safe template fallback `decomposition_mode="template"` when model is unavailable or malformed).
- [x] 4. Enable parallel dispatch in `src/master/orchestrator.py` (`ThreadPoolExecutor`, `MASTER_PARALLEL_DISPATCH`) for independent ready tasks; visualize the decomposition plan and shared contract in `master_agent_projesi/app.py`.

---

## 4. Capacity & Workload Allocation Matrix

| Developer | Student ID | Agent & Model | Assigned Cards | Delivered SP | Est. Hours | Primary Technical Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | S4-01, S4-07 | 10 SP | 18h | Orchestrator retry state machine, failover, LLM task decomposition & parallel dispatch |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | S4-02 | 3 SP | 8h | Error classification, input/output security hardening & Scrum facilitation |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | S4-03 | 3 SP | 8h | UI code generation, live status monitor & review visualizer |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | S4-04 | 3 SP | 8h | Workspace path/schema conflict detection & SQLite attempt history |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | S4-06 | 5 SP | 10h | Test expansion, CI quality gate hardening & QA |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | S4-05 | 5 SP | 10h | Manifest aggregation, AST/SQL syntax review & packaging |

---

## 5. Definition of Done Compliance & Verification Summary

All Sprint 4 Product Backlog Items satisfied the Definition of Done before Sprint Review on November 26, 2026:
- [x] **Automated Testing:** All unit and integration tests pass cleanly offline without live network connections (`python -m unittest discover -s tests`).
- [x] **CI Quality Gate:** GitHub Actions build reports green on all feature branches and `main`.
- [x] **Code Hygiene & Standards:** PEP 8 compliance, type hints on public interfaces, and zero hardcoded secrets.
- [x] **Sandbox Confinement:** All worker file outputs strictly confined to `workspaces/{run_id}/`.
- [x] **Transparency:** All task outcomes, retry attempts, and file conflicts recorded accurately in SQLite (`state.db` v5) and closed in [Sprint 4 Review & Retrospective Report](sprint_4_report.md).

---

**Plan Created By:** Scrum Team at Sprint Planning (Nov 12, 2026)  
**Closed & Verified By:** İrem Yılmaz (Scrum Master) at Sprint Review (Nov 26, 2026)