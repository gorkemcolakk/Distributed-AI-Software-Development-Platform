# Sprint 1 Backlog & Task Distribution

* **Sprint Period:** 2026-10-01 – 2026-10-15 (Weeks 1 – 2)
* **Scrum Master:** İrem Yılmaz 
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Status:** **COMPLETED** (7 of 7 cards completed, 24 SP delivered)

---

## 1. Commitment: Sprint Goal (Why)

> *"Establish foundational repository and team workflow guidelines, define testable system requirements and acceptance criteria, document the distributed multi-agent architecture and SQLite persistence model, verify local Ollama model candidates across team hardware, and deliver working prototypes for the Streamlit web UI and Master-Agent task decomposition engine."*

---

## 2. Selected Product Backlog Items & Owners (What & Who - At Sprint Planning)

During Sprint Planning on Oct 01, 2026, the Developers selected the following 7 PBIs from the Product Backlog, estimated their sizing, and assigned primary owners:

| Card ID | Task Title & Scope | Primary Assignee | Collaboration & Support | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S1-01** | Establish GitHub Repository & Team Workflow Guidelines | Eren Görkem Çolak (Master Agent) | İrem Yılmaz (SM), All Team | High | 2 | 4h | None | **Done** |
| **S1-02** | Develop Initial Streamlit Web Interface Prototype (`app.py`, `start.bat`) | Kübra Hepcan (Frontend Agent) | Elif Yılmaz, İrem Yılmaz | High | 5 | 8h | S1-01 | **Done** |
| **S1-03** | Document System Architecture & Component Boundaries (`docs/ARCHITECTURE.md`) | Mahmut Karaalioğlu (Database Agent) | Kübra Hepcan, Eren Görkem Çolak | High | 3 | 8h | S1-05 | **Done** |
| **S1-04** | Design Initial Data Model & SQLite Storage (`docs/DATA_MODEL.md`, `db_manager.py`) | İrem Yılmaz (Backend Agent) | Mahmut Karaalioğlu (Reviewer) | High | 3 | 6h | S1-05, S1-03 | **Done** |
| **S1-05** | List System Requirements & Testable Acceptance Criteria (`docs/SRS.md`) | Kübra Hepcan (Frontend Agent) | Elif Yılmaz, Mahmut Karaalioğlu | Highest | 3 | 6h | None | **Done** |
| **S1-06** | Research & Verify Team Local Ollama Model Options (`docs/MODEL_RESEARCH.md`) | Berat İnan (Testing Agent) | Eren Görkem Çolak, All Team | High | 3 | 8h | Team Hardware | **Done** |
| **S1-07** | Develop Master-Agent Orchestrator & Decomposition Prototype (`orchestrator.py`) | Eren Görkem Çolak (Master Agent) | İrem Yılmaz, Elif Yılmaz, Berat İnan | Highest | 5 | 12h | S1-01, S1-03 | **Done** |

* **Total Sprint 1 Committed Capacity:** **24 Story Points** (52 Estimated Development Hours)
* **Target Delivery:** Baseline working prototype increment meeting the Definition of Done.

---

## 3. Actionable Task Breakdown & Checklists (How - At Sprint Planning)

### S1-01: GitHub Repository & Team Workflow
- [x] Verify GitHub access and permissions for all 6 team members.
- [x] Establish branch protection rules on `main` and define PR review requirements.
- [x] Create initial repository structure, `.gitignore`, and `start.bat` launch script.
- [x] Document collaboration workflow in `README.md`.

### S1-02: Streamlit Web UI Prototype
- [x] Create Streamlit form for entering software requirements specification text.
- [x] Implement visual cards displaying available worker agents and capability dimensions.
- [x] Build task decomposition results table with assigned candidate models.
- [x] Test one-click launch via `start.bat`.

### S1-03: System Architecture Specification
- [x] Document Master Agent, Worker Agent, and Integration layer boundaries in `docs/ARCHITECTURE.md`.
- [x] Diagram message flow: User Requirement -> Master Analysis -> Worker Execution -> Integration.
- [x] Distinguish existing modules from planned network layers (`src/api`).

### S1-04: Initial Data Model & SQLite Design
- [x] Analyze entities requiring persistence (runs, tasks, attempts, output files).
- [x] Distinguish in-memory scheduler state from persistent SQLite WAL storage.
- [x] Draft initial relational schema in `docs/DATA_MODEL.md` and prototype `src/master/db_manager.py`.

### S1-05: System Requirements Inventory
- [x] Decompose course project specifications into numbered functional requirements (REQ-1 to REQ-9).
- [x] Define verifiable non-functional requirements (NFR-1 to NFR-4).
- [x] Establish traceability matrix linking requirements to planned codebase modules.

### S1-06: Ollama Model Verification
- [x] Survey local team hardware (RAM, VRAM, OS) across all 6 environments.
- [x] Pull and smoke test candidate local models (`qwen2.5:7b`, `qwen2.5-coder:7b`, `llama3.2:3b`, `phi4-mini:3.8b`, `deepseek-coder:6.7b`, `qwen2.5-coder:3b`).
- [x] Record latency, quantization, and context limits in `docs/MODEL_RESEARCH.md`.

### S1-07: Master-Agent Prototype
- [x] Implement core orchestration loop in `src/master/orchestrator.py`.
- [x] Build baseline `RequirementAnalyzer` (`src/master/analyzer.py`) decomposing text into 6 task categories.
- [x] Implement initial greedy agent capability evaluation and scheduler dispatch.
- [x] Author baseline unit tests in `tests/test_master_engine.py`.

---

## 4. Definition of Done Compliance
All 7 selected items were verified against the [Definition of Done](../definition_of_done.md). All unit tests and CLI executions passed cleanly without errors.
