# Sprint 2 Backlog & Task Distribution

* **Sprint Period:** October 15, 2026 – October 29, 2026 (Weeks 3 – 4)
  * **Sprint 2 – Week 3:** October 15, 2026 – October 22, 2026
  * **Sprint 2 – Week 4:** October 22, 2026 – October 29, 2026
* **Sprint Status:** **COMPLETED**
* **Scrum Master:** İrem Yılmaz (Backend Agent & Scrum Master)

---

## 1. Commitment: Sprint Goal (Why)
Standardize runtime API configuration and safe fallback logic, unify the Streamlit UI and core engine under a single canonical agent registry (`agents_config.json`), enforce weighted capability selection with availability filtering (`BUSY`/`OFFLINE`/`ERROR`), validate task decomposition JSON schemas, isolate per-run scheduler lifecycle states (`run_id`), and integrate SQLite persistence with comprehensive automated unit tests.

---

## 2. Selected Product Backlog Items & Task Plan (What & How)

| Card ID | Task Title & Scope | Responsible | Priority | Story Points | Est. Hours | Dependencies | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Backend API / Local Ollama Standardization & Safe Fallback (`app.py`, `.env.example`) | İrem Yılmaz | Highest | 3 | 4h | S1-06 | Done |
| **S2-02** | Unify Streamlit UI with Shared Agent Registry (`app.py`, `agents_config.json`) | Kübra Hepcan | Highest | 5 | 10h | S1-06, S2-01 | Done (PR #20) |
| **S2-03** | Master Agent Weighted Selection Algorithm & Availability Filtering (`capability_eval.py`) | Eren Görkem Çolak | High | 3 | 6h | S2-02, S1-06 | Done |
| **S2-04** | Task Schema Validation & Inter-Agent Integration Contracts (`contracts.py`, `analyzer.py`, `app.py`) | Elif Yılmaz | High | 3 | 6h | S2-01, S2-02, S1-05 | Done |
| **S2-05** | Run-Scoped Scheduler Lifecycle (`run_id`) & Failed/Unassigned Task Reporting (`scheduler.py`, `orchestrator.py`) | Eren Görkem Çolak | Highest | 3 | 8h | S2-03, S2-04 | Done |
| **S2-06** | Bind Visible UI Task Assignments & Statuses to Real Engine Results (`app.py`) | Kübra Hepcan | High | 3 | 6h | S2-02, S2-03, S2-05 | Done (PRs #20, #23, #24) |
| **S2-07** | SQLite Persistence Layer (`db_manager.py`) with Unified Agent Registry & Run Lifecycle | Mahmut Karaalioğlu | High | 2 | 4h | S1-04, S2-02, S2-05 | Done |

**Total Sprint 2 Capacity:** 22 Story Points (44 Estimated Hours) | **Delivered:** 22 Story Points (100%)

**Ownership changes during the sprint:** S2-04 moved from Mahmut Karaalioğlu to Elif Yılmaz, and S2-07 moved from İrem Yılmaz to Mahmut Karaalioğlu (the Sprint 1 plan listed the original owners). Supporting work: Berat İnan wrote the unit tests for S2-03, S2-04 and S2-05 (`tests/test_master_engine.py`); Eren Görkem Çolak added the GitHub Actions CI workflow (PR #22).

---

## 3. Sprint 2 Verification & Acceptance Checklist
- [x] **S2-01:** Only a single `load_api_key()` path remains; missing keys trigger clearly labeled demo/fallback mode without unhandled exceptions.
- [x] **S2-02:** Hardcoded `agents_data` in `app.py` is replaced by the canonical `config/agents_config.json` loader.
- [x] **S2-03:** `BUSY`, `OFFLINE`, and `ERROR` agents are excluded from candidate selection; specialty bonuses are unit-tested. *(No dedicated tie-breaker test yet; carried to Sprint 3.)*
- [x] **S2-04:** Malformed JSON and empty requirements are validated against the task schema. *(No multi-paragraph long-document test yet, and `validate_master_tasks()` is not yet called by the orchestrator; both carried to Sprint 3.)*
- [x] **S2-05:** Consecutive orchestrator runs execute independently under unique `run_id` values; failed/unassigned tasks are never marked `COMPLETED`.
- [x] **S2-06:** UI task progress reflects backend execution states rather than manual simulation buttons.
- [x] **S2-07:** `src/master/db_manager.py` schema supports `run_id` and updated task states; `state.db` is excluded via `.gitignore`.
