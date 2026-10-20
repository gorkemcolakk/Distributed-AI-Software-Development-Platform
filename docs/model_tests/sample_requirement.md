# Online Kütüphane Yönetim Sistemi - Yazılım Gereksinim Dokümanı

## 1. Proje Özeti ve Kapsam
Bu proje; üniversite veya halk kütüphanelerinde kitap envanterini, üyelik işlemlerini, ödünç alma ve iade döngülerini dijitalleştiren modern, güvenli ve ölçeklenebilir bir "Online Kütüphane Yönetim Sistemi" (Library Management System) yazılımını kapsamaktadır. Sistem; web tabanlı kullanıcı arayüzü, RESTful API servisleri ve ilişkisel veritabanı mimarisi üzerinde çalışacaktır.

## 2. Kullanıcı Rolleri ve Yetkilendirme
Sistemde rol tabanlı yetkilendirme (RBAC) uygulanacaktır:
- **Okuyucu / Üye:** Kitap arama, rezervasyon yapma, ödünç aldığı kitapları ve ceza durumunu görüntüleme.
- **Kütüphaneci (Librarian):** Fiziksel ödünç verme ve teslim alma işlemlerini onaylama, yeni kitap ve yazar kaydı açma, raf lokasyonlarını güncelleme.
- **Sistem Yöneticisi (Admin):** Kullanıcı hesaplarını yönetme, rol atama, sistem parametrelerini (günlük gecikme bedeli vb.) yapılandırma ve denetim loglarını inceleme.

## 3. Temel İşlevsel Gereksinimler

### 3.1. Katalog Arama ve Kitap Envanteri
- Kullanıcılar kitap adı, yazar, yayınevi, kategori ve ISBN numarasına göre hızlı ve filtreli arama yapabilmelidir.
- Arama sonuçlarında kitabın toplam adet, mevcut uygun adet ve raf konumu bilgisi anlık gösterilmelidir.
- Kütüphaneciler ISBN numarası üzerinden otomatik meta-veri çekebilmeli ve barkod etiketleri oluşturabilmelidir.

### 3.2. Ödünç Alma, İade ve Rezervasyon Akışı
- Bir üye aynı anda en fazla 3 adet kitap ödünç alabilmelidir.
- Standart ödünç süresi 15 gündür; başka bir kullanıcı rezervasyon yapmamışsa kullanıcı web panelinden süreyi 1 kez 7 gün uzatabilmelidir.
- Fiziksel teslim sırasında kütüphaneci barkod okutarak iade işlemini sisteme kaydeder ve kitap anında tekrar "uygun" statüsüne geçer.

### 3.3. Ceza ve Gecikme Hesaplama
- İade tarihi geçen her gün için sistem otomatik olarak kitap başına günlük 5 TL gecikme bedeli tahakkuk ettirir.
- Toplam ödenmemiş cezası 50 TL'yi aşan veya 15 günden fazla gecikmesi bulunan üyelerin yeni ödünç alma hakları otomatik olarak askıya alınır.
- Kütüphaneci panelinde ceza tahsilat makbuzu kesilebilmeli ve bakiye düşülebilmelidir.

### 3.4. Bildirim ve İletişim Sistemi
- Kitap iade tarihine 3 gün ve 1 gün kala üyeye otomatik e-posta ve SMS hatırlatma bildirimi iletilmelidir.
- Rezerve edilen kitap kütüphaneye iade edildiğinde, sıradaki üyeye 48 saat geçerli "Kitabınız Hazır" bildirimi gönderilmelidir.

### 3.5. Raporlama ve İstatistikler
- Yöneticiler için aylık ve yıllık en çok ödünç alınan kategoriler, en aktif okuyucular ve gecikme trendleri grafiksel gösterge paneliyle sunulmalıdır.
- Envanter ve finansal ceza raporları Excel ve PDF formatında dışa aktarılabilmelidir.

## 4. Güvenlik, Performans ve Teknik Kriterler
- Tüm API uç noktaları JWT (JSON Web Token) ile korunmalı, parolalar Argon2 veya BCrypt ile tuzlanarak hash'lenmelidir.
- Veritabanı işlemleri ACID prensiplerine uygun transaction bloklarında yürütülmeli; eşzamanlı rezervasyonlarda çifte tahsis engellenmelidir.
- Katalog arama sorguları 500 ms altında yanıt vermeli, sistem en az 10.000 aktif üyeyi destekleyecek yapıda tasarlanmalıdır.
