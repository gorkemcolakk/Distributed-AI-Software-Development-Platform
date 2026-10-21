# Scrum Calendar & Ceremony Schedule

* **Project Title:** Distributed AI Software Development Platform
* **Course:** CM6453 Software Processes Term Project
* **Instructor:** Prof. Dr. Ensar Gül
* **Team:** Team 3 (6 Members)
* **Scrum Master:** İrem Yılmaz (2204012301)
* **Product Owner:** Elif Yılmaz (2204012297)
* **Cadence:** 5 Sprints × 2 Weeks (Total 10 Weeks: Sept 24, 2026 – Dec 02, 2026)

---

## 1. Scrum Team Roster, Accountabilities & Assigned Trello Cards

Within the Scrum Team, there are no sub-teams or hierarchies. In accordance with the **2020 Scrum Guide**, the team comprises one Scrum Master, one Product Owner, and Developers:

| Student ID | Full Name | Scrum Accountability | Assigned Local Ollama Model (`S1-06`) | Primary Technical Focus & Owned Trello Cards |
| :--- | :--- | :--- | :--- | :--- |
| **2204012301** | **İrem Yılmaz** | **Scrum Master & Developer** | `qwen2.5-coder:7b` (Backend Agent) | Scrum Facilitation, SQLite Data Layer (`db_manager.py`), API Config, Worker HTTP API & Retry Logic (**S1-04, S2-01, S2-07, S3-02, S4-01**) |
| **2204012297** | **Elif Yılmaz** | **Product Owner & Developer** | `phi4-mini:3.8b` (Integration Agent) | Product Backlog Management, Web UI Prototype, Evidence-Based Integration Agent, Security Policy & Release Docs (**S1-02, S4-02, S4-04, S5-04**) |
| **2204012296** | **Eren Görkem Çolak** | **Developer** (Tech Lead) | `qwen2.5:3b` (Master Agent) | Master Orchestrator, Analyzer, Weighted Selection, Run-Scoped Scheduler & Agent Contracts (**S1-01, S1-07, S2-03, S2-05, S3-01**) |
| **2204012300** | **Mahmut Karaalioğlu** | **Developer** | `llama3.2:3b` (Database Agent) | System Architecture, JSON Schema Validation, Safe Workspace Artifact Writer & DAG Validation (**S1-03, S2-04, S3-03, S3-04**) |
| **2204012302** | **Kübra Hepcan** | **Developer** | `qwen2.5-coder:3b` / `gemma2:2b` (Frontend Agent) | System Requirements (`SRS`), Streamlit UI Prototype, Unified Registry UI, Live Status & Telemetry Dashboard (**S1-02, S1-05, S2-02, S2-06, S5-01**) |
| **2204012303** | **Berat İnan** | **Developer** | `deepseek-coder:6.7b` (Testing Agent) | Ollama Hardware Research, Unit/Integration Test Suite, CI Quality Gate, Model Benchmarking & E2E Demo (**S1-06, S4-03, S5-02, S5-03**) |

---

## 2. 5-Sprint Master Schedule & Story Point Capacity

| Sprint | Iteration Dates (2026) | Theme / Focus Area | Trello Cards Included | Total Story Points | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | Sept 24 – Oct 07 | Foundation & Requirements | `S1-01` – `S1-07` (7 Cards) | 24 SP | 52h | **Completed** |
| **Sprint 2** | Oct 08 – Oct 21 | Agent Management & Task Assignment | `S2-01` – `S2-07` (7 Cards) | 22 SP | 44h | **In Progress** |
| **Sprint 3** | Oct 22 – Nov 04 | Distributed Development | `S3-01` – `S3-04` (4 Cards) | 18 SP | 42h | Planned |
| **Sprint 4** | Nov 05 – Nov 18 | Integration & Quality Assurance | `S4-01` – `S4-04` (4 Cards) | 16 SP | 40h | Planned |
| **Sprint 5** | Nov 19 – Dec 02 | Complete System & Evaluation | `S5-01` – `S5-04` (4 Cards) | 14 SP | 34h | Planned |

---

## 3. Formal Scrum Events & Cadence

In accordance with the **2020 Scrum Guide**, each Sprint operates as a container for four formal opportunities to inspect and adapt:

1. **Sprint Planning (First Thursday of each Sprint, 90 mins):**
   * **Topic 1 (Why):** Product Owner proposes how the product can increase value, and the team defines the **Sprint Goal**.
   * **Topic 2 (What):** Developers select ready items from the Product Backlog.
   * **Topic 3 (How):** Developers decompose items into actionable tasks with checklists on Trello.
2. **Daily Scrum (Every weekday at 10:00, 15 mins):**
   * Developers inspect progress toward the Sprint Goal, synchronize daily development plans, and highlight any technical or hardware impediments.
3. **Sprint Review (Final Wednesday of each Sprint, 60 mins):**
   * The Scrum Team demonstrates the working Increment (verified against the Definition of Done) and collaborates on Product Backlog adaptations.
4. **Sprint Retrospective (Immediately following Sprint Review, 45 mins):**
   * The team inspects individuals, interactions, processes, tools, and the Definition of Done to identify actionable improvements for the next Sprint.