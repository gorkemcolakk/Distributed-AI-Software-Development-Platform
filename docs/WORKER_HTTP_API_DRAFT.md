# Dağıtık Worker Ajan HTTP REST İletişim Protokolü ve Entegrasyon Taslağı
## (Worker Agent HTTP Interface & Communication Contract)

**Hazırlayan:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b` / Scrum Master)  
**İlgili Belgeler & Referanslar:** 
- Elif Yılmaz (Product Owner) — [`docs/SRS.md`](file:///c:/Users/admin/OneDrive/Desktop/Distributed-AI-Software-Development-Platform/docs/SRS.md) (*REQ-8 Dağıtık Ağ İletişimi, REQ-9 Zaman Aşımı ve Hata Kurtarma, NFR-2 Düğüm Hata İzolasyonu*)
- Sistem Mimarisi — [`docs/ARCHITECTURE.md`](file:///c:/Users/admin/OneDrive/Desktop/Distributed-AI-Software-Development-Platform/docs/ARCHITECTURE.md) (*Bölüm 3: Communication Protocol*)
- Temel Veri Modelleri — [`src/agents/base_agent.py`](file:///c:/Users/admin/OneDrive/Desktop/Distributed-AI-Software-Development-Platform/src/agents/base_agent.py) (*BaseAgent, AgentStatus, TaskCategory, TaskResult*)
- Sprint Kartı: **S2-01** / **S2-07** / Hazırlık: **Sprint 3 (REQ-8 & REQ-3.2)**

---

## 1. Genel Bakış ve Amaç
Bu doküman, dağıtık makinelerde veya farklı çalışma ortamlarında yerel Ollama modelleriyle çalışan bağımsız Worker Ajanların (`FrontendAgent`, `DatabaseAgent`, `TestingAgent`, `IntegrationAgent`), İrem Yılmaz sorumluluğundaki **Merkezi Backend API Servisi (Master/Backend Node)** ile HTTP REST üzerinden nasıl haberleşeceğini, hangi adrese bağlanacağını, hangi JSON verilerini gönderip ne yanıt alacağını standartlaştırmak üzere hazırlanmıştır.

Elif'in SRS dokümanındaki **NFR-2 (Node Fault Isolation)** ilkesi uyarınca, herhangi bir worker ajan makinesinin çökmesi, ağının kopması veya zaman aşımına uğraması merkezi orkestratörü ve Streamlit arayüzünü kilitlemeyecek; tüm iletişim durum kodları ve zaman aşımı mekanizmalarıyla izole edilecektir.

---

## 2. Ağ Yapılandırması ve Temel Parametreler

| Parametre | Değer / Açıklama |
| :--- | :--- |
| **Temel Servis Adresi (Base URL)** | `http://<BACKEND_HOST>:<PORT>/api/v1` (Örn: `http://localhost:8000/api/v1`) |
| **İletişim Protokolü** | HTTP/1.1 REST over JSON |
| **İstek Başlıkları (Headers)** | `Content-Type: application/json`<br>`Authorization: Bearer <BACKEND_AUTH_TOKEN>` |
| **Varsayılan Zaman Aşımı (Timeout)** | 45 saniye (`OLLAMA_TIMEOUT` / `HTTP_TIMEOUT`) |
| **Heartbeat Sıklığı** | 15 saniyede bir |

---

## 3. Uç Noktalar (Endpoints): Ne Alır, Ne Döner?

### 3.1. Sistem Sağlık Kontrolü (Health Check)
Ajanların merkezi servisin ayakta olup olmadığını doğrulaması için kullanılır.

- **Adres:** `GET /api/v1/health`
- **Ne Alır (İstek):** Parametre yok.
- **Ne Döner (HTTP 200 OK):**
```json
{
  "status": "HEALTHY",
  "service": "Nexus Distributed Multi-Agent Backend",
  "version": "2.0.0",
  "active_run_id": "run-a89c2f10",
  "registered_agents_count": 5,
  "timestamp": 1792489000.12
}
```

---

