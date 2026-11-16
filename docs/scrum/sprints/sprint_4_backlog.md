# Sprint 4 Backlog & Task Distribution

* **Sprint Period:** 2026-11-05 – 2026-11-18 (Weeks 7 – 8)
* **Sprint Planning Date:** 2026-11-05
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
* **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz
* **Sprint Status:** **ACTIVE / IN PROGRESS**

---

## 1. Commitment: Sprint Goal (Topic One: Why is this Sprint valuable?)

> *"Implement bounded task retry and automatic failover reassignment for failed tasks, build automated Python AST syntax and LLM code review into the Integration Agent, resolve file path and schema conflicts with SQLite attempt history persistence, enforce a deterministic CI quality gate on GitHub Actions, and complete the rolled-over distributed UI status monitor and artifact manifest aggregation."*

---

## 2. Selected Product Backlog Items & Owners (Topic Two: What can be done this Sprint?)

During Sprint Planning on November 05, 2026, the Developers selected 8 Product Backlog Items (6 newly committed PBIs from Epic 4 and 2 rolled-over items from Sprint 3), committed to a total capacity of **30 Story Points**, and assigned primary technical owners:

| Card ID | PBI Title & Technical Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Status on Trello |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S3-03** | *(Rolled over from S3)* FrontendAgent Local Ollama UI Generation & Distributed Agent/File Status Monitor | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | High | 3 | 8h | S3-01, S2-02 | **In Progress** |
| **S3-05** | *(Rolled over from S3)* Worker Output Artifact Manifest Aggregation & Output Collection | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | High | 3 | 8h | S3-01, S3-04 | **Sprint Backlog** |
| **S4-01** | Bounded Retry Mechanism & Automatic Alternative Agent Reassignment | Eren Görkem Çolak (Master Agent — `qwen2.5:3b`) | Highest | 5 | 8h | S3-01, S3-04, S4-02 | **Sprint Backlog** |
| **S4-02** | Error Detection, Transient/Permanent Error Classification & Security Hardening | İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`) | High | 3 | 8h | S3-02, S2-01 | **Sprint Backlog** |
| **S4-03** | UI Display of Code Review Findings, Conflict Alerts & Reassignment History | Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`) | High | 3 | 8h | S4-01, S4-05 | **Sprint Backlog** |
| **S4-04** | File Path/Schema Conflict Resolution & SQLite Attempt History Persistence | Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`) | High | 3 | 8h | S3-04, S4-01 | **Sprint Backlog** |
| **S4-05** | Automated Python AST Syntax / Code Review & Integrated Packaging | Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`) | Highest | 5 | 10h | S3-05, S4-04 | **Sprint Backlog** |
| **S4-06** | Automated Test Expansion, Generated Code Tests & GitHub Actions CI Quality Gate | Berat İnan (Testing Agent — `deepseek-coder:6.7b`) | Highest | 5 | 10h | S4-01, S4-02, S4-04, S4-05 | **Sprint Backlog** |

* **Total Sprint 4 Committed Capacity:** **30 Story Points** (~68 Estimated Development Hours)
  - **Carry-over Capacity:** 6 Story Points (S3-03, S3-05)
  - **New Sprint 4 Committed Capacity:** 24 Story Points (S4-01 to S4-06)

---

## 3. Actionable Task Breakdown & Checklists (Topic Three: How will the chosen work get done?)

### S3-03: FrontendAgent Ollama Generation & UI Status Monitor
- [ ] 1. Dedicated model `qwen2.5-coder:3b` configured in `config/agents_config.json`, connecting `FrontendAgent` to generate UI code.
- [ ] 2. Streamlit UI displays remote/local worker connection status (`ONLINE`/`OFFLINE`) dynamically.
- [ ] 3. Streamlit UI displays generated output filenames and workspace paths upon task completion.
- [ ] 4. Empty or corrupt model outputs are trapped gracefully and not displayed as successful completions.

### S3-05: Worker Output Artifact Manifest Aggregation
- [ ] 1. Create standardized manifest for worker output files containing filename, relative path, byte size, and SHA-256 hash.
- [ ] 2. Detect missing, empty, or unverified outputs during the collection phase and report discrepancies.
- [ ] 3. Catalog collected files according to the unified project directory structure.
- [ ] 4. Ensure the completed manifest provides structured input for the Sprint 4 code review stage.

