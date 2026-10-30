# 5-Sprint Project Execution Roadmap

## Overview
This document outlines the detailed 5-sprint agile execution roadmap for the **CM6453 Software Engineering Process and DevOps** term project: **Distributed AI Software Development Platform**. The project spans 10 weeks across 5 two-week sprints (October 01, 2026 – December 10, 2026). Each sprint delivers a functional, verifiable product increment meeting the Definition of Done.

In accordance with project governance, every Trello card is assigned strictly to a single accountable owner.

---

## 🏃 Sprint 1 — Foundation & Requirements Baseline (Weeks 1–2: Oct 01 – Oct 15, 2026)
* **Sprint 1 – Week 1:** October 01, 2026 – October 08, 2026
* **Sprint 1 – Week 2:** October 08, 2026 – October 15, 2026
* **Sprint Goal:** Establish repository governance, define testable system requirements, document multi-agent architecture and SQLite data model, verify local Ollama models across team hardware, and deliver working prototypes for the Streamlit web UI and Master Agent task decomposition engine.
* **Status:** **COMPLETED** (24 / 24 Story Points)

### Deliverables & Trello Mapping:
- [x] **S1-01:** GitHub Repository Setup, Branch Protection & Team Workflow Guidelines (`README.md`, `.gitignore`, `start.bat`) — **Owner: Eren Görkem Çolak** [2 SP]
- [x] **S1-02:** Initial Streamlit Web Interface Prototype (`master_agent_projesi/app.py`, `requirements.txt`) — **Owner: Kübra Hepcan** [5 SP]
- [x] **S1-03:** Comprehensive System Architecture & Component Boundaries Specification (`docs/ARCHITECTURE.md`) — **Owner: Mahmut Karaalioğlu** [3 SP]
- [x] **S1-04:** Initial Data Model & SQLite Persistent Storage Design (`docs/DATA_MODEL.md`, `src/master/db_manager.py`) — **Owner: İrem Yılmaz** [3 SP]
- [x] **S1-05:** System Requirements Inventory & Testable Acceptance Criteria (`docs/SRS.md`, `docs/scrum/product_backlog.md`) — **Owner: Kübra Hepcan** [3 SP]
- [x] **S1-06:** Local Ollama Model Research & Hardware Capability Matrix (`docs/MODEL_RESEARCH.md`, `config/agents_config.json`) — **Owner: Berat İnan** [3 SP]
- [x] **S1-07:** Master-Agent Orchestrator & Basic Task Decomposition Engine (`src/master/orchestrator.py`, `src/master/analyzer.py`, `tests/test_master_engine.py`) — **Owner: Eren Görkem Çolak** [5 SP]

---

## 🏃 Sprint 2 — Agent Registry, Fit Score & Lifecycle Isolation (Weeks 3–4: Oct 15 – Oct 29, 2026)
* **Sprint 2 – Week 3:** October 15, 2026 – October 22, 2026
* **Sprint 2 – Week 4:** October 22, 2026 – October 29, 2026
* **Sprint Goal:** Standardize runtime API configuration and safe fallback logic, unify the Streamlit UI and core engine under a single canonical agent registry (`agents_config.json`), enforce weighted capability selection with availability filtering (`BUSY`/`OFFLINE`/`ERROR`), validate task decomposition JSON schemas, isolate per-run scheduler lifecycle states (`run_id`), and integrate SQLite persistence with automated unit tests.
* **Status:** **COMPLETED** (22 / 22 Story Points)

### Deliverables & Trello Mapping:
- [x] **S2-01:** Backend API & Local Ollama Standardization and Safe Fallback (`app.py`, `.env.example`, `tests/test_api_config_fallback.py`) — **Owner: İrem Yılmaz** [3 SP]
- [x] **S2-02:** Unify Streamlit UI with Shared Agent Registry & Engine Status Monitoring (`config/agents_config.json`, `app.py`) — **Owner: Kübra Hepcan** [5 SP]
- [x] **S2-03:** Master Agent Weighted Selection Algorithm, Availability Filtering (`src/master/capability_eval.py`, `src/master/orchestrator.py`) — **Owner: Eren Görkem Çolak** [3 SP]
- [x] **S2-04:** Task Classification Schema Validation & Inter-Agent Integration Contracts (`src/contracts.py`, `docs/INTER_AGENT_CONTRACTS.md`) — **Owner: Elif Yılmaz** [3 SP]
- [x] **S2-05:** Run-Scoped Scheduler Lifecycle (`run_id`) & Failed/Unassigned Task Reporting (`src/master/scheduler.py`, `src/master/orchestrator.py`) — **Owner: Eren Görkem Çolak** [3 SP]
- [x] **S2-06:** Bind Visible UI Task Assignments & Statuses to Real Engine Results (`master_agent_projesi/app.py`) — **Owner: Kübra Hepcan** [3 SP]
- [x] **S2-07:** SQLite Persistence Layer Integration (`db_manager.py`) with Unified Agent Registry & Run Lifecycle (`docs/DATA_MODEL.md`, `tests/test_db_manager.py`) — **Owner: Mahmut Karaalioğlu** [2 SP]

---

## 🏃 Sprint 3 — Distributed Execution & DAG Scheduling (Weeks 5–6: Oct 29 – Nov 12, 2026)
* **Sprint 3 – Week 5:** October 29, 2026 – November 05, 2026
* **Sprint 3 – Week 6:** November 05, 2026 – November 12, 2026
* **Sprint Goal:** Define versioned Master–Worker HTTP/JSON task contracts (`contracts.py`), implement authenticated Worker Agent endpoints (`src/api/`), execute live local Ollama code generation across worker agents in isolated workspaces, validate the task dependency graph (DAG) to prevent cycle deadlocks, and aggregate output artifacts into standardized manifests.
* **Status:** **IN PROGRESS** (8 / 24 Story Points Completed)

