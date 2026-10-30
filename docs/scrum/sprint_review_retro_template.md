# Standard Sprint Review & Retrospective Template

* **Prepared by:** İrem Yılmaz (Scrum Master & Backend Agent — `qwen2.5-coder:7b`)  
* **Application Scope:** Distributed AI Software Development Platform — All Sprint Closures  
* **Methodology:** Scrum Framework (5 Iterations / 10 Weeks)  

---

## 1. Sprint General Information
* **Sprint Name:** Sprint [X]
* **Sprint Period:** October [XX], 2026 – November/December [XX], 2026 (Weeks [X] – [Y])
  * *Week [X]:* [Date] – [Date]
  * *Week [Y]:* [Date] – [Date]
* **Commitment: Sprint Goal (Why):** [Formal Sprint Goal agreed during Sprint Planning describing why the Sprint is valuable]
* **Sprint Status:** [COMPLETED / IN PROGRESS / UNDER REVIEW]
* **Capacity & Velocity:** Planned: [X] SP ([A]h) | Delivered: [Y] SP ([B]h) ([Z]% Completion Rate)

---

## 2. Delivered Increment & Observable Evidence (Sprint Review)

In accordance with the **2020 Scrum Guide**, the Scrum Team presents the increment of value delivered during the Sprint. Each item has been verified against the **Definition of Done**:

| Card ID | Task Title & Scope | Responsible | Repository Evidence (Files & Modules) | Verification & DoD Acceptance Status |
| :--- | :--- | :--- | :--- | :--- |
| **S[X]-01** | [Task Title] | [Assigned Developer] | `path/to/file1.py`, `docs/...` | [Passed unit tests / DoD verified] |
| **S[X]-02** | [Task Title] | [Assigned Developer] | `path/to/file2.py` | [Passed unit tests / DoD verified] |
| **S[X]-03** | [Task Title] | [Assigned Developer] | `path/to/file3.py` | [Passed unit tests / DoD verified] |
| **S[X]-04** | [Task Title] | [Assigned Developer] | `path/to/file4.py` | [Passed unit tests / DoD verified] |
| **S[X]-05** | [Task Title] | [Assigned Developer] | `path/to/file5.py` | [Passed unit tests / DoD verified] |
| **S[X]-06** | [Task Title] | [Assigned Developer] | `path/to/file6.py` | [Passed unit tests / DoD verified] |

---

## 3. Terminal & Test Verification Evidence
Observable command line execution outputs and automated test results demonstrating the working increment:

```bash
# Execute automated test suite
python -m unittest discover -s tests

# Verify Master Agent orchestration CLI
python -m src.master.orchestrator "Requirement prompt example"
```

* **Test Execution Summary:** `Ran X tests in Ys — OK`
* **Key Observable Behaviors:**
  - *Observation 1:* [Decomposition / Routing / Contract verification]
  - *Observation 2:* [Fallback / Persistence / Telemetry verification]

---

## 4. Sprint Retrospective (Inspection & Adaptation)

The purpose of the Sprint Retrospective is to plan ways to increase quality and effectiveness. The team inspects how the Sprint went with regards to individuals, interactions, processes, tools, and the Definition of Done.

### 4.1. What Went Well?
* [Process, communication, or teamwork strengths to maintain]
* [Technical, architectural, or code quality milestones achieved]
* [Effective collaboration between Product Owner, Scrum Master, and Developers]

### 4.2. Challenges & Identified Technical Debt
* [Unanticipated technical hurdles or hardware limitations (e.g., local model VRAM/latency)]
* [Transition gaps between mock/fallback states and live distributed execution]
* [Estimation inaccuracies or blocked dependencies]

### 4.3. Actionable Improvements for the Next Sprint
* **[Owner Name]:** [Specific action item to improve process or engineering practice]
* **[Owner Name]:** [Remediation step for identified technical debt]

---

**Scrum Master:** İrem Yılmaz  
