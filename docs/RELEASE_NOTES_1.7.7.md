# Scoliosis Follow-Up 1.7.7

1.7.7, DICOM görüntüleme akışında **stabilite, yanıt süresi ve bellek kullanımı** odaklı bir performans sürümüdür. Kaynak DICOM dosyaları değiştirilmez; görünüm dönüşümleri ve ölçüm katmanları kaynak veriden ayrı tutulur.

## Ana viewer performansı

- Ana viewer yükleme akışı iptal edilebilir ve öncelikli lazy/asenkron queue yapısına geçirildi.
- Kullanıcının seçtiği current görüntü, düşük öncelikli komşu prefetch isteklerinin önüne alınır.
- Kuyruk derinliği sınırlandı; varsayılan olarak en fazla bir önceki ve bir sonraki görüntü prefetch edilir.
- Aynı dosya, frame ve source signature için devam eden duplicate decode istekleri yeniden kullanılabilir.
- Yeni seçim veya dosya kaldırma durumunda eski istekler cancellation event ile geçersizleştirilir.
- Request generation, path, frame, reason ve `(mtime_ns, file_size)` source signature kontrolleriyle stale worker sonuçlarının yanlış görüntü veya scene durumuna uygulanması engellendi.
- Qt `QImage` ve `QPixmap` nesneleri worker thread içinde oluşturulmaz; GUI nesneleri GUI thread callback'inde üretilir.

## Decode ve cache iyileştirmeleri

- Path-based `pydicom.pixels.pixel_array(..., index=frame)` akışıyla istenen frame'in lazy alınabileceği decode yolu eklendi.
- Tam çözünürlüklü decoded-array cache'i **2 entry / 128 MiB**, view pixmap cache'i **10 entry / 128 MiB** sınırlarıyla korunur.
- Window/Level, brightness, invert, rotation ve flip değişiklikleri mümkün olduğunda yeniden DICOM decode etmek yerine decoded cache'i kullanır.
- Cache anahtarlarına dosyanın modification time ve boyutundan oluşan source signature eklendi.
- Aynı path üzerine yeni dosya kopyalandığında eski decoded array ve pixmap entry'leri temizlenir.
- Cache benchmarkında gerçek DICOM dosyalarıyla cold decode+render ortalaması yaklaşık 996 ms, yalnızca view-state değişimi render'ı yaklaşık 45 ms ölçüldü.

## Seçim ve önizleme deneyimi

- Liste thumbnail'i ve büyük önizleme aynı preview worker sonucunu paylaşır; aynı dosya iki kez decode edilmez.
- Seçim önizlemeleri uzun kenarda **640 px** ile sınırlandırıldı.
- Native/uncompressed grayscale DICOM dosyalarında hızlı strided raw-pixel preview yolu eklendi; compressed dosyalarda güvenli pydicom decoder fallback'i korunur.
- Viewer dosya ağacına ekleme sırasında senkron full-resolution pixmap decode kaldırıldı; metadata ile ağaç oluşturulur, gerçek render arka planda yapılır.

## Sıkıştırılmış DICOM codec desteği

- Transfer Syntax'a göre preferred decoder seçimi eklendi.
- JPEG Lossless SV1 ve JPEG ailesi için `pylibjpeg`/`pylibjpeg-libjpeg` native yolu kullanılır.
- JPEG 2000 için `pylibjpeg-openjpeg`, JPEG-LS için `pyjpegls`/CharLS yolu tanınır.
- Preferred plugin başarısız olursa pydicom'un otomatik fallback yolu denenir.
- DICOM bilgi ekranında Transfer Syntax ve seçilen decoder tanısı gösterilir.
- Mevcut gerçek geliştirme setinde 16 dosyanın tamamı JPEG Lossless SV1'dir. JPEG 2000 ve JPEG-LS için hız sonucu verilmemiştir; bu formatlar için gerçek anonymized fixture gerektiği özellikle belirtilmiştir.

## Stabilite ve doğrulama

- Path temizliği, uygulama kapanışı, worker ve timer yaşam döngüsü kontrolleri güçlendirildi.
- PACS ağ işlemleri, longitudinal snapshot ve rapor bundle işlemleri GUI thread dışına taşındı.
- Gerçek DICOM codec benchmark araçları ve PHI içermeyen transfer-syntax inventory araçları eklendi.
- Priority queue, duplicate request, bounded queue, cancellation, source signature invalidation, codec seçimi ve kaynak dosya bütünlüğü için yeni testler eklendi.

## Doğrulama

- `compileall`: başarılı.
- Tam pytest: **205 passed, 5 warnings**.
- Offscreen UI smoke: `UI_THEME_SMOKE_OK`.
- Gerçek JPEG Lossless SV1 benchmarkı: `pylibjpeg` **16/16 başarılı**, array digest uyuşmazlığı **0**.
- Benchmark ve testler sırasında kaynak DICOM dosyalarında değişiklik yapılmadı.

## Bilinen sınırlamalar

Hâlihazırda çalışan native codec çağrısı ortasında thread zorla sonlandırılmaz. Bu nedenle çok büyük bir compressed frame decode edilirken yeni seçim kısa süreliğine mevcut decode'un tamamlanmasını bekleyebilir. Daha yüksek eşzamanlılık veya ayrı process tabanlı decode ancak codec türüne ve gerçek RAM ölçümlerine göre ayrıca değerlendirilmelidir.

JPEG 2000 ve JPEG-LS için gerçek compressed DICOM örnekleri bulunmadığından bu sürümde yalnızca preferred plugin seçimi ve fallback davranışı doğrulanmıştır; bu codec'ler için performans karşılaştırması yapılmamıştır.
