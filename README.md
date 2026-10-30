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
| **2204012296** | **Eren Görkem Çolak** | Developer · Technical Lead | Master Agent · Qwen 2.5 7B | Architecture, Routing & Engine Setup |
| **2204012297** | **Elif Yılmaz** | Product Owner · Developer | Integration Agent · Phi-4 Mini 3.8B | Code Review, Integration & Product Backlog |
| **2204012300** | **Mahmut Karaalioğlu** | Developer | Database Agent · Llama 3.2 3B | Database, Schema & Migration Design |
| **2204012301** | **İrem Yılmaz** | Scrum Master · Developer | Backend Agent · Qwen2.5-Coder 7B | Backend APIs, Business Logic & Scrum Facilitation |
| **2204012302** | **Kübra Hepcan** | Developer | Frontend Agent · Qwen2.5-Coder 3B | Frontend UI / UX Components & State |
| **2204012303** | **Berat İnan** | Developer | Testing Agent · DeepSeek-Coder 6.7B | Automated Testing, Assertion Checks & QA |

---

## 📊 Status — Sprint 3 (29 Oct – 12 Nov 2026, in progress)

Sprint 1 (1–15 Oct) and Sprint 2 (15–29 Oct) are completed. Details: [`docs/scrum/Sprints.md`](docs/scrum/Sprints.md).

### ✅ Working Now
- 🖥️ **Web Interface:** Streamlit arayüzü ajanları `config/agents_config.json` dosyasından okur; "Analiz et" butonu gerçek `MasterOrchestrator`'ı çalıştırır, görev ve ajan durumları motordan gelir.
- ⚙️ **Master Agent Engine:** Ağırlıklı yetenek puanı (FitScore) ile ajan seçimi, `BUSY`/`OFFLINE`/`ERROR` filtresi, failover ve her çalıştırma için ayrı `run_id`.
- 📐 **DAG Scheduling:** Bağımlılık sırasına göre çalıştırma; döngüsel bağımlılık tespiti ve başarısız görevin sonrasındaki görevlerin `BLOCKED` işaretlenmesi.
- 🗄️ **SQLite Persistence:** Her çalıştırma `state.db`'ye (`runs`, `agents`, `tasks`, `attempts`) kaydedilir; başarısız görevler `COMPLETED` olarak yazılamaz.
- 🌐 **Worker HTTP API:** Bearer token ile korunan FastAPI worker sunucusu (`/health`, `/task`) — [`src/api/worker_server.py`](src/api/worker_server.py).
- 🤖 **Local LLM Agents:** BackendAgent (`qwen2.5-coder:7b`) ve TestingAgent (`deepseek-coder:6.7b`) yerel Ollama'ya kod/test ürettirir; Ollama kapalıysa etiketli yedek moda geçer.
- ✅ **CI:** Her pull request'te GitHub Actions ile 111 birim testi çalışır.

### 🚧 Not Yet
- Görev ayrıştırma (`src/master/analyzer.py`) henüz sabit bir şablon kullanıyor; Master modeline bağlanması planlanıyor.
- Frontend, Database ve Integration ajanları henüz örnek çıktı üretiyor (Sprint 3 kartları).
- Master, worker'lara henüz HTTP üzerinden görev göndermiyor; tüm ajanlar tek süreçte çalışıyor (S3-01).

### 🔮 Planned
- **Sprint 3:** Master–worker görev sözleşmeleri ve dağıtık gönderim, Frontend/Database ajanlarının yerel Ollama'ya bağlanması, artifact manifest.
- **Sprint 4:** Error recovery & reassignment, Code Review agent, CI quality gate.
- **Sprint 5:** End-to-end integration, telemetry & benchmarking dashboard, final demonstration.

---

## 🏗️ Repository Architecture

```text
├── config/                  # Agent capability profiles & configuration
│   └── agents_config.json
├── docs/                    # Architectural & Sprint documentation
│   ├── ARCHITECTURE.md      # Multi-Agent Architecture Specification
│   └── scrum/               # 5-Sprint Roadmap, Backlogs & Scrum Records
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
│   ├── api/                 # Worker Agent HTTP API (FastAPI)
│   │   └── worker_server.py
│   └── contracts.py         # Pydantic Inter-Agent Contracts
├── master_agent_projesi/    # Streamlit Web Interface
│   └── app.py
└── tests/                   # Automated Unit Tests (7 modules)
```

---

## 🛠️ Quick Start & Development

### Prerequisites
- Python 3.10+
- pip

### 1. Installation & Dependencies
```bash
git clone https://github.com/gorkemcolakk/Distributed-AI-Software-Development-Platform.git
cd Distributed-AI-Software-Development-Platform

# Install required dependencies
pip install -r requirements.txt
```

### 2. Launch Web Interface
```bash
streamlit run master_agent_projesi/app.py
# veya doğrudan:
.\start
```
Açılan tarayıcı ekranından gereksinim girip **"🚀 Analiz et ve ajanlara dağıt"** butonuyla Master Agent motorunu çalıştırabilirsiniz. Ollama kapalıyken de çalışır (etiketli yedek mod).

### 3. Run the Worker HTTP API (optional)
```bash
# Windows PowerShell: $env:WORKER_AUTH_TOKEN="your-token"
export WORKER_AUTH_TOKEN=your-token
python -m src.api.worker_server
```
Sunucu varsayılan olarak `8000` portunda açılır (`WORKER_PORT` ile değiştirilebilir). `GET /health` herkese açıktır; `POST /task` için `Authorization: Bearer <token>` gerekir.

### 4. Run Automated Unit Tests
```bash
python -m unittest discover -s tests
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
