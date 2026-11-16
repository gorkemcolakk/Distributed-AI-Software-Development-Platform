# Sprint 2 Review Report, Retrospective & Progress Report

* **Sprint Period:** October 08, 2026 – October 21, 2026 (Weeks 3 – 4)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Goal (Why):**
  > *"Standardize API key and safe fallback configuration, unify the Streamlit UI and core engine under a canonical agent registry (`config/agents_config.json`), enforce weighted capability-based agent selection (`calculate_fit_score`) with busy/offline agent filtering, validate task decomposition JSON schemas, and ensure scheduler and SQLite persistence state isolation via `run_id`."*
* **Sprint Status:** **COMPLETED** (Closed on 2026-10-22; all 7 cards verified on `main`, 22 / 22 SP delivered)

---

## 1. Sprint Review (At the Review)

### 1.1. Delivered Product Increment & Observable Evidence (What Was Demonstrated)
On October 21, 2026, the Scrum Team demonstrated the Sprint 2 Increment to the Product Owner:

| Card ID | Task Title & Scope | Primary Assignee | Repository Evidence | Verification Outcome & Acceptance |
| :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Standardize Backend API & Local Ollama Config with Safe Fallback Logic | İrem Yılmaz | `app.py`, `.env.example`, `test_api_config_fallback.py` | **VERIFIED:** Removed duplicate loaders; centralized `load_api_key()` and `get_model_config()`. Hardcoded credentials purged. Resilient fallback mode for HTTP 429, timeouts, and offline status. 9 unit tests pass. |
| **S2-02** | Unify Streamlit UI and Core Engine Under Canonical Agent Registry | Kübra Hepcan | `config/agents_config.json`, `app.py` (PR #20) | **VERIFIED:** Hardcoded `agents_data` replaced by dynamic loading from `agents_config.json`. Displays member names, models, capabilities, and live statuses. |
| **S2-03** | Weighted Capability-Based Scoring (`FitScore`) & Availability Filtering | Eren Görkem Çolak | `capability_eval.py`, `orchestrator.py`, `tests/test_master_engine.py` | **VERIFIED:** Excluded `BUSY`, `OFFLINE`, and `ERROR` agents from selection pool. Integrated weighted fit scores with specialty bonus and failover protection. |
| **S2-04** | Validate Task Decomposition Output & Harden Safe Fallback Template | Elif Yılmaz | `src/contracts.py`, `docs/INTER_AGENT_CONTRACTS.md`, `tests/test_contracts.py` | **VERIFIED:** Pydantic schema validation implemented for decomposed subtasks; 5-stage normalization and malformed JSON protection active. 4 contract tests pass. |
| **S2-05** | Scheduler Lifecycle Isolation (`run_id`) & Accurate Failure Reporting | Eren Görkem Çolak | `scheduler.py`, `orchestrator.py`, `tests/test_master_engine.py` | **VERIFIED:** Unique `run_id` generated per execution. State reset between runs; failed/unassigned tasks reported accurately without false `COMPLETED`. |
| **S2-06** | Bind UI Task Assignments & Status Monitoring to Real Engine Execution | Kübra Hepcan | `app.py` (PR #20, #23, #24) | **VERIFIED:** Manual mock buttons removed; "Analyze" executes real `MasterOrchestrator`, binding UI progress and status indicators to backend results. |
| **S2-07** | Integrate SQLite Persistence (`db_manager.py`) with Unified Registry & `run_id` | Mahmut Karaalioğlu | `src/master/db_manager.py`, `docs/DATA_MODEL.md`, `tests/test_db_manager.py` | **VERIFIED:** `runs`, `agents`, `tasks`, and `attempts` tables initialized with WAL mode. Added 3-layer guard against false `COMPLETED` insertion. 11 unit tests pass. |

### 1.2. Verification & Terminal Evidence
```bash
python -m unittest discover tests
```
* **Output (2026-10-22 on `main`):**
```text
Ran 44 tests in 0.420s
OK
```
* **Test Suite Breakdown:**
  - `tests/test_master_engine.py` (20 tests): Candidate selection, availability filtering, schema validation, failover, `run_id` isolation.
  - `tests/test_db_manager.py` (11 tests): SQLite schema, constraints, WAL mode, and false `COMPLETED` guard.
  - `tests/test_api_config_fallback.py` (9 tests): Configuration management and offline/timeout fallback mode.
  - `tests/test_contracts.py` (4 tests): Pydantic contract validation.
* **Continuous Integration:** Automated via GitHub Actions on every Pull Request (PR #22).

### 1.3. Stakeholder Feedback (Product Owner Inspection)
* **Feedback from Prof. Dr. Ensar Gül (Product Owner):**
  - Commended the elimination of hardcoded secrets and the adoption of deterministic, offline-first unit tests.
  - Verified that task allocation now genuinely evaluates multi-dimensional weights (Coding, Reasoning, Context Capacity).
  - Emphasized that Sprint 3 must advance from single-process execution into true distributed multi-agent execution, where worker agents run on separate computers or local servers communicating via HTTP REST APIs and Bearer Tokens.
* **Acceptance Verdict:** **ACCEPTED** (Sprint 2 Increment accepted).

### 1.4. Product Backlog Adaptations & Changes (At the Review)
* Added **S3-01**: Define versioned Master–Worker HTTP/JSON task, result, and error contracts in `src/contracts.py`.
* Added **S3-02**: Implement authenticated REST worker HTTP server (`src/api/worker_server.py`) and connect BackendAgent to local Ollama (`qwen2.5-coder:7b`).
* Added **S3-04**: Build DAG cycle detection and safe workspace confinement to `workspaces/{run_id}/`.
* Added **S3-05**: Worker output artifact manifest collection layer.
* Added **S3-06**: TestingAgent Ollama test generation and distributed test suite.
* Reprioritized Sprint 3 Backlog for Distributed Development (24 Story Points).

---

## 2. Sprint Retrospective (At the Retrospective)

### 2.1. Team Observations: What Went Well?
1. **API & Security Standardization (S2-01):** Hardcoded credentials and dummy API placeholders were eliminated from the codebase; `.env.example` template was established and `.env` was secured in `.gitignore`.
2. **Robust Fault Isolation (NFR-2):** When local Ollama servers are unreachable, the UI remains responsive without crashing; HTTP 429 quota exhaustion, socket timeouts, and connection refusal are gracefully caught with informative feedback.
3. **Cross-Role Alignment:** Specifications produced by the development team (contracts, REST drafts, architecture) were synchronized cleanly with the product vision.

### 2.2. Team Observations: Challenges & Identified Technical Debt
1. **Hardware & Model Footprint:** Running `qwen2.5-coder:7b` and `deepseek-coder:6.7b` locally requires 8GB+ RAM/VRAM; ensuring rock-solid offline fallback is essential when team machines are under load.
2. **Streamlit UI Reactivity:** Updating UI state during asynchronous agent execution requires asynchronous polling or live status updates in Sprint 3.
3. **Integration Test Coverage:** A bug in PR #23 was missed by unit tests because UI-to-engine interaction was not covered end-to-end; automated integration tests must be expanded.
4. **Real Model Prompting:** `analyzer.py` returns structured boilerplate tasks; connecting the analyzer and worker agents to real local Ollama inference is the primary goal of Sprint 3.

### 2.3. Actionable Improvement Items for Sprint 3

| Improvement Action Item | Target Area | Assignee / Owner | Success Criteria |
| :--- | :--- | :--- | :--- |
| Implement FastAPI worker REST server (`worker_server.py`) with Bearer Token auth | Distributed Architecture | İrem Yılmaz | Remote HTTP task execution with `/health` endpoint and timeout protection |
| Author versioned Pydantic Master-Worker communication contracts (`v1.0`) | Inter-Agent Contracts | Eren Görkem Çolak & Elif Yılmaz | Strict schemas for task dispatch, result envelopes, and error reporting |
| Enforce DAG cycle validation & sandbox file writing to `workspaces/{run_id}/` | Security & Scheduling | Mahmut Karaalioğlu | Tarjan cycle detection; path traversal (`../`) automatically blocked |
| Connect TestingAgent to `deepseek-coder:6.7b` and test distributed endpoints | QA & Automation | Berat İnan | Deterministic test suite verifying HTTP auth, DAG validation, and sandboxing |

---

## 3. Course Progress Report (Mandated by CM6453 Syllabus)

### 3.1. Project Milestone & Schedule Status
* **Iteration Timeline:** Sprint 2 of 5 (Weeks 3–4 of 10-Week Semester Schedule: Oct 08 – Oct 21, 2026).
* **Milestone Objective:** Agent Management & Task Assignment (Capability profiles, weighted selection, status monitoring, run isolation).
* **Schedule Status:** **ON SCHEDULE** (100% of planned Sprint 2 scope delivered).

### 3.2. Cumulative Velocity & Story Point Burnup Tracking
* **Committed Capacity:** 22 Story Points (44 Estimated Hours).
* **Delivered Velocity:** **22 Story Points** (100% Velocity Completion Rate).
* **Cumulative Story Points Delivered to Date:** 46 SP (Sprint 1: 24 SP + Sprint 2: 22 SP).

### 3.3. Team Member Contribution Matrix

| Team Member | Student ID | Agent & Model | Sprint Role & Primary Deliverables | Estimated vs Actual Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:3b`) | Tech Lead: Weighted fitness selection (`S2-03`), scheduler run isolation (`S2-05`) | 14h / 14h | **Done** |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | Developer: Canonical registry UI (`S2-02`), live status & progress binding (`S2-06`) | 16h / 16h | **Done** |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | Developer: SQLite persistence layer (`S2-07`), false `COMPLETED` database guards | 4h / 4h | **Done** |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | Scrum Master: API key & fallback standardization (`S2-01`), REST draft specification | 4h / 4h | **Done** |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | Developer: Authoring 44-test unit suite, CI GitHub Actions setup (PR #22) | 6h / 6h | **Done** |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | Developer: Task decomposition Pydantic schema validation (`S2-04`) | 6h / 6h | **Done** |

### 3.4. Risk Assessment & Mitigation Strategies
* **Risk 1 (Network Latency & Worker Communication):** Connecting distributed nodes over local network may introduce connection failures or dropped payloads.  
  * *Mitigation:* `WORKER_HTTP_API_DRAFT.md` defines timeout thresholds and client retry limits; unit tests authored before network rollout.
* **Risk 2 (Model Hallucination / Invalid Output):** Worker LLMs may return text that fails syntax checks or schema compliance.  
  * *Mitigation:* S2-04 established Pydantic validation; Sprint 3 contracts mandate structured JSON result envelopes with status tagging.

### 3.5. Next Sprint Focus & Functional Increment Preview
* **Sprint 3 Focus:** Distributed Development (Remote worker execution via HTTP, local Ollama code generation across agents, DAG validation, safe file collection).
* **Deliverable Preview:** An authenticated REST worker server capable of executing backend, database, testing, and frontend code generation tasks locally while saving files to isolated run directories.

---

**Report Prepared By:** İrem Yılmaz (Scrum Master)  
