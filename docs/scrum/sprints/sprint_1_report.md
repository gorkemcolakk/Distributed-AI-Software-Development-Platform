# Sprint 1 Review Report & Retrospective

* **Sprint Period:** October 01, 2026 – October 15, 2026 (Weeks 1 – 2)
  * **Sprint 1 – Week 1:** October 01, 2026 – October 08, 2026
  * **Sprint 1 – Week 2:** October 08, 2026 – October 15, 2026
* **Commitment: Sprint Goal:** Establish foundational infrastructure, document multi-agent architecture and data model, verify local Ollama models, implement the web interface prototype, and build the initial Master Agent task decomposition pipeline.
* **Sprint Status:** **COMPLETED** (Working Prototype Increment Delivered — 24 / 24 Story Points)
* **Scrum Master:** İrem Yılmaz (Backend Agent & Scrum Master)
* **Product Owner:** Elif Yılmaz (Integration Agent & Product Owner)

---

## 1. Sprint Review — Delivered Increment & Observable Evidence

In accordance with the **2020 Scrum Guide**, the Scrum Team presented the working increment to the Product Owner and verified each item against the **Definition of Done**. Each card is assigned strictly to a responsible owner:

| Card ID | Deliverable Summary | Responsible Owner | Repository Evidence | Verification & DoD Status |
| :--- | :--- | :--- | :--- | :--- |
| **S1-01** | Repository setup, branch workflow, and launcher scripts | Eren Görkem Çolak | `README.md`, `.gitignore`, `start.bat` | Cloned and verified across team environments. |
| **S1-02** | Streamlit Web UI Prototype for requirement input & agent monitoring | Kübra Hepcan | `master_agent_projesi/app.py`, `requirements.txt` | Launches locally; accepts requirements and visualizes subtasks/agents. |
| **S1-03** | Multi-Agent Architecture & Component Boundaries | Mahmut Karaalioğlu | `docs/ARCHITECTURE.md`, `docs/scrum/Sprints.md` | Reviewed against source tree; planned `src/api` explicitly distinguished. |
| **S1-04** | Initial Data Model & SQLite Persistence Prototype | İrem Yılmaz | `docs/DATA_MODEL.md`, `src/master/db_manager.py` | ERD documented; SQLite table initialization verified. |
| **S1-05** | System Requirements Inventory & Acceptance Criteria | Kübra Hepcan | `docs/SRS.md`, `docs/scrum/product_backlog.md` | Requirements mapped to observable acceptance criteria and code status. |
| **S1-06** | Local Ollama Model Research & Capability Matrix | Berat İnan | `docs/MODEL_RESEARCH.md`, `config/agents_config.json` | Team hardware and candidate Ollama tags (`qwen2.5:3b`, `qwen2.5-coder:7b`, `deepseek-coder:6.7b`, `llama3.2:3b`, `phi4-mini:3.8b`) evaluated. |
| **S1-07** | Master-Agent Orchestrator & Task Decomposition Engine | Eren Görkem Çolak | `src/master/orchestrator.py`, `analyzer.py`, `capability_eval.py`, `scheduler.py`, `tests/test_master_engine.py` | Unit tests pass; CLI decomposes requirements into subtasks and routes to top-scoring agents. |

---

## 2. Sprint Review — Working Software Demonstration & Terminal Evidence

Executing `python -m src.master.orchestrator "Develop an online library management system"` and `python -m unittest discover -s tests` confirmed the baseline orchestration loop:
* `task-req-1` (*System Specification*) ➔ Routed to **Agent B** [Reasoning: 95.0]
* `task-db-1` (*Database Schema*) ➔ Routed to **Agent A** [Context: 95.0]
* `task-be-1` (*Core Backend API*) ➔ Routed to **Agent A** [Coding: 90.0]
* `task-fe-1` (*Frontend UI*) ➔ Routed to **Agent C** [Coding: 95.0]
* `task-qa-1` (*Testing & QA*) ➔ Routed to **Agent B** [Reasoning: 85.0]
* `task-int-1` (*Integration*) ➔ Routed to **Agent C** [Coding: 82.5]

---

## 3. Sprint Retrospective — Inspection & Adaptation

In accordance with the **2020 Scrum Guide**, the Scrum Team inspected how Sprint 1 went with regards to individuals, interactions, processes, tools, and the Definition of Done:

### 3.1. What Went Well (Processes & Interactions)
* The team established clear Scrum accountabilities (Product Owner, Scrum Master, Developers) without sub-teams or hierarchies, delivering backend orchestration and Streamlit UI in parallel.
* Architectural documentation (`ARCHITECTURE.md`) and data modeling (`DATA_MODEL.md`) established explicit technical boundaries and contracts early.
* Transparent inspection of the codebase enabled the team to clearly separate prototype features from mock behaviors.

### 3.2. Challenges & Identified Technical Debt (Tools & Codebase)
1. **UI vs. Core Registry Discrepancy:** `master_agent_projesi/app.py` utilized a hardcoded 3-agent list (`agents_data`) and single-dimension matching, whereas the core engine used `config/agents_config.json` and weighted scoring (`capability_eval.py`).
2. **Duplicate API Key Loader:** `app.py` contained two `load_api_key()` definitions requiring a unified, safe fallback configuration path.
3. **Unconditional Completion Status:** `scheduler.py` retained state across runs on the same instance, and `orchestrator.py` marked tasks `COMPLETED` even when an agent was unavailable.

### 3.3. Actionable Improvements for Sprint 2 (`S2-01` – `S2-06`)
* **İrem Yılmaz (S2-01):** Remove duplicate `load_api_key()` and enforce safe offline/quota fallback mode.
* **Kübra Hepcan (S2-02):** Unify Streamlit UI and core engine under `config/agents_config.json` and bind UI views to verified engine outputs.
* **Eren Görkem Çolak (S2-03):** Enforce weighted task-fitness scoring, filter out `BUSY`/`OFFLINE`/`ERROR` agents, and isolate scheduler state per `run_id`.
* **Elif Yılmaz (S2-04):** Implement strict JSON schema validation for decomposed tasks and define inter-agent contracts.
* **Mahmut Karaalioğlu (S2-05):** Align `src/master/db_manager.py` with the unified agent registry and per-run lifecycle states.
* **Berat İnan (S2-06):** Develop comprehensive unit tests covering agent selection, schema validation, and scheduler lifecycle isolation.

---

**Prepared by:** İrem Yılmaz (Scrum Master)  
