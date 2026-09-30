# 🚀 Distributed AI Software Development Platform

[![Python Version](https://img.shields.io/badge/python-3.13-blue.svg)](https://python.org)
[![Node Version](https://img.shields.io/badge/node-v24.18.0-green.svg)](https://nodejs.org)
[![Course](https://img.shields.io/badge/CM6453-SW%20Processes%20%26%20DevOps-orange.svg)](https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **CM6453 Software Engineering Process and DevOps**  
> **Instructor:** Prof. Dr. Ensar Gül  
> A web-based software development platform powered by a distributed multi-agent architecture and capability-based task allocation algorithms.

---

## 📋 Executive Summary

A web-based platform where a **Master Agent** receives long software requirements documents, decomposes them into structured dependency-aware subtasks, and dynamically distributes those tasks to specialized LLM-based worker agents running across team members' environments based on their measured model capabilities (Coding, Reasoning, Context Capacity). The generated artifacts are integrated, tested, and reviewed into a complete web application increment. The project follows the **Scrum methodology** across 5 two-week iterations using **Trello** and **GitHub**.

---

## 🎯 Key Principles

- 🧠 **Capability-Based Allocation:** Master agent evaluates agents by *Coding capability*, *Reasoning capability*, and *Context capacity* to optimize task distribution.
- 🔗 **Distributed Multi-Agent Architecture:** Ajanlar yerel veya uzak sunucularda (Ollama / LLM API) bağımsız çalışır ve Master Agent ile REST API / Bearer Token üzerinden haberleşir.
- ⚡ **Automated Task Decomposition (DAG):** Gelen karmaşık gereksinimleri Veritabanı, Backend, Frontend, Test ve Entegrasyon aşamalarına böler.
- 🔄 **Agile & Scrum Governance:** 5 Sprint × 2 Hafta = 10 Haftalık Scrum yönetimi, Trello panosu ve GitHub Pull Request / Code Review iş akışı.

---

## 👥 Team & Roles

| Student No. | Member Name | Scrum Role | Agent & Model | Primary Focus Area |
| :--- | :--- | :--- | :--- | :--- |
| **2204012296** | **Eren Görkem Çolak** | Developer · Technical Lead | Master Agent · Qwen3.5 4B | Architecture & Engine Setup |
| **2204012297** | **Elif Yılmaz** | Product Owner · Developer | Agent 2 · Phi-4 3.8B | Requirements & Product Backlog |
| **2204012300** | **Mahmut Karaalioğlu** | Developer | Agent 3 · Llama 3.2 3B | Database & Schema Design |
| **2204012301** | **İrem Yılmaz** | Scrum Master · Developer | Agent 4 · Qwen2.5-Coder 7B | Process Facilitation & Review |
| **2204012302** | **Kübra Hepcan** | Developer | Agent 5 · Gemma 2 9B | Frontend UI / UX Components |
| **2204012303** | **Berat İnan** | Developer | Agent 6 · DeepSeek-Coder 6.7B | Automated Testing & QA |

---

## 📊 Status — Sprint 1 (24 Sep – 7 Oct 2026)

### ✅ Working Now (Sprint 1 Completed Baseline)
- 🖥️ **Web Interface Baseline:** Arayüz bileşenleri ve yönetim paneli tasarımı.
- ⚙️ **Master Agent Engine:** REST API Gateway, gereksinim analizi ve Ajan Kayıt Sistemi (`src/master/analyzer.py`).
- 🤖 **Agent Capability Matrix:** Model puanlama sistemi ve yapılandırması (`config/agents_config.json`).
- 📐 **DAG Task Decomposition:** Gereksinimleri *Requirement Analysis → DB / Backend / Frontend → QA → Integration* bağımlılık grafiğine bölen mekanizma.
- 📜 **System Architecture & Sprint Docs:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ve [`docs/SPRINTS.md`](docs/SPRINTS.md) kılavuzları.

### 🔮 Planned for Sprints 2–5
- **Sprint 2:** Capability evaluation algorithms, dynamic agent selection UI, and status monitoring.
- **Sprint 3:** Distributed task execution, shared repository synchronization, and result collection.
- **Sprint 4:** Automated test generation, Code Review agent, error recovery & reassignment.
- **Sprint 5:** End-to-end integration, performance benchmarking dashboard, final demonstration.

---

## 🏗️ Repository Architecture

```text
├── config/                  # Agent capability profiles & configuration
│   └── agents_config.json
├── docs/                    # Architectural & Sprint documentation
│   ├── ARCHITECTURE.md      # Multi-Agent Architecture Specification
│   └── SPRINTS.md           # 5-Sprint Agile Roadmap
├── src/                     # Core Python Engine
│   ├── agents/              # BaseAgent & Specialized Worker Agents
│   │   ├── base_agent.py
│   │   ├── frontend_agent.py
│   │   ├── backend_agent.py
│   │   ├── database_agent.py
│   │   ├── testing_agent.py
│   │   └── integration_agent.py
│   ├── master/              # Master Agent Logic
│   │   ├── analyzer.py      # Requirements Decomposition Engine
│   │   ├── capability_eval.py # Model Evaluation & Selection Algorithm
│   │   ├── scheduler.py     # Task Dependency Scheduler
│   │   └── orchestrator.py  # Execution Pipeline Orchestrator
│   └── api/                 # API Gateway Service
└── tests/                   # Automated Unit Tests
    └── test_master_engine.py
```

---

## 🛠️ Quick Start & Development

### Prerequisites
- Python 3.10+
- Node.js v18+

### 1. Installation
```bash
git clone https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform.git
cd Distributed-AI-Software-Development-Platform
```

### 2. Run Automated Unit Tests
```bash
python -m unittest discover -s tests
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
