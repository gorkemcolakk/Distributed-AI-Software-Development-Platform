# Sprint 2 Review Report & Retrospective
## (Sprint 2 Değerlendirme ve Retrospektif Raporu)

* **Sprint Dönemi:** 2026-10-08 – 2026-10-21 (Hafta 3 – 4)
* **Sprint Hedefi:** API anahtarı ve güvenli yedek (fallback) yapılandırmasını standartlaştırmak, Streamlit arayüzü ile çekirdek motoru tekil ajan sicili (`agents_config.json`) altında birleştirmek, ağırlıklı yetenek puanlamasını (`FitScore`) ve meşgul/çevrimdışı ajan filtrelemesini hayata geçirmek, görev parçalama şemasını doğrulamak ve `run_id` ile zamanlayıcı/SQLite durum izolasyonunu sağlamak.
* **Sprint Durumu:** **TAMAMLANMA AŞAMASINDA / ARA DEĞERLENDİRME**
* **Scrum Rolleri:**
  - **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - **Product Owner:** Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`)
  - **Geliştirici Takımı:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz

---

## 1. Teslim Edilen Artırımlar ve Gözlemlenebilir Kanıtlar

| Kart Kimliği | Görev Başlığı ve Kapsamı | Asıl Sorumlu | Depo Kanıtları (Dosyalar & Modüller) | Doğrulama & Kabul Durumu |
| :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Backend API / Yerel Ollama yapılandırmasını standartlaştırma ve güvenli yedek (fallback) mantığını kurma | İrem Yılmaz | `master_agent_projesi/app.py`, `master_agent_projesi/test_api.py`, `.env.example`, `config/agents_config.json`, `docs/WORKER_HTTP_API_DRAFT.md`, `tests/test_api_config_fallback.py` | **TAMAMLANDI (DONE):** Yinelenen anahtar yükleyiciler kaldırıldı. `load_api_key()` ve `get_model_config()` tek merkez yapıldı. Sabit kimlik bilgileri temizlendi. HTTP 429, zaman aşımı ve çevrimdışı durumlar için çökmesiz güvenli yedek mod sağlandı. 12 birim testin tümü geçti. |
| **S2-02** | Streamlit UI ve Çekirdek Motoru Tekil Ajan Sicilinde Birleştirme | Kübra Hepcan | `config/agents_config.json`, `app.py`, `src/agents/base_agent.py` | **İNCELEMEDE / ENTEGRASYONDA:** `agents_config.json` v2.0 formatına getirildi, UI eşleştirmesi güncelleniyor. |
| **S2-03** | Ağırlıklı Yetenek Puanlaması (`FitScore`) ve Müsait Olmayan Ajanların Filtrelenmesi | Eren Görkem Çolak | `src/master/capability_eval.py`, `tests/test_master_engine.py` | **TAMAMLANDI (DONE):** `BUSY`, `OFFLINE` ve `ERROR` durumundaki ajanlar seçim havuzundan filtrelendi; `calculate_fit_score` entegre edildi. |
| **S2-04** | Görev Parçalama Çıktısını Doğrulama ve Güvenli Fallback Şablonunu Güçlendirme | Mahmut Karaalioğlu | `src/master/analyzer.py`, `master_agent_projesi/app.py` | **TAMAMLANDI (DONE):** 5 standart aşama normalizasyonu eklendi; bozuk JSON koruması tamamlandı. |
| **S2-05** | Zamanlayıcı Yaşam Döngüsü (`run_id`) ve Başarısız Görev Raporlaması | Eren Görkem Çolak | `src/master/scheduler.py`, `src/master/orchestrator.py` | **TAMAMLANDI (DONE):** Her çalıştırma için tekil `run_id` üretildi; başarısız görevler izole edildi. |
| **S2-06** | UI Görev Atamalarını ve Durumlarını Gerçek Motor Sonuçlarına Bağlama | Kübra Hepcan | `master_agent_projesi/app.py` | **DEVAM EDİYOR (IN PROGRESS):** UI buton simülasyonundan canlı yürütmeye geçiş. |
| **S2-07** | SQLite Kalıcılık Katmanını (`db_manager.py`) Tekil Ajan Sicili ve `run_id` ile Bütünleştirme | İrem Yılmaz | `src/master/db_manager.py`, `docs/DATA_MODEL.md` | **DEVAM EDİYOR (IN PROGRESS):** Veritabanı şemasına `run_id` ve yürütme metrikleri eklendi. |

---

## 2. Doğrulama ve Terminal Kanıtları (Terminal Evidence)

### 2.1. Birim Test Çalıştırma Kanıtı
```bash
python -m unittest discover -s tests
```
* **Sonuç:**
```text
Ran 12 tests in 0.030s
OK
SQLite veritabanı (state.db) başarıyla başlatıldı.
```
* **Doğrulanan Özellikler:**
  - `test_load_api_key_empty`: Ortamda anahtar yokken çökmeden boş dize dönülmesi.
  - `test_load_api_key_filters_dummy_placeholders`: `"api.key"` gibi sahte sabitlerin ayıklanması.
  - `test_call_local_ollama_quota_exceeded_429`: HTTP 429 kota hatasının sınıflandırılması.
  - `test_call_local_ollama_timeout`: Zaman aşımı (socket timeout) durumunun yakalanması.
  - `test_call_local_ollama_connection_refused`: Çevrimdışı Ollama sunucusuna karşı güvenli koruma.
  - `test_decompose_task_fallback_on_429`: Kota aşıldığında sistemin çökmeden etiketlenmiş yedek kipine geçmesi.
  - `test_decompose_task_fallback_on_offline`: Ollama kapalıyken 5 görevli yedek veri setinin dönmesi.

### 2.2. Ajan HTTP REST İletişim Protokolü Kanıtı
* [`docs/WORKER_HTTP_API_DRAFT.md`](file:///c:/Users/admin/OneDrive/Desktop/Distributed-AI-Software-Development-Platform/docs/WORKER_HTTP_API_DRAFT.md) hazırlandı.
* Elif'in SRS (`docs/SRS.md`) dokümanındaki REQ-8, REQ-9 ve NFR-2 ile tam uyumlu HTTP adresleri, `POST /register`, `POST /heartbeat`, `GET /tasks/pending`, `POST /tasks/{id}/result` sözleşmeleri ve Bearer Token kimlik doğrulama mekanizmaları tanımlandı.

---

## 3. Sprint Retrospektifi (Scrum Retrospective)

### 3.1. Ne İyi Gitti? (What Went Well)
1. **API ve Güvenlik Standardizasyonu (S2-01):** Kod tabanındaki tüm sahte ve sabit kimlik bilgileri (`api.key` vb.) temizlendi, `.env.example` şablonu oluşturuldu ve `.env` dosyası `.gitignore` ile korumaya alındı.
2. **Sağlam Hata İzolasyonu (NFR-2):** Ollama sunucusu çalışmadığında dahi kullanıcı arayüzü çökmüyor; HTTP 429 (kota), bağlantı zaman aşımı veya çevrimdışı sunucu durumlarında kullanıcıya Türkçe bilgilendirici mesajlar gösterilerek etiketli yedek mod devrede tutuluyor.
3. **Roller Arası Güçlü Eşgüdüm:** Product Owner (Elif Yılmaz) gereksinimleri ile Backend (İrem Yılmaz) REST taslağı ve mimari belgeleri tam uyumlu hale getirildi.

### 3.2. Karşılaşılan Zorluklar ve Teknik Borçlar
1. **Donanım ve Model Boyutları:** `qwen2.5-coder:7b` ve `deepseek-coder:6.7b` modellerinin yerel yüklenmesi 8GB+ RAM/VRAM gerektirdiği için takım üyelerinin yerel testlerinde yedek fallback modunun önemi kritik hale geldi.
2. **Streamlit UI Senkronizasyonu:** UI oturum durumunun (`st.session_state`) asenkron ajan yürütmeleriyle canlı tetiklenmesi için WebSocket veya polling mekanizmasının Sprint 3'te olgunlaştırılması gerekiyor.

### 3.3. Sprint 3 İçin Eylem Maddeleri (Action Items)
* **İrem Yılmaz (Backend):** `docs/WORKER_HTTP_API_DRAFT.md` protokolünü FastAPI tabanlı canlı bir REST servisine dönüştürerek worker ajanların gerçek ağ çağrılarını kabul etmesini sağlamak (**REQ-8 / S3-02**).
* **Elif Yılmaz (Integration & PO):** Entegrasyon ajanını (`phi4-mini:3.8b`) HTTP üzerinden gelen kod bloklarını birleştirecek ve statik inceleme yapacak şekilde yapılandırmak (**S4-02**).
* **Kübra Hepcan (Frontend):** UI üzerinde her ajanın gerçek ağ durumunu (`IDLE`, `BUSY`, `OFFLINE`) heartbeat sinyallerinden okuyarak canlı görselleştirmek (**REQ-2.3 / S3-01**).

---

**Raporu Hazırlayan:** İrem Yılmaz (Scrum Master & Backend Agent)  
**Tarih:** 2026-10-20  
