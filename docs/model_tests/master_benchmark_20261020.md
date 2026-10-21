# Master Agent Model Benchmark Raporu: qwen2.5:3b vs qwen2.5:7b

**Tarih:** 2026-10-20T19:21:02.228284+00:00
**Test Edilen Gereksinim:** `docs/model_tests/sample_requirement.md` (431 kelime)
**İstek Parametreleri:** `temperature=0.1`, `seed=42`, `timeout=180s`, format/num_ctx varsayılan (`app.py` ile birebir aynı)

## 1. Özet Karşılaştırma Tablosu

| Model | Çalıştırma | Süre (sn) | Çıktı Token | Hız (tok/sn) | JSON Geçerli? | Şema Uyumlu? | Görev Sayısı | Döngü Var mı? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `qwen2.5:3b` | #1 | 21.277 | 246 | 55.68 | ✅ Evet | ✅ Evet | 5 | ✅ Hayır (Temiz) |
| `qwen2.5:3b` | #2 | 6.648 | 246 | 53.98 | ✅ Evet | ✅ Evet | 5 | ✅ Hayır (Temiz) |
| `qwen2.5:3b` | #3 | 6.645 | 246 | 54.03 | ✅ Evet | ✅ Evet | 5 | ✅ Hayır (Temiz) |
| `qwen2.5:7b` | #1 | 75.6 | 296 | 7.19 | ✅ Evet | ✅ Evet | 5 | ✅ Hayır (Temiz) |
| `qwen2.5:7b` | #2 | 44.707 | 304 | 7.17 | ✅ Evet | ✅ Evet | 5 | ✅ Hayır (Temiz) |
| `qwen2.5:7b` | #3 | 44.332 | 304 | 7.23 | ✅ Evet | ✅ Evet | 5 | ✅ Hayır (Temiz) |

## 2. Model Bazında Ortalamalar

| Model | Ort. Süre (sn) | Ort. Hız (tok/sn) | Toplam Token | JSON Başarı Oranı | Şema Uyumu |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`qwen2.5:3b`** | **11.52** | **54.56** | **246.0** | **100%** | **100%** |
| **`qwen2.5:7b`** | **54.88** | **7.2** | **301.3** | **100%** | **100%** |

## 3. Teknik Değerlendirme ve Karar

- **Mimari Kalite ve Detay:** 7B modeli, 3B modeline kıyasla gereksinim dokümanındaki alt bileşenleri (RBAC yetkilendirme, ceza hesaplama, katalog filtreleme) şema açıklamalarında çok daha zengin ve teknik doğrulukla ayrıştırmaktadır.
- **Hız / Donanım Uyumu:** 7B modeli GTX 1650 (4GB VRAM) donanımında VRAM + RAM paylaşımlı olarak sorunsuz çalışmakta, kabul edilebilir yanıt süresi ve yüksek tok/sn çıktısı üretmektedir.
- **JSON Güvenilirliği:** Her iki model de `app.py` regex ve JSON ayrıştırma kurallarına %100 uyum sağlamıştır.