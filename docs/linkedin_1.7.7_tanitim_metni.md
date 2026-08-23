# LinkedIn Tanıtım Metni — Scoliosis Follow-Up 1.7.7

## Ana paylaşım

Uzun süredir üzerinde çalıştığım **Scoliosis Follow-Up** projesinin 1.7.7 sürümünü yayımladım.

Bu proje; skolyoz radyografilerinin DICOM formatında görüntülenmesi, Cobb açısı ve mesafe ölçümleri, farklı tarihlerdeki tetkiklerin yan yana/Overlay/Blink karşılaştırması, longitudinal takip ve uzun grafilerin birleştirilmesi için geliştirdiğim Windows masaüstü uygulamasıdır.

Bu sürümde özellikle görüntüleme akışını daha hızlı ve kararlı hâle getirmeye odaklandım:

• Ana viewer için iptal edilebilir ve öncelikli lazy/asenkron decode kuyruğu.
• Kullanıcının seçtiği görüntüyü komşu prefetch işlemlerinin önüne alan bounded queue yapısı.
• Duplicate in-flight istekleri engelleyen generation ve source-signature kontrolleri.
• Byte bütçeli decoded-array ve pixmap cache katmanları.
• Aynı path üzerine yeni dosya geldiğinde stale cache entry’lerinin otomatik temizlenmesi.
• Seçim ekranında ortak preview worker ve uzun kenarı 640 px ile sınırlandırılmış düşük çözünürlüklü önizlemeler.
• Path-based tek-frame lazy decode akışı.
• JPEG Lossless, JPEG 2000 ve JPEG-LS için transfer syntax bazlı native decoder seçimi ve güvenli fallback mekanizması.

Performans çalışmalarını sentetik büyük veri üretmek yerine gerçek DICOM test dosyalarıyla doğruladım. Mevcut 16 dosyalık test setinde JPEG Lossless SV1 decode için `pylibjpeg` başarı oranı 16/16, çıktı digest uyuşmazlığı ise 0 oldu. Cache benchmarkında cold decode+render ortalaması yaklaşık 996 ms iken, yalnızca görünüm değişimi render’ı yaklaşık 45 ms seviyesine indi.

Bu çalışmanın önemli bir sınırı da şu: Uygulama klinik tanı veya tedavi kararının yerine geçmez. Görüntüleme, ölçüm ve otomatik hizalama sonuçları uzman değerlendirmesini destekleyen teknik araçlar olarak ele alınmalıdır. Kaynak DICOM dosyaları değiştirilmez; ölçüm ve görünüm katmanları kaynak veriden ayrı tutulur.

1.7.7 sürümünü, release notes dosyasını ve teknik ayrıntıları aşağıdaki bağlantılarda paylaşıyorum:

GitHub Release: https://github.com/mryusufcan/scoliosis-followup-releases/releases/tag/1.7.7
Proje sayfası: https://mryusufcan.github.io/scoliosis-followup-releases/

Bu süreçte özellikle **PySide6, pydicom, NumPy, Qt thread yaşam döngüsü, cache invalidation ve DICOM pixel decode performansı** üzerine önemli pratik deneyim kazandım. Benzer tıbbi görüntüleme, masaüstü uygulama performansı veya DICOM iş akışları üzerine çalışanların görüşlerini duymaktan memnuniyet duyarım.

#Python #PySide6 #DICOM #pydicom #MedicalImaging #Radiology #ComputerVision #SoftwareEngineering #PerformanceEngineering #DesktopApplications

## Daha kısa paylaşım alternatifi

**Scoliosis Follow-Up 1.7.7 yayımlandı.**

Skolyoz radyografilerinin DICOM görüntüleme, Cobb ölçümü, seri karşılaştırma, longitudinal takip ve görüntü birleştirme süreçlerini tek Windows masaüstü uygulamasında bir araya getiren proje üzerinde çalışmaya devam ediyorum.

Bu sürümde ana viewer için iptal edilebilir priority lazy queue, komşu prefetch, in-flight request deduplication, source-signature tabanlı cache invalidation ve byte bütçeli decoded/pixmap cache geliştirdim. Seçim ekranında da 640 px bounded preview ve ortak preview worker ile ilk görüntüleme deneyimini hızlandırdım.

Gerçek DICOM testlerinde JPEG Lossless SV1 için `pylibjpeg` decode başarı oranı 16/16 oldu. Cache reuse benchmarkında görünüm değişiklikleri yaklaşık 45 ms seviyesine indi.

Proje klinik tanı veya tedavi kararının yerine geçmez; görüntüleme ve ölçüm sonuçları uzman değerlendirmesini destekleyen teknik araçlardır.

GitHub Release: https://github.com/mryusufcan/scoliosis-followup-releases/releases/tag/1.7.7

#Python #PySide6 #DICOM #MedicalImaging #Radiology #SoftwareEngineering

## Paylaşım görseli için öneri

İlk görselde uygulamanın viewer ekranını ve üzerinde “Scoliosis Follow-Up 1.7.7” başlığını kullanın. İkinci görselde eski/yeni akışı temsil eden kısa bir şema yer alabilir: “Senkron full decode → Priority lazy queue → Current + komşu prefetch”. Üçüncü görselde ise benchmark özeti gösterilebilir: “Cold render ≈ 996 ms”, “View-state render ≈ 45 ms”, “Cache reuse ≈ 21.9×”. Görsellerde gerçek hasta adı, PatientID veya DICOM metadata bulunmamalıdır.

## İlk yorum için öneri

Teknik ayrıntıları, benchmark JSON çıktılarını ve release notes dosyasını GitHub repository’sinde paylaştım. Özellikle DICOM compressed pixel decode, PySide6 worker yaşam döngüsü veya Windows/PyInstaller native codec paketleme deneyimi olanların önerilerini bekliyorum.