### 3.2. Ajan Kaydı ve Yetenek Profili Bildirimi (Agent Registration)
Bir worker ajan süreci (node) başlatıldığında merkezi sisteme kendini ve yerel Ollama modelini tanıtır.

- **Adres:** `POST /api/v1/agents/register`
- **Ne Alır (İstek Gövdesi - Request Body):**
```json
{
  "agent_id": "agent-frontend",
  "name": "Frontend Agent",
  "member": "Kübra Hepcan",
  "role": "Frontend UI/UX",
  "model_name": "qwen2.5-coder:3b",
  "status": "IDLE",
  "capabilities": {
    "coding": 95.0,
    "reasoning": 78.0,
    "context_capacity": 85.0,
    "specialties": ["frontend", "ui_ux", "react", "css_design_system"],
    "provenance": {
      "coding": "estimated",
      "reasoning": "estimated",
      "context_capacity": "estimated"
    }
  },
  "endpoint_callback": "http://192.168.1.42:8001/task"
}
```

- **Ne Döner (HTTP 201 Created):**
```json
{
  "success": true,
  "agent_id": "agent-frontend",
  "session_token": "agt-sess-9f81d4a0",
  "heartbeat_interval_seconds": 15,
  "message": "Ajan kaydı başarıyla doğrulandı ve havuza eklendi."
}
```

---

### 3.3. Canlılık Sinyali (Heartbeat & Keep-Alive)
Elif'in SRS REQ-9 kuralı doğrultusunda, ajanın kilitlenmediğini ve çevrim içi olduğunu raporlar.

- **Adres:** `POST /api/v1/agents/heartbeat`
- **Ne Alır (İstek Gövdesi):**
```json
{
  "agent_id": "agent-frontend",
  "status": "IDLE",
  "active_tasks": [],
  "hardware_metrics": {
    "vram_used_mb": 2400,
    "cpu_percent": 14.5
  }
}
```

- **Ne Döner (HTTP 200 OK):**
```json
{
  "acknowledged": true,
  "has_pending_task": true,
  "next_task_id": "task-fe-1"
}
```

---

### 3.4. Atanmış Görevi Çekme (Poll Next Task)
Worker ajan boşta (`IDLE`) olduğunda, Master Agent orkestratörünün kendisine atadığı sıradaki görevi teslim alır.

- **Adres:** `GET /api/v1/tasks/pending?agent_id=agent-frontend`
- **Ne Alır (Query Parametresi):** `agent_id` (Zorunlu)
- **Ne Döner (HTTP 200 OK — Görev Varsa):**
```json
{
  "has_task": true,
  "task": {
    "task_id": "task-fe-1",
    "run_id": "run-a89c2f10",
    "category": "FRONTEND",
    "title": "Frontend User Interface & Components",
    "description": "Kütüphane kitap arama ve ödünç alma form bileşenlerinin kodlanması.",
    "complexity": "Medium",
    "story_points": 5,
    "primary_skill_required": "Coding",
    "dependencies": ["task-be-1"],
    "context_artifacts": {
      "backend_api_specs": ["/api/v1/books", "/api/v1/borrow"],
      "schema_summary": "Users, Books, Loans tabloları hazır"
    },
    "timeout_seconds": 180
  }
}
```

- **Ne Döner (HTTP 200 OK — Bekleyen Görev Yoksa):**
```json
{
  "has_task": false,
  "message": "Atanmış veya hazır bekleyen görev bulunmuyor."
}
```

---

### 3.5. Görev Başlama Onayı (Task Acknowledgment)
Ajan görevi işlemeye başladığında durumu `BUSY` olarak günceller.

- **Adres:** `POST /api/v1/tasks/{task_id}/ack`
- **Ne Alır (İstek Gövdesi):**
```json
{
  "agent_id": "agent-frontend",
  "status": "BUSY",
  "estimated_completion_seconds": 45
}
```

- **Ne Döner (HTTP 200 OK):**
```json
{
  "acknowledged": true,
  "task_id": "task-fe-1",
  "state": "RUNNING"
}
```

