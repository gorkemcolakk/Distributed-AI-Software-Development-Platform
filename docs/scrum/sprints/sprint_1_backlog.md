# Sprint 1 Backlog & Task Distribution

* **Sprint Period:** 2026-09-24 – 2026-10-07 (Weeks 1 – 2)
* **Sprint Status:** **COMPLETED**

---

## 1. Commitment: Sprint Goal (Why)
Establish the foundational repository and team workflow, define testable system requirements, document the multi-agent architecture and SQLite persistence model, verify local Ollama model options across team hardware, and build the initial Streamlit web UI and Master-Agent task decomposition prototypes.

---

## 2. Selected Product Backlog Items & Task Plan (What & How)

| Card ID | Task Title | Primary Assignee | Collaboration & Support | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S1-01** | Establish GitHub Repository & Team Workflow Guidelines | Eren Görkem Çolak | İrem Yılmaz (SM), All Team | High | 2 | 4h | None | Done |
| **S1-02** | Develop Initial Streamlit Web Interface Prototype (`master_agent_projesi/app.py`, `start.bat`) | Kübra Hepcan | Elif Yılmaz (PO), İrem Yılmaz | High | 5 | 8h | S1-01 | Done |
| **S1-03** | Document System Architecture & Component Boundaries (`docs/ARCHITECTURE.md`) | Mahmut Karaalioğlu | Kübra Hepcan, Eren Görkem Çolak | High | 3 | 8h | S1-05 | Done |
| **S1-04** | Design Initial Data Model & SQLite Persistent Storage (`docs/DATA_MODEL.md`, `src/master/db_manager.py`) | İrem Yılmaz | Mahmut Karaalioğlu (Reviewer) | High | 3 | 6h | S1-05, S1-03 | Done |
| **S1-05** | List System Requirements & Define Testable Acceptance Criteria (`docs/SRS.md`, `product_backlog.md`) | Kübra Hepcan | Elif Yılmaz (PO), Mahmut Karaalioğlu | Highest | 3 | 6h | None | Done |
| **S1-06** | Research & Verify Team Local Ollama Model Options (`docs/MODEL_RESEARCH.md`, `config/agents_config.json`) | Berat İnan | Eren Görkem Çolak, All Team | High | 3 | 8h | Team Hardware | Done |
| **S1-07** | Develop Master-Agent Orchestrator & Basic Task Decomposition Prototype (`orchestrator.py`, `analyzer.py`) | Eren Görkem Çolak | İrem Yılmaz, Elif Yılmaz, Berat İnan | Highest | 5 | 12h | S1-01, S1-03 | Done |

**Total Sprint 1 Capacity:** 24 Story Points (52 Estimated Hours)

---

## 3. Definition of Done Verification
- All 7 Sprint 1 cards were verified against observable repository files and checklists in `docs/scrum/definition_of_done.md`.
- Core engine unit tests (`python -m unittest discover -s tests`) and CLI execution (`python -m src.master.orchestrator`) passed.