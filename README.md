# 🚀 Distributed AI Software Development Platform

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/)
[![Python Version](https://img.shields.io/badge/python-3.13-blue.svg)](https://python.org)
[![Node Version](https://img.shields.io/badge/node-v24.18.0-green.svg)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **CM6453 Software Engineering Process and DevOps - Term Project**  
> A web-based software development platform powered by a distributed multi-agent architecture and capability-based task allocation algorithms.

---

## 📌 Features

- 🧠 **Dynamic Requirements Decomposition:** Automatically converts high-level requirement documents into structured Task DAGs.
- 🎯 **Capability-Based Task Assignment:** Evaluates LLMs across **Coding Capability**, **Reasoning Capability**, and **Context Capacity** to assign tasks to the best-suited agent.
- 🤖 **Specialized Worker Agents:** Includes pre-built agents for Frontend, Backend, Database, Automated Testing, and Code Integration.
- ⚡ **Distributed Execution Pipeline:** Manages dependency execution order and collects generated code artifacts.
- 📊 **Scrum & DevOps Integration:** Designed for 5-sprint agile delivery with Trello and GitHub version control.

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

## 🛠️ Quick Start & Installation

### Prerequisites
- Python 3.10+
- Node.js v18+

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform.git
   cd Distributed-AI-Software-Development-Platform
   ```

2. **Run Automated Tests:**
   ```bash
   python -m unittest discover -s tests
   ```

---

## 🤝 Team & Scrum Management

- **Scrum Framework:** 5 Iterations (2 weeks per Sprint, 10 weeks total).
- **Task Management:** Trello Board
- **Version Control:** GitHub Repository

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
