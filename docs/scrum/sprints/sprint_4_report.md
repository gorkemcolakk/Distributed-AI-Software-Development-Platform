# Sprint 4 Review Report, Retrospective & Progress Report

- **Sprint Period:** November 12, 2026 – November 26, 2026 (Weeks 7 – 8)
- **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
- **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
- **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
- **Sprint Goal (Why):**
  > *"Implement bounded retry state machines with automatic alternative agent reassignment, enforce transient vs. permanent error classification and input/output security hardening, detect cross-agent file path/schema conflicts with SQLite attempt history persistence, automate Python AST/SQL syntax review and packaging in the Integration Agent, connect the Master Agent analyzer to local Ollama with a shared domain contract and parallel dispatch, surface review verdicts and conflict alerts in the Streamlit UI, and enforce a hardened GitHub Actions CI quality gate."*
- **Sprint Status:** **COMPLETED (7 of 7 Cards Done)** (Closed on 2026-11-26; all Sprint 4 scope verified against the Definition of Done)
- **Capacity & Velocity Metrics:**
  - **Initial Committed Capacity:** **24 Story Points** (6 Cards: `S4-01` to `S4-06`, 52 Estimated Hours)
  - **Mid-Sprint Accepted Scope (`S4-07`):** **5 Story Points** (10 Estimated Hours)
  - **Total Delivered Velocity:** **29 Story Points** (7 Cards: `S4-01` to `S4-07`, 100% completion rate)

---

## 1. Sprint Review (At the Review)

### 1.1. Delivered Product Increment & Observable Evidence (What Was Demonstrated)

On November 26, 2026, the Scrum Team demonstrated the completed Sprint 4 Increment. All 7 items (`S4-01` – `S4-07`) met the [Definition of Done](../definition_of_done.md) and were verified against existing repository modules and automated tests:

