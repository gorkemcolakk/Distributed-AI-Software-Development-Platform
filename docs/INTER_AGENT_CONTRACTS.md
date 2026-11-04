# Ajanlar Arası Entegrasyon ve İletişim Sözleşmesi (v1.0)

**Sorumlular:** Eren Görkem Çolak (**S3-01** — Master Agent & Dağıtık Gönderim) · Elif Yılmaz (**S2-04 / S3-05** — Integration Agent) · İrem Yılmaz (**S3-02** — Worker HTTP API)

Bu doküman; Master Agent (`MasterOrchestrator`), İşçi Ajanlar (`BaseAgent` / `RemoteAgentProxy` / `worker_server.py`) ve `IntegrationAgent` arasındaki veri alışverişi kurallarını, durum ayrımlarını, zaman aşımı (timeout) / mükerrer mesaj (idempotency) davranışlarını ve sürümlü sözleşmeleri (`v1.0`) tanımlar.

---

## 1. Master Agent Görev Sınıflandırma Doğrulama Kuralı
Master motorunun ürettiği alt görevler [`src/contracts.py`](../src/contracts.py) içerisindeki `validate_master_tasks()` fonksiyonu ve `MasterSubTaskSchema` modeli ile doğrulanır.

* **Zorunlu Alanlar ve Türleri:**
  * `task_id` (`str`): Alt görevin tekil kimliği.
  * `title` (`str`): Görev başlığı.
  * `category` (`str`): Görev kategorisi (`REQUIREMENTS`, `BACKEND`, `FRONTEND`, `DATABASE`, `TESTING`, `INTEGRATION`).
  * `description` (`str`): Yapılacak işin detaylı açıklaması.
  * `dependencies` (`List[str]`): Bağımlı olunan `task_id` listesi.
  * `required_specialty` (`str`): Görev için gereken uzmanlık alanı.

---

## 2. Ana Ajan -> İşçi Ajan Görev Zarfı Sözleşmesi (`TaskPayloadContract_v1`)
Master Agent (`MasterOrchestrator`) bir işçi ajana (yerel veya Tailscale/HTTP üzerinden `RemoteAgentProxy`) görev atarken `build_task_envelope()` ile aşağıdaki sürümlü zarfı oluşturur:

```json
{
  "contract_version": "1.0",
  "envelope_id": "env-8f3c91a04b12",
  "run_id": "run-a89c2f10",
  "task_id": "task-be-1",
  "title": "Core Backend API Implementation",
  "category": "BACKEND",
  "description": "Implement RESTful API endpoints, business logic, authentication, and database ORM layer.",
  "dependencies": ["task-db-1"],
  "required_specialty": "backend",
  "timeout_seconds": 180.0,
  "context_artifacts": {
    "project_title": "Library System",
    "requirement": "Develop an online library management system...",
    "upstream_artifacts": {
      "task-db-1": {
        "tables_designed": ["users", "projects", "audit_log"]
      }
    },
    "generated_files": {
      "database/schema_task_db_1.sql": "CREATE TABLE IF NOT EXISTS users (...);"
    }
  }
}
```

---

## 3. İşçi Ajan -> Ana Ajan Sonuç Sözleşmesi (`WorkerTaskResultContract_v1`)
İşçi ajanlar (`src/agents/base_agent.py` içindeki `TaskResult` yapısıyla birebir uyumlu olarak) görev sonunda aşağıdaki şemayı döner:

```json
{
  "contract_version": "1.0",
  "run_id": "run-a89c2f10",
  "task_id": "task-be-1",
  "agent_id": "agent-backend",
  "status": "SUCCESS",
  "output_artifacts": {
    "files": [
      {
        "filename": "backend_task_be_1.py",
        "content": "from fastapi import FastAPI\napp = FastAPI()\n",
        "language": "python"
      }
    ]
  },
  "logs": [
    "[Backend Architecture Agent] Starting execution for task 'task-be-1'...",
    "[Backend Architecture Agent] Successfully generated backend Python code."
  ],
  "error_message": null,
  "execution_time_seconds": 1.42
}
```
* **İşçi Ajan Durumları (`WorkerTaskStatus`) ve Normalizasyon:**
  * İşçi ajan `PENDING`, `IN_PROGRESS`, `SUCCESS`, `COMPLETED` veya `FAILED` döndürebilir.
  * `normalize_worker_status()` fonksiyonu hem `SUCCESS` hem `COMPLETED` değerlerini çekirdek motor ve SQLite `tasks` tablosu kısıtlarıyla (`agent_result_status IN ('SUCCESS', 'FAILED')`) uyumlu olacak şekilde `'SUCCESS'` olarak normalize eder.

---

## 4. Standart Hata Zarfı Sözleşmesi (`WorkerErrorContract_v1`)
Dağıtık HTTP çağrılarında veya şema doğrulamalarında oluşan hatalar `WorkerErrorContract_v1` şemasıyla standartlaştırılmıştır:

