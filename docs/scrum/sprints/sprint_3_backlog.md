# Sprint 3 Backlog & Task Distribution

* **Sprint Period:** October 29, 2026 – November 12, 2026 (Weeks 5 – 6)
  * **Sprint 3 – Week 5:** October 29, 2026 – November 05, 2026
  * **Sprint 3 – Week 6:** November 05, 2026 – November 12, 2026
* **Sprint Status:** **IN PROGRESS**
* **Scrum Master:** İrem Yılmaz (Backend Agent & Scrum Master)

---

## 1. Commitment: Sprint Goal (Why)
Define versioned Master–Worker HTTP/JSON task contracts (`contracts.py`), implement authenticated Worker Agent endpoints (`src/api/`), execute live local Ollama code generation across Frontend, Backend, Database, and Testing worker agents in isolated workspaces, validate the task dependency graph (DAG) to prevent cycle deadlocks, and aggregate output artifacts into standardized manifests.

---

## 2. Selected Product Backlog Items & Task Plan (What & How)

| Card ID | Task Title & Scope | Responsible | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S3-01** | Define Master–Worker HTTP/JSON Task Contracts & Orchestrate Distributed Dispatch | Eren Görkem Çolak | Highest | 5 | 10h | S2-03, S2-04 | Sprint Backlog |
| **S3-02** | Develop Authenticated Worker Agent HTTP API Endpoint & BackendAgent Ollama Code Generation | İrem Yılmaz | Highest | 5 | 10h | S3-01, S2-01 | Done |
| **S3-03** | Connect FrontendAgent Local Ollama UI Code Generation & Display Distributed Agent/File Status in UI | Kübra Hepcan | High | 3 | 8h | S3-01, S2-02 | Sprint Backlog |
| **S3-04** | Validate Task Dependency Graph (DAG), Generate DatabaseAgent SQL & Establish Secure Workspace Writer | Mahmut Karaalioğlu | Highest | 5 | 10h | S3-01, S2-05 | Sprint Backlog |
| **S3-05** | Collect Worker Agent Output Files & Artifact Manifest in Common Project Structure | Elif Yılmaz | High | 3 | 8h | S3-01, S3-04 | Sprint Backlog |
| **S3-06** | Connect TestingAgent Local Ollama Test Generation & Implement Distributed Communication/DAG Unit Tests | Berat İnan | High | 3 | 8h | S3-01, S3-02, S3-04 | Done |

**Total Sprint 3 Capacity:** 24 Story Points (54 Estimated Hours)  
**Current Progress:** 8 Story Points Completed (S3-02, S3-06) | 16 Story Points In Progress (S3-01, S3-03, S3-04, S3-05)

---

## 3. Sprint 3 Verification Checklist (Trello Synchronized)

### S3-01: Master–Worker Contracts & Dispatch Orchestration (Eren Görkem Çolak)
- [ ] 1. Task, result, and error JSON schemas versioned in `src/contracts.py` and `docs/INTER_AGENT_CONTRACTS.md`.
- [ ] 2. Master Agent includes `run_id` and `task_id` in task envelopes during dispatch.
- [ ] 3. Timeout and duplicate message handling behaviors specified.
- [ ] 4. Contract models verified via `tests/test_contracts.py` unit tests.

### S3-02: Authenticated Worker API & BackendAgent Generation (İrem Yılmaz)
- [x] 1. Valid authenticated HTTP/JSON task requests accepted via Bearer Token; unauthorized requests rejected.
- [x] 2. Worker agent health/status (`/health`) endpoint active and responsive.
- [x] 3. BackendAgent prompts local Ollama (`qwen2.5-coder:7b`) and produces valid Python backend code output.
- [x] 4. Zero secret keys or tokens hardcoded in source code (`.env.example` verified).

### S3-03: FrontendAgent UI Generation & UI Monitoring (Kübra Hepcan)
- [ ] 1. Selected model (`qwen2.5-coder:3b` / `gemma2:2b`) configured in `config/agents_config.json`; FrontendAgent connects to generate UI code.
- [ ] 2. Streamlit dashboard displays remote/local worker agent connection status (`ONLINE`/`OFFLINE`).
- [ ] 3. Generated output file names and paths listed live in the UI upon completion.
- [ ] 4. Empty or malformed model outputs are not marked as successful in the UI.

### S3-04: DAG Graph Validation, SQL Generation & Safe Workspace Writer (Mahmut Karaalioğlu)
- [ ] 1. Dependency cycles (Tarjan SCC) and missing task IDs detected and rejected before execution.
- [ ] 2. Tasks with failed prerequisites not executed and marked as `BLOCKED`.
- [ ] 3. DatabaseAgent generates real SQL/schema outputs using local Ollama (`llama3.2:3b`).
- [ ] 4. File writing restricted strictly to `workspaces/{run_id}/`; path traversal attacks prevented.

### S3-05: Worker Artifact Manifest Aggregation (Elif Yılmaz)
- [ ] 1. Standardized artifact manifest created containing file sizes and SHA-256 hashes for all worker outputs.
- [ ] 2. Empty, missing, or unverified outputs detected and reported during aggregation.
- [ ] 3. Collected files cataloged according to the shared project directory layout.
- [ ] 4. Completed artifact manifest provides input to Sprint 4 code review stage.

### S3-06: TestingAgent Test Generation & Distributed Unit Tests (Berat İnan)
- [x] 1. TestingAgent generates real test code outputs using local Ollama (`deepseek-coder:6.7b`).
- [x] 2. Automated unit/integration tests for valid/invalid token handling and timeouts on worker endpoints.
- [x] 3. Unit tests verify DAG cycle detection and upstream failure causing `BLOCKED` task state.
- [x] 4. Path traversal (`../`) prevention and corrupt model output handling verified with tests.
