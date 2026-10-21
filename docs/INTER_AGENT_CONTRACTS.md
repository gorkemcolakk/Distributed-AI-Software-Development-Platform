# Ajanlar Arası Entegrasyon ve İletişim Sözleşmesi (v1.0)

Bu doküman, Master Agent, İşçi Ajanlar (Database, Backend, Frontend, Testing) ve Integration Agent arasındaki veri alışverişi kurallarını ve sürümlü sözleşmeleri (`v1.0`) tanımlar.

---

## 1. Master Agent Görev Sınıflandırma Doğrulama Kuralı
Master Agent (`qwen2.5:7b`) kullanıcı gereksinimini parçaladığında ürettiği JSON çıktısı `contracts.py` içerisindeki `validate_master_classification()` fonksiyonu ile doğrulanır.
* **Zorunlu Kategoriler:** `Requirements_Analysis`, `Frontend_Development`, `Backend_Development`, `Database_Design`, `Quality_Assurance_and_Testing`
* **Alt Alan Kuralları:**
  * `description`: En az 10 karakterli teknik açıklama (`str`)
  * `complexity`: `"Low"`, `"Medium"` veya `"High"`
  * `primary_skill_required`: `"Coding"`, `"Reasoning"` veya `"Context"`
  * `story_points`: `1` ile `13` arasında tam sayı (`int`)

---

## 2. Ana Ajan -> İşçi Ajan Görev Sözleşmesi (`TaskContract_v1`)
Master Agent bir işçi ajana HTTP `POST` isteği ile görev atarken aşağıdaki JSON şemasını gönderir:

```json
{
  "contract_version": "1.0",
  "run_id": "run_20261021_001",
  "task_id": "task_backend_01",
  "target_agent": "backend",
  "description": "Kullanıcı kayıt ve giriş işlemleri için FastAPI endpointlerini yaz.",
  "input_artifacts": {
    "schema.sql": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password TEXT);"
  }
}
{
  "contract_version": "1.0",
  "run_id": "run_20261021_001",
  "task_id": "task_backend_01",
  "agent_role": "backend",
  "status": "COMPLETED",
  "output_files": {
    "main.py": "from fastapi import FastAPI\napp = FastAPI()\n..."
  },
  "error_message": null
}
{
  "contract_version": "1.0",
  "run_id": "run_20261021_001",
  "overall_status": "PASSED",
  "inspected_files": ["schema.sql", "main.py", "index.html", "test_auth.py"],
  "findings": [
    {
      "file_name": "main.py",
      "severity": "WARNING",
      "issue": "Eksik tablo referansı",
      "actionable_suggestion": "schema.sql içindeki users tablosunu main.py modellerine ekleyin."
    }
  ],
  "llm_review_summary": "Dosyalar genel olarak uyumlu, sentaks hatası bulunmadı."
}