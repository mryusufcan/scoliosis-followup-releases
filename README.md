#  Scoliosis Follow-Up

**Skolyoz radyografilerinin görüntülenmesi, karşılaştırılması ve takip sürecinin değerlendirilmesi için geliştirilmiş masaüstü uygulaması.**

Scoliosis Follow-Up, farklı tarihlerde elde edilen skolyoz grafilerinin tek bir çalışma ortamında incelenmesini ve hastanın zaman içerisindeki değişiminin görsel olarak takip edilmesini kolaylaştırmak amacıyla geliştirilmiştir.

> ⚠️ Scoliosis Follow-Up klinik karar destek veya otomatik tanı sistemi değildir.  
> Görüntüleme ve takip süreçlerini desteklemek amacıyla geliştirilmiş bir yazılımdır.

---

## 📸 Uygulamadan Görüntüler

<!-- Buraya ekran görüntülerimizi ekleyeceğiz -->

![Scoliosis Follow-Up](assests/goruntuleyici.png)

---

## ✨ Öne Çıkan Özellikler

### 🩻 DICOM Görüntüleyici
- DICOM görüntülerini görüntüleme
- Window / Level ayarları
- Zoom ve pan
- Görüntü bilgilerini inceleme
- Temel görüntü işleme araçları

### 📐 Skolyoz Takibi
- Referans ve kontrol grafilerini karşılaştırma
- Farklı tarihlerdeki çekimleri takip etme
- Overlay karşılaştırma
- Blink karşılaştırma
- Cobb açısı ölçüm araçları
- Tedavi sürecindeki değişimin görsel olarak değerlendirilmesi

### 🧩 DICOM Stitching
- Uzun skolyoz grafilerinin birleştirilmesi
- Otomatik ve manuel hizalama araçları
- Birleşim bölgelerinde yumuşak geçiş
- Birleştirilmiş görüntünün tek çalışma alanında incelenmesi

### 🏥 PACS
- PACS bağlantı desteği
- DICOM çalışma listeleriyle çalışma
- Görüntülerin uygulama içerisinden seçilmesi ve açılması

### 📄 Raporlama
- Ölçüm ve takip bilgilerinin raporlanması
- Profesyonel rapor görünümü
- PDF dışa aktarma

---

## 🔄 Takip ve Karşılaştırma

Scoliosis Follow-Up'ın temel amacı yalnızca bir radyografiyi görüntülemek değil, **zaman içerisindeki değişimi görünür hale getirmektir.**

Örneğin:

**İlk çekim → Kontrol çekimi → Overlay / Blink → Cobb karşılaştırması → Takip raporu**

Bu yapı sayesinde farklı tarihlerde elde edilen görüntüler aynı çalışma ortamında değerlendirilebilir.

---

## 🔐 Lisans ve Güvenlik

Uygulama cihaz tabanlı lisanslama altyapısına sahiptir.

- Cihaz bazlı lisans doğrulama
- Sunucu taraflı lisans kontrolü
- Güvenli RPC tabanlı lisans işlemleri
- Deneme süresi (Trial) yönetimi
- Güncelleme bütünlük doğrulaması
- İmzalı güncelleme bilgileri
- Dağıtım öncesi güvenlik kontrolleri

Yönetici lisans araçları son kullanıcı dağıtım paketinden ayrı tutulmaktadır.

---

## 🖥️ Sistem

Scoliosis Follow-Up şu anda **Windows masaüstü ortamı** için geliştirilmektedir.

Temel teknolojiler:

- Python
- PySide6 / Qt
- pydicom
- pynetdicom
- OpenCV
- NumPy
- ReportLab

---

## 📦 Kurulum

Son kararlı sürümü GitHub üzerindeki **Releases** bölümünden indirebilirsiniz.

1. En güncel `ScoliosisFollowUp_Setup.exe` dosyasını indirin.
2. Kurulum dosyasını çalıştırın.
3. Kurulum tamamlandıktan sonra Scoliosis Follow-Up'ı başlatın.

> Python veya geliştirme ortamı kurulması gerekmez.

---

## 🔄 Güncellemeler

Uygulama sürümleri GitHub Releases üzerinden yayınlanmaktadır.

Yeni sürümlerde:

- hata düzeltmeleri,
- performans geliştirmeleri,
- görüntüleme araçları,
- takip özellikleri,
- güvenlik geliştirmeleri

yayınlanabilir.

---

## ⚠️ Tıbbi Kullanım Hakkında

Scoliosis Follow-Up'ın geliştirilme amacı radyolojik görüntülerin görüntülenmesini, karşılaştırılmasını ve takip süreçlerinin organize edilmesini kolaylaştırmaktır.

Yazılımın ürettiği görüntüler, ölçümler veya diğer bilgiler **tek başına tanı ya da tedavi kararı amacıyla kullanılmamalıdır.**

Klinik değerlendirme ve tıbbi kararlar yetkili sağlık profesyonelleri tarafından verilmelidir.

---

## 🚧 Proje Durumu

Scoliosis Follow-Up aktif olarak geliştirilmektedir.

Yeni özellikler, performans iyileştirmeleri ve kullanıcı deneyimi geliştirmeleri üzerinde çalışmalar devam etmektedir.

---

## 👨‍💻 Geliştirici

**Yusufcan**

Radyoloji iş akışlarından edinilen saha deneyimi doğrultusunda geliştirilen Scoliosis Follow-Up, özellikle skolyoz görüntüleme ve takip süreçlerini daha pratik bir çalışma ortamında bir araya getirmeyi hedeflemektedir.

---

## 📄 Lisans

Bu repository'deki kaynak kodun ve uygulamanın kullanım koşulları proje lisansına tabidir.

© 2026 Scoliosis Follow-Up
