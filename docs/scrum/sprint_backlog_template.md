# Standard Sprint Backlog Template
## Distributed AI Software Development Platform (CM6453)

* **Document Owner:** İrem Yılmaz (Scrum Master & Developer — `qwen2.5-coder:7b`)
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Application Scope:** Distributed AI Software Development Platform — All Sprint Planning & Backlog Management
* **Framework:** Scrum (2020 Scrum Guide, 5 Sprints × 2 Weeks = 10 Weeks)
* **Commitment:** Sprint Goal

---

## 1. Sprint General Information & Team Roster
* **Sprint Number:** Sprint [X]
* **Sprint Period:** YYYY-MM-DD – YYYY-MM-DD (Weeks [X*2-1] – [X*2])
* **Sprint Planning Date:** YYYY-MM-DD
* **Sprint Status:** [PLANNED / ACTIVE / IN PROGRESS / COMPLETED]
* **Scrum Team Roster & Accountabilities:**
  - **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
  - **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - **Developers:**
    - Eren Görkem Çolak (Master Agent — `qwen2.5:3b` / `qwen2.5:7b`)
    - Kübra Hepcan (Frontend Agent — `qwen2.5-coder:3b`)
    - Mahmut Karaalioğlu (Database Agent — `llama3.2:3b`)
    - Berat İnan (Testing Agent — `deepseek-coder:6.7b`)
    - İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
    - Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`)

---

## 2. Commitment: Sprint Goal (Topic One: Why is this Sprint valuable?)

> *"[Single overarching objective formulated collaboratively by the Scrum Team during Sprint Planning that communicates why the Sprint is valuable to stakeholders.]"*

---

## 3. Selected Product Backlog Items & Owners (Topic Two: What can be done this Sprint?)

The Developers select items from the Product Backlog, forecast delivery capacity, and assign primary owners:

| Card ID | PBI Title & Scope | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Initial Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S[X]-01** | [Task Title] | [Member Name & Agent Model] | Highest / High | [SP] | [H]h | [Dep IDs] | Sprint Backlog |
| **S[X]-02** | [Task Title] | [Member Name & Agent Model] | High | [SP] | [H]h | [Dep IDs] | Sprint Backlog |
| **S[X]-03** | [Task Title] | [Member Name & Agent Model] | High | [SP] | [H]h | [Dep IDs] | Sprint Backlog |

* **Total Sprint Committed Capacity:** **[X] Story Points** ([H] Estimated Development Hours)
* **Carry-over Work (if applicable):** [List of rolled-over items from prior sprint with SP]
* **New Committed Work:** [List of newly pulled PBIs with SP]

---

## 4. Actionable Task Breakdown & Checklists (Topic Three: How will the chosen work get done?)

Each selected Product Backlog Item is decomposed into concrete, testable technical tasks and acceptance criteria:

### S[X]-01: [Task Title]
- [ ] 1. [Specific architectural or implementation step]
- [ ] 2. [Data contract, schema, or endpoint requirement]
- [ ] 3. [Error handling, boundary, or security check]
- [ ] 4. [Unit / integration test verification condition]

### S[X]-02: [Task Title]
- [ ] 1. [Implementation step]
- [ ] 2. [Implementation step]
- [ ] 3. [Validation criteria]

---

## 5. Capacity & Workload Allocation Matrix

| Developer | Student ID | Agent & Model | Assigned Cards | Total SP | Est. Hours | Availability Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:3b`) | S[X]-01 | [SP] | [H]h | 100% capacity |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | S[X]-02 | [SP] | [H]h | 100% capacity |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | S[X]-03 | [SP] | [H]h | 100% capacity |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | S[X]-04 | [SP] | [H]h | 100% capacity |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | S[X]-05 | [SP] | [H]h | 100% capacity |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | S[X]-06 | [SP] | [H]h | 100% capacity |

---

## 6. Definition of Done Compliance & Verification Strategy

All selected items must satisfy the [Definition of Done](../definition_of_done.md) before presentation at the Sprint Review:
- [ ] **Working Software:** Implementation executes cleanly in target Python 3.10+ / Streamlit runtime.
- [ ] **Deterministic Testing:** Mock-based offline unit tests pass (`python -m unittest discover -s tests`).
- [ ] **CI Quality Gate:** GitHub Actions workflow passes cleanly on all PRs.
- [ ] **Physical Sandboxing:** File writes confined to `workspaces/{run_id}/`; path traversal rejected.
- [ ] **Zero Hardcoded Secrets:** Dynamic `.env` configuration verified; no secrets in logs or git.
- [ ] **Truth in Reporting:** Unfinished items are never marked COMPLETED; rolled over honestly.

---

**Plan Created By:** Scrum Team at Sprint Planning  
**Facilitated By:** İrem Yılmaz (Scrum Master)  
**Reviewed By:** Prof. Dr. Ensar Gül (Product Owner)  