### S4-01: Bounded Retry & Automatic Task Reassignment
- [ ] 1. Configure retry limit (`max_retries`) on `orchestrator.py`; if exceeded, fail over the task to a backup agent.
- [ ] 2. Verify alternative worker availability (`IDLE`) and calculate fit score before reassigning.
- [ ] 3. If no eligible alternative exists or all retries are exhausted, honestly report the task as `FAILED`.
- [ ] 4. Hold dependent downstream tasks in `BLOCKED` status without premature execution.

### S4-02: Error Classification & Security Hardening
- [ ] 1. Separate transient errors (network timeout, quota 429) from permanent errors (syntax error, schema violation) to prevent futile retries.
- [ ] 2. Validate input requirement string length, empty input, and malformed characters on backend.
- [ ] 3. Sanitize and escape model outputs before rendering in UI or writing to disk.
- [ ] 4. Verify that error logs and SQLite attempt records are purged of API keys or sensitive authorization tokens.

### S4-03: UI Code Review Display & Reassignment Badges
- [ ] 1. Visually indicate retried (`RETRYING`) and reassigned (`REASSIGNED`) tasks with status badges in Streamlit.
- [ ] 2. Render file-by-file code review verdicts (`APPROVED`, `REVIEW_REQUIRED`, `REJECTED`) produced by the Integration Agent.
- [ ] 3. Present informative warning cards when file conflicts or syntax errors occur.

### S4-04: File Path Conflict Resolution & SQLite Attempt History
- [ ] 1. Detect and report duplicate or conflicting target write paths in the same workspace directory.
- [ ] 2. Record every task attempt (attempt number, assigned agent, error message, duration) in SQLite `attempts` table.
- [ ] 3. Record generated file metadata (path, size, SHA-256 hash, review status) in SQLite `output_files` table.

### S4-05: Integration Agent AST Syntax Review & Packaging
- [ ] 1. Integration Agent reads real output files from `workspaces/{run_id}/` and executes Python AST syntax validation.
- [ ] 2. Provide actionable review findings with specific file path and line numbers for any syntax defect.
- [ ] 3. Issue `APPROVED` when mandatory checks pass; otherwise issue `REVIEW_REQUIRED` or `REJECTED`.
- [ ] 4. Generate the assembled project archive package only when all mandatory checks pass.

### S4-06: Automated Test Expansion & GitHub Actions CI Gate
- [ ] 1. Author deterministic mock-based unit tests for retry, reassignment, and conflict detection.
- [ ] 2. Expand `.github/workflows/tests.yml` to execute the full test suite automatically on every Pull Request.
- [ ] 3. Enforce that any failing test unconditionally blocks the Pull Request merge.
- [ ] 4. Purge dummy key assumptions and obsolete constants in `master_agent_projesi/test_api.py`.

---

## 4. Capacity & Workload Allocation Matrix

| Developer | Student ID | Agent & Model | Assigned Cards | Total SP | Est. Hours | Primary Technical Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:3b`) | S4-01 | 5 SP | 8h | Orchestrator retry state machine & agent failover |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | S4-02 | 3 SP | 8h | Error classification, input validation & Scrum facilitation |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | S3-03, S4-03 | 6 SP | 16h | UI code generation, live status monitor & review visualizer |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | S4-04 | 3 SP | 8h | Workspace path conflict detection & SQLite attempt history |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | S4-06 | 5 SP | 10h | Test expansion, CI quality gate hardening & QA |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | S3-05, S4-05 | 8 SP | 18h | Manifest aggregation, AST syntax review & packaging |

---

## 5. Definition of Done Compliance & Verification Strategy

Before any item is certified for the Sprint 4 Increment:
- [ ] **Automated Testing:** All unit and integration tests must pass cleanly without live network connections (`python -m unittest discover -s tests`).
- [ ] **CI Quality Gate:** GitHub Actions build must report green on all feature branches before merging into `main`.
- [ ] **Code Hygiene & Standards:** PEP 8 compliance, full type hints on public interfaces, and zero hardcoded secrets.
- [ ] **Sandbox Confinement:** All worker file outputs strictly confined to `workspaces/{run_id}/`.
- [ ] **Transparency:** Incomplete items will never be marked as completed; status transitions will be recorded accurately in SQLite and on Trello.

---

**Plan Created By:** Scrum Team at Sprint Planning (Nov 16, 2026)  
**Facilitated By:** İrem Yılmaz (Scrum Master)  
**Reviewed By:** Prof. Dr. Ensar Gül (Product Owner)  
