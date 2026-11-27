# Testing Agent model kıyaslaması (2026-11-27)

Betik: `scripts/testing_model_benchmark.py` · Görev kümesi: 3 senaryo × 1 tekrar · Donanım: Windows 10, 20 mantıksal çekirdek, Python 3.11.0

## Özet

| Model | Görev | Geçerli çıktı | İlk denemede kabul | Medyan süre | Üretilen test geçme oranı | Tamamı geçen paket |
|---|---|---|---|---|---|---|
| deepseek-coder:6.7b | 3 | %100 | %100 | 39.68 sn | %100 (16/16) | 3 |

## Tahmini puanlarla karşılaştırma (config/agents_config.json)

Ölçülen değerler 0-100 ölçeğine çevrilmiş vekil metriklerdir: kodlama ≈ geçerli çıktı oranı × test geçme oranı, akıl yürütme ≈ ilk denemede kabul oranı (sözleşme ve durum kodu kurallarına düzeltme gerekmeden uyma). Yapılandırmadaki puanlar değiştirilmedi.

| Model | Kodlama (tahmini → ölçülen) | Fark | Akıl yürütme (tahmini → ölçülen) | Fark |
|---|---|---|---|---|
| deepseek-coder:6.7b | 88.0 → 100.0 | 12.0 | 95.0 → 100.0 | 5.0 |

## Görev ayrıntıları

| Model | Senaryo | Tekrar | Durum | Süre | Yeniden deneme | Testler (geçen/çalışan) | Not |
|---|---|---|---|---|---|---|---|
| deepseek-coder:6.7b | books | 1 | SUCCESS | 39.68 sn | 0 | 5/5 |  |
| deepseek-coder:6.7b | events_tickets | 1 | SUCCESS | 58.9 sn | 0 | 8/8 |  |
| deepseek-coder:6.7b | todos | 1 | SUCCESS | 21.79 sn | 0 | 3/3 |  |

## Uçtan uca (E2E) doğrulama

Gereksinim: `docs/model_tests/sample_requirement.md` · Süre: 47.66 sn · Sistem durumu: **COMPLETED** · Ayrıştırma: template

- Görev durumları: {'COMPLETED': 6, 'FAILED': 0, 'UNASSIGNED': 0, 'BLOCKED': 0}
- Ortak sözleşme: yok (sabit şablon ayrıştırma sözleşme üretmez)
- Duman testi: PASSED (1/1 uç nokta çalıştı): GET /health -> 200
- Üretilen testler: FAILED (2/3 test geçti (%67)), test modeli: deepseek-coder:6.7b
  - `test_normal`: IndexError: list index out of range

| Görev | Durum | Ajan | Model | Süre (sn) | Not |
|---|---|---|---|---|---|
| task-req-1 | COMPLETED | Backend Architecture Agent | qwen2.5-coder:7b | 3.08 |  |
| task-db-1 | COMPLETED | Database Schema Agent | llama3.2:3b | 3.06 |  |
| task-be-1 | COMPLETED | Backend Architecture Agent | qwen2.5-coder:7b | 3.06 |  |
| task-fe-1 | COMPLETED | Frontend Specialist Agent | qwen2.5-coder:3b | 2.04 |  |
| task-qa-1 | COMPLETED | Automated Testing Agent | deepseek-coder:6.7b | 32.37 |  |
| task-int-1 | COMPLETED | Integration Agent | phi4-mini:3.8b | 2.1144 |  |

## Otomatik test paketi

python -m unittest discover -s tests: 521 test, OK (11 atlandı) — 27 Kasım 2026, CI ile aynı çevrim dışı ayarlar (OLLAMA_HOST kapalı port).

## Sınırlar

- temperature 0.1 + seed 42: aynı makinede sonuçlar büyük ölçüde tekrarlanabilir, farklı donanımda süreler değişir.
- Ölçülen vekil metrikler yalnızca test yazma görevini kapsar; yapılandırmadaki genel yetenek puanlarının yerine geçmez.
- Yalnızca deepseek-coder:6.7b ölçüldü (Testing Agent'ın atanmış modeli); diğer modeller bu makinede kurulu değil. Betik --model ile çoklu model kıyasını destekler.
- E2E çalıştırmasında yalnızca Testing Agent'ın modeli kurulu; diğer ajanlar etiketli yedek şablonla çalıştı ve ayrıştırma sabit şablondan geldi (qwen2.5:7b kurulu değil).
