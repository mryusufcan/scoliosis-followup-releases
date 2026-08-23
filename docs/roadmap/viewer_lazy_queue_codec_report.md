# Ana Viewer Lazy Queue, Cache ve Native Codec Raporu

**Proje:** Scoliosis Follow Up

**Kapsam:** Tam çözünürlüklü ana DICOM viewer için iptal edilebilir öncelikli lazy/asenkron decode kuyruğu, bellek bütçeli cache yaşam döngüsü ve JPEG ailesi native decoder seçimi.

**Sonuç:** Uygulama, kaynak DICOM'u değiştirmeden priority scheduler, signature/generation doğrulaması, komşu prefetch ve transfer-syntax bazlı decoder seçimi ile güncellendi. Gerçek geliştirme veri seti JPEG 2000 veya JPEG-LS değil, JPEG Lossless SV1 içerdiği için bu iki codec için hız iddiası yapılmadı; yalnızca kurulabilir ve fallback'li entegrasyon yolu hazırlandı.

## 1. Gerçek veri ve ortam bulgusu

`dev_data/dicom_samples` altında **16 gerçek DICOM dosyası** incelendi. Dosyaların tamamı `1.2.840.10008.1.2.4.70` UID'li JPEG Lossless, Non-Hierarchical, First-Order Prediction (Process 14 [Selection Value 1]) aktarım sözdizimini kullanıyor. Dosyaların tamamı compressed, tek frameli ve 12 Bits Stored değerine sahip. Bu fixture setinde JPEG 2000 (`1.2.840.10008.1.2.4.90/.91`) veya JPEG-LS (`1.2.840.10008.1.2.4.80/.81`) örneği bulunmuyor.

| Ölçüm | Sonuç |
|---|---:|
| Gerçek DICOM dosyası | 16 |
| Compressed dosya | 16 |
| Multi-frame dosya | 0 |
| JPEG Lossless SV1 | 16 |
| JPEG 2000 | 0 |
| JPEG-LS | 0 |
| Bits Stored | 12 |
| Pydicom | 3.0.2 |
| Aktif pylibjpeg | 2.1.0 |
| pylibjpeg-libjpeg | 2.4.0 |
| pylibjpeg-openjpeg | 2.5.0 |
| pylibjpeg-rle | 2.2.0 |
| pyjpegls | 1.5.1 |
| python-gdcm | Kurulu değil |

Pydicom'un güncel dokümantasyonu compressed Pixel Data için pylibjpeg eklentilerini, pyjpegls, GDCM ve Pillow seçeneklerini listeliyor; aynı doküman Pillow'un decoded görüntü üzerinde her zaman geri döndürülemeyebilecek işlemler yapabildiği konusunda uyarıyor [1]. Bu nedenle klinik Pixel Data yolunda Pillow birincil backend yapılmadı.

## 2. Uygulanan queue mimarisi

`modular_app/ui/dicom_preload_worker.py` içindeki eski slot-başına doğrudan FIFO başlatma akışı, GUI thread'inde yönetilen küçük bir priority heap ile değiştirildi. Controller aynı anda yalnızca **bir native decode** çalıştırıyor. Büyük 16-bit radyografi frame'lerinde bu varsayılan, birden fazla codec çağrısının RAM ve disk baskısını artırmaması için korunuyor.

Her `PreloadRequest` artık normalize edilmiş absolute path, frame index, priority, generation, reason ve `(mtime_ns, size)` source signature taşıyor. `current` ve `frame-change` gibi görünür istekler düşük numeric priority ile, `prefetch-neighbor` istekleri daha düşük öncelikle kuyruğa giriyor. Yeni görünür istek geldiğinde eski slot isteği iptal ediliyor ve bekleyen düşük öncelikli işler evict ediliyor. Kuyruk derinliği controller seviyesinde `max_queue=3` ile sınırlandırıldı; viewer komşu prefetch politikası en fazla **bir önceki + bir sonraki** dosyayı ekliyor.

