# Scrum Calendar & Ceremony Schedule

* **Project Title:** Distributed AI Software Development Platform
* **Course:** CM6453 Software Processes Term Project
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Scrum Master:** İrem Yılmaz
* **Team:** Team 3 (6 Members)
* **Cadence:** 5 Sprints × 2 Weeks (Total 10 Weeks: Oct 01, 2026 – Dec 10, 2026)

---

## 1. Scrum Team Roster, Accountabilities & Assigned Trello Cards

Within the Scrum Team, there are no sub-teams or hierarchies. In accordance with the **2020 Scrum Guide**, the team comprises one Product Owner (representing project requirements and academic evaluation), one Scrum Master, and Developers:

| Student ID / Role | Full Name | Scrum Accountability | Assigned Local Ollama Model | Primary Technical Focus & Owned Trello Cards |
| :--- | :--- | :--- | :--- | :--- |
| **2204012301** | **İrem Yılmaz** | **Scrum Master & Developer** | `qwen2.5-coder:7b` (Backend Agent) | Scrum Facilitation, API Config & Fallbacks, Worker REST API, Error Classification & Release Docs (**S1-04, S2-01, S3-02, S4-02, S5-02**) |
| **2204012296** | **Eren Görkem Çolak** | **Developer** (Tech Lead) | `qwen2.5:7b` (Master Agent) | Master Orchestrator, Analyzer, Weighted Selection, Scheduler Lifecycle, Bounded Retry, LLM Decomposition & E2E Pipeline (**S1-01, S1-07, S2-03, S3-01, S4-01, S4-07, S5-01**) |
| **2204012302** | **Kübra Hepcan** | **Developer** | `qwen2.5-coder:3b` (Frontend Agent) | SRS Document, Canonical Registry UI, Distributed Agent Monitor, Code Review UI & Telemetry Dashboard (**S1-05, S2-02, S3-03, S4-03, S5-03**) |
| **2204012300** | **Mahmut Karaalioğlu** | **Developer** | `llama3.2:3b` (Database Agent) | Architecture Specification, SQLite Layer (`db_manager.py`), Safe Workspace Writer, Conflict Detection & Benchmark Data Export (**S1-03, S2-05, S3-04, S4-04, S5-04**) |
| **2204012303** | **Berat İnan** | **Developer** | `deepseek-coder:6.7b` (Testing Agent) | Ollama Hardware Research, Unit & Integration Test Suite, CI Quality Gate, Model Benchmarking & E2E Verification (**S1-06, S2-06, S3-06, S4-06, S5-06**) |
| **2204012297** | **Elif Yılmaz** | **Developer** | `phi4-mini:3.8b` (Integration Agent) | Streamlit UI Prototype, Inter-Agent Contracts, Task Schema Validation, Artifact Manifest Aggregation, Automated Code Review & Packaging (**S1-02, S2-04, S3-05, S4-05, S5-05**) |

---

## 2. 5-Sprint Master Schedule & Story Point Capacity

| Sprint | Iteration Dates (2026) | Theme / Focus Area | Trello Cards Included | Total Story Points | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | 1 – 15 Oct | Foundation & Requirements | `S1-01` – `S1-07` (7 Cards) | 24 SP | 52h | **Completed** |
| **Sprint 2** | 15 – 29 Oct | Agent Management & Task Assignment | `S2-01` – `S2-06` (6 Cards) | 22 SP | 44h | **Completed** |
| **Sprint 3** | 29 Oct – 12 Nov | Distributed Development | `S3-01` – `S3-06` (6 Cards) | 24 SP | 52h | **Completed** (6 of 6 Done) |
| **Sprint 4** | 12 – 26 Nov | Integration & Quality Assurance | `S4-01` – `S4-07` (7 Cards) | 29 SP | 62h | **In Progress** |
| **Sprint 5** | 26 Nov – 10 Dec | Complete System & Evaluation | `S5-01` – `S5-06` (6 Cards) | 20 SP | 42h | Planned |

---

## 3. Formal Scrum Events & Cadence

In accordance with the **2020 Scrum Guide**, each Sprint operates as a container for four formal opportunities to inspect and adapt:

1. **Sprint Planning (First Thursday of each Sprint, 90 mins):**
   * **Topic 1 (Why):** Product Owner provides requirements vision, and the Scrum Team collaborates to define the **Sprint Goal**.
   * **Topic 2 (What):** Developers select ready items from the Product Backlog.
   * **Topic 3 (How):** Developers decompose items into actionable tasks with checklists on Trello.
2. **Daily Scrum (Every weekday at 10:00, 15 mins):**
   * Developers inspect progress toward the Sprint Goal, synchronize daily development plans, and highlight any technical or hardware impediments.
3. **Sprint Review (Final Wednesday of each Sprint, 60 mins):**
   * The Scrum Team presents the working Increment (verified against the Definition of Done) to the Product Owner and stakeholders, discussing progress toward the Product Goal.
4. **Sprint Retrospective (Immediately following Sprint Review, 45 mins):**
   * The team inspects individuals, interactions, processes, tools, and the Definition of Done to identify actionable improvements for the next Sprint.