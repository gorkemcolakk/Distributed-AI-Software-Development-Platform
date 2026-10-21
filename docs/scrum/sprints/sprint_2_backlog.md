# Sprint 2 Backlog & Task Distribution

* **Sprint Period:** 2026-10-08 – 2026-10-21 (Weeks 3 – 4)
* **Sprint Status:** **IN PROGRESS**

---

## 1. Commitment: Sprint Goal (Why)
Standardize API key and fallback configuration, unify the Streamlit UI and core Master Agent engine under a single canonical agent registry, enforce weighted capability-based agent selection with availability filtering (`BUSY`/`OFFLINE`/`ERROR`), validate task decomposition JSON schemas, and isolate per-run scheduler and SQLite persistence states (`run_id`).

---

## 2. Selected Product Backlog Items & Action Plan (What & How)

| Card ID | Task Title | Primary Assignee | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Fix API Key Configuration & Remove Credential-Like Constants (`app.py`, `.env.example`) | İrem Yılmaz | Highest | 3 | 4h | S1-06 | Done |
| **S2-02** | Unify Streamlit UI and Core Engine Under a Single Agent Registry (`agents_config.json`) | Kübra Hepcan | Highest | 5 | 10h | S1-06, S2-01 | In Progress |
| **S2-03** | Use Weighted Task-Fitness Scoring & Filter Out Unavailable Agents (`capability_eval.py`) | Eren Görkem Çolak | High | 3 | 6h | S2-02, S1-06 | In Progress |
| **S2-04** | Validate Task Decomposition Output & Make Fallback Behavior Reliable (`analyzer.py`, `app.py`) | Mahmut Karaalioğlu | High | 3 | 6h | S2-01, S2-02, S1-05 | To Do |
| **S2-05** | Fix Scheduler Lifecycle (`run_id`) & Accurately Report Failed/Unassigned Tasks (`scheduler.py`, `orchestrator.py`) | Eren Görkem Çolak | Highest | 3 | 8h | S2-03, S2-04 | To Do |
| **S2-06** | Bind Visible UI Task Assignments & Statuses to Real Engine Results (`app.py`) | Kübra Hepcan | High | 3 | 6h | S2-02, S2-03, S2-05 | To Do |
| **S2-07** | Integrate SQLite Persistence Layer (`db_manager.py`) with Unified Agent Registry & Run Lifecycle | İrem Yılmaz | High | 2 | 4h | S1-04, S2-02, S2-05 | To Do |

**Total Sprint 2 Capacity:** 22 Story Points (44 Estimated Hours)

---

## 3. Sprint 2 Verification & Acceptance Checklist
- [x] **S2-01:** Only a single `load_api_key` path remains; missing keys trigger clearly labeled demo/fallback mode without errors.
- [ ] **S2-02:** Hardcoded `agents_data` in `app.py` is replaced by the canonical `config/agents_config.json` loader.
- [ ] **S2-03:** `BUSY`, `OFFLINE`, and `ERROR` agents are excluded from candidate selection; specialty bonuses and tie-breakers are unit-tested.
- [ ] **S2-04:** Malformed JSON, empty requirements, and multi-paragraph long requirement documents are validated against the task schema.
- [ ] **S2-05:** Consecutive orchestrator runs execute independently under unique `run_id` values; failed/unassigned tasks are never marked `COMPLETED`.
- [ ] **S2-06:** UI task progress reflects backend execution states rather than manual simulation buttons.
- [ ] **S2-07:** `src/master/db_manager.py` schema supports `run_id` and updated task states; `state.db` is excluded via `.gitignore`.