| Olay | Uygulanan davranış |
|---|---|
| Yeni dosya/frame seçimi | Generation artırılır, current request priority 0 ile kuyruğa girer |
| Komşu prefetch | Current render tamamlandıktan sonra en fazla 2 request, priority 10 |
| Aynı slotta aynı frame/signature | In-flight request identity tekrar kullanılır; duplicate decode başlatılmaz |
| Current request gelmesi | Düşük öncelikli bekleyen/çalışan prefetch cancellation event alır |
| Native decoder dönüşü | Path, frame ve current source signature yeniden doğrulanır |
| Dosya kaldırma | `cancel_path()` ile current ve prefetch istekleri iptal edilir |
| Uygulama kapanışı | Event'ler set edilir, queue/pending temizlenir ve pool kapanış akışına bırakılır |

Cancellation event native codec çağrısının ortasında zorla kesme yapmaz; decoder dönüşten önce/sonra kontrol edilir. Bu nedenle kullanıcı yeni görüntü seçtiğinde hâlihazırda çalışan tek bir JPEG decode'unun bitmesi beklenebilir. Bu, thread'i zorla sonlandırıp yarım array veya Qt nesnesi üretmekten daha güvenli bir davranıştır.

## 3. Cache yaşam döngüsü ve stale-result koruması

Ana viewer'ın tam çözünürlüklü davranışı korunuyor. Decoded-array cache read-only contiguous NumPy frame'i `(absolute_path, (mtime_ns, size), frame_index)` anahtarıyla tutuyor. View pixmap cache anahtarına da aynı source signature eklendi; böylece aynı path üzerine yeni dosya konduğunda eski pixmap yeni görüntüye aitmiş gibi kullanılmıyor. Signature değiştiği fark edildiğinde o path'in eski decoded-array ve pixmap entry'leri evict ediliyor.

Worker sonucu GUI callback'e ulaştığında üç kontrol yapılıyor: request'in path/frame'i hâlâ current mı, request source signature diskteki güncel signature ile aynı mı ve request'in reason'ı current mı yoksa prefetch mi? Current olmayan geçerli prefetch sonucu yalnızca decoded-array cache'i ısıtabilir; scene, annotation, zoom veya ölçüm state'ini değiştiremez. Signature uyuşmazlığı olduğunda current request aynı path için yeni signature ile yeniden kuyruğa alınır.

| Cache | Mevcut sınır | Yeni güvenlik davranışı |
|---|---:|---|
| Header cache | 32 entry | Pixel Data'sız metadata yolu korunuyor |
| Dataset cache | 1 entry / 32 MiB | Büyük Dataset sınıra sığmazsa tutulmuyor |
| Decoded array | 2 entry / 128 MiB | `nbytes` ile byte bütçesi; oversize entry cache'e alınmıyor |
| View pixmap | 10 entry / 128 MiB | `sizeInBytes()`/byte budget; signature view key'e dahil |

`process_dicom_array()` içindeki görünüm işlemleri source array'i değiştirmiyor; Window/Level, brightness, invert, rotation ve flip ayrı görünüm katmanında kalıyor. Qt `QImage`/`QPixmap` nesneleri worker içinde oluşturulmuyor. Path-based `pydicom.pixels.pixel_array(..., index=frame)` çağrısı ile özellikle ileride multi-frame dosyalarda yalnızca istenen frame'in lazy alınabilmesi hedefleniyor; mevcut 16 dosyalık fixture tek frame olduğu için bunun multi-frame kazancı ayrıca ölçülmedi.

## 4. Native codec kararı

`modular_app/ui/dicom_codec.py` transfer syntax'a göre mantıksal pydicom plugin seçiyor ve başarısız olursa pydicom'un otomatik plugin fallback yolunu deniyor. Pydicom plugin tablosu JPEG Lossless P14/SV1 için `pylibjpeg-libjpeg`, JPEG 2000 için `pylibjpeg-openjpeg`, JPEG-LS için `pyjpegls` ve RLE için `pylibjpeg-rle` eşleşmelerini gösteriyor [2].

