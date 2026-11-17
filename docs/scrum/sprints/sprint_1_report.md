# Sprint 1 Review Report, Retrospective & Progress Report

* **Sprint Period:** September 24, 2026 – October 07, 2026 (Weeks 1 – 2)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Goal (Why):**
  > *"Establish foundational infrastructure, document multi-agent architecture and data model, verify local Ollama models across team hardware, implement the web interface prototype, and build the initial Master Agent task decomposition pipeline."*
* **Sprint Status:** **COMPLETED** (7 of 7 cards completed, 24 / 24 SP delivered)

---

## 1. Sprint Review (At the Review)

### 1.1. Delivered Product Increment & Observable Evidence (What Was Demonstrated)
On October 07, 2026, the Scrum Team presented the working prototype Increment to the Product Owner:

| Card ID | Deliverable Summary | Primary Assignee | Repository Evidence | Verification Outcome & Acceptance |
| :--- | :--- | :--- | :--- | :--- |
| **S1-01** | Repository setup, branch workflow, and launcher scripts | Eren Görkem Çolak | `README.md`, `.gitignore`, `start.bat` | **VERIFIED:** Cloned and verified across all team machines; branch protection active. |
| **S1-02** | Streamlit Web UI Prototype for requirement input & agent monitoring | Kübra Hepcan | `master_agent_projesi/app.py`, `requirements.txt` | **VERIFIED:** Launches cleanly via `start.bat`; accepts long input; renders agent capability cards. |
| **S1-03** | Multi-Agent Architecture & Component Boundaries | Mahmut Karaalioğlu | `docs/ARCHITECTURE.md`, `docs/scrum/product_backlog.md` | **VERIFIED:** Component boundaries and planned REST worker API explicitly documented. |
| **S1-04** | Initial Data Model & SQLite Persistence Prototype | İrem Yılmaz | `docs/DATA_MODEL.md`, `src/master/db_manager.py` | **VERIFIED:** Initial relational schema designed; SQLite table creation verified. |
| **S1-05** | System Requirements Inventory & Acceptance Criteria | Kübra Hepcan | `docs/SRS.md`, `docs/scrum/product_backlog.md` | **VERIFIED:** Decomposed course requirements into REQ-1..REQ-9 with testable criteria. |
| **S1-06** | Local Ollama Model Research & Capability Matrix | Berat İnan | `docs/MODEL_RESEARCH.md`, `config/agents_config.json` | **VERIFIED:** Hardware benchmarked across team laptops; candidate model tags evaluated. |
| **S1-07** | Master-Agent Orchestrator & Task Decomposition Engine | Eren Görkem Çolak | `src/master/orchestrator.py`, `analyzer.py`, `tests/test_master_engine.py` | **VERIFIED:** CLI decomposes requirements into 6 subtask categories; deterministic tests pass. |

### 1.2. Verification & Terminal Evidence
Executing `python -m src.master.orchestrator "Develop an online library management system"` and `python -m unittest discover -s tests` confirmed the baseline orchestration loop:
```text
[RequirementAnalyzer] Decomposed 6 subtasks across 6 categories.
[CapabilityEvaluator] Evaluating fit scores across candidate models...
* task-req-1 (Requirements Analysis) -> Routed to Agent B [Reasoning: 95.0]
* task-db-1  (Database Schema)       -> Routed to Agent A [Context: 95.0]
* task-be-1  (Core Backend API)      -> Routed to Agent A [Coding: 90.0]
* task-fe-1  (Frontend UI)           -> Routed to Agent C [Coding: 95.0]
* task-qa-1  (Testing & QA)          -> Routed to Agent B [Reasoning: 85.0]
* task-int-1 (Integration)           -> Routed to Agent C [Coding: 82.5]
Ran 4 tests in 0.045s - OK
```

### 1.3. Stakeholder Feedback (Product Owner Inspection)
* **Feedback from Prof. Dr. Ensar Gül (Product Owner):**
  - Confirmed the foundational architecture meets the course project intent.
  - Emphasized that task allocation must not be hardcoded or greedy-single-metric; it must evaluate multi-dimensional capability weights (Coding, Reasoning, Context Window) and filter out unavailable agents.
  - Advised that the Streamlit UI and core engine must use the exact same canonical configuration file.
* **Acceptance Verdict:** **ACCEPTED** (Sprint 1 Increment accepted without reservation).

### 1.4. Product Backlog Adaptations & Changes (At the Review)
* Added **S2-01**: Centralize API key configuration and remove duplicate loader functions in `app.py`.
* Added **S2-02**: Unify Streamlit UI and core engine under canonical `config/agents_config.json`.
* Prioritized **S2-03**: Multi-dimensional weighted fitness scoring and availability filtering (`BUSY`/`OFFLINE`/`ERROR`).
* Reprioritized Sprint 2 Backlog to focus on Agent Management & Task Assignment (22 Story Points).

---

## 2. Sprint Retrospective (At the Retrospective)

### 2.1. Team Observations: What Went Well?
* The team established clear Scrum accountabilities (Product Owner, Scrum Master, Developers) and delivered both backend engine and Streamlit UI prototypes in parallel.
* Architectural documentation (`ARCHITECTURE.md`) and data modeling (`DATA_MODEL.md`) provided clear contracts before deep implementation.
* Transparent inspection of the codebase allowed the team to separate working prototype features from simulated/mock behaviors early.

### 2.2. Team Observations: Challenges & Identified Technical Debt
1. **UI vs. Core Registry Discrepancy:** `master_agent_projesi/app.py` currently uses a hardcoded 3-agent list (`agents_data`) and single-dimension matching (`assign_best_agent`), whereas the core engine uses `config/agents_config.json` and weighted scoring (`capability_eval.py`).
2. **Duplicate API Key Loader:** `app.py` contains two `load_api_key()` definitions and needs a unified, safe demo/fallback configuration path.
3. **Unconditional Completion Status:** `scheduler.py` retains state across runs on the same instance, and `orchestrator.py` marks tasks `COMPLETED` even if an agent is unavailable or fails.

### 2.3. Actionable Improvement Items for Sprint 2

| Improvement Action Item | Target Area | Assignee / Owner | Success Criteria |
| :--- | :--- | :--- | :--- |
| Remove duplicate `load_api_key()` and build safe offline fallback | Code Quality & Security | İrem Yılmaz | Single loader function; no crash when Ollama is offline |
| Connect UI to canonical `agents_config.json` | Architecture & UI | Kübra Hepcan | Hardcoded `agents_data` removed; all 6 agents render dynamically |
| Implement multi-dimensional fitness scoring (`calculate_fit_score`) | Algorithm & Core | Eren Görkem Çolak | Weighted combination of coding/reasoning/context; unit tested |
| Isolate scheduler and database lifecycle per `run_id` | Reliability & Persistence | Eren Görkem Çolak & Mahmut Karaalioğlu | Unique `run_id` generated per execution; failed tasks recorded honestly |

---

## 3. Course Progress Report (Mandated by CM6453 Syllabus)

### 3.1. Project Milestone & Schedule Status
* **Iteration Timeline:** Sprint 1 of 5 (Weeks 1–2 of 10-Week Semester Schedule: Sept 24 – Oct 07, 2026).
* **Milestone Objective:** Foundation & Requirements (Establish repository, define architecture, create initial prototypes).
* **Schedule Status:** **ON SCHEDULE** (100% of planned Sprint 1 scope delivered).

### 3.2. Cumulative Velocity & Story Point Burnup Tracking
* **Committed Capacity:** 24 Story Points (52 Estimated Hours).
* **Delivered Velocity:** **24 Story Points** (100% Velocity Completion Rate).
* **Cumulative Story Points Delivered to Date:** 24 SP.

### 3.3. Team Member Contribution Matrix

| Team Member | Student ID | Agent & Model | Sprint Role & Primary Deliverables | Estimated vs Actual Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | Tech Lead: Repository setup (`S1-01`), core orchestrator & analyzer (`S1-07`) | 16h / 15h | **Done** |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | Developer: Streamlit prototype (`S1-02`), SRS requirements inventory (`S1-05`) | 14h / 14h | **Done** |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | Developer: System architecture documentation (`S1-03`) | 8h / 8h | **Done** |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | Scrum Master: Initial data model & SQLite design (`S1-04`), process facilitation | 6h / 6h | **Done** |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | Developer: Local Ollama model research & hardware capability matrix (`S1-06`) | 8h / 8h | **Done** |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | Developer: Architecture review, contract requirements support (`S1-03`, `S1-07`) | 4h / 4h | **Done** |

### 3.4. Risk Assessment & Mitigation Strategies
* **Risk 1 (Hardware Incompatibility):** Team members have varying RAM/VRAM capacities for local Ollama execution.  
  * *Mitigation:* Conducted smoke tests in `S1-06`; small models (e.g. `llama3.2:3b`, `qwen2.5-coder:3b`) assigned to lower-spec machines.
* **Risk 2 (Component Drift):** UI and backend developed in parallel could drift in data models.  
  * *Mitigation:* Scheduled Sprint 2 cards `S2-02` and `S2-06` to bind UI directly to the canonical JSON registry and engine outputs.

### 3.5. Next Sprint Focus & Functional Increment Preview
* **Sprint 2 Focus:** Agent Management and Task Assignment.
* **Deliverable Preview:** A unified Streamlit UI displaying real-time agent availability, weighted fitness selection, schema validation on task decomposition, and per-run SQLite persistence.

---

**Report Prepared By:** İrem Yılmaz (Scrum Master)  
