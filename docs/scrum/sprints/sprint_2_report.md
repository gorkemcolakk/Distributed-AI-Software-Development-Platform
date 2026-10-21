# Sprint 2 Review Report & Retrospective
## (Sprint 2 Değerlendirme ve Retrospektif Raporu)

* **Sprint Dönemi:** 2026-10-08 – 2026-10-21 (Hafta 3 – 4)
* **Sprint Hedefi:** API anahtarı ve güvenli yedek (fallback) yapılandırmasını standartlaştırmak, Streamlit arayüzü ile çekirdek motoru tekil ajan sicili (`agents_config.json`) altında birleştirmek, ağırlıklı yetenek puanlamasını (`FitScore`) ve meşgul/çevrimdışı ajan filtrelemesini hayata geçirmek, görev parçalama şemasını doğrulamak ve `run_id` ile zamanlayıcı/SQLite durum izolasyonunu sağlamak.
* **Sprint Durumu:** **TAMAMLANDI** (2026-10-22, yedi kartın tamamı `main`'de)
* **Scrum Rolleri:**
  - **Scrum Master:** İrem Yılmaz (Backend Agent — `qwen2.5-coder:7b`)
  - **Product Owner:** Elif Yılmaz (Integration Agent — `phi4-mini:3.8b`)
  - **Geliştirici Takımı:** Eren Görkem Çolak, Kübra Hepcan, Mahmut Karaalioğlu, Berat İnan, İrem Yılmaz, Elif Yılmaz

---

## 1. Teslim Edilen Artırımlar ve Gözlemlenebilir Kanıtlar

| Kart Kimliği | Görev Başlığı ve Kapsamı | Asıl Sorumlu | Depo Kanıtları (Dosyalar & Modüller) | Doğrulama & Kabul Durumu |
| :--- | :--- | :--- | :--- | :--- |
| **S2-01** | Backend API / Yerel Ollama yapılandırmasını standartlaştırma ve güvenli yedek (fallback) mantığını kurma | İrem Yılmaz | `master_agent_projesi/app.py`, `master_agent_projesi/test_api.py`, `.env.example`, `config/agents_config.json`, `docs/WORKER_HTTP_API_DRAFT.md`, `tests/test_api_config_fallback.py` | **TAMAMLANDI (DONE):** Yinelenen anahtar yükleyiciler kaldırıldı. `load_api_key()` ve `get_model_config()` tek merkez yapıldı. Sabit kimlik bilgileri temizlendi. HTTP 429, zaman aşımı ve çevrimdışı durumlar için çökmesiz güvenli yedek mod sağlandı. Bu kart için 9 birim test yazıldı, tümü geçiyor. |
| **S2-02** | Streamlit UI ve Çekirdek Motoru Tekil Ajan Sicilinde Birleştirme | Kübra Hepcan | `config/agents_config.json`, `master_agent_projesi/app.py` (PR #20) | **TAMAMLANDI (DONE):** Arayüzdeki sabit `agents_data` listesi kaldırıldı; ajan adları, modeller, puanlar ve üyeler `agents_config.json` dosyasından okunuyor. |
| **S2-03** | Ağırlıklı Yetenek Puanlaması (`FitScore`) ve Müsait Olmayan Ajanların Filtrelenmesi | Eren Görkem Çolak | `src/master/capability_eval.py`, `src/master/orchestrator.py`, `tests/test_master_engine.py` | **TAMAMLANDI (DONE):** `BUSY`, `OFFLINE` ve `ERROR` durumundaki ajanlar seçim havuzundan filtrelendi; `calculate_fit_score` entegre edildi; failover ve kilitlenme koruması eklendi. Testler: Berat İnan. |
| **S2-04** | Görev Parçalama Çıktısını Doğrulama ve Güvenli Fallback Şablonunu Güçlendirme | Elif Yılmaz *(sprint içinde Mahmut Karaalioğlu'ndan devralındı)* | `src/contracts.py` (`validate_master_tasks`), `docs/INTER_AGENT_CONTRACTS.md`, `tests/test_contracts.py`, `master_agent_projesi/app.py` (`normalize_tasks`) | **TAMAMLANDI (DONE):** Pydantic sözleşmeleri ve görev listesi doğrulayıcısı eklendi; 5 standart aşama normalizasyonu ve bozuk JSON koruması tamamlandı. Şema testleri: Berat İnan. Doğrulayıcının orchestrator akışına bağlanması Sprint 3'e kaldı. |
| **S2-05** | Zamanlayıcı Yaşam Döngüsü (`run_id`) ve Başarısız Görev Raporlaması | Eren Görkem Çolak | `src/master/scheduler.py`, `src/master/orchestrator.py`, `tests/test_master_engine.py` | **TAMAMLANDI (DONE):** Her çalıştırma için tekil `run_id` üretildi; başarısız görevler izole edildi. Testler: Berat İnan. |
| **S2-06** | UI Görev Atamalarını ve Durumlarını Gerçek Motor Sonuçlarına Bağlama | Kübra Hepcan | `master_agent_projesi/app.py` (PR #20; entegrasyon düzeltmeleri #23, #24) | **TAMAMLANDI (DONE):** Elle "Başlat/Tamamla" butonları kaldırıldı; "Analiz et" gerçek `MasterOrchestrator`'ı çalıştırıyor, görev ve ajan durumları motordan geliyor. |
| **S2-07** | SQLite Kalıcılık Katmanını (`db_manager.py`) Tekil Ajan Sicili ve `run_id` ile Bütünleştirme | Mahmut Karaalioğlu *(sprint içinde İrem Yılmaz'dan devralındı)* | `src/master/db_manager.py`, `docs/DATA_MODEL.md`, `tests/test_db_manager.py` | **TAMAMLANDI (DONE):** `runs`, `agents`, `tasks`, `attempts` tabloları `run_id` ile kuruldu; WAL kipi; hatalı görevlerin `COMPLETED` yazılmasını önleyen 3 katmanlı koruma (Python guard + `CHECK` + trigger); Sprint 1 tabloları için `*_legacy_v1` göçü. 11 birim test. Arayüz çalıştırmaları artık `state.db`'ye yazılıyor (#24). |

---

## 2. Doğrulama ve Terminal Kanıtları (Terminal Evidence)

### 2.1. Birim Test Çalıştırma Kanıtı
```bash
python -m unittest discover tests
```
* **Sonuç (2026-10-22, `main`):**
```text
Ran 44 tests
OK
```
* **Test dağılımı:**
  - `tests/test_master_engine.py` — 20 test: ajan seçimi, durum filtresi, şema doğrulama, failover, `run_id` izolasyonu (Berat İnan, Eren Görkem Çolak)
  - `tests/test_db_manager.py` — 11 test: SQLite şeması ve `COMPLETED` koruması (S2-07)
  - `tests/test_api_config_fallback.py` — 9 test: yapılandırma ve güvenli yedek mod (İrem Yılmaz)
  - `tests/test_contracts.py` — 4 test: Pydantic sözleşmeleri (Elif Yılmaz)
* Bu testler 2026-10-22'den itibaren her PR'da GitHub Actions ile otomatik çalışıyor (PR #22).
* **S2-01 testlerinin doğruladığı özellikler:**
  - `test_load_api_key_empty`: Ortamda anahtar yokken çökmeden boş dize dönülmesi.
  - `test_load_api_key_filters_dummy_placeholders`: `"api.key"` gibi sahte sabitlerin ayıklanması.
  - `test_call_local_ollama_quota_exceeded_429`: HTTP 429 kota hatasının sınıflandırılması.
  - `test_call_local_ollama_timeout`: Zaman aşımı (socket timeout) durumunun yakalanması.
  - `test_call_local_ollama_connection_refused`: Çevrimdışı Ollama sunucusuna karşı güvenli koruma.
  - `test_decompose_task_fallback_on_429`: Kota aşıldığında sistemin çökmeden etiketlenmiş yedek kipine geçmesi.
  - `test_decompose_task_fallback_on_offline`: Ollama kapalıyken 5 görevli yedek veri setinin dönmesi.

### 2.2. Ajan HTTP REST İletişim Protokolü Kanıtı
* [`docs/WORKER_HTTP_API_DRAFT.md`](../../WORKER_HTTP_API_DRAFT.md) hazırlandı.
* Kübra'nın SRS (`docs/SRS.md`) dokümanındaki REQ-8, REQ-9 ve NFR-2 ile tam uyumlu HTTP adresleri, `POST /register`, `POST /heartbeat`, `GET /tasks/pending`, `POST /tasks/{id}/result` sözleşmeleri ve Bearer Token kimlik doğrulama mekanizmaları tanımlandı.

### 2.3. Sprint Sonu Entegrasyon Doğrulaması (2026-10-22)
* **PR #22:** GitHub Actions CI eklendi; her PR'da `python -m unittest discover tests` çalışıyor.
* **PR #23:** Arayüz motora bağlandığında Integration Agent'ın durum alanı diğer ajanlardan farklı tipte olduğu için "Analiz et" çöküyordu; düzeltildi.
* **PR #20:** S2-02 ve S2-06 birleştirildi.
* **PR #24:** Arayüzden başlatılan çalıştırmaların `state.db`'ye yazılması sağlandı.
* **PR #21:** İrem'in `qwen2.5-coder:7b` smoke test sonuçları eklendi (kod görevi 3/3).
* **Arayüz testi:** Ollama kapalıyken "Analiz et" ile 6/6 görev `COMPLETED`; tek çalıştırmada `state.db`'ye 1 run, 5 ajan, 6 görev ve 8 deneme kaydı yazıldı.

---

## 3. Sprint Retrospektifi (Scrum Retrospective)

### 3.1. Ne İyi Gitti? (What Went Well)
1. **API ve Güvenlik Standardizasyonu (S2-01):** Kod tabanındaki tüm sahte ve sabit kimlik bilgileri (`api.key` vb.) temizlendi, `.env.example` şablonu oluşturuldu ve `.env` dosyası `.gitignore` ile korumaya alındı.
2. **Sağlam Hata İzolasyonu (NFR-2):** Ollama sunucusu çalışmadığında dahi kullanıcı arayüzü çökmüyor; HTTP 429 (kota), bağlantı zaman aşımı veya çevrimdışı sunucu durumlarında kullanıcıya Türkçe bilgilendirici mesajlar gösterilerek etiketli yedek mod devrede tutuluyor.
3. **Roller Arası Güçlü Eşgüdüm:** Product Owner (Elif Yılmaz) gereksinimleri ile Backend (İrem Yılmaz) REST taslağı ve mimari belgeleri tam uyumlu hale getirildi.

### 3.2. Karşılaşılan Zorluklar ve Teknik Borçlar
1. **Donanım ve Model Boyutları:** `qwen2.5-coder:7b` ve `deepseek-coder:6.7b` modellerinin yerel yüklenmesi 8GB+ RAM/VRAM gerektirdiği için takım üyelerinin yerel testlerinde yedek fallback modunun önemi kritik hale geldi.
2. **Streamlit UI Senkronizasyonu:** UI oturum durumunun (`st.session_state`) asenkron ajan yürütmeleriyle canlı tetiklenmesi için WebSocket veya polling mekanizmasının Sprint 3'te olgunlaştırılması gerekiyor.
3. **Birim testler entegrasyon hatasını yakalamadı:** PR #23'teki çökme 44 test yeşilken ortaya çıktı; arayüz → motor yolu için entegrasyon testi Sprint 3'e alındı.
4. **Görev ayrıştırma hâlâ statik:** `analyzer.py` her gereksinim için aynı 6 görevi döndürüyor ve alt ajanlar örnek çıktı veriyor. İkisini gerçek modellere bağlamak Sprint 3'ün ana hedefi.

### 3.3. Sprint 3 İçin Eylem Maddeleri (Action Items)
* **İrem Yılmaz (Backend):** `docs/WORKER_HTTP_API_DRAFT.md` protokolünü FastAPI tabanlı canlı bir REST servisine dönüştürerek worker ajanların gerçek ağ çağrılarını kabul etmesini sağlamak (**REQ-8 / S3-02**).
* **Elif Yılmaz (Integration & PO):** Entegrasyon ajanını (`phi4-mini:3.8b`) HTTP üzerinden gelen kod bloklarını birleştirecek ve statik inceleme yapacak şekilde yapılandırmak (**S4-02**).
* **Kübra Hepcan (Frontend):** UI üzerinde her ajanın gerçek ağ durumunu (`IDLE`, `BUSY`, `OFFLINE`) heartbeat sinyallerinden okuyarak canlı görselleştirmek (**REQ-2.3 / S3-01**).

---

**Raporu Hazırlayan:** İrem Yılmaz (Scrum Master & Backend Agent)  
**Tarih:** 2026-10-20  
**Sprint kapanış güncellemesi:** Eren Görkem Çolak, 2026-10-22  
