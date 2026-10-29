# Sprint 3 Backlog & Task Distribution

* **Sprint Period:** 2026-10-22 – 2026-11-04 (Weeks 5 – 6)
* **Sprint Status:** **IN PROGRESS**
* **Scrum Master:** İrem Yılmaz (Backend Agent & Scrum Master)

---

## 1. Commitment: Sprint Goal (Why)
Define versioned Master–Worker communication contracts, implement authenticated HTTP/JSON worker endpoints, execute real local Ollama model inference (`qwen2.5-coder:7b`, `deepseek-coder:6.7b`) to generate verified code/test artifacts in isolated workspaces, and enforce DAG dependency scheduling.

---

## 2. Selected Product Backlog Items & Action Plan (What & How)

| Card ID | Task Title | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S3-01** | Define Versioned Master–Worker Task, Result, and Error JSON Contracts (`docs/ARCHITECTURE.md`, `src/contracts.py`) | Mahmut Karaalioğlu | Highest | 5 | 10h | S2-07 | Done |
| **S3-02** | Authenticated Worker Agent HTTP/JSON API & BackendAgent Ollama Code Generation (`src/api/`, `src/agents/backend_agent.py`) | İrem Yılmaz | Highest | 5 | 10h | S3-01, S2-01 | **Done** |
| **S3-03** | Real Worker Execution & Safe Workspace Artifact Collection (`src/agents/*_agent.py`) | Multi-Agent Team | Highest | 5 | 10h | S3-01, S3-02 | In Progress |
| **S3-04** | Validate Task Dependency Graph (DAG Cycles & Missing Refs) & Schedule Ready Tasks (`src/master/scheduler.py`) | Eren Görkem Çolak | High | 3 | 6h | S2-05, S3-01 | In Progress |
| **S3-06** | Black-box HTTP Tests & Quality Assurance for Worker Endpoints (`tests/test_worker_http.py`) | Berat İnan | High | 3 | 6h | S3-02 | Done |

**Total Sprint 3 Planned Capacity:** 21 Story Points (42 Estimated Hours)

---

## 3. Sprint 3 Verification & Acceptance Checklist

- [x] **S3-01:** Task envelopes, result contracts, and status models strictly defined in `src/contracts.py` with Pydantic v2 validation.
- [x] **S3-02:** (İrem Yılmaz)
  - [x] 1. Authenticated valid HTTP/JSON task requests accepted with Bearer Token, unauthorized requests rejected (401 fast rejection without echoing token).
  - [x] 2. Active worker health endpoint (`/health`, `/api/v1/health`) functional and does not leak credentials.
  - [x] 3. `BackendAgent` sends engineering prompt to local Ollama (`qwen2.5-coder:7b`), parses Python AST code output, extracts endpoints, and provides safe fallback mode.
  - [x] 4. Zero hardcoded secrets/tokens in source tree (`TestNoHardcodedSecrets` verified).
- [ ] **S3-03:** All worker agents generate valid code in isolated workspaces without path traversal.
- [ ] **S3-04:** Cyclic dependencies and missing prerequisites caught before execution.
- [x] **S3-06:** Black-box HTTP test suite verifies worker server live loopback under uvicorn.

