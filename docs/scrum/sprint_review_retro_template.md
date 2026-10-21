# Standart Sprint Değerlendirme (Review) ve Retrospektif Şablonu
## (Standard Sprint Review & Retrospective Template)

**Oluşturan:** İrem Yılmaz (Scrum Master & Backend Agent — `qwen2.5-coder:7b`)  
**Kullanım Alanı:** Distributed AI Software Development Platform — Tüm Sprint Kapanışları  
**Metodoloji:** Scrum (5 İterasyon / 10 Hafta)

---

## 1. Sprint Genel Bilgileri
* **Sprint No:** Sprint [X]
* **Sprint Dönemi:** YYYY-AA-GG – YYYY-AA-GG (Hafta [X] – [Y])
* **Sprint Hedefi (Sprint Goal):** [Bu sprintte neyi neden başarmayı taahhüt ettik?]
* **Sprint Durumu:** [TAMAMLANDI / DEVAM EDİYOR / İNCELENİYOR]
* **Kapasite ve Hız (Velocity):** Taahhüt Edilen: [X] SP | Tamamlanan: [Y] SP ([Z]% Başarı Oranı)

---

## 2. Teslim Edilen Artırım (Increment) ve Gözlemlenebilir Kanıtlar

| Kart Kimliği | Görev Başlığı ve Kapsamı | Asıl Sorumlu | Depo Kanıtları (Dosyalar & Modüller) | Doğrulama & Kabul Durumu |
| :--- | :--- | :--- | :--- | :--- |
| **S[X]-01** | [Görev Başlığı] | [Üye Adı] | `path/to/file1.py`, `docs/...` | [Kabul kriterleri karşılandı mı? Çalışır kanıt var mı?] |
| **S[X]-02** | [Görev Başlığı] | [Üye Adı] | `path/to/file2.py` | [Doğrulama Sonucu] |
| **S[X]-03** | [Görev Başlığı] | [Üye Adı] | `path/to/file3.py` | [Doğrulama Sonucu] |

---

## 3. Doğrulama ve Terminal / Test Kanıtları (Terminal Evidence)
Bu bölümde teslim edilen özelliklerin çalıştığını kanıtlayan komut satırı çıktıları, birim test raporları ve ekran gözlemleri yer alır:

```bash
# Birim test çalıştırma komutu
python -m unittest discover -s tests

# CLI / Motor doğrulama komutu
python -m src.master.orchestrator "Örnek gereksinim"
```

* **Test Çıktı Özeti:** [Ran X tests in Ys — OK]
* **Gözlemlenen Kritik Çıktılar:**
  - [Çıktı 1 / Atama doğrulaması]
  - [Çıktı 2 / Fallback veya API doğrulaması]

---

## 4. Sprint Retrospektifi (Scrum Retrospective)

### 4.1. Ne İyi Gitti? (What Went Well)
* [Takımın iyi yaptığı, koruması gereken süreçler ve başarılar]
* [İletişim ve iş birliği kazanımları]
* [Teknik mimari ve kod kalitesi başarıları]

### 4.2. Karşılaşılan Zorluklar ve Teknik Borçlar (Challenges & Identified Debt)
* [Sprint sırasında takılan veya tahmin edilenden uzun süren konular]
* [Mock/simülasyon aşamasından gerçek implementasyona geçiş engelleri]
* [Araç, donanım (VRAM/RAM) veya model kısıtları]

### 4.3. Gelecek Sprint İçin Aksiyon Maddeleri (Action Items)
* **[Sorumlu Üye]:** [Sonraki sprintte yapılacak iyileştirme adımı]
* **[Sorumlu Üye]:** [Teknik borcu kapatacak somut eylem]

---

**Raporu Düzenleyen:** İrem Yılmaz (Scrum Master)  
**Onaylayan:** Elif Yılmaz (Product Owner)