---

### 3.6. Görev Sonucu ve Çıktı Eserlerin Gönderilmesi (Submit Task Result)
Ajan yerel Ollama modeliyle işi tamamladığında çıktıları (`output_artifacts`), logları ve yürütme süresini Backend'e teslim eder. Bu yapı `src/agents/base_agent.py` içerisindeki `TaskResult` sınıfı ile birebir örtüşür.

- **Adres:** `POST /api/v1/tasks/{task_id}/result`
- **Ne Alır (İstek Gövdesi — `TaskResult` Sözleşmesi):**
```json
{
  "task_id": "task-fe-1",
  "agent_id": "agent-frontend",
  "status": "SUCCESS",
  "output_artifacts": {
    "files": [
      {
        "filename": "frontend/src/App.jsx",
        "content": "// React App Code..."
      },
      {
        "filename": "frontend/src/components/BookList.jsx",
        "content": "// React BookList..."
      }
    ],
    "components_count": 2,
    "framework": "React / Vite"
  },
  "logs": [
    "[Frontend Agent] Starting execution for task 'task-fe-1': Frontend User Interface & Components",
    "[Frontend Agent] Generating React layout with CSS design system tokens...",
    "[Frontend Agent] Component synthesis completed successfully."
  ],
  "execution_time_seconds": 14.85,
  "error_message": null
}
```

- **Ne Döner (HTTP 200 OK):**
```json
{
  "success": true,
  "task_id": "task-fe-1",
  "next_state": "COMPLETED",
  "unlocked_downstream_tasks": ["task-qa-1"],
  "message": "Görev çıktısı ve eserler başarıyla kaydedildi, bağımlı görevler tetiklendi."
}
```

---

## 4. Hata Yönetimi, Kota (429), Zaman Aşımı ve Güvenli Yedekleme

| Durum Kodu | Anlamı | Backend Davranışı & Güvenli Yedek Protokolü |
| :--- | :--- | :--- |
| **HTTP 401 Unauthorized** | Geçersiz veya eksik Bearer token | İstek reddedilir; ajan `.env` dosyasındaki `BACKEND_AUTH_TOKEN` değerini kontrol etmelidir. |
| **HTTP 404 Not Found** | Görev ID veya Ajan ID sistemde kayıtlı değil | Hata kaydı düşülür, ajana tekrar kayıt olma (`/register`) talimatı verilir. |
| **HTTP 429 Too Many Requests** | Hız sınırı veya model çıkarım kotası aşıldı | `Retry-After: <saniye>` başlığı döner. Ajan üstel geri çekilme (exponential backoff) uygular. Eğer yerel inferans kilitlenirse sistem güvenli şablon/yedek kipine geçer. |
| **HTTP 408 / 504 Timeout** | Ajan veya sunucu yanıt süresi aşıldı | Elif'in SRS REQ-9 kuralı gereğince görev `FAILED` işaretlenir ve uygun alternatif ajana yönlendirilir. |
| **HTTP 503 Service Unavailable** | Backend veritabanı meşgul veya bakımda | Ajan yerel belleğinde çıktıları geçici olarak saklar ve 5 saniye sonra tekrar dener. |

---

## 5. Elif Yılmaz (Product Owner) ile Eşgüdüm ve Entegrasyon Adımları
1. **SRS REQ-8 Uyumu:** Bu taslak Sprint 3'te gerçekleştirilecek `FastAPI` tabanlı worker ağının temel sözleşmesini oluşturur.
2. **BaseAgent Uyumu:** `src/agents/base_agent.py` içerisindeki `to_dict()`, `execute_task()`, ve `TaskResult` veri yapıları HTTP JSON şemalarıyla tam uyumlu hale getirilmiştir.
3. **Sprint 2 Veritabanı Entegrasyonu (S2-07):** SQLite tablosundaki `tasks` ve `agent_executions` tabloları yukarıdaki `run_id`, `task_id`, `execution_time_seconds` alanlarını kalıcı olarak saklayacaktır.
