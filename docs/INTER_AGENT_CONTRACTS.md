# Ajanlar Arası Entegrasyon ve İletişim Sözleşmesi (v1.0)

Bu doküman; Master Agent (`Orchestrator`), İşçi Ajanlar (`BaseAgent`) ve Integration Agent arasındaki veri alışverişi kurallarını, durum ayrımlarını ve sürümlü sözleşmeleri (`v1.0`) tanımlar.

---

## 1. Master Agent Görev Sınıflandırma Doğrulama Kuralı
Master motorunun ürettiği alt görevler `src/contracts.py` içerisindeki `validate_master_tasks()` fonksiyonu ve `MasterSubTaskSchema` modeli ile doğrulanır.

* **Zorunlu Alanlar ve Türleri:**
  * `task_id` (`str`): Alt görevin tekil kimliği.
  * `title` (`str`): Görev başlığı.
  * `category` (`str`): Görev kategorisi (`backend`, `frontend`, `database`, `testing`, `integration`).
  * `description` (`str`): Yapılacak işin detaylı açıklaması.
  * `dependencies` (`List[str]`): Bağımlı olunan `task_id` listesi.
  * `required_specialty` (`str`): Görev için gereken uzmanlık alanı.

---

## 2. Ana Ajan -> İşçi Ajan Görev Sözleşmesi (`TaskPayloadContract_v1`)
Master Agent bir işçi ajana görev atarken aşağıdaki şemayı iletir:

```json
{
  "contract_version": "1.0",
  "run_id": "run_20261021_001",
  "task_id": "task_backend_01",
  "title": "Kullanıcı Kayıt API Geliştirmesi",
  "category": "backend",
  "description": "FastAPI ile /register uç noktasını geliştir.",
  "dependencies": ["task_db_01"],
  "required_specialty": "backend",
  "context_artifacts": {
    "schema.sql": "CREATE TABLE users (id INT PRIMARY KEY, email TEXT);"
  }
}
```

---

## 3. İşçi Ajan -> Ana Ajan Sonuç Sözleşmesi (`WorkerTaskResultContract_v1`)
İşçi ajanlar (`src/agents/base_agent.py` içindeki `TaskResult` yapısıyla birebir uyumlu olarak) görev sonunda aşağıdaki şemayı döner:

```json
{
  "contract_version": "1.0",
  "task_id": "task_backend_01",
  "agent_id": "backend_agent_1",
  "status": "COMPLETED",
  "output_artifacts": {
    "main.py": "from fastapi import FastAPI\napp = FastAPI()\n"
  },
  "logs": [
    "FastAPI modülü oluşturuldu.",
    "Endpoint doğrulaması tamamlandı."
  ],
  "error_message": null,
  "execution_time_seconds": 1.42
}
```
* **İşçi Ajan Durumları (`WorkerTaskStatus`):** İşçi ajan yalnızca `PENDING`, `IN_PROGRESS`, `COMPLETED` veya `FAILED` döndürebilir.

---

## 4. Master Orchestrator Görev Kayıt ve Integration Agent Rapor Sözleşmesi

### 4.1. Orchestrator Görev Sonuç Kaydı (`OrchestratorTaskRecordContract_v1`)
`UNASSIGNED` ve `BLOCKED` durumları işçi ajanlar tarafından değil, doğrudan `MasterOrchestrator` (`src/master/orchestrator.py`) tarafından üretilir. Ayrıca failover takibi için `agent_result_status` ve `attempted_agents` alanları tutulur:

```json
{
  "contract_version": "1.0",
  "run_id": "run_20261021_001",
  "task_id": "task_backend_01",
  "status": "COMPLETED",
  "assigned_agent": "backend_agent_1",
  "agent_result_status": "COMPLETED",
  "attempted_agents": ["backend_agent_1"],
  "output_artifacts": {
    "main.py": "from fastapi import FastAPI..."
  },
  "error_message": null
}
```

### 4.2. Integration Agent Denetim Raporu (`IntegrationReportContract_v1`)
`src/agents/integration_agent.py` gerçek çıktı dosyalarını (`output_artifacts`) inceler; sözdizimi (AST), güvenli yol ve çakışma kontrollerini yaptıktan sonra kanıta dayalı rapor döner:

```json
{
  "contract_version": "1.0",
  "run_id": "run_20261021_001",
  "status": "APPROVED",
  "inspected_files": ["schema.sql", "main.py"],
  "conflicts_detected": [],
  "conflicts_resolved": 0,
  "findings": [],
  "package_path": null,
  "summary": "2 dosya incelendi, 0 bulgu saptandı. Durum: APPROVED"
}
```