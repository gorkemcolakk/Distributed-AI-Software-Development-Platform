# Sprint 3 Review Report, Retrospective & Progress Report

- **Sprint Period:** October 22, 2026 – November 04, 2026 (Weeks 5 – 6)
- **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
- **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
- **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
- **Sprint Goal (Why):**
  > *"Define versioned Master–Worker JSON communication contracts, implement authenticated REST worker endpoints with Bearer Token auth, execute real local Ollama code generation across worker agents (Backend, Database, Testing, Frontend), enforce DAG cycle detection and dependency scheduling with safe workspace isolation, and aggregate code outputs into an artifact manifest."*
- **Sprint Status:** **COMPLETED (6 of 6 Cards Done)** (Closed on 2026-11-04; all Sprint 3 scope verified against Definition of Done)
- **Capacity & Velocity Metrics:**
  - **Committed Capacity:** **24 Story Points** (6 Cards: S3-01 to S3-06, 54 Estimated Hours)
  - **Delivered Velocity:** **24 Story Points** (6 Cards: S3-01 to S3-06)
  - **Sprint Velocity Completion Rate:** **100.0%**

---

## 1. Sprint Review (At the Review)

### 1.1. Delivered Product Increment & Observable Evidence (What Was Demonstrated)
On November 04, 2026, the Scrum Team demonstrated the complete, working Sprint 3 Increment to the Product Owner. In accordance with the **2020 Scrum Guide**, all 6 committed items met the [Definition of Done](../definition_of_done.md) and were presented as part of the verified Increment:

| Card ID | Task Title & Scope | Primary Assignee | Repository Evidence | Verification Outcome & Acceptance |
| :--- | :--- | :--- | :--- | :--- |
| **S3-01** | Master–Worker HTTP/JSON Task Contracts & Distributed Dispatch Orchestration | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | `src/contracts.py`, `docs/INTER_AGENT_CONTRACTS.md`, `src/master/orchestrator.py`, `tests/test_contracts.py` | **VERIFIED (5 SP):** Defined versioned schemas (`TaskPayloadContract_v1`, `WorkerTaskResultContract_v1`, `ErrorResponseContract_v1`). Attached `run_id` and `task_id` to envelopes. Timeouts and duplicate message rejection verified with unit tests. |
| **S3-02** | Authenticated Worker HTTP API Endpoint & BackendAgent Local Ollama Code Generation | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | `src/api/worker_server.py`, `src/agents/backend_agent.py`, `docs/WORKER_HTTP_API_DRAFT.md`, `tests/test_worker_http.py` | **VERIFIED (5 SP):** Implemented FastAPI worker server with Bearer Token authentication (`/health`, task endpoints). BackendAgent prompts local Ollama (`qwen2.5-coder:7b`) generating real Python code. Zero hardcoded secrets; configuration loaded from `.env`. |
| **S3-03** | FrontendAgent Local Ollama Generation & Distributed Agent/File Status Monitor | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | `src/agents/frontend_agent.py`, `master_agent_projesi/app.py`, `config/agents_config.json`, `tests/test_frontend_agent.py` | **VERIFIED (3 SP):** Dedicated model finalized (`qwen2.5-coder:3b`) in `config/agents_config.json`. `FrontendAgent` generates UI components via local Ollama, and Streamlit (`app.py`) renders live worker statuses (`ONLINE`/`OFFLINE`), active task assignments, and generated output file lists. |
| **S3-04** | DAG Dependency Graph Validation, DatabaseAgent SQL Generation & Safe Workspace Writer | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | `src/master/scheduler.py`, `src/agents/database_agent.py`, `src/master/db_manager.py`, `tests/test_workspace.py` | **VERIFIED (5 SP):** Built topological sorting and cycle detection in `scheduler.py`. Enforced cascading `BLOCKED` states on predecessor failure. DatabaseAgent generates real SQL via `llama3.2:3b`. Filesystem writer strictly confines file creation to `workspaces/{run_id}/`, automatically rejecting path traversal (`../`) attacks. |
| **S3-05** | Worker Output Artifact Manifest Aggregation & Output Collection | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | `src/agents/integration_agent.py`, `src/contracts.py`, `docs/INTER_AGENT_CONTRACTS.md`, `src/master/orchestrator.py` | **VERIFIED (3 SP):** Implemented `ArtifactManifest` schema and `IntegrationAgent` collection layer. Aggregates generated files across Frontend, Backend, Database, and Testing workers, recording relative paths, byte sizes, and SHA-256 integrity hashes while flagging empty or missing outputs. |
| **S3-06** | TestingAgent Local Ollama Test Generation & Distributed Unit Tests | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | `src/agents/testing_agent.py`, `tests/test_contracts.py`, `tests/test_worker_http.py`, `tests/test_master_engine.py` | **VERIFIED (3 SP):** TestingAgent connected to local Ollama (`deepseek-coder:6.7b`) to generate pytest test suites. Authored automated tests verifying Bearer Token authentication (valid, missing, and invalid tokens), worker health checks, DAG cycle rejection, cascading `BLOCKED` task propagation, and path traversal rejection. |

