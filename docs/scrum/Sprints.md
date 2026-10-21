# 5-Sprint Project Execution Roadmap

## Overview
This document outlines the 5-sprint agile execution roadmap for the **CM6453 Software Processes** term project: **Distributed AI Software Development Platform**. Each sprint lasts 2 weeks (10 weeks total) and delivers a functional, verifiable product increment.

---

## 🏃 Sprint 1 — Foundation & Requirements (Weeks 1–2: Oct 01 – Oct 15, 2026)
**Sprint Goal:** Establish repository governance, define testable system requirements, document multi-agent architecture and SQLite data model, verify local Ollama models across team hardware, and deliver working prototypes for the Streamlit web UI and Master Agent task decomposition engine.

### Deliverables & Trello Mapping:
- [x] **S1-01:** GitHub Repository Setup, Branch Protection & Team Workflow (`README.md`, `.gitignore`)
- [x] **S1-02:** Initial Streamlit Web Interface Prototype (`master_agent_projesi/app.py`, `start.bat`)
- [x] **S1-03:** System Architecture & Component Boundaries Specification (`docs/ARCHITECTURE.md`)
- [x] **S1-04:** Initial Data Model & SQLite Persistent Storage Design (`docs/DATA_MODEL.md`, `src/master/db_manager.py`)
- [x] **S1-05:** System Requirements Inventory & Testable Acceptance Criteria (`docs/SRS.md`, `docs/scrum/product_backlog.md`)
- [x] **S1-06:** Local Ollama Model Research & Hardware Capability Matrix (`docs/MODEL_RESEARCH.md`, `config/agents_config.json`)
- [x] **S1-07:** Master-Agent Orchestrator & Basic Task Decomposition Prototype (`src/master/orchestrator.py`, `src/master/analyzer.py`, `src/master/capability_eval.py`, `src/master/scheduler.py`, `tests/test_master_engine.py`)

---

## 🏃 Sprint 2 — Agent Management & Task Assignment (Weeks 3–4: Oct 08 – Oct 21, 2026)
**Sprint Goal:** Standardize runtime API/fallback configuration, unify the Streamlit UI and core engine under a single canonical agent registry, enforce weighted capability selection with availability filtering, validate task decomposition JSON schemas, and isolate per-run scheduler and SQLite states (`run_id`).

### Deliverables & Trello Mapping:
- [ ] **S2-01:** Fix API Key Configuration, Remove Duplicate Loaders & Enforce Safe Demo/Fallback Mode (`master_agent_projesi/app.py`, `.env.example`)
- [ ] **S2-02:** Unify Streamlit UI and Core Engine Under a Single Canonical Agent Registry (`config/agents_config.json`, `src/agents/base_agent.py`, `app.py`)
- [ ] **S2-03:** Implement Weighted Task-Fitness Scoring & Filter Unavailable (`BUSY`/`OFFLINE`/`ERROR`) Agents (`src/master/capability_eval.py`)
- [ ] **S2-04:** Validate Task Decomposition JSON Output Against Schema & Label Fallback Data (`src/master/analyzer.py`, `app.py`)
- [ ] **S2-05:** Isolate Per-Run Scheduler Lifecycle (`run_id`) & Accurately Report `FAILED`/`BLOCKED`/`UNASSIGNED` Tasks (`src/master/scheduler.py`, `src/master/orchestrator.py`)
- [ ] **S2-06:** Bind UI Task Assignments, Progress & Status Monitoring to Real Core Engine Results (`master_agent_projesi/app.py`)
- [ ] **S2-07:** Align SQLite Persistence Layer (`src/master/db_manager.py`) with Unified Agent Registry & Run Lifecycle (`docs/DATA_MODEL.md`)

---

## 🏃 Sprint 3 — Distributed Development (Weeks 5–6: Oct 22 – Nov 04, 2026)
**Sprint Goal:** Define versioned Master–Worker communication contracts, implement authenticated HTTP/JSON worker endpoints, execute real local Ollama model inference to generate code artifacts in isolated workspaces, and enforce DAG dependency scheduling.

### Deliverables & Trello Mapping:
- [ ] **S3-01:** Define Versioned Master–Worker Task, Result, and Error JSON Contracts (`docs/ARCHITECTURE.md`, `docs/contracts/v1/*.json`)
- [ ] **S3-02:** Implement Authenticated Worker Agent HTTP/JSON Endpoint & Client Adapter with Health Checks and Timeouts (`src/api/`)
- [ ] **S3-03:** Execute Real Worker Agent Tasks via Local Ollama Models & Safely Collect Workspace Artifact Files (`src/agents/*_agent.py`)
- [ ] **S3-04:** Validate Task Dependency Graph (DAG Cycles/Missing Refs) & Schedule Only Ready Tasks (`src/master/scheduler.py`)

---

## 🏃 Sprint 4 — Integration & Quality Assurance (Weeks 7–8: Nov 05 – Nov 18, 2026)
**Sprint Goal:** Implement bounded retry and alternative agent reassignment for failed tasks, build evidence-based syntax and conflict inspection in the Integration Agent, establish a repeatable CI quality gate, and harden input/output security and privacy compliance.

### Deliverables & Trello Mapping:
- [ ] **S4-01:** Implement Bounded Task Retry & Eligible Alternative Agent Reassignment State Machine (`src/master/orchestrator.py`)
- [ ] **S4-02:** Enable Evidence-Based Integration Agent Inspection (Artifact Verification, Syntax Check, Path Conflict Detection) (`src/agents/integration_agent.py`)
- [ ] **S4-03:** Expand Deterministic Unit/Integration Test Suite & Add GitHub Actions CI Quality Gate (`tests/`, `.github/workflows/ci.yml`)
- [ ] **S4-04:** Harden Requirement Input, Untrusted Model Output & External Provider Privacy Policy Compliance (`docs/scrum/definition_of_done.md`, `app.py`)

---

## 🏃 Sprint 5 — Complete System & Evaluation (Weeks 9–10: Nov 19 – Dec 02, 2026)
**Sprint Goal:** Display real execution telemetry on the dashboard, empirically benchmark local Ollama models across standardized tasks, verify the end-to-end distributed workflow (including failure handling), and align all release documentation with verified system behavior.

### Deliverables & Trello Mapping:
- [ ] **S5-01:** Display Real Execution Run (`run_id`) and Agent Telemetry in the Streamlit Dashboard (`master_agent_projesi/app.py`)
- [ ] **S5-02:** Measure Execution Time, Success Rate & Empirical Agent/Model Comparison (`docs/MODEL_BENCHMARK.md`)
- [ ] **S5-03:** Verify End-to-End Distributed Development Scenario & Negative Failure Path Demo (`tests/`, Live Demo)
- [ ] **S5-04:** Synchronize `README.md`, `ARCHITECTURE.md`, `Definition of Done` & Run Instructions with Verified System Behavior