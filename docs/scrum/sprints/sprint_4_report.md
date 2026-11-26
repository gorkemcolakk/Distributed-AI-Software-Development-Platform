# Sprint 4 Review Report, Retrospective & Progress Report

* **Sprint Period:** November 13, 2026 – November 26, 2026 (Weeks 7 – 8)
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Goal (Why):**
  > *"Implement bounded retry state machines with automatic alternative agent reassignment, enforce transient vs. permanent error classification and input/output security hardening, detect cross-agent file path/schema conflicts with SQLite attempt history persistence, automate Python AST syntax review and packaging in the Integration Agent, surface review verdicts and conflict alerts in the Streamlit UI, and enforce a hardened GitHub Actions CI quality gate."*
* **Sprint Status:** **COMPLETED (6 of 6 Core Cards Done + Nov 24 Test Findings Resolved)** (Closed on 2026-11-26; all Sprint 4 scope verified against Definition of Done)
* **Capacity & Velocity Metrics:**
  * **Committed Capacity:** **24 Story Points** (6 Cards: S4-01 to S4-06, 54 Estimated Hours)
  * **Delivered Velocity:** **24 Story Points** (6 Cards: S4-01 to S4-06 + Nov 24 Integration Test Verification)
  * **Sprint Velocity Completion Rate:** **100.0%**

---

## 1. Sprint Review (At the Review)

### 1.1. Delivered Product Increment & Observable Evidence (What Was Demonstrated)

On November 26, 2026, the Scrum Team demonstrated the complete, working Sprint 4 Increment to the Product Owner. Following the mid-sprint integration audit (`24 Kasım Test Bulguları`) and subsequent bug-fix verification, all 6 committed items met the [Definition of Done](../definition_of_done.md) and were presented as part of the verified Increment:

| Card ID | Task Title & Scope | Primary Assignee | Repository Evidence | Verification Outcome & Acceptance | 
| ----- | ----- | ----- | ----- | ----- | 
| **S4-01** | Bounded Retry State Machine & Automatic Alternative Agent Reassignment | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | `src/master/orchestrator.py`, `src/master/recovery.py`, `src/contracts.py`, `tests/test_recovery.py` | **VERIFIED (5 SP):** Implemented bounded retry loop (`max_retries`) with exponential backoff and deterministic failover to the second-highest capability idle worker when a primary agent exceeds retry limits or remains offline. | 
| **S4-02** | Error Detection, Classification & Input/Output Security Hardening | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | `src/api/worker_server.py`, `src/security/sanitizer.py`, `src/utils/logger.py`, `tests/test_security_errors.py` | **VERIFIED (3 SP):** Implemented structured error taxonomy (`TRANSIENT` vs. `PERMANENT`), prompt payload length/injection sanitization, and automatic regex masking of Bearer tokens and `.env` secrets in runtime logs. | 
| **S4-03** | Streamlit UI Display of Code Review Verdicts, Conflict Alerts & Reassignment History | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | `master_agent_projesi/app.py`, `src/ui/components.py`, `tests/test_ui_state.py` | **VERIFIED (3 SP):** Added real-time UI badges for `APPROVED`, `REVIEW_REQUIRED`, and `REJECTED` file verdicts, highlighted cross-agent path/schema conflict warnings, and rendered step-by-step agent reassignment timelines without page-rerun flicker. | 
| **S4-04** | Output File Path/Schema Conflict Detection & SQLite Attempt History Persistence | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | `src/master/conflict_detector.py`, `src/master/db_manager.py`, `tests/test_conflict_db.py` | **VERIFIED (3 SP):** Built automated pre-write conflict scanner detecting duplicate file paths and overlapping SQL/API schemas across parallel workers. Persisted full execution attempt histories (`run_id`, `task_id`, `attempt_no`, `agent_id`, `status`) in SQLite `attempts` table. | 
| **S4-05** | Integration Agent Automated AST Syntax Review & Packaging | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | `src/agents/integration_agent.py`, `src/review/ast_inspector.py`, `src/contracts.py`, `tests/test_ast_review.py` | **VERIFIED (5 SP):** Implemented deterministic Python `ast.parse()` syntax inspection reporting exact line/column numbers and structured `CodeReviewVerdict` objects (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`), bundled alongside validated manifests into reproducible ZIP packages. | 
| **S4-06** | Test Expansion, Generated Code Tests & GitHub Actions CI Quality Gate Hardening | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | `.github/workflows/ci.yml`, `tests/test_recovery.py`, `tests/test_ast_review.py`, `tests/test_conflict_db.py` | **VERIFIED (5 SP):** Expanded deterministic unit and integration test suites covering fault recovery, AST syntax rejection, conflict trapping, and generated artifact syntax validation. Configured GitHub Actions CI workflow to block PR merges on any test failure or lint violation. | 
| **QA-24** | *24 Kasım Test Bulguları* (End-to-End Integration Audit & Bug Verification) | Elif Yılmaz, Kübra Hepcan, Eren Görkem Çolak | `src/master/orchestrator.py`, `src/review/ast_inspector.py`, `master_agent_projesi/app.py` | **VERIFIED (Unpointed QA Checklist):** Executed full multi-agent pipeline test on Nov 24; resolved 3 findings (UTF-8 encoding edge case in AST parser, SQLite lock contention during parallel retries, and UI badge alignment for `REVIEW_REQUIRED` files). | 

### 1.2. Verification & Terminal Evidence

#### Full Automated Test Suite (`main` Branch Baseline — Expanded from 176 to 238 Tests)

```
python -m unittest discover -s tests -v

```
* **Output:** `Ran 238 tests in 4.182s — OK`
* **Verified:** All 176 Sprint 3 baseline tests plus 62 new Sprint 4 tests covering bounded retries, alternative worker failover, error classification, secret log masking, SQLite attempt history, file conflict detection, AST syntax inspection, and UI state rendering pass deterministically without requiring live Ollama daemons or external API keys.

#### Fault Recovery & Alternative Agent Reassignment (`S4-01` & `S4-02`)

```
python -m unittest tests/test_recovery.py tests/test_security_errors.py

```
* **Verified:**
  * **Transient Failure Retry:** Simulated HTTP `503` / Ollama timeout triggers up to `max_retries=2` before escalating.
  * **Alternative Worker Failover:** Exhausted retries on `BackendAgent-Primary` automatically reassign the task envelope to `BackendAgent-Backup` and log the transition in `ReassignmentHistory`.
  * **Permanent Error Short-Circuit:** Invalid schema / `HTTP 400` errors classify as `PERMANENT` and skip redundant retries.
  * **Credential Masking:** Verified that `Authorization: Bearer <token>` strings are scrubbed to `Bearer ***REDACTED***` in all log streams.

#### Conflict Detection & SQLite Attempt Persistence (`S4-04`)

```
python -m unittest tests/test_conflict_db.py

```
* **Verified:**
  * **Path Collision Trapping:** Parallel outputs targeting `src/models.py` from two agents trigger `FileConflictWarning` before workspace overwrite.
  * **SQLite Persistence:** `attempts` table accurately records every retry attempt, timestamps, failure reason, and reassigned worker ID across `run_id` sessions.

#### Automated Python AST Syntax Review & Packaging (`S4-05`)

```
python -m unittest tests/test_ast_review.py

```
* **Verified:**
  * **Syntax Error Pinpointing:** Malformed generated Python files fail AST parsing with exact `lineno` and `offset`, automatically assigning `REJECTED` verdict and triggering `S4-01` feedback retry.
  * **Clean Artifact Packaging:** Validated workspaces produce `ArtifactManifest` + `CodeReviewReport` bundled inside `workspaces/{run_id}/release_bundle.zip`.

#### GitHub Actions CI Quality Gate (`S4-06`)
```
act -j quality-gate  # Local CI verification matching .github/workflows/ci.yml

```
* **Verified:** Pull request checks execute `flake8` linting, `unittest` discovery (`238` tests), and security secret-scan checks; any non-zero exit code strictly blocks merge into `main`.

### 1.3. Stakeholder Feedback (Product Owner Inspection)

* **Feedback from Prof. Dr. Ensar Gül (Product Owner):**
  * Praised the team for addressing every Sprint 3 review directive—specifically the automated AST syntax inspection (`S4-05`), cross-agent path conflict detection (`S4-04`), and deterministic failover to backup workers (`S4-01`).
  * Noted that the November 24 integration test checkpoint (`24 Kasım Test Bulguları`) significantly improved demo stability, as error recovery and AST rejection loops worked seamlessly live.
  * Directed thespri team to focus Sprint 5 (the final sprint) on full end-to-end capstone scenarios, multi-node deployment benchmarks, comprehensive user/architecture documentation, and final project presentation readiness.
* **Acceptance Verdict:** **ACCEPTED** (All 6 Sprint 4 cards / 24 SP accepted into the product Increment).

### 1.4. Product Backlog Adaptations & Changes (At the Review)

* All Sprint 4 items (`S4-01` to `S4-06`) and `24 Kasım Test Bulguları` QA checklist items were closed and moved to `Done` with zero carry-over debt.
* Confirmed the Sprint 5 scope (24 SP committed — Final Milestone):
  * **S5-01**: Multi-node distributed worker deployment & concurrent load benchmarking (5 SP).
  * **S5-02**: End-to-end full-stack capstone project generation scenarios & prompt tuning (5 SP).
  * **S5-03**: Streamlit UI polish, interactive zip bundle downloader & execution metrics dashboard (3 SP).
  * **S5-04**: SQLite analytics queries & historical run comparison reporting (3 SP).
  * **S5-05**: Comprehensive system architecture documentation, deployment guide & user manual (4 SP).
  * **S5-06**: Final end-to-end system validation suite & capstone demo rehearsal (4 SP).

## 2. Sprint Retrospective (At the Retrospective)

### 2.1. Team Observations: What Went Well?
1. **Mid-Sprint Integration Audit (`24 Kasım Test Bulguları`):** Scheduling a dedicated integration test session two days before the Sprint Review uncovered UTF-8 AST parsing issues and SQLite write-lock contention early enough to resolve and verify before the demo.
2. **Seamless Coupling Between AST Review (`S4-05`) and Retry Loop (`S4-01`):** Returning structured syntax error line numbers from `IntegrationAgent` directly into the `MasterAgent` retry prompt enabled worker models to self-correct broken Python syntax automatically.
3. **Deterministic Mock Testing & CI Gate (`S4-06`):** Isolating Ollama HTTP responses behind deterministic test fixtures kept the 238-test suite running in \~4 seconds inside GitHub Actions.
4. **Clear UI Observability (`S4-03`):** Surfacing conflict alerts and reassignment badges in Streamlit made complex background recovery behavior immediately transparent to stakeholders.

### 2.2. Team Observations: Challenges & Identified Technical Debt
1. **SQLite Concurrency Under Parallel Retries:** During the Nov 24 stress test, simultaneous worker retries briefly caused `sqlite3.OperationalError: database is locked`. Enabling WAL (Write-Ahead Logging) mode and connection timeouts resolved the issue, though multi-node scaling in Sprint 5 will require careful connection pooling.
2. **AST Scope Limited to Python:** `ast_inspector.py` validates Python syntax natively, whereas generated SQL (`DatabaseAgent`) and HTML/JS (`FrontendAgent`) currently rely on lighter structural checks. Adding SQL/JS syntax validators in Sprint 5 will further strengthen quality assurance.
3. **Cold-Start Latency on Failover:** When `S4-01` reassigns a task to a backup worker running a different local Ollama model, Ollama model swap latency adds 10–20 seconds to total run duration.

### 2.3. Actionable Improvement Items for Sprint 5

| Improvement Action Item | Target Area | Assignee / Owner | Success Criteria | 
| ----- | ----- | ----- | ----- | 
| Implement **S5-01**: Multi-node deployment & concurrency benchmarks with model warm-up | Distributed Systems | Eren Görkem Çolak | Concurrent multi-worker benchmark report; zero SQLite lock errors | 
| Implement **S5-02**: End-to-end full-stack capstone scenarios & error-feedback prompt templates | Backend & Prompts | İrem Yılmaz | 3 complete reference apps generated end-to-end without manual intervention | 
| Implement **S5-03**: Interactive ZIP bundle download & run analytics dashboard in Streamlit | Frontend & UI | Kübra Hepcan | One-click bundle download and latency/retry charts rendered in `app.py` | 
| Implement **S5-04**: SQLite WAL optimization & historical run metrics queries | Database & Storage | Mahmut Karaalioğlu | WAL mode enabled by default; query module for success/retry rates | 
| Implement **S5-05**: Final architecture documentation, API specs & deployment guide | Documentation | Elif Yılmaz | Complete `docs/` suite aligned with final codebase and diagrams | 
| Implement **S5-06**: Final E2E acceptance test suite & SQL/JS syntax checks | QA & Testing | Berat İnan | Extended syntax checks + full E2E release sign-off suite green on CI | 

## 3. Course Progress Report (Mandated by CM6453 Syllabus)

### 3.1. Project Milestone & Schedule Status
* **Iteration Timeline:** Sprint 4 of 5 (Weeks 7–8 of 10-Week Semester Schedule: Nov 13 – Nov 26, 2026).
* **Milestone Objective:** Integration, Quality Assurance & Fault Recovery (Bounded retry and alternative agent failover, error taxonomy and security hardening, conflict detection with SQLite attempt logging, automated AST syntax review, UI alerting, and CI quality gate).

* **Schedule Status:** **ON TRACK (100% MILESTONE DELIVERED)** (All Sprint 4 deliverables and Nov 24 QA findings completed and verified on schedule).

### 3.2. Cumulative Velocity & Story Point Burnup Tracking

* **Sprint 1 Velocity:** 24 SP (100% completed)
* **Sprint 2 Velocity:** 22 SP (100% completed)
* **Sprint 3 Velocity:** 24 SP (100% completed)
* **Sprint 4 Committed:** 24 SP | **Delivered:** 24 SP (100% completed) | **Rolled Over:** 0 SP
* **Total Cumulative Story Points Delivered to Date:** **94 Story Points**
* **Sprint 5 Committed Capacity:** **24 Story Points** (6 Cards: S5-01 to S5-06)

### 3.3. Team Member Contribution Matrix

| Team Member | Student ID | Agent & Model | Sprint Role & Primary Deliverables | Estimated vs Actual Hours | Status | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | Tech Lead: Bounded retry state machine & alternative worker reassignment (`S4-01`), Nov 24 QA fixes | 10h / 10h | **Done** | 
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | Scrum Master: Error classification (`TRANSIENT`/`PERMANENT`), input sanitization & secret masking (`S4-02`) | 8h / 8h | **Done** | 
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | Developer: Streamlit UI code review verdicts, conflict alerts & reassignment history (`S4-03`), Nov 24 UI fixes | 8h / 8h | **Done** | 
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | Developer: Cross-agent file/schema conflict detector & SQLite `attempts` persistence (`S4-04`) | 8h / 8h | **Done** | 
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | Developer: 62 new unit/integration tests & GitHub Actions CI merge-blocking quality gate (`S4-06`) | 10h / 10h | **Done** | 
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | Developer: Automated Python AST syntax review, verdict generation & ZIP packaging (`S4-05`), Nov 24 test audit | 10h / 10h | **Done** | 

### 3.4. Risk Assessment & Mitigation Strategies

* **Risk 1 (Model Swap Latency During Reassignment):** Switching between distinct Ollama models (`7b` vs `3b`) on memory-constrained hosts during `S4-01` failover can cause cold-start delays.
  * *Mitigation:* `S5-01` will introduce pre-warmed worker health probes and configurable `OLLAMA_KEEP_ALIVE` settings alongside concurrency benchmarks.
* **Risk 2 (Non-Python Syntax Blind Spots):** While Python outputs are strictly gated by `ast.parse()`, multi-file full-stack projects also depend on valid SQL DDL and frontend markup.
  * *Mitigation:* `S5-06` extends `ast_inspector.py` with lightweight SQL (`sqlparse`) and HTML/JSON structural validators before final packaging.

### 3.5. Next Sprint Focus & Functional Increment Preview
* **Sprint 5 Focus:** Final Polish, Multi-Node Benchmarking & Capstone Release.
* **Deliverable Preview:** A production-ready distributed AI software development platform validated across multi-node workers, capable of generating, reviewing, repairing, and packaging complete multi-tier applications with full architectural documentation and a `250+` test green CI pipeline.

---

**Report Prepared By:** İrem Yılmaz (Scrum Master)