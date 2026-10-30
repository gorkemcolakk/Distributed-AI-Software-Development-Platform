# Scrum Calendar & Ceremony Schedule

* **Project Title:** Distributed AI Software Development Platform
* **Course:** CM6453 Software Engineering Process and DevOps
* **Instructor:** Prof. Dr. Ensar Gül
* **Team:** Team 3 (6 Members)
* **Scrum Master:** İrem Yılmaz (2204012301)
* **Cadence:** 5 Sprints × 2 Weeks (Total 10 Weeks: October 01, 2026 – December 10, 2026)

---

## 1. Scrum Team Roster, Accountabilities & Assigned Trello Cards

Within the Scrum Team, there are no sub-teams or hierarchies. In accordance with the **2020 Scrum Guide**, the team consists of one Scrum Master, one Product Owner, and Developers. When the Scrum Master and Product Owner participate in technical execution of Sprint Backlog items, they do so as Developers.

Each Trello card is assigned strictly to a single accountable owner:

| Student ID | Full Name | Scrum Accountability | Assigned Local Ollama Model | Primary Technical Focus | Owned Trello Cards |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2204012296** | **Eren Görkem Çolak** | **Developer** (Lead Architect) | `qwen2.5:3b` (Master Agent) | Master Orchestration, Task Decomposition, Capability Evaluation & Scheduler Lifecycle | **S1-01, S1-07, S2-03, S3-01, S4-01, S5-01** |
| **2204012301** | **İrem Yılmaz** | **Scrum Master & Developer** | `qwen2.5-coder:7b` (Backend Agent) | Scrum Process Facilitation, API Config & Fallback, Worker HTTP Server & Error Classification | **S1-04, S2-01, S3-02, S4-02, S5-02** |
| **2204012302** | **Kübra Hepcan** | **Developer** | `qwen2.5-coder:3b` / `gemma2:2b` (Frontend Agent) | UI/UX Design, Streamlit Dashboard, Requirements Specification & Distributed Telemetry Visuals | **S1-02, S1-05, S2-02, S3-03, S4-03, S5-03** |
| **2204012300** | **Mahmut Karaalioğlu** | **Developer** | `llama3.2:3b` (Database Agent) | System Architecture, SQLite Database Layer (`db_manager.py`), DAG Validation & Conflict Resolution | **S1-03, S2-05, S3-04, S4-04, S5-04** |
| **2204012297** | **Elif Yılmaz** | **Product Owner & Developer** | `phi4-mini:3.8b` (Integration Agent) | Product Backlog Management, Task Schema Validation, Artifact Aggregation & Automated Code Review | **S2-04, S3-05, S4-05, S5-05** *(+ Backlog Setup)* |
| **2204012303** | **Berat İnan** | **Developer** | `deepseek-coder:6.7b` (Testing & QA Agent) | Local Ollama Research, Automated Unit/Integration Tests, CI Quality Gate & Model Benchmarking | **S1-06, S2-06, S3-06, S4-06, S5-06** |

---

## 2. 5-Sprint Master Schedule & Story Point Capacity

| Sprint | Iteration Dates (2026) | Detailed Weekly Breakdown | Theme / Focus Area | Trello Cards Included | Story Points | Est. Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | Oct 01 – Oct 15 | **Week 1:** Oct 01 – Oct 08<br>**Week 2:** Oct 08 – Oct 15 | Foundation & Requirements Baseline | `S1-01` – `S1-07` (7 Cards) | 24 SP | 52h | **Completed** |
| **Sprint 2** | Oct 15 – Oct 29 | **Week 3:** Oct 15 – Oct 22<br>**Week 4:** Oct 22 – Oct 29 | Agent Registry, Fit Score & Lifecycle Isolation | `S2-01` – `S2-06` (6 Cards) | 20 SP | 38h | **Completed** |
| **Sprint 3** | Oct 29 – Nov 12 | **Week 5:** Oct 29 – Nov 05<br>**Week 6:** Nov 05 – Nov 12 | Distributed Execution & DAG Scheduling | `S3-01` – `S3-06` (6 Cards) | 24 SP | 54h | **In Progress** |
| **Sprint 4** | Nov 12 – Nov 26 | **Week 7:** Nov 12 – Nov 19<br>**Week 8:** Nov 19 – Nov 26 | Error Recovery, Code Review & CI Quality Gate | `S4-01` – `S4-06` (6 Cards) | 24 SP | 52h | Planned |
| **Sprint 5** | Nov 26 – Dec 10 | **Week 9:** Nov 26 – Dec 03<br>**Week 10:** Dec 03 – Dec 10 | Telemetry Dashboard, Benchmarking & E2E Release | `S5-01` – `S5-06` (6 Cards) | 20 SP | 40h | Planned |
| **Total** | **Oct 01 – Dec 10** | **10 Weeks (Weeks 1 – 10)** | **Complete Distributed Multi-Agent Platform** | **31 Cards** | **112 SP** | **236h** | **Active Project** |

---

## 3. Formal Scrum Events & Timeboxes

In accordance with the **2020 Scrum Guide**, each Sprint serves as a container for four formal inspection and adaptation events:

1. **Sprint Planning (First Thursday of each Sprint, 90 mins):**
   * **Topic One (Why is this Sprint valuable?):** The Product Owner presents how the product will increase in utility, and the Scrum Team collaborates to finalize the **Sprint Goal**.
   * **Topic Two (What can be Done this Sprint?):** Developers forecast and select items from the Product Backlog into the Sprint Backlog.
   * **Topic Three (How will the chosen work get done?):** Developers plan the technical tasks and checklists required to deliver an Increment meeting the Definition of Done.
2. **Daily Scrum (Every working day at 10:00, 15 mins):**
   * The Developers inspect daily progress toward the Sprint Goal and adapt the upcoming 24-hour plan, eliminating unnecessary ad-hoc meetings.
3. **Sprint Review (Final Wednesday of each Sprint, 60 mins):**
   * The Scrum Team and stakeholders inspect the working Increment produced during the Sprint, review what changed in the environment, and adapt the Product Backlog.
4. **Sprint Retrospective (Immediately following the Sprint Review, 45 mins):**
   * The Scrum Team inspects how the sprint went with respect to individuals, interactions, processes, tools, and the Definition of Done, establishing actionable improvements for the next Sprint.