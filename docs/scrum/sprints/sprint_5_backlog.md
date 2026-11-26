# Sprint 5 Backlog & Task Distribution
## Distributed AI Software Development Platform (CM6453)

* **Document Owner:** İrem Yılmaz (Scrum Master & Developer)
* **Application Scope:** Distributed AI Software Development Platform — Sprint 5 Planning & Final Capstone Release
* **Framework:** Scrum (2020 Scrum Guide, 5 Sprints × 2 Weeks = 10 Weeks)
* **Sprint Number:** Sprint 5 (Final Sprint)
* **Sprint Period:** 2026-11-26 – 2026-12-10 (Weeks 9 – 10)
* **Sprint Planning Date:** 2026-11-26
* **Sprint Status:** **PLANNED / ACTIVE**
* **Scrum Team Roster & Accountabilities:**
  - **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
  - **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - **Developers:**
    - Eren Görkem Çolak (Master Agent — `qwen2.5:7b`)
    - Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`)
    - Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`)
    - Berat İnan (Testing Agent — `deepseek-coder:6.7b`)
    - İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
    - Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`)

---

## 1. Commitment: Sprint Goal (Topic One: Why is this Sprint valuable?)

> *"Deliver a production-ready, end-to-end Distributed AI Software Development Platform validated on multi-node benchmarks and capstone scenarios, incorporate all Product Owner final-sprint review requirements (multi-language syntax validation, one-click archive export, and run analytics), and complete the comprehensive CM6453 Final Project Report and Capstone Presentation Deck."*

---

## 2. Selected Product Backlog Items & Owners (Topic Two: What can be done this Sprint?)

During Sprint Planning on November 26, 2026, the Developers selected 6 core technical Product Backlog Items from Epic 5 and added **2 dedicated Capstone Deliverable Cards (`S5-07` and `S5-08`)** in response to Prof. Dr. Ensar Gül's final-sprint directives (with zero carry-over debt from Sprint 4), committing to a total capacity of **30 Story Points**:

| Card ID | PBI Title & Technical Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Initial Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S5-01** | Multi-Node Distributed Worker Deployment & Concurrent Load Benchmarking | Eren Görkem Çolak (Master Agent — `qwen2.5:7b`) | Highest | 5 | 8h | S4-01, S4-07 | Sprint Backlog |
| **S5-02** | End-to-End Capstone Project Scenarios & Self-Healing Error-Feedback Prompts | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | Highest | 4 | 8h | S4-02, S4-07 | Sprint Backlog |
| **S5-03** | Streamlit UI Final Polish, One-Click ZIP Bundle Download & Analytics Dashboard | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | High | 3 | 6h | S4-03, S4-05 | Sprint Backlog |
| **S5-04** | SQLite WAL Mode Optimization & Historical Run Comparison Metrics | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | High | 3 | 6h | S4-04 | Sprint Backlog |
| **S5-05** | Multi-Language Syntax Validation (SQL/HTML/JS) & Final Release Packaging | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | Highest | 4 | 7h | S4-05 | Sprint Backlog |
| **S5-06** | End-to-End Acceptance Test Suite & Capstone Demo Rehearsal | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | Highest | 4 | 7h | S4-06, S5-05 | Sprint Backlog |
| **S5-07** | **[PO Request]** Comprehensive CM6453 Final Project Technical Report | Elif Yılmaz & Mahmut Karaalioğlu (Co-Owners) | Highest | 4 | 8h | S5-01..S5-05 | Sprint Backlog |
| **S5-08** | **[PO Request]** Capstone Final Presentation Deck & Live Demo Script | Kübra Hepcan & Eren Görkem Çolak (Co-Owners) | Highest | 3 | 6h | S5-03, S5-06 | Sprint Backlog |

* **Total Sprint 5 Committed Capacity:** **30 Story Points** (~56 Estimated Development & Documentation Hours)
  - **Carry-over Work:** 0 Story Points (All Sprint 4 cards `S4-01` – `S4-07` completed and accepted)
  - **Core Technical PBIs (`S5-01` – `S5-06`):** 23 Story Points (~42h)
  - **Product Owner Final Deliverables (`S5-07` – `S5-08`):** 7 Story Points (~14h)

---

## 3. Actionable Task Breakdown & Checklists (Topic Three: How will the chosen work get done?)

### S5-01: Multi-Node Distributed Worker Deployment & Concurrent Load Benchmarking
- [ ] 1. Verify distributed execution across at least 2 physically separate network nodes (Master host + remote Ollama worker host) using Bearer Token authentication.
- [ ] 2. Configure `OLLAMA_KEEP_ALIVE` and worker health warm-up probes to eliminate cold-start latency during task reassignment (`S4-01`).
- [ ] 3. Benchmark sequential vs. parallel (`MASTER_PARALLEL_DISPATCH`) task execution times and record throughput metrics.
- [ ] 4. Document multi-node environment setup in `.env.example` and `docs/DEPLOYMENT_GUIDE.md`.

### S5-02: End-to-End Capstone Project Scenarios & Self-Healing Error-Feedback Prompts
- [ ] 1. Implement structured error-feedback prompt templates so failed AST/syntax findings (`S4-05`) are fed back cleanly into worker retries.
- [ ] 2. Curate and validate 3 canonical end-to-end benchmark prompts (e.g., *Task Tracker REST API*, *Inventory Management CRUD + SQL*, *Student Portal Dashboard*).
- [ ] 3. Verify that shared domain contracts (`S4-07`) align database schemas, backend routes, and frontend API calls across all 3 scenarios.
- [ ] 4. Ensure zero unhandled exceptions or secret leaks across full multi-step runs.

### S5-03: Streamlit UI Final Polish, One-Click ZIP Bundle Download & Analytics Dashboard
- [ ] 1. Add a one-click `Download Project Bundle (.zip)` button in `master_agent_projesi/app.py` wired directly to the Integration Agent's verified release archive.
- [ ] 2. Build a **Run Analytics & Telemetry** tab displaying task latency breakdown, retry/reassignment counts, and per-agent success rates.
- [ ] 3. Add a preset selector in the UI allowing quick selection of the 3 curated capstone demo prompts (`S5-02`).
- [ ] 4. Polish responsive layout, status badges, and error/conflict alert readability for the live classroom presentation.

### S5-04: SQLite WAL Mode Optimization & Historical Run Comparison Metrics
- [ ] 1. Enable SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) and busy-timeout handling in `src/master/db_manager.py` to prevent write locks under parallel worker retries.
- [ ] 2. Implement analytical SQL queries aggregating historical run durations, retry frequencies, and conflict rates across `runs`, `attempts`, and `output_files`.
- [ ] 3. Expose clean Python repository methods consumed by the Streamlit Analytics Dashboard (`S5-03`) and Final Project Report (`S5-07`).
- [ ] 4. Verify database migration safety and deterministic unit tests in `tests/test_db_analytics.py`.

### S5-05: Multi-Language Syntax Validation (SQL/HTML/JS) & Final Release Packaging
- [ ] 1. Extend `src/review/ast_inspector.py` beyond Python AST to validate generated SQL DDL statements, JSON/YAML configs, and HTML/JS structural integrity.
- [ ] 2. Ensure `IntegrationAgent` generates a comprehensive `BUILD_SUMMARY.md` inside `workspaces/{run_id}/` containing the artifact manifest, SHA-256 hashes, and code review report.
- [ ] 3. Package verified multi-tier outputs into a clean, runnable directory structure inside `release_bundle.zip`.
- [ ] 4. Enforce strict `REJECTED` blocking if critical syntax or path-traversal violations remain unresolved.

### S5-06: End-to-End Acceptance Test Suite & Capstone Demo Rehearsal
- [ ] 1. Expand automated unit and integration test coverage beyond `250+` passing offline tests (`python -m unittest discover -s tests`).
- [ ] 2. Author an end-to-end acceptance test suite (`tests/test_e2e_capstone.py`) simulating full prompt-to-ZIP execution with realistic mock Ollama outputs.
- [ ] 3. Verify GitHub Actions CI workflow (`.github/workflows/ci.yml`) passes cleanly with linting, security checks, and full test discovery.
- [ ] 4. Coordinate full-team live demo rehearsal and prepare fallback offline recording/logs in case of classroom network/hardware disruptions.

### S5-07: [PO Request] Comprehensive CM6453 Final Project Technical Report
- [ ] 1. Structure the final academic & technical report covering: *Problem Statement, System Architecture, Inter-Agent Contracts, DAG Scheduling, Fault Recovery & AST QA, Experimental Benchmarks, and 5-Sprint Scrum Metrics*.
- [ ] 2. Embed verified architectural diagrams (Master–Worker topology, sequence diagrams, ER schema) and Sprint 1–5 cumulative velocity charts (`124 SP` total).
- [ ] 3. Include empirical benchmark tables comparing single-node vs. multi-node execution times, retry recovery rates, and AST defect catch rates (`S5-01`, `S5-04`).
- [ ] 4. Review formatting, citations, repository links, and export final submission files (`docs/FINAL_PROJECT_REPORT.md` and `.pdf`).

### S5-08: [PO Request] Capstone Final Presentation Deck & Live Demo Script
- [ ] 1. Design a clear, visually engaging 12–15 slide presentation deck (`docs/CAPSTONE_PRESENTATION.pptx` / `.pdf`) tailored to Prof. Dr. Ensar Gül's evaluation rubric.
- [ ] 2. Cover project motivation, distributed local-LLM architecture, live fault-tolerance & AST code-review highlights, Scrum journey, and lessons learned.
- [ ] 3. Prepare a timed 10-minute live demo script synchronized with `S5-03` UI presets and `S5-06` test verification outputs.
- [ ] 4. Conduct speaker role assignment across all 6 team members for the final presentation day.

---

## 4. Capacity & Workload Allocation Matrix (With PO Deliverable Recommendations)

| Developer | Student ID | Agent & Model | Assigned Cards | Total SP | Est. Hours | Primary Technical & Capstone Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:7b`) | S5-01, S5-08 (Co) | 6.5 SP | 11h | Multi-node benchmarks, architecture diagrams & technical demo lead |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | S5-02 | 4 SP | 8h | Self-healing prompts, capstone scenarios, Scrum Master & report/deck review |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | S5-03, S5-08 (Lead) | 4.5 SP | 9h | UI final polish/analytics + **Presentation Deck Lead** (visual design & UI walkthrough) |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | S5-04, S5-07 (Co) | 5 SP | 9h | SQLite WAL & analytics queries + **Project Report Co-Owner** (data tables & benchmarks) |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | S5-06 | 4 SP | 7h | E2E acceptance test suite (`250+` tests), CI sign-off & demo QA rehearsal |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | S5-05, S5-07 (Lead) | 6 SP | 12h | Multi-language validation/packaging + **Final Project Report Lead** (system synthesis) |

---

## 5. Definition of Done Compliance & Verification Strategy

All selected items must satisfy the [Definition of Done](../definition_of_done.md) before presentation at the Final Capstone Review:
- [ ] **Working Software:** Complete end-to-end pipeline executes cleanly across distributed nodes and exports runnable `.zip` project bundles.
- [ ] **Deterministic Testing:** `250+` offline unit and E2E acceptance tests pass (`python -m unittest discover -s tests`).
- [ ] **CI Quality Gate:** GitHub Actions workflow passes cleanly on `main` and all release branches.
- [ ] **Physical Sandboxing:** File writes strictly confined to `workspaces/{run_id}/`; path traversal rejected.
- [ ] **Zero Hardcoded Secrets:** Dynamic `.env` configuration verified; no secrets in logs, reports, slides, or git.
- [ ] **Capstone Deliverables Submitted:** Final Project Technical Report (`S5-07`) and Presentation Deck (`S5-08`) reviewed by all team members and submitted on schedule.

---

**Plan Created By:** Scrum Team at Sprint 5 Planning (Nov 26, 2026)  
**Facilitated By:** İrem Yılmaz (Scrum Master)