| Transfer syntax | Önerilen birincil yol | Fallback | Bu projedeki durum |
|---|---|---|---|
| JPEG Lossless SV1 | `pylibjpeg` plugin + `pylibjpeg-libjpeg` native backend | Pydicom otomatik yolu; gerekirse GDCM | Gerçek veriyle aktif ve başarılı |
| JPEG 2000 Lossless/Lossy | `pylibjpeg` plugin + `pylibjpeg-openjpeg` | Pillow veya GDCM, yalnızca kabul testi sonrası | Paket kurulu; gerçek fixture yok |
| JPEG-LS Lossless/Near-lossless | `pyjpegls` plugin; CharLS C++ backend | `pylibjpeg` veya GDCM | Paket kurulu; gerçek fixture yok |
| Geniş transfer syntax fallback'i | `python-gdcm` | Pydicom otomatik yol | Kurulu değil; opsiyonel bırakıldı |

`pylibjpeg-openjpeg` repository'si J2K, JP2 ve HTJ2K için pylibjpeg plugini olduğunu ve Linux, macOS, Windows desteğini belirtiyor [3]. `pylibjpeg-libjpeg` repository'si JPEG Baseline, Extended, Lossless P14, Lossless SV1 ve JPEG-LS UID'lerini desteklediğini ve Windows'u listeliyor [4]. `pyjpegls` ise JPEG-LS için CharLS C++ Library üzerinden Python arayüzü sunuyor; repository geçmişinde CharLS v2.4.2 güncellemesi bulunuyor [5].

Bu nedenle `imagecodecs`, SimpleITK/ITK veya OpenCV, pydicom'un mevcut transfer-syntax plugin yolunun yerine eklenmedi. Böyle bir backend ancak gerçek kurum verisinde aynı `shape`, `dtype`, signedness, min/max, istatistik ve tam array digest değerlerini doğrulayan bir kabul testi ile ayrıca değerlendirilmelidir. Mevcut uygulamanın `requirements.txt` dosyası zaten `pylibjpeg`, `pylibjpeg-libjpeg`, `pylibjpeg-openjpeg`, `pylibjpeg-rle` ve `pyjpegls` paketlerini içeriyor. Windows `onedir` build script'i ve spec dosyası da ilgili native paket varlıklarını toplamak üzere mevcut `collect-all` adımlarını içeriyor; bu iterasyonda requirements veya packaging dosyasında gereksiz değişiklik yapılmadı.

## 5. Gerçek codec benchmarkı

`tools/benchmark_dicom_codecs.py` ile gerçek dosyalarda her plugin için decoded array'in `shape`, `dtype`, SHA-256 digest, min/max/mean ve süre değerleri karşılaştırıldı. DICOM dosyaları benchmark boyunca değiştirilmedi.

Dört gerçek dosyada iki timed repeat kullanıldığında `pylibjpeg` 4/4 başarılı oldu ve digest uyuşmazlığı görülmedi. Dosya başına median sürelerin ortalaması yaklaşık **1,096.5 ms** oldu. Pydicom `default` yolu 4/4 başarılı, digest uyuşmazlığı 0 ve ortalama median yaklaşık **1,118.4 ms** oldu. Bu küçük ölçümde açık `pylibjpeg` seçimi yaklaşık **1.02×** düzeyinde sınırlı bir fark gösterdi; bu sonuç native codec'in zaten etkin olduğunu, yeni bir backend eklenmesinin mevcut JPEG Lossless SV1 verisinde otomatik büyük hız kazancı sağlamayacağını gösteriyor.

