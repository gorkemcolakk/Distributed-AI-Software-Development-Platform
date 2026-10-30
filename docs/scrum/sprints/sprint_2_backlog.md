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
| **S2-02** | Unify Streamlit UI with Shared Agent Registry & Engine Status Monitoring (`app.py`, `agents_config.json`) | Kübra Hepcan | Highest | 5 | 10h | S1-06, S2-01 | Done |
| **S2-03** | Master Agent Weighted Selection Algorithm, Availability Filtering & Scheduler Lifecycle (`capability_eval.py`, `scheduler.py`) | Eren Görkem Çolak | High | 3 | 6h | S1-07 | Done |
| **S2-04** | Task Classification Schema Validation & Inter-Agent Integration Contracts (`contracts.py`, `analyzer.py`) | Elif Yılmaz | High | 3 | 6h | S1-05 | Done |
| **S2-05** | SQLite Database Layer Integration (`db_manager.py`) with Capabilities and Run States (`DATA_MODEL.md`) | Mahmut Karaalioğlu | High | 3 | 6h | S1-04, S2-03 | Done |
| **S2-06** | Automated Unit Tests (Pytest/Unittest) for Selection, Schema Validation & Scheduler (`test_master_engine.py`) | Berat İnan | High | 3 | 6h | S2-03, S2-04 | Done |

**Total Sprint 2 Capacity:** 20 Story Points (38 Estimated Hours) | **Delivered:** 20 Story Points (100%)

---

## 3. Sprint 2 Verification & Acceptance Checklist
- [x] **S2-01:** Only a single `load_api_key()` path remains; missing keys trigger clearly labeled demo/fallback mode without unhandled exceptions.
- [x] **S2-02:** Hardcoded `agents_data` in `app.py` is removed; UI reads dynamically from `config/agents_config.json`.
- [x] **S2-03:** `BUSY`, `OFFLINE`, and `ERROR` agents are filtered from selection; weighted fit score and specialty bonus implemented.
- [x] **S2-04:** Pydantic contracts and schema validation (`validate_master_tasks`) verify required fields (`task_id`, `title`, `category`, `dependencies`).
- [x] **S2-05:** `src/master/db_manager.py` schema incorporates `run_id`, agent capability profiles, and multi-tier completion guards.
- [x] **S2-06:** Deterministic test suite (`tests/test_master_engine.py`, `tests/test_api_config_fallback.py`) runs 44 tests and passes with 0 failures without external credentials.