### 1.2. Verification & Terminal Evidence

#### Full Automated Test Suite (`main` Branch Baseline)
```bash
python -m unittest discover -s tests
```
- **Output:** `Ran 176 tests — OK`
- **Verified:** All unit and integration suites across contracts, distributed HTTP workers, DAG scheduling, workspace sandboxing, agent generators, and UI file rendering pass without requiring live external API keys.

#### Inter-Agent Contract Schemas
```bash
python -m unittest tests/test_contracts.py
```
- **Verified:** Envelope structure, mandatory timestamp fields, status enumeration, `ArtifactManifest` hashing metadata, and error payload validation.

#### Distributed Worker REST Server & Authentication
```bash
python -m unittest tests/test_worker_http.py
```
- **Verified:** `GET /health` operational, unauthenticated requests rejected with HTTP 401, invalid tokens rejected with HTTP 403, and execution timeouts trapped cleanly.

#### DAG Validation & Sandboxed Workspace Writer
- Verified in `tests/test_master_engine.py` and `tests/test_workspace.py`:
  - **DAG Cycle Trapping:** Circular graphs (e.g., `Task-A -> Task-B -> Task-A`) raise `CyclicDependencyError` before execution.
  - **Cascading Failure Propagation:** Predecessor task failure transitions dependent tasks immediately to `BLOCKED`.
  - **Path Traversal Shield:** Attempts to write outside `workspaces/{run_id}/` raise `SecurityException: Path traversal detected`.

### 1.3. Stakeholder Feedback (Product Owner Inspection)
- **Feedback from Prof. Dr. Ensar Gül (Product Owner):**
  - Commended the team for completing the full distributed execution pipeline (`S3-01` through `S3-06`) and demonstrating live worker status tracking alongside artifact manifest aggregation.
  - Emphasized that Sprint 4 must build upon this baseline by implementing robust error recovery (bounded retry logic and alternative agent reassignment) and automated code review before final packaging.
  - Instructed that output files must be inspected for syntax correctness using automated AST parsing, and that file path/schema conflicts between worker agents must be automatically detected.
- **Acceptance Verdict:** **ACCEPTED** (All 6 Sprint 3 cards / 24 SP accepted into the product Increment).

### 1.4. Product Backlog Adaptations & Changes (At the Review)
- All Sprint 3 items (`S3-01` to `S3-06`) were closed and moved to `Done` with zero carry-over debt.
- Confirmed the Sprint 4 scope (24 SP committed):
  - **S4-01**: Bounded retry and automatic alternative agent reassignment (5 SP).
  - **S4-02**: Error detection, classification, and input/output security hardening (3 SP).
  - **S4-03**: Streamlit UI display of code review verdicts, conflict alerts, and reassignment history (3 SP).
  - **S4-04**: Output file path/schema conflict detection and SQLite attempt history persistence (3 SP).
  - **S4-05**: Integration Agent automated AST syntax review and packaging (5 SP).
  - **S4-06**: Test expansion, generated code tests, and GitHub Actions CI quality gate hardening (5 SP).

---

## 2. Sprint Retrospective (At the Retrospective)

### 2.1. Team Observations: What Went Well?
1. **Strong Architectural Contracts (S3-01):** Authoring versioned Pydantic contracts in `src/contracts.py` before worker implementation established clear interfaces and prevented integration mismatches across all 6 agents.
2. **Robust HTTP Authentication & Worker Isolation (S3-02):** The FastAPI REST worker endpoint provides clean separation between the central orchestrator and worker agents, enabling remote deployment across independent machines.
3. **Security-First Persistence & File Writing (S3-04):** Path traversal protection and strict directory sandboxing ensure that local Ollama models cannot overwrite critical repository files.
4. **End-to-End Visibility & Integrity Hashing (S3-03 & S3-05):** Connecting the Streamlit dashboard to live worker states and generating SHA-256 manifests for every produced file gave the team full traceability during the Sprint Review demo.

### 2.2. Team Observations: Challenges & Identified Technical Debt
1. **Streamlit Polling & Refresh Overhead:** While live worker statuses (`ONLINE`/`OFFLINE`) and output file lists are now displayed in `app.py`, Streamlit's page-rerun model requires careful state management to avoid UI flicker during long-running tasks.
2. **Local Model Inference Latency:** Running 7B models (`qwen2.5:7b` and `qwen2.5-coder:7b`) locally on CPU or low-VRAM machines introduced 15–30 second inference delays per subtask. Timeout thresholds and transient error retries must be formalized in Sprint 4.
3. **Static Code Quality Verification:** Currently, `ArtifactManifest` verifies file existence, size, and SHA-256 hash, but does not yet validate whether generated Python/SQL files compile without syntax errors.

### 2.3. Actionable Improvement Items for Sprint 4

| Improvement Action Item | Target Area | Assignee / Owner | Success Criteria |
| :--- | :--- | :--- | :--- |
| Implement **S4-01**: Bounded retry state machine and alternative agent reassignment | Fault Recovery | Eren Görkem Çolak | State machine with `max_retries`; failover to second-highest idle candidate |
| Implement **S4-02**: Error classification (transient vs permanent) and input sanitization | Backend & Security | İrem Yılmaz | Classification logic; requirements text length checks; credential masking in logs |
| Implement **S4-03**: UI display for code review findings, conflicts & reassignment history | Frontend & UI | Kübra Hepcan | Reassignment badges, conflict alerts, and file-level review statuses rendered in `app.py` |
| Implement **S4-04**: Workspace file conflict detection & SQLite attempt history | Database & Storage | Mahmut Karaalioğlu | Detect duplicate write paths; persist attempts in SQLite `attempts` table |
| Implement **S4-05**: Automated Python AST syntax review & packaging | Integration & QA | Elif Yılmaz | AST syntax check with line numbers; actionable `APPROVED`/`REVIEW_REQUIRED`/`REJECTED` verdicts |
| Implement **S4-06**: Expand automated tests and enforce GitHub Actions CI gate | QA & DevOps | Berat İnan | Deterministic mock tests; failing test blocks Pull Request merge on GitHub Actions |

---

## 3. Course Progress Report (Mandated by CM6453 Syllabus)

### 3.1. Project Milestone & Schedule Status
- **Iteration Timeline:** Sprint 3 of 5 (Weeks 5–6 of 10-Week Semester Schedule: Oct 22 – Nov 04, 2026).
- **Milestone Objective:** Distributed Development (Remote worker execution via HTTP, Ollama model code generation, DAG dependency management, safe workspace isolation, and artifact manifest aggregation).
- **Schedule Status:** **ON TRACK (100% MILESTONE DELIVERED)** (All Sprint 3 deliverables completed and verified on schedule).

### 3.2. Cumulative Velocity & Story Point Burnup Tracking
- **Sprint 1 Velocity:** 24 SP (100% completed)
- **Sprint 2 Velocity:** 22 SP (100% completed)
- **Sprint 3 Committed:** 24 SP | **Delivered:** 24 SP (100% completed) | **Rolled Over:** 0 SP
- **Total Cumulative Story Points Delivered to Date:** **70 Story Points**
- **Sprint 4 Committed Capacity:** **24 Story Points** (6 Cards: S4-01 to S4-06)

### 3.3. Team Member Contribution Matrix

| Team Member | Student ID | Agent & Model | Sprint Role & Primary Deliverables | Estimated vs Actual Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | Tech Lead: Master-Worker contracts (`S3-01`), task dispatch orchestration | 10h / 10h | **Done** |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | Scrum Master: Authenticated worker HTTP server (`S3-02`), BackendAgent Ollama integration | 10h / 10h | **Done** |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | Developer: FrontendAgent Ollama UI generation & live worker/file status monitor (`S3-03`) | 8h / 8h | **Done** |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | Developer: DAG cycle validation, DatabaseAgent SQL generation, workspace writer (`S3-04`) | 10h / 10h | **Done** |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | Developer: TestingAgent test generation, distributed HTTP & DAG unit test suite (`S3-06`) | 8h / 8h | **Done** |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | Developer: Output artifact manifest schema & SHA-256 aggregation layer (`S3-05`) | 8h / 8h | **Done** |

### 3.4. Risk Assessment & Mitigation Strategies
- **Risk 1 (Model Code Quality / Syntax Errors):** Generated code from worker models may contain syntax flaws or missing imports when combined into a single project.
  - *Mitigation:* `S4-05` (Integration Agent AST review) and `S4-01` (retry/reassignment) specifically address this risk by catching syntax errors programmatically before packaging.
- **Risk 2 (Concurrent File Write Collisions):** Multiple worker agents generating files in parallel may target overlapping file paths inside `workspaces/{run_id}/`.
  - *Mitigation:* `S4-04` introduces automated path/schema conflict detection and SQLite attempt logging in Sprint 4.

### 3.5. Next Sprint Focus & Functional Increment Preview
- **Sprint 4 Focus:** Integration, Quality Assurance & Fault Recovery.
- **Deliverable Preview:** A resilient multi-agent platform where worker errors trigger bounded retries or reassignment to alternative models, output code files undergo automated AST syntax review by the Integration Agent, file conflicts are trapped, and a green build (`176+` tests) is enforced by GitHub Actions CI.

---

**Report Prepared By:** İrem Yılmaz (Scrum Master)