# 🚀 Distributed AI Software Development Platform

[![Python Version](https://img.shields.io/badge/python-3.13-blue.svg)](https://python.org)
[![Node Version](https://img.shields.io/badge/node-v24.18.0-green.svg)](https://nodejs.org)
[![Course](https://img.shields.io/badge/CM6453-SW%20Processes%20%26%20DevOps-orange.svg)](https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **CM6453 Software Engineering Process and DevOps**  
> **Product Owner & Instructor:** Prof. Dr. Ensar Gül  
> **Scrum Master:** İrem Yılmaz  
> A web-based software development platform powered by a distributed multi-agent architecture, versioned HTTP/JSON contracts, and capability-based task allocation algorithms.

---

## 📋 Executive Summary

A web-based platform where a **Master Agent** receives software requirements documents, decomposes them into a structured dependency-aware Directed Acyclic Graph (DAG) with a shared domain contract, and dynamically distributes tasks to specialized LLM-based worker agents running locally or across distributed nodes (Tailscale / HTTP REST) based on their measured model capabilities (*Coding*, *Reasoning*, *Context Capacity*). The generated artifacts undergo automated AST/SQL syntax inspection, conflict resolution, and packaging into an isolated run workspace (`workspaces/{run_id}/`). The project follows the **Scrum methodology** across 5 two-week iterations using **Trello** and **GitHub**.

---

## 🎯 Key Principles

- 🧠 **Capability-Based Allocation:** Master agent evaluates agents by *Coding capability*, *Reasoning capability*, and *Context capacity* (`FitScore`) to optimize task distribution (`src/master/capability_eval.py`).
- 🔗 **Distributed Multi-Agent Architecture:** Worker agents run independently across local or remote machines (`RemoteAgentProxy` + FastAPI `worker_server.py`) and communicate with the Master Agent via versioned JSON envelopes (`TaskPayloadContract_v1`) with Bearer Token authentication.
- ⚡ **LLM Task Decomposition & Parallel DAG Execution:** Decomposes complex requirements via local Ollama (`qwen2.5:7b`) into a validated DAG (`src/master/analyzer.py`, `src/master/scheduler.py`) and dispatches independent ready tasks concurrently (`ThreadPoolExecutor`).
- 🛡️ **Fault Recovery, AST Review & Safe Sandboxing:** Enforces bounded retries and automatic failover (`src/master/retry_policy.py`), transient/permanent error classification (`src/security/`), path/schema conflict resolution (`src/master/conflicts.py`), and automated Python AST / SQLite DDL syntax review (`src/agents/integration_agent.py`).
- 🔄 **Agile & Scrum Governance:** 5 Sprints × 2 Weeks = 10-week Scrum project lifecycle, managed transparently with Trello and GitHub Pull Request / CI quality gate workflows adhering to the 2020 Scrum Guide.

---

## 👥 Team & Roles

| Student No. | Member Name | Scrum Role | Agent & Ollama Model | Primary Focus Area |
| :--- | :--- | :--- | :--- | :--- |
| **2204012296** | **Eren Görkem Çolak** | Developer · Technical Lead | Master Agent · `qwen2.5:7b` | Orchestrator Engine, LLM Decomposition, Retry/Failover & Parallel Dispatch |
| **2204012297** | **Elif Yılmaz** | Developer | Integration Agent · `phi4-mini:3.8b` | Inter-Agent Contracts, Artifact Manifest, AST/SQL Code Review & Packaging |
| **2204012300** | **Mahmut Karaalioğlu** | Developer | Database Agent · `llama3.2:3b` | SQLite Persistence (`state.db`), Workspace Isolation, Conflict Resolution & Export |
| **2204012301** | **İrem Yılmaz** | Scrum Master · Developer | Backend Agent · `qwen2.5-coder:7b` | Worker HTTP API, Backend Code Gen, Error Classification, Security & Scrum Governance |
| **2204012302** | **Kübra Hepcan** | Developer | Frontend Agent · `qwen2.5-coder:3b` | Frontend Code Gen, Live Worker Monitor, Code Review UI & Telemetry Dashboard |
| **2204012303** | **Berat İnan** | Developer | Testing Agent · `deepseek-coder:6.7b` | Pytest Test Gen, Automated Unit/E2E Test Suite, Model Benchmarking & CI Quality Gate |

---

## 📊 Project Status — Sprint 5 Active (Nov 26 – Dec 10, 2026)

Sprints 1 through 4 are **completed** (99 Story Points delivered across 26 cards). Sprint 5 (End-to-End Integration, Telemetry Dashboard, Empirical Benchmarking & Final Release) is currently in progress. Full tracking: [`docs/scrum/product_backlog.md`](docs/scrum/product_backlog.md) and [`docs/scrum/scrum_calendar.md`](docs/scrum/scrum_calendar.md).

### ✅ Verified System Capabilities
- 🖥️ **Streamlit Web Interface (`master_agent_projesi/app.py`, `review_panel.py`, `run_export.py`):** Reads agent profiles from `config/agents_config.json`, runs `MasterOrchestrator`, displays live worker status, shared domain contracts, reassignment history, file conflict alerts, AST review verdicts, and run export reports.
- ⚙️ **Master Agent Engine (`src/master/orchestrator.py`, `analyzer.py`, `capability_eval.py`):** LLM-powered requirement decomposition (`qwen2.5:7b`) with shared contract injection, weighted `FitScore` selection, `BUSY`/`OFFLINE`/`ERROR` filtering, bounded retry/failover (`retry_policy.py`), and `ThreadPoolExecutor` parallel dispatch.
- 📐 **DAG Scheduling & Sandbox (`src/master/scheduler.py`, `workspace.py`, `conflicts.py`):** Topological DAG execution with cycle detection, cascading `BLOCKED` status on upstream failure, strict `workspaces/{run_id}/` path traversal protection, and automatic path/schema conflict resolution.
- 🌐 **Distributed Worker HTTP API & A2A Protocol (`src/api/worker_server.py`, `src/agents/remote_agent.py`, `src/a2a_protocol.py`):** Bearer-token authenticated FastAPI worker server (`/health`, `/task`) supporting remote deployment across Tailscale/HTTP nodes with duplicate task tracking and versioned Pydantic `v1.0` contracts (`src/contracts.py`).
- 🤖 **Specialized Local Ollama Agents (`src/agents/`):** All 5 worker agents (`FrontendAgent`, `BackendAgent`, `DatabaseAgent`, `TestingAgent`, `IntegrationAgent`) connect to local Ollama models with automatic labeled fallback mode when Ollama is offline.
- 🛡️ **Security & Error Classification (`src/security/`):** Input length/character validation (`input_validation.py`), transient vs. permanent error classification (`error_classification.py`), and output sanitization / credential masking (`output_sanitizer.py`).
- 🗄️ **SQLite Persistence (`src/master/db_manager.py`):** Schema v5 WAL-mode database (`state.db`) tracking `runs`, `agents`, `tasks`, `attempts`, `output_files`, and `file_conflicts`, with stale `RUNNING` recovery and database-level guards preventing failed tasks from being recorded as `COMPLETED`.
- ✅ **CI Quality Gate (`.github/workflows/tests.yml`):** Automated deterministic `unittest` suite across 30 test modules runs on every Pull Request and blocks merges on any failure.

---

## 🏗️ Repository Architecture

```text
├── .github/workflows/
│   └── tests.yml                # GitHub Actions CI quality gate
├── config/
│   └── agents_config.json       # Canonical agent profiles, Ollama tags & weights
├── docs/
│   ├── ARCHITECTURE.md          # Multi-Agent System Architecture Specification
│   ├── CI_QUALITY_GATE.md       # CI pipeline & merge protection rules
│   ├── DATA_MODEL.md            # SQLite v5 schema, ERD & integrity guards
│   ├── INTER_AGENT_CONTRACTS.md # Versioned JSON contract specification (v1.0)
│   ├── MODEL_RESEARCH.md        # Local Ollama hardware & model research
│   ├── SRS.md                   # Software Requirements Specification
│   ├── WORKER_HTTP_API_DRAFT.md # FastAPI worker endpoint specification
│   ├── model_tests/             # Empirical model benchmark JSON/MD reports
│   └── scrum/                   # Scrum governance, DoD, backlog & sprint records
│       ├── definition_of_done.md
│       ├── product_backlog.md
│       ├── scrum_calendar.md
│       ├── sprint_backlog_template.md
│       ├── sprint_review_retro_template.md
│       └── sprints/             # Sprint 1–5 backlogs & review/retro reports
├── master_agent_projesi/        # Streamlit Web UI & Run Export Modules
│   ├── app.py                   # Main interactive dashboard
│   ├── review_panel.py          # Code review, conflicts & reassignment UI panel
│   ├── run_export.py            # Run summary & artifact export helpers
│   └── test_api.py              # API configuration diagnostic helper
├── scripts/
│   ├── master_model_benchmark.py # Standardized multi-model benchmark runner
│   └── model_smoke_test.py      # Local Ollama smoke test script
├── src/
│   ├── a2a_protocol.py          # Agent-to-Agent message framing & helpers
│   ├── contracts.py             # Pydantic v2 versioned task/result/error schemas
│   ├── agents/                  # BaseAgent, RemoteAgentProxy & 5 Worker Agents
│   │   ├── base_agent.py
│   │   ├── remote_agent.py
│   │   ├── frontend_agent.py
│   │   ├── backend_agent.py
│   │   ├── database_agent.py
│   │   ├── testing_agent.py
│   │   └── integration_agent.py
│   ├── api/                     # FastAPI Worker HTTP Server
│   │   └── worker_server.py
│   ├── master/                  # Master Orchestration & Persistence Engine
│   │   ├── analyzer.py          # LLM & template requirement decomposition
│   │   ├── capability_eval.py   # Weighted FitScore candidate evaluator
│   │   ├── conflicts.py         # Workspace file path & SQL schema conflict resolver
│   │   ├── db_manager.py        # SQLite WAL persistence & stale-run recovery
│   │   ├── generated_tests.py   # Generated test execution & verification runner
│   │   ├── orchestrator.py      # End-to-end execution & failover pipeline
│   │   ├── retry_policy.py      # Bounded retry & backoff decision policy
│   │   ├── scheduler.py         # Topological DAG scheduler & cycle detector
│   │   ├── smoke_test.py        # Orchestrator pipeline smoke test utility
│   │   └── workspace.py         # Sandboxed workspaces/{run_id}/ file writer
│   └── security/                # Input/Output Security & Error Classification
│       ├── error_classification.py
│       ├── input_validation.py
│       └── output_sanitizer.py
├── tests/                       # Deterministic Mock-Based Test Suite (30 modules)
├── .env.example                 # Environment variables template
├── requirements.txt             # Python dependencies
└── start.bat                    # Windows quick-start launcher
```

---

## 🛠️ Quick Start & Local Ollama Setup

### Prerequisites
- **Python 3.10+** (verified on Python 3.13)
- **Ollama** ([ollama.com](https://ollama.com)) for local LLM inference *(optional — system runs in labeled fallback mode if Ollama is offline)*

### 1. Installation & Environment Configuration
```bash
git clone [https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform.git](https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform.git)
cd Distributed-AI-Software-Development-Platform

# Create and activate virtual environment (recommended)
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:        source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt

# Copy environment template and configure tokens/hosts
# Windows PowerShell: Copy-Item .env.example .env
cp .env.example .env
```

### 2. Pull Local Ollama Models
Pull the canonical models mapped in [`config/agents_config.json`](config/agents_config.json) (or only the model for your assigned worker role):
```bash
ollama pull qwen2.5:7b            # Master Agent (Eren Görkem Çolak)
ollama pull qwen2.5-coder:7b      # Backend Agent (İrem Yılmaz)
ollama pull qwen2.5-coder:3b      # Frontend Agent (Kübra Hepcan)
ollama pull llama3.2:3b           # Database Agent (Mahmut Karaalioğlu)
ollama pull deepseek-coder:6.7b   # Testing Agent (Berat İnan)
ollama pull phi4-mini:3.8b        # Integration Agent (Elif Yılmaz)
```
Verify that Ollama is serving on `http://localhost:11434`:
```bash
ollama list
```

### 3. Launch Web Interface (Single-Node or Master Node)
```bash
streamlit run master_agent_projesi/app.py
# Or on Windows:
.\start.bat
```
Open the browser interface, enter a software requirement (or load `docs/model_tests/sample_requirement.md`), and click **"🚀 Analiz et ve ajanlara dağıt"**. Generated project files are written under `workspaces/{run_id}/`.

### 4. Run Distributed Worker HTTP Nodes (Multi-Machine / Tailscale)
Each team member can start their specialized worker node on a dedicated port with Bearer Token protection:

```bash
# Set shared authentication token in .env or shell:
# Windows PowerShell: $env:BACKEND_AUTH_TOKEN="your-secure-token"
export BACKEND_AUTH_TOKEN=your-secure-token

# Start role-specific worker servers on separate machines or terminals:
python -m src.api.worker_server --agent backend --port 8001
python -m src.api.worker_server --agent database --port 8002
python -m src.api.worker_server --agent frontend --port 8003
python -m src.api.worker_server --agent testing --port 8004
python -m src.api.worker_server --agent integration --port 8005
```

On the Master node, configure the worker URLs (e.g., Tailscale `100.x.y.z` IPs) in `.env`:
```env
BACKEND_AGENT_URL=[http://100.](http://100.)x.y.1:8001
DATABASE_AGENT_URL=[http://100.](http://100.)x.y.2:8002
FRONTEND_AGENT_URL=[http://100.](http://100.)x.y.3:8003
TESTING_AGENT_URL=[http://100.](http://100.)x.y.4:8004
INTEGRATION_AGENT_URL=[http://100.](http://100.)x.y.5:8005
```
Any worker URL left blank runs locally in-process automatically. `GET /health` is public; `POST /task` requires `Authorization: Bearer <token>`.

### 5. Run Automated Unit Tests & Model Benchmarks
```bash
# Execute full deterministic offline unit test suite
python -m unittest discover -s tests

# Run local Ollama smoke test
python scripts/model_smoke_test.py
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).