### Deliverables & Trello Mapping:
- [ ] **S3-01:** Define Master–Worker HTTP/JSON Task Contracts & Orchestrate Distributed Dispatch (`src/contracts.py`, `docs/INTER_AGENT_CONTRACTS.md`) — **Owner: Eren Görkem Çolak** [5 SP]
- [x] **S3-02:** Develop Authenticated Worker Agent HTTP API Endpoint & BackendAgent Ollama Code Generation (`src/api/worker_server.py`, `src/agents/backend_agent.py`) — **Owner: İrem Yılmaz** [5 SP]
- [ ] **S3-03:** Connect FrontendAgent Local Ollama UI Code Generation & Display Distributed Agent/File Status in UI (`src/agents/frontend_agent.py`, `app.py`) — **Owner: Kübra Hepcan** [3 SP]
- [ ] **S3-04:** Validate Task Dependency Graph (DAG), Generate DatabaseAgent SQL & Establish Secure Workspace Writer (`src/master/scheduler.py`, `src/agents/database_agent.py`) — **Owner: Mahmut Karaalioğlu** [5 SP]
- [ ] **S3-05:** Collect Worker Agent Output Files & Artifact Manifest in Common Project Structure (`src/agents/integration_agent.py`, `src/contracts.py`) — **Owner: Elif Yılmaz** [3 SP]
- [x] **S3-06:** Connect TestingAgent Local Ollama Test Generation & Implement Distributed Communication/DAG Unit Tests (`src/agents/testing_agent.py`, `tests/test_worker_http.py`) — **Owner: Berat İnan** [3 SP]

---

## 🏃 Sprint 4 — Error Recovery, Code Review & CI Quality Gate (Weeks 7–8: Nov 12 – Nov 26, 2026)
* **Sprint 4 – Week 7:** November 12, 2026 – November 19, 2026
* **Sprint 4 – Week 8:** November 19, 2026 – November 26, 2026
* **Sprint Goal:** Implement bounded retry and alternative agent reassignment for failed tasks, build automated syntax and conflict inspection in the Integration Agent, establish a repeatable CI quality gate via GitHub Actions, and harden input/output security.
* **Status:** Planned (24 Story Points)

### Deliverables & Trello Mapping:
- [ ] **S4-01:** Bounded Task Retry & Alternative Agent Reassignment Mechanism (`src/master/orchestrator.py`, `src/master/scheduler.py`) — **Owner: Eren Görkem Çolak** [5 SP]
- [ ] **S4-02:** Error Detection, Transient/Permanent Classification & I/O Security Hardening (`src/agents/base_agent.py`, `src/api/`) — **Owner: İrem Yılmaz** [3 SP]
- [ ] **S4-03:** Display Code Review Findings, Conflict Warnings & Reassignment History in UI (`master_agent_projesi/app.py`) — **Owner: Kübra Hepcan** [3 SP]
- [ ] **S4-04:** Detect Path/Schema Conflicts & Persist Attempt/Output History in SQLite (`src/master/db_manager.py`, `tests/test_db_manager.py`) — **Owner: Mahmut Karaalioğlu** [3 SP]
- [ ] **S4-05:** Automated Syntax & Code Review via Local Integration Agent & Project Merging (`src/agents/integration_agent.py`, `src/contracts.py`) — **Owner: Elif Yılmaz** [5 SP]
- [ ] **S4-06:** Expand Test Suite, Verify Generated Code & Harden GitHub Actions CI Quality Gate (`tests/`, `.github/workflows/tests.yml`) — **Owner: Berat İnan** [5 SP]

---

## 🏃 Sprint 5 — Telemetry Dashboard, Benchmarking & E2E Release (Weeks 9–10: Nov 26 – Dec 10, 2026)
* **Sprint 5 – Week 9:** November 26, 2026 – December 03, 2026
* **Sprint 5 – Week 10:** December 03, 2026 – December 10, 2026
* **Sprint Goal:** Display real execution telemetry on the dashboard, empirically benchmark local Ollama models across standardized tasks, verify the end-to-end distributed workflow, and synchronize all project documentation for release.
* **Status:** Planned (20 Story Points)

### Deliverables & Trello Mapping:
- [ ] **S5-01:** End-to-End Distributed Orchestration Workflow & Runtime Telemetry/Latency Recording (`src/master/orchestrator.py`) — **Owner: Eren Görkem Çolak** [3 SP]
- [ ] **S5-02:** Synchronize README, Architecture, Definition of Done & Scrum Release Documents (`README.md`, `docs/ARCHITECTURE.md`, `docs/scrum/*`) — **Owner: İrem Yılmaz** [3 SP]
- [ ] **S5-03:** Real Execution Telemetry, Latency & Agent/Model Comparison Charts on Dashboard (`master_agent_projesi/app.py`) — **Owner: Kübra Hepcan** [3 SP]
- [ ] **S5-04:** SQLite Execution History & Benchmark Metric Export (CSV/JSON) & Verification (`src/master/db_manager.py`, `docs/DATA_MODEL.md`) — **Owner: Mahmut Karaalioğlu** [3 SP]
- [ ] **S5-05:** End-to-End Live Demonstration Scenario, Final Web App Verification & PO Acceptance (`docs/model_tests/sample_requirement.md`, Demo) — **Owner: Elif Yılmaz** [3 SP]
- [ ] **S5-06:** Empirical Local Ollama Model Benchmark (Speed, Success Rate, Code Validity) & E2E Tests (`docs/MODEL_BENCHMARK.md`, `tests/`) — **Owner: Berat İnan** [5 SP]
