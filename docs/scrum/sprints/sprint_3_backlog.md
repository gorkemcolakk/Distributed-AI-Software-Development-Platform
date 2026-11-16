# Sprint 3 Backlog & Task Distribution

* **Sprint Period:** 2026-10-22 – 2026-11-04 (Weeks 5 – 6)
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Status:** **COMPLETED** (Sprint closed on 2026-11-04; 4 of 6 cards Done, 2 cards rolled over to Sprint 4)

---

## 1. Commitment: Sprint Goal (Why)

> *"Define versioned Master–Worker JSON communication contracts, implement authenticated REST worker endpoints with Bearer Token auth, execute real local Ollama code generation across worker agents (Backend, Database, Testing, Frontend), enforce DAG cycle detection and dependency scheduling with safe workspace isolation, and aggregate code outputs into an artifact manifest."*

---

## 2. Selected Product Backlog Items & Task Plan (What & How)

| Card ID | Task Title & Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Status at Sprint End |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S3-01** | Define Master–Worker HTTP/JSON Contracts & Orchestrate Distributed Task Dispatch | Eren Görkem Çolak | Highest | 5 | 10h | S2-03, S2-04 | **Done** |
| **S3-02** | Authenticated Worker HTTP API Endpoint & BackendAgent Local Ollama Generation | İrem Yılmaz | Highest | 5 | 10h | S3-01, S2-01 | **Done** |
| **S3-03** | FrontendAgent Local Ollama UI Generation & Distributed Agent/File Status Monitor | Kübra Hepcan | High | 3 | 8h | S3-01, S2-02 | **In Progress** *(Rolled over to S4)* |
| **S3-04** | DAG Dependency Validation, DatabaseAgent SQL Generation & Safe Workspace Writer | Mahmut Karaalioğlu | Highest | 5 | 10h | S3-01, S2-05 | **Done** |
| **S3-05** | Worker Output Artifact Manifest Aggregation & Standardized Output Collection | Elif Yılmaz | High | 3 | 8h | S3-01, S3-04 | **Sprint Backlog** *(Rolled over to S4)* |
| **S3-06** | TestingAgent Local Ollama Test Generation & Distributed Communication / DAG Tests | Berat İnan | High | 3 | 8h | S3-01, S3-02, S3-04 | **Done** |

* **Total Committed Capacity:** **24 Story Points** (54 Estimated Hours)
* **Delivered Velocity:** **18 Story Points** (4 of 6 Cards Completed)
* **Rolled Over to Sprint 4:** **6 Story Points** (S3-03: In Progress, S3-05: In Backlog)

---

## 3. Detailed Task Checklists (From Trello Cards)

### S3-01: Master–Worker HTTP/JSON Task Contracts & Dispatch Orchestration
- [x] 1. Versioned JSON schemas for task, result, and error responses defined in `src/contracts.py` and documented in `docs/INTER_AGENT_CONTRACTS.md`.
- [x] 2. Master Agent includes `run_id` and `task_id` in the task payload envelope during dispatch.
- [x] 3. Timeouts and duplicate message behaviors are formalized.
- [x] 4. Contract schemas verified with deterministic unit tests in `tests/test_contracts.py`.

### S3-02: Authenticated Worker HTTP API & BackendAgent Local Ollama Code Generation
- [x] 1. Valid authenticated HTTP/JSON task requests accepted via Bearer Token; unauthorized requests rejected with HTTP 401.
- [x] 2. Worker health check endpoint (`GET /health`) implemented and operational in `src/api/worker_server.py`.
- [x] 3. BackendAgent prompts local Ollama (`qwen2.5-coder:7b`) to generate real Python/API code.
- [x] 4. Zero hardcoded secrets in source code; dynamic loading from `.env` enforced with `.env.example` guidance.

### S3-03: FrontendAgent Local Ollama Generation & Distributed UI Monitor
- [ ] 1. Finalize and configure `qwen2.5-coder:3b` in `config/agents_config.json`, connecting FrontendAgent to generate UI code. *(In Progress)*
- [ ] 2. Streamlit UI displays remote/local worker connection status (`ONLINE`/`OFFLINE`). *(In Progress)*
- [ ] 3. Streamlit UI dynamically lists generated output filenames and paths upon task completion. *(In Progress)*
- [ ] 4. Empty or corrupt model outputs are caught and prevented from false success display. *(In Progress)*

### S3-04: DAG Dependency Validation, DatabaseAgent SQL Generation & Safe Workspace Writer
- [x] 1. Dependency cycles and missing task references detected and rejected using cycle detection algorithms in `src/master/scheduler.py`.
- [x] 2. Dependent tasks cascade to `BLOCKED` state when predecessor tasks fail.
- [x] 3. DatabaseAgent prompts local Ollama (`llama3.2:3b`) to generate real SQL schemas.
- [x] 4. File writer safely confines output strictly to `workspaces/{run_id}/`, automatically rejecting path traversal (`../`) attacks.

### S3-05: Worker Output Artifact Manifest Aggregation & Output Collection
- [ ] 1. Manifest structure created for worker output files including file path, size, and SHA-256 hash. *(Carried to Sprint 4)*
- [ ] 2. Missing, empty, or unverified outputs detected and reported during aggregation. *(Carried to Sprint 4)*
- [ ] 3. Collected files cataloged according to the unified project directory layout. *(Carried to Sprint 4)*
- [ ] 4. Completed manifest feeds directly into the Sprint 4 code review stage. *(Carried to Sprint 4)*

### S3-06: TestingAgent Local Ollama Test Generation & Distributed Unit Tests
- [x] 1. TestingAgent connected to local Ollama (`deepseek-coder:6.7b`) to generate unit test code.
- [x] 2. Automated tests written for worker HTTP endpoint authentication (valid/invalid tokens) and timeout handling.
- [x] 3. Automated tests verify DAG cycle detection and cascading `BLOCKED` states.
- [x] 4. Automated tests verify path traversal attack prevention and malformed model output handling.

---

## 4. Definition of Done Compliance
In accordance with the **2020 Scrum Guide**, only PBIs that fully satisfy the [Definition of Done](../definition_of_done.md) were marked as `Done` and included in the Sprint 3 Increment. Incomplete items (S3-03 and S3-05) were transparently returned to the Product Backlog and prioritized in the Sprint 4 Backlog.
