# Standard Sprint Review, Retrospective & Progress Report Template
## Distributed AI Software Development Platform (CM6453)

* **Document Owner:** İrem Yılmaz (Scrum Master & Developer — `qwen2.5-coder:7b`)
* **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
* **Application Scope:** Distributed AI Software Development Platform — All Sprint Reviews, Retrospectives, and Course Progress Reports
* **Framework:** Scrum (2020 Scrum Guide, 5 Sprints × 2 Weeks = 10 Weeks)
* **Course Requirement:** CM6453 Term Project — Product Increment, Sprint Backlog, Task Assignments, Review/Demo, Retrospective, and Progress Report

---

## 1. Sprint General Information & Team Accountabilities
* **Sprint Number:** Sprint [X]
* **Sprint Period:** YYYY-MM-DD – YYYY-MM-DD (Weeks [X] – [Y])
* **Sprint Goal (Why):** [Single objective committed by the Scrum Team during Sprint Planning]
* **Sprint Status:** [COMPLETED / IN PROGRESS / CLOSED]
* **Capacity & Velocity Metrics:**
  - **Committed Capacity:** [X] Story Points ([H] Estimated Hours)
  - **Delivered Velocity:** [Y] Story Points ([Z]% Completion Rate)
  - **Rolled Over to Next Sprint:** [W] Story Points
* **Scrum Accountabilities:**
  - **Product Owner:** Prof. Dr. Ensar Gül (Course Instructor)
  - **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - **Developers:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz

---

## 2. Sprint Review (At the Review)

### 2.1. Delivered Product Increment & Observable Evidence (What Was Demonstrated)
In accordance with the 2020 Scrum Guide, only Product Backlog Items that meet the Definition of Done are presented as part of the usable Increment.

| Card ID | Task Title & Scope | Primary Assignee | Repository Evidence (Files & Modules) | Verification Outcome & Acceptance Status |
| :--- | :--- | :--- | :--- | :--- |
| **S[X]-01** | [Task Title] | [Assignee & Model] | `path/to/file1.py`, `docs/...` | [VERIFIED / DONE — Observable runtime behavior and acceptance criteria fulfilled] |
| **S[X]-02** | [Task Title] | [Assignee & Model] | `path/to/file2.py` | [VERIFIED / DONE] |
| **S[X]-03** | [Task Title] | [Assignee & Model] | `path/to/file3.py` | [INCOMPLETE — Reason and roll-over status to next sprint] |

### 2.2. Verification & Terminal Evidence
Reproducible command-line outputs, test reports, and runtime logs demonstrating the working Increment:

```bash
# Automated unit & integration test execution
python -m unittest discover -s tests

# Runtime engine execution / demonstration
python -m src.master.orchestrator "Sample software specification requirement"
```

* **Test Suite Output:** `Ran X tests in Y.YYYs — OK`
* **Observable Demonstration Highlights:**
  - [Highlight 1: Working feature demonstrated to stakeholders]
  - [Highlight 2: Live multi-agent interaction or UI behavior]

### 2.3. Stakeholder Feedback (Product Owner Inspection)
* **Feedback from Prof. Dr. Ensar Gül (Course Instructor / Product Owner):**
  - [Key observations and evaluation on the demonstrated Increment]
  - [Guidance on technical scope, architecture, or academic deliverables]
* **Stakeholder Acceptance Verdict:** [ACCEPTED / ACCEPTED WITH CONDITIONS / RE-ESTIMATE]

### 2.4. Product Backlog Adaptations & Changes (Resulting from the Review)
* [Changes made to the Product Backlog ordering or priority based on stakeholder review]
* [New items identified, or scope clarifications negotiated with the Product Owner]
* [Carry-over items returned to the Product Backlog and reprioritized for the next sprint]

---

## 3. Sprint Retrospective (At the Retrospective)

In accordance with the 2020 Scrum Guide, the Scrum Team inspects the last Sprint with regards to individuals, interactions, processes, tools, and the Definition of Done.

### 3.1. Team Observations: What Went Well?
* [High-performing engineering practices, effective collaboration patterns]
* [Architectural milestones and code quality improvements]
* [Successful process adaptations and tooling usage]

### 3.2. Team Observations: Challenges & Identified Technical Debt
* [Impediments, unexpected bottlenecks, or hardware constraints encountered]
* [Gaps between mocked/fallback implementations and live multi-agent execution]
* [Process friction or coordination delays]

### 3.3. Actionable Improvement Items for Next Sprint
Measurable process, tool, or quality improvements prioritized for immediate adoption:

| Improvement Action Item | Target Area | Assignee / Owner | Success Criteria |
| :--- | :--- | :--- | :--- |
| [Action Item 1] | [Process / Code / Quality] | [Member Name] | [Measurable Outcome] |
| [Action Item 2] | [Infrastructure / Testing] | [Member Name] | [Measurable Outcome] |

---

## 4. Course Progress Report (Mandated by CM6453 Syllabus)

### 4.1. Project Milestone & Schedule Status
* **Iteration Timeline:** Sprint [X] of 5 (Week [X*2-1] – [X*2] of 10-Week Semester Schedule)
* **Milestone Objective:** [Phase milestone from course project syllabus]
* **Schedule Variance:** [On Schedule / Minor Delay / Ahead of Schedule]

### 4.2. Cumulative Velocity & Story Point Burnup Tracking
* **Sprint 1 Velocity:** 24 SP (Completed)
* **Sprint 2 Velocity:** 22 SP (Completed)
* **Sprint 3 Velocity:** 18 SP Completed (6 SP Rolled Over)
* **Total Cumulative Story Points Delivered to Date:** [Total] SP
* **Sprint 4 Committed Capacity:** [X] SP

### 4.3. Team Member Contribution Matrix

| Team Member | Student ID | Agent & Model | Sprint Role & Primary Deliverables | Estimated vs Actual Hours | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eren Görkem Çolak** | 2204012296 | Master Agent (`qwen2.5:3b`) | Tech Lead: [Deliverables] | [Est]h / [Act]h | Done |
| **İrem Yılmaz** | 2204012301 | Backend Agent (`qwen2.5-coder:7b`) | Scrum Master: [Deliverables] | [Est]h / [Act]h | Done |
| **Kübra Hepcan** | 2204012302 | Frontend Agent (`qwen2.5-coder:3b`) | Developer: [Deliverables] | [Est]h / [Act]h | In Progress |
| **Mahmut Karaalioğlu** | 2204012300 | Database Agent (`llama3.2:3b`) | Developer: [Deliverables] | [Est]h / [Act]h | Done |
| **Berat İnan** | 2204012303 | Testing Agent (`deepseek-coder:6.7b`) | Developer: [Deliverables] | [Est]h / [Act]h | Done |
| **Elif Yılmaz** | 2204012297 | Integration Agent (`phi4-mini:3.8b`) | Developer: [Deliverables] | [Est]h / [Act]h | In Backlog |

### 4.4. Risk Assessment & Mitigation Strategies
* **Risk 1:** [Identified technical or schedule risk]  
  * *Mitigation:* [Concrete risk mitigation action]
* **Risk 2:** [Identified technical or schedule risk]  
  * *Mitigation:* [Concrete risk mitigation action]

### 4.5. Next Sprint Focus & Functional Increment Preview
* [Concise preview of the functional increment planned for the upcoming sprint]

---

**Report Prepared By:** İrem Yılmaz (Scrum Master)  