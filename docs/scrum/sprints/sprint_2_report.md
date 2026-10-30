# Sprint 2 Review Report & Retrospective

* **Sprint Period:** October 15, 2026 – October 29, 2026 (Weeks 3 – 4)
  * **Sprint 2 – Week 3:** October 15, 2026 – October 22, 2026
  * **Sprint 2 – Week 4:** October 22, 2026 – October 29, 2026
* **Commitment: Sprint Goal:** Standardize runtime API configuration and safe fallback logic, unify the Streamlit UI and core Master Agent engine under a single canonical agent registry (`agents_config.json`), enforce weighted capability selection with availability filtering (`BUSY`/`OFFLINE`/`ERROR`), validate task decomposition JSON schemas, isolate per-run scheduler lifecycle states (`run_id`), and integrate SQLite persistence with automated unit tests.
* **Sprint Status:** **COMPLETED** (22 / 22 Story Points delivered to `main`)
* **Scrum Master:** İrem Yılmaz (Backend Agent & Scrum Master)
* **Product Owner:** Elif Yılmaz (Integration Agent & Product Owner)

---

## 1. Sprint Review — Delivered Increments & Observable Evidence

In accordance with the **2020 Scrum Guide**, the Scrum Team presented the working increment to the Product Owner and verified each item against the **Definition of Done**. Each card is assigned strictly to a responsible owner:

| Card ID | Task Title & Scope | Responsible Owner | Repository Evidence (Files & Modules) | Verification & DoD Status |
| :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Backend API & Local Ollama Standardization and Safe Fallback | İrem Yılmaz | `master_agent_projesi/app.py`, `.env.example`, `config/agents_config.json`, `docs/WORKER_HTTP_API_DRAFT.md`, `tests/test_api_config_fallback.py` | **COMPLETED (DONE):** Duplicate key loaders removed; `load_api_key()` centralized; secrets excluded via `.env.example`; graceful fallback on HTTP 429 quota and offline states verified via 9 unit tests. |
| **S2-02** | Unify Streamlit UI with Shared Agent Registry & Engine Status Monitoring | Kübra Hepcan | `config/agents_config.json`, `master_agent_projesi/app.py` (PR #20) | **COMPLETED (DONE):** Hardcoded `agents_data` removed from the UI; agent names, models, scores and members are read from `agents_config.json`. |
| **S2-03** | Master Agent Weighted Selection Algorithm & Availability Filtering | Eren Görkem Çolak | `src/master/capability_eval.py`, `src/master/orchestrator.py`, `tests/test_master_engine.py` | **COMPLETED (DONE):** `BUSY`, `OFFLINE` and `ERROR` agents are filtered from the selection pool; `calculate_fit_score` integrated; failover and deadlock protection added. Tests: Berat İnan. |
| **S2-04** | Task Schema Validation & Inter-Agent Integration Contracts | Elif Yılmaz *(took over from Mahmut Karaalioğlu during the sprint)* | `src/contracts.py` (`validate_master_tasks`), `docs/INTER_AGENT_CONTRACTS.md`, `tests/test_contracts.py`, `master_agent_projesi/app.py` (`normalize_tasks`) | **COMPLETED (DONE):** Pydantic contracts and task-list validator added; 5-phase normalization and malformed-JSON protection completed. Schema tests: Berat İnan. Wiring the validator into the orchestrator moved to Sprint 3. |
| **S2-05** | Run-Scoped Scheduler Lifecycle (`run_id`) & Failed/Unassigned Task Reporting | Eren Görkem Çolak | `src/master/scheduler.py`, `src/master/orchestrator.py`, `tests/test_master_engine.py` | **COMPLETED (DONE):** A unique `run_id` per run; failed tasks are isolated and never marked `COMPLETED`. Tests: Berat İnan. |
| **S2-06** | Bind UI Task Assignments & Statuses to Real Engine Results | Kübra Hepcan | `master_agent_projesi/app.py` (PR #20; integration fixes #23, #24) | **COMPLETED (DONE):** Manual start/complete buttons removed; "Analiz et" runs the real `MasterOrchestrator` and task/agent states come from the engine. |
| **S2-07** | SQLite Persistence Layer (`db_manager.py`) with Unified Agent Registry & Run Lifecycle | Mahmut Karaalioğlu *(took over from İrem Yılmaz during the sprint)* | `src/master/db_manager.py`, `docs/DATA_MODEL.md`, `tests/test_db_manager.py` | **COMPLETED (DONE):** `runs`, `agents`, `tasks`, `attempts` tables with `run_id`; WAL mode; 3-layer guard against writing failed tasks as `COMPLETED`; legacy `*_legacy_v1` migration; 11 unit tests. UI runs are persisted to `state.db` (PR #24). |

---

## 2. Sprint Review — Working Software Demonstration & Terminal Evidence

### 2.1. Automated Unit Test Suite Execution
```bash
python -m unittest discover tests
```
* **Execution Result:**
```text
Ran 44 tests in 0.412s
OK
```
* **Test Suite Breakdown:**
  - `tests/test_master_engine.py` (20 tests): Agent selection, status filtering, schema validation, failover, `run_id` isolation.
  - `tests/test_db_manager.py` (11 tests): SQLite schema, foreign keys, `COMPLETED` state protection guards.
  - `tests/test_api_config_fallback.py` (9 tests): Configuration management, missing key handling, and fallback on 429 quota/offline server.
  - `tests/test_contracts.py` (4 tests): Pydantic contract validation.
* All tests run without requiring live external API credentials or internet connectivity.
* Continuous Integration: GitHub Actions workflow (`.github/workflows/tests.yml`, PR #22) executes the test suite on every pull request.

### 2.2. Inter-Agent Communication Specification
* [`docs/WORKER_HTTP_API_DRAFT.md`](../../WORKER_HTTP_API_DRAFT.md) and [`docs/INTER_AGENT_CONTRACTS.md`](../../INTER_AGENT_CONTRACTS.md) published.
* Endpoints defined for `POST /tasks/execute`, `POST /heartbeat`, and `/health` with Bearer token authentication.

---

## 3. Sprint Retrospective — Inspection & Adaptation

In accordance with the **2020 Scrum Guide**, the Scrum Team inspected how Sprint 2 went with regards to individuals, interactions, processes, tools, and the Definition of Done:

### 3.1. What Went Well (Processes & Interactions)
1. **API Security & Clean Configuration (S2-01):** Hardcoded secrets removed, `.env.example` template provided, and `.env` strictly ignored by Git.
2. **Robust Fault Isolation:** The platform operates reliably in demo/fallback mode even when local Ollama services are offline or API rate limits are hit.
3. **Seamless Cross-Functional Collaboration:** Product Owner requirements, backend schemas, database persistence, and testing gates aligned without blocking dependencies.

### 3.2. Challenges & Identified Technical Debt (Tools & Local Hardware)
1. **Local Hardware Constraints:** Running 7B models (`qwen2.5-coder:7b`, `deepseek-coder:6.7b`) locally requires significant RAM/VRAM, reinforcing the necessity of reliable mock and fallback mechanisms.
2. **Static Task Decomposition Baseline:** In Sprint 2, task breakdown remained based on deterministic templates; connecting decomposition directly to live local LLM inference is the core goal of Sprint 3.
3. **Integration Test Gap:** Unit tests passed while UI-to-engine type differences surfaced during manual integration; full end-to-end integration tests must be expanded.

### 3.3. Actionable Improvements for Sprint 3 (`S3-01` – `S3-06`)
* **Eren Görkem Çolak (S3-01):** Finalize versioned HTTP/JSON task envelopes (`TaskPayloadContract_v1`, `WorkerTaskResultContract_v1`) and orchestrate distributed dispatch.
* **İrem Yılmaz (S3-02):** Implement authenticated FastAPI Worker Agent HTTP service with `/health` and live local Ollama backend code generation.
* **Kübra Hepcan (S3-03):** Connect FrontendAgent to local Ollama model for UI generation and render distributed worker connection statuses in Streamlit.
* **Mahmut Karaalioğlu (S3-04):** Enforce DAG cycle detection (Tarjan SCC), connect DatabaseAgent to local Ollama, and implement safe workspace file writer.
* **Elif Yılmaz (S3-05):** Build artifact manifest aggregation layer (`ArtifactManifest`) to collect, hash, and structure worker outputs.
* **Berat İnan (S3-06):** Connect TestingAgent to local Ollama for test generation and implement automated black-box HTTP API and DAG tests.

---

**Prepared by:** İrem Yılmaz (Scrum Master & Backend Agent)  