```json
{
  "contract_version": "1.0",
  "run_id": "run-a89c2f10",
  "task_id": "task-be-1",
  "agent_id": "agent-backend",
  "error_code": "TIMEOUT",
  "message": "Worker HTTP zaman aşımı (45.0s)",
  "retryable": true,
  "timestamp": 1793815200.0
}
```
* **Standart Hata Kodları (`WorkerErrorCode`):**
  * `UNAUTHORIZED` (HTTP 401 — Geçersiz veya eksik Bearer Token)
  * `INVALID_PAYLOAD` (HTTP 400 / 422 — Şema veya JSON doğrulama hatası)
  * `TIMEOUT` (HTTP 408 / 504 veya soket zaman aşımı)
  * `DUPLICATE_TASK` (HTTP 409 — Aynı `(run_id, task_id)` şu an işleniyor)
  * `UNREACHABLE` (Bağlantı reddedildi / Tailscale düğümü çevrimdışı)
  * `UNSAFE_PATH` (Çalışma alanı dışına yazma girişimi)
  * `CONTRACT_VIOLATION` (Sözleşme şemasına uymayan yanıt)
  * `EXECUTION_ERROR` (Ajan içi çalışma hatası)

---

## 5. Zaman Aşımı (Timeout) ve Mükerrer Mesaj (Duplicate / Idempotency) Davranışı (S3-01)

### 5.1. Zaman Aşımı Yönetimi
1. Her görev zarfı `timeout_seconds` (varsayılan `180.0` sn) alanı taşır.
2. `RemoteAgentProxy`, HTTP `POST /task` isteğinde `effective_timeout = min(envelope.timeout_seconds, self.timeout)` süresini zorunlu kılar.
3. Süre aşılırsa istek derhal kesilir, hata `WorkerErrorCode.TIMEOUT` olarak sınıflandırılır, ajan durumu `ERROR` işaretlenir ve `MasterOrchestrator` sıradaki uygun yedek ajana (**failover**) geçer.

### 5.2. Mükerrer Görev Koruması (`DuplicateTaskTracker`)
Ağ gecikmeleri veya istemci tekrarları nedeniyle aynı `(run_id, task_id)` (veya `envelope_id`) ikinci kez gönderildiğinde `DuplicateTaskTracker` şu kuralları uygular:
1. **Görev Halen Çalışıyorsa (`IN_PROGRESS`):** Worker HTTP sunucusu ikinci isteği modeli tekrar çalıştırmadan **HTTP 409 Conflict** (`error_code: "DUPLICATE_TASK"`) ile reddeder.
2. **Görev Aynı Çalıştırmada Başarıyla Tamamlandıysa (`COMPLETED`):** Worker HTTP sunucusu LLM'i tekrar çağırmaz; önbellekteki (`_completed_cache`) doğrulanmış sonucu `duplicate_cached: true` işaretiyle idempotent olarak döner.
3. **Görev Başarısız Olduysa (`FAILED`):** Kilit (`release()`) serbest bırakılır; böylece failover veya yeniden deneme (retry) mekanizmasının görevi tekrar çalıştırmasına izin verilir.

---

## 6. Tailscale / Dağıtık Görev Gönderimi (`RemoteAgentProxy`)
1. Her ekip üyesi kendi bilgisayarında uzman ajanını HTTP sunucusu olarak başlatabilir:
   ```bash
   WORKER_AUTH_TOKEN=gizli-token python -m src.api.worker_server --agent database --port 8002
   ```
2. Master makinede `.env` (ör. `DATABASE_AGENT_URL=http://100.64.0.12:8002`) veya `config/agents_config.json` (`deployment.endpoint_url`) tanımlandığında `wrap_agent_if_remote()` ajanı otomatik olarak `RemoteAgentProxy` ile sarar.
3. `MasterOrchestrator` kodunda hiçbir değişiklik gerekmeden görevler Tailscale/HTTP üzerinden ilgili ekip üyesinin makinesine gönderilir ve üretilen dosyalar Master üzerinde `workspaces/{run_id}/` dizinine güvenle yazılır.

---

## 7. Master Orchestrator Görev Kayıt ve Integration Agent Rapor Sözleşmesi

### 7.1. Orchestrator Görev Sonuç Kaydı (`OrchestratorTaskRecordContract_v1`)
`UNASSIGNED` ve `BLOCKED` durumları işçi ajanlar tarafından değil, doğrudan `MasterOrchestrator` (`src/master/orchestrator.py`) tarafından üretilir. Ayrıca failover takibi için `agent_result_status`, `attempted_agents` ve `output_files` alanları tutulur:

```json
{
  "contract_version": "1.0",
  "run_id": "run-a89c2f10",
  "task_id": "task-be-1",
  "status": "COMPLETED",
  "assigned_agent": "Backend Architecture Agent",
  "agent_result_status": "SUCCESS",
  "attempted_agents": ["Backend Architecture Agent"],
  "output_artifacts": {},
  "output_files": ["backend_task_be_1.py"],
  "error_message": null
}
```

### 7.2. Integration Agent Denetim Raporu (`IntegrationReportContract_v1`)
`src/agents/integration_agent.py` önceki görevlerin ürettiği gerçek çıktı dosyalarını (`output_artifacts` ve `artifact_sources`) inceler; sözdizimi (AST), güvenli yol ve çakışma kontrollerini yaptıktan sonra kanıta dayalı rapor döner:

```json
{
  "contract_version": "1.0",
  "run_id": "run-a89c2f10",
  "status": "APPROVED",
  "inspected_files": ["database/schema_task_db_1.sql", "backend_task_be_1.py"],
  "conflicts_detected": [],
  "conflicts_resolved": 0,
  "findings": [],
  "package_path": null,
  "summary": "2 dosya incelendi, 0 bulgu saptandı. Durum: APPROVED"
}
```