On altı dosyanın tamamında tek timed repeat ile `pylibjpeg` 16/16 başarılı, mismatch 0; dosya medianlarının ortalaması **1,409.8 ms**, tüm dosyaların medianı **1,209.6 ms** oldu. `default` yolu da 16/16 başarılı, mismatch 0; ortalama median **1,397.1 ms**, tüm dosyaların medianı **1,174.7 ms** oldu. Tek tekrar ve sistem yükü nedeniyle bu all-file sonuç yalnızca kapsam doğrulaması olarak değerlendirilmelidir.

| Benchmark | Sonuç |
|---|---:|
| Gerçek JPEG Lossless örnek sayısı | 16 |
| `pylibjpeg` başarı | 16/16 |
| `pylibjpeg` digest mismatch | 0 |
| `default` başarı | 16/16 |
| `default` digest mismatch | 0 |
| Pillow, JPEG Lossless SV1 için plugin sonucu | 0/16; decoder plugini yok |
| pyjpegls, JPEG Lossless SV1 için plugin sonucu | 0/16; bu UID için uygun plugin değil |
| GDCM | 0/16; `python-gdcm` eksik |

Ana viewer cache benchmarkı, yeni path-based worker decode ve queue değişikliklerinden sonra dört gerçek dosyada cold decode+render ortalamasını **996.2 ms**, yalnızca view-state değişimindeki decoded-cache render ortalamasını **45.4 ms** ve cache reuse oranını yaklaşık **21.94×** ölçtü. Bu, Window/Level/parlaklık değişiminin full DICOM decode'u tekrar etmediği garantisini koruyor. JPEG 2000/JPEG-LS hızlarını ölçmek için anonymized gerçek compressed fixture gerektiğinden bu codec'ler için simülasyon yapılmadı.

## 6. Doğrulama

| Kontrol | Sonuç |
|---|---:|
| `compileall` (`main.py`, `modular_app`, `tools`, `tests`) | Başarılı |
| Tam pytest | **205 passed, 5 warnings** |
| Yeni codec/preload/viewer focused testleri | **37 passed**; son eklemelerle codec/preload alt kümesi 19 ve viewer/preload alt kümesi 16 passed |
| Offscreen UI theme smoke | `UI_THEME_SMOKE_OK` |
| DICOM dosya bütünlüğü | Codec acceptance testlerinde kaynak byte içeriği değişmedi |
| Qt worker güvenliği | QImage/QPixmap worker içinde oluşturulmuyor |
| Qt uyarısı | Font directory uyarısı görüldü; smoke/test başarısızlığı değil |

Yeni test kapsamı priority current'ın queued prefetch önüne alınmasını, duplicate in-flight identity reuse'u, max queue derinliğini, source signature/generation/reason alanlarını, cancellation sonrası yalnızca en yeni sonucun yayınlanmasını, gerçek fixture decoder seçimini ve gerçek dosya değişiminde stale pixmap eviction davranışını kapsıyor.

## 7. Restore point ve değişen dosyalar

Değişiklik öncesi ana restore point:

`C:\Users\yusuf\Desktop\Scoliosis Follow Up\.restore_points\viewer_priority_queue_design_20260822_235554`

Bu klasörde `main.py` ve `modular_app\ui\dicom_preload_worker.py` kopyaları bulunuyor. Ayrıca önceki worker-only yedekleme klasörü `C:\Users\yusuf\Desktop\Scoliosis Follow Up\.restore_points\viewer_priority_queue_20260822_235409` olarak oluşturuldu.

| Dosya | Değişiklik |
|---|---|
| `modular_app/ui/dicom_preload_worker.py` | Priority heap, generation/signature request metadata, cancellation, bounded queue, path-based single-frame decode ve telemetry counters |
| `modular_app/ui/dicom_codec.py` | Transfer syntax bazlı preferred plugin ve otomatik pydicom fallback |
| `main.py` | Signature-aware pixmap cache, stale eviction, current/prefetch ayrımı, iki komşu prefetch ve source replacement retry |
| `modular_app/ui/viewer_core.py` | Path temizliğinde tüm in-flight queue işlerini iptal etme ve decoder diagnostics gösterimi |
| `tests/test_dicom_preload_worker.py` | Priority, dedup, bounded queue ve cancellation regresyonları |
| `tests/test_dicom_codec.py` | Gerçek fixture decoder ve JPEG 2000/JPEG-LS preferred route testleri |
| `tests/test_real_dicom_viewer_state.py` | Pixmap signature/stale eviction testi |
| `tools/inspect_dicom_codecs.py` | PHI içermeyen transfer syntax envanteri |
| `tools/inspect_dicom_handlers.py` | Kurulu decoder/plugin durumu |
| `tools/benchmark_dicom_codecs.py` | Gerçek codec çıktısı ve süre karşılaştırması |
| `docs/roadmap/dicom_codec_inventory_latest.json` | 16 dosyalık transfer syntax özeti |
| `docs/roadmap/dicom_codec_benchmark_latest.json` | Dört gerçek dosya, çoklu repeat codec benchmarkı |
| `docs/roadmap/dicom_codec_benchmark_all_latest.json` | On altı dosya kapsam benchmarkı |
| `docs/roadmap/viewer_lazy_queue_cache_design.md` | Ayrıntılı mimari tasarım |

## 8. Sınırlamalar ve sonraki güvenli adım

Mevcut gerçek veri JPEG Lossless SV1 olduğu için JPEG 2000 ve JPEG-LS için hız karşılaştırması yoktur. Bu codec'lerde karar vermek için kullanıcıdan hasta kimlikleri temizlenmiş, gerçek transfer syntax'ı korunan en az birkaç JPEG 2000 Lossless ve JPEG-LS Lossless örneği gerekir. Aynı dosyalarda `pylibjpeg-openjpeg`, `pyjpegls`, `python-gdcm` ve pydicom fallback yolları yalnızca eşdeğer array digest ve metadata kontratı ile birlikte benchmark edilmelidir.

Native codec çağrısının ortasında zorla thread termination yapılmıyor. Çok yavaş bir tek decode yeni current seçiminden sonra tamamlanana kadar UI worker kuyruğu bekleyebilir; bunun çözümü zorla öldürme değil, codec-specific ölçümden sonra ayrı decoder process veya daha güvenli adaptive concurrency değerlendirmesidir. Daha önceki gerçek benchmarkta thread pool 2/4 anlamlı kazanç göstermediği için GUI varsayılanı hâlâ tek worker'dır.

Önerilen sonraki adım, anonymized JPEG 2000/JPEG-LS fixture geldiğinde mevcut benchmark scriptine bu dosyaları eklemek ve `python-gdcm`'yi yalnızca ayrı bir Windows build ortamında, native DLL paketleme ve output eşdeğerliği kabul testleriyle denemektir. Mevcut requirements/spec zaten gerekli pylibjpeg ailesini taşıdığı için yeni bir codec paketi eklemeden önce gerçek ölçüm beklenmelidir.

## References

[1]: https://pydicom.github.io/pydicom/stable/guides/user/image_data_handlers.html "Handling of compressed pixel data — pydicom 3.0.2 documentation"

[2]: https://pydicom.github.io/pydicom/stable/guides/plugin_table.html "Plugins for Pixel Data Compression and Decompression — pydicom 3.0.2 documentation"

[3]: https://github.com/pydicom/pylibjpeg-openjpeg "pydicom/pylibjpeg-openjpeg — J2K, JP2 and HTJ2K plugin for pylibjpeg"

[4]: https://github.com/pydicom/pylibjpeg-libjpeg "pydicom/pylibjpeg-libjpeg — JPEG, JPEG-LS and JPEG XT plugin for pylibjpeg"

[5]: https://github.com/pydicom/pyjpegls "pydicom/pyjpegls — JPEG-LS for Python via CharLS C++ Library"

[6]: https://pydicom.github.io/pydicom/stable/tutorials/installation.html "How to install pydicom — GDCM and python-gdcm"