| Card ID | Task Title & Scope | Primary Assignee | Repository Evidence | Verification Outcome & Acceptance |
| :--- | :--- | :--- | :--- | :--- |
| **S4-01** | Bounded Retry State Machine & Automatic Alternative Agent Reassignment | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | `src/master/orchestrator.py`, `src/master/retry_policy.py`, `src/contracts.py`, `tests/test_retry_policy.py` | **VERIFIED (5 SP):** Implemented bounded retry loop (`max_retries`) and deterministic failover to the next highest-scoring `IDLE` candidate agent when a primary worker exhausts retries or remains unavailable. |
| **S4-02** | Error Detection, Classification & Input/Output Security Hardening | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | `src/security/error_classification.py`, `src/security/input_validation.py`, `src/security/output_sanitizer.py`, `src/api/worker_server.py`, `tests/test_s4_error_classification_security.py` | **VERIFIED (3 SP):** Separated transient errors (timeouts, rate limits) from permanent errors (invalid payloads, unsafe paths), enforced prompt input validation, escaped untrusted model output, and masked Bearer tokens/secrets in logs. |
| **S4-03** | Streamlit UI Display of Code Review Verdicts, Conflict Alerts & Reassignment History | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | `master_agent_projesi/app.py`, `master_agent_projesi/review_panel.py`, `tests/test_review_reassignment_ui.py` | **VERIFIED (3 SP):** Added UI panels and badges for `APPROVED`, `REVIEW_REQUIRED`, and `REJECTED` file verdicts, surfaced cross-agent path/schema conflict alerts, and displayed task reassignment histories. |
| **S4-04** | Output File Path/Schema Conflict Detection & SQLite Attempt History Persistence | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | `src/master/conflicts.py`, `src/master/db_manager.py`, `tests/test_s4_failover_and_conflicts.py` | **VERIFIED (3 SP):** Implemented workspace path deduplication/renaming (`DEDUPLICATED`, `RENAMED`) and SQL `CREATE TABLE` schema mismatch detection (`REPORTED`), persisting full attempt and conflict records in SQLite (`state.db` schema v5). |
| **S4-05** | Integration Agent Automated AST/SQL Syntax Review & Packaging | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | `src/agents/integration_agent.py`, `src/contracts.py`, `tests/test_s4_generated_code.py`, `tests/test_integration_manifest.py` | **VERIFIED (5 SP):** Implemented Python `ast.parse()` and SQLite DDL syntax inspection reporting exact line details and structured review verdicts (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`), alongside SHA-256 artifact manifests and workspace packaging. |
| **S4-06** | Test Expansion, Generated Code Tests & GitHub Actions CI Quality Gate Hardening | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | `.github/workflows/tests.yml`, `src/master/generated_tests.py`, `master_agent_projesi/test_api.py`, `tests/test_s4_ci_quality_gate.py` | **VERIFIED (5 SP):** Expanded the offline mock-based unit test suite to **418 passing tests** at Sprint 4 closure (subsequently expanded to **495 tests** at Sprint 5 kickoff) and enforced merge-blocking PR checks in `.github/workflows/tests.yml`. |
| **S4-07** | Master Agent Local Model Task Decomposition, Shared Contract & Parallel Dispatch | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | `src/master/analyzer.py`, `src/master/orchestrator.py`, `master_agent_projesi/app.py`, `tests/test_llm_decomposition.py`, `tests/test_parallel_dispatch.py` | **VERIFIED (5 SP):** Connected `analyzer.py` to local Ollama (`qwen2.5:7b`) with deterministic template fallback, extracted a shared domain contract injected into worker envelopes, and added `ThreadPoolExecutor` parallel dispatch for independent ready tasks. |

### 1.2. Verification & Terminal Evidence

#### Full Automated Test Suite (Sprint 4 Closure Baseline: 418 Tests)

```bash
python -m unittest discover -s tests
```
- **Sprint 4 Closure Result:** `Ran 418 tests — OK` (subsequent Sprint 4–5 test additions brought the repository suite to **495 passing tests**).
- **Verified:** All unit and integration tests run deterministically offline without live Ollama daemons or external network dependencies.

#### Fault Recovery, Error Classification & Security Hardening (`S4-01` & `S4-02`)

```bash
python -m unittest tests/test_retry_policy.py tests/test_s4_error_classification_security.py
```
- **Verified:**
  - **Transient vs. Permanent Classification:** Transient network/timeout errors trigger bounded retries (`src/master/retry_policy.py`), whereas permanent contract or unsafe-path errors short-circuit immediately without futile retries.
  - **Alternative Worker Failover:** Exhausted retries on a primary worker automatically reassign the task to the next highest-scoring `IDLE` candidate agent and record the transition in `attempted_agents` and SQLite `attempts`.
  - **Input/Output Sanitization:** Oversized or malformed requirement strings are rejected by `src/security/input_validation.py`, and Bearer tokens/credentials are masked by `src/security/output_sanitizer.py`.

#### Conflict Detection & SQLite Attempt Persistence (`S4-04`)

```bash
python -m unittest tests/test_s4_failover_and_conflicts.py tests/test_db_manager.py
```
- **Verified:**
  - **Path & Schema Conflict Handling:** Duplicate target paths with identical SHA-256 hashes are `DEDUPLICATED`, differing contents are `RENAMED` (`<stem>.<task_id><ext>`), and conflicting SQL `CREATE TABLE` definitions are `REPORTED` in SQLite `file_conflicts`.
  - **Truthful State Integrity:** Database `CHECK` constraints and triggers prevent failed, blocked, or unassigned tasks from being marked `COMPLETED`.

#### Automated AST/SQL Review, LLM Decomposition & Parallel Dispatch (`S4-05` & `S4-07`)

```bash
python -m unittest tests/test_s4_generated_code.py tests/test_llm_decomposition.py tests/test_parallel_dispatch.py
```
- **Verified:**
  - **Syntax Verification:** Malformed Python files fail `ast.parse()` with file/line diagnostics and receive `REVIEW_REQUIRED` / `REJECTED` verdicts instead of a static `APPROVED` status.
  - **Shared Domain Contract & Parallelism:** `RequirementsAnalyzer` extracts entities, fields, and endpoints into a shared contract and dispatches independent DAG tasks concurrently via `ThreadPoolExecutor`.

#### GitHub Actions CI Quality Gate (`S4-06`)

```bash
python -m unittest tests/test_s4_ci_quality_gate.py
```
- **Verified:** `.github/workflows/tests.yml` executes `python -m unittest discover -s tests` on every Pull Request and push to `main`, blocking merges on any test failure.

### 1.3. Sprint Review Outcome & Product Owner Acceptance

- **Review Verification:** All 7 Sprint 4 PBIs (`S4-01` through `S4-07`) were demonstrated against the Definition of Done criteria, confirming automated AST/SQL code review, cross-agent conflict resolution, bounded retry/failover, local Ollama task decomposition, and a green CI quality gate.
- **Acceptance Status:** **ACCEPTED** (All 7 Sprint 4 cards / 29 SP accepted into the product Increment; 0 SP carried over).

### 1.4. Product Backlog Adaptations & Sprint 5 Scope Alignment

- All Sprint 4 items (`S4-01` to `S4-07`) were closed and moved to `Done` in [`docs/scrum/product_backlog.md`](../product_backlog.md) and [`sprint_4_backlog.md`](sprint_4_backlog.md).
- Confirmed the Sprint 5 Backlog (**27 Story Points** across 8 cards in [`sprint_5_backlog.md`](sprint_5_backlog.md)):
  - **S5-01**: End-to-End Distributed Workflow & Telemetry Logging (3 SP)
  - **S5-02**: Documentation & System Harmonization (3 SP)
  - **S5-03**: Live Telemetry & Model Benchmark Visualizer Dashboard (3 SP)
  - **S5-04**: SQLite Telemetry & Benchmark Data Export (3 SP)
  - **S5-05**: Final Demonstration Scenario & PO Acceptance Verification (3 SP)
  - **S5-06**: Empirical Ollama Benchmark & E2E Test Suite Validation (5 SP)
  - **S5-07**: Comprehensive Final Project Report — CM6453 Deliverable (4 SP)
  - **S5-08**: Final Project Presentation Deck & Live Demo Script (3 SP)

---

## 2. Sprint Retrospective (At the Retrospective)

### 2.1. Team Observations: What Went Well?
1. **Distributed Test Before Review (November 24):** Running all five workers together before the Sprint Review exposed real integration issues early: mismatched worker tokens (HTTP 401), empty worker results counted as `COMPLETED`, a forbidden `CHECK` constraint in generated SQL, a frontend that did not fetch from the backend, and the Integration Agent's Ollama timeout. Each finding was added to the Sprint 5 cards.
2. **Error Classification Guiding Retry/Failover (`S4-01`, `S4-02`):** Classifying worker errors as transient or permanent let the retry policy retry only transient failures (timeouts, unreachable workers) and move permanent ones straight to failover, while the Integration Agent's AST/SQL review (`S4-05`) marks faulty files in its review verdict.
3. **Deterministic Offline Test Suite (`S4-06`):** Isolating Ollama HTTP calls behind deterministic mocks allowed 418+ unit tests to execute rapidly inside GitHub Actions (`.github/workflows/tests.yml`).
4. **Shared Domain Contract (`S4-07`):** Injecting extracted entities, fields, and endpoints into every worker envelope reduced schema drift between `DatabaseAgent`, `BackendAgent`, and `FrontendAgent`.

### 2.2. Team Observations: Challenges & Identified Technical Debt
1. **SQLite Concurrency Under Parallel Dispatch:** Running independent DAG tasks concurrently (`ThreadPoolExecutor`) required WAL mode (`PRAGMA journal_mode=WAL`) and proper connection handling in `src/master/db_manager.py` to avoid lock contention during simultaneous attempt writes.
2. **Cold-Start Latency on Model Switching:** Reassigning tasks across workers using different local Ollama models (`7b` vs `3b` vs `6.7b`) introduces model-loading latency on single-GPU machines, which needs empirical measurement in Sprint 5 (`S5-06`).
3. **Documentation Drift After Mid-Sprint Scope (`S4-07`):** Adding `S4-07` and new security/conflict modules created temporary gaps between `README.md`/`docs/` and the codebase, prioritized as `S5-02` at the start of Sprint 5.

### 2.3. Actionable Improvement Items for Sprint 5

| Improvement Action Item | Target Area | Assignee / Owner | Success Criteria |
| :--- | :--- | :--- | :--- |
| Implement **S5-01**: End-to-end distributed workflow & per-task latency telemetry logging | Master Orchestration | Eren Görkem Çolak | Full pipeline runs end-to-end with verified start/finish timestamps in SQLite |
| Implement **S5-02**: Harmonize `README.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `SRS.md` & Scrum docs | Documentation & Scrum | İrem Yılmaz | Zero mismatch between repository file tree, model tags, and documentation |
| Implement **S5-03**: Live telemetry & model benchmark visualizer in Streamlit dashboard | Frontend & UI | Kübra Hepcan | Real run metrics, durations, and retry counts charted in UI with clear live vs. demo labels |
| Implement **S5-04**: SQLite telemetry queries & CSV/JSON export (`run_export.py`) | Database & Export | Mahmut Karaalioğlu | Exportable CSV/JSON reports for agent success rates, latencies, and attempt counts |
| Implement **S5-05** & **S5-07**: Final demo rehearsal, PO acceptance checklist & final project report | Integration & Reporting | Elif Yılmaz | Rehearsed multi-paragraph demo, negative failover check, and complete CM6453 report |
| Implement **S5-06**: Empirical Ollama model benchmarks & full E2E test suite validation | QA & Benchmarking | Berat İnan | Standardized benchmark results (`scripts/master_model_benchmark.py`) and 495+ green CI tests |

---

## 3. Course Progress Report (Mandated by CM6453 Syllabus)

### 3.1. Project Milestone & Schedule Status
- **Iteration Timeline:** Sprint 4 of 5 (Weeks 7–8 of 10-Week Semester Schedule: Nov 12 – Nov 26, 2026).
- **Milestone Objective:** Integration, Quality Assurance & Fault Recovery (Bounded retry and alternative agent failover, error classification and security hardening, conflict detection with SQLite attempt logging, automated AST/SQL syntax review, LLM task decomposition with shared contract, UI alerting, and CI quality gate).
- **Schedule Status:** **ON TRACK (100% MILESTONE DELIVERED)**

### 3.2. Cumulative Velocity & Story Point Burnup Tracking
- **Sprint 1 Velocity:** 24 SP (7 of 7 cards completed)
- **Sprint 2 Velocity:** 22 SP (6 of 6 cards completed)
- **Sprint 3 Velocity:** 24 SP (6 of 6 cards completed)
- **Sprint 4 Committed:** 24 SP initial + 5 SP mid-sprint (`S4-07`) = **29 SP** | **Delivered:** **29 SP** (7 of 7 cards completed) | **Rolled Over:** 0 SP
- **Total Cumulative Story Points Delivered to Date:** **99 Story Points** (26 of 26 cards completed across Sprints 1–4)
- **Sprint 5 Committed Capacity:** **27 Story Points** (8 Cards: `S5-01` to `S5-08`)

### 3.3. Team Member Contribution Matrix

| Team Member | Student ID | Agent & Model | Sprint Role & Primary Deliverables | Estimated vs Actual Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | Tech Lead: Bounded retry & failover (`S4-01`), local Ollama decomposition, shared contract & parallel dispatch (`S4-07`) | 18h / 18h | **Done** |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | Scrum Master: Error classification (`TRANSIENT`/`PERMANENT`), input validation, output sanitization & secret masking (`S4-02`) | 8h / 8h | **Done** |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | Developer: Streamlit UI code review verdicts, conflict alerts & reassignment history (`S4-03` / `review_panel.py`) | 8h / 8h | **Done** |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | Developer: Cross-agent file/schema conflict resolver (`conflicts.py`) & SQLite `attempts`/`output_files` persistence (`S4-04`) | 8h / 8h | **Done** |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | Developer: Deterministic unit/integration test expansion (418 tests at closure) & GitHub Actions CI quality gate (`S4-06`) | 10h / 10h | **Done** |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | Developer: Automated Python AST & SQLite DDL syntax review, verdict generation & artifact manifest packaging (`S4-05`) | 10h / 10h | **Done** |

### 3.4. Risk Assessment & Mitigation Strategies
- **Risk 1 (Model Swap Latency During Reassignment):** Switching between distinct Ollama models (`qwen2.5:7b`, `qwen2.5-coder:7b`, `deepseek-coder:6.7b`) on memory-constrained hosts during `S4-01` failover can cause cold-start delays.
  - *Mitigation:* `S5-06` benchmarks per-model load and inference latency via `scripts/master_model_benchmark.py` to document realistic hardware thresholds.
- **Risk 2 (Multi-Node Network & Timeout Variance):** Distributed HTTP workers running across Tailscale VPN nodes may experience variable latency under concurrent `ThreadPoolExecutor` dispatch (`S4-07`).
  - *Mitigation:* `S5-01` and `S5-03` instrument per-task start/finish timestamps and retry counts in SQLite (`state.db`) and expose them in the Streamlit telemetry panel.

### 3.5. Next Sprint Focus & Functional Increment Preview
- **Sprint 5 Focus:** End-to-End Integration, Live Telemetry, Empirical Model Benchmarking & Final Release Deliverables (`S5-01` – `S5-08`).
- **Deliverable Preview:** A verified end-to-end multi-agent software development platform with live SQLite telemetry and CSV/JSON export, empirical local Ollama benchmark results, harmonized system documentation, a 495+ test green CI pipeline, and final course report/presentation deliverables.

---

**Report Prepared By:** İrem Yılmaz (Scrum Master)