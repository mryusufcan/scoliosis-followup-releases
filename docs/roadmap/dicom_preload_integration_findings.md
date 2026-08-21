# DICOM Preload Worker Gerçek Viewer Entegrasyon Bulguları

## Uygulanan kapsam

İlk DICOM decode/preload worker gerçek projeye `modular_app/ui/dicom_preload_worker.py` olarak eklendi. `viewer_core.render_viewer_file()` DICOM cache miss durumunda GUI’yi bloklamadan preload request başlatıyor; `main.py` içindeki GUI callback’i NumPy array’i mevcut Window/Level, brightness, invert, rotation ve flip state’i ile display array’e çevirip QImage/QPixmap üretiyor. Scene ve pixmap cache güncellemesi yalnızca GUI callback’inde yapılıyor.

Mevcut senkron `get_viewer_file_pixmap()` yolu kaldırılmadı. Worker hatası olduğunda `allow_preload=False` ile kontrollü senkron fallback çalışıyor; böylece preload hatası sonsuz request döngüsüne dönüşmüyor.

## Kabul sonuçları

| Kontrol | Sonuç |
|---|---|
| Python derleme | `main.py`, `viewer_core.py`, worker, bridge, testler ve benchmark başarılı |
| Yeni worker/acceptance/integration testleri | **15/15 başarılı** |
| UI tema smoke | **UI_THEME_SMOKE_OK** |
| Standart modüler regresyon | **94/94 başarılı** |
| Gerçek DICOM async scene | 2393 × 3056 görüntü async preload sonrası scene’de görünür |
| İkinci açılış | Pixmap cache kullanılıyor; yeni preload request oluşmuyor |
| Preload hata yolu | Fallback recursion olmadan tamamlanıyor |
| Kaynak değişmezliği | DICOM dosya SHA-256 değeri decode öncesi/sonrası aynı |
| Bellek koruması | `DecodeLimits` kaynak/kare tahmini sınırları aşınca pixel decode başlamadan reddediyor |

## Görsel smoke notu

`dicom_preload_windows_viewer.png` gerçek Windows Python 3.13 offscreen oturumunda async preload sonrası alınmıştır. DICOM görüntüsü tam boyutuyla render edilmiştir. Offscreen Qt ortamı PySide6 font klasörünü bulamadığı için başlık ve toolbar metinleri kutucuk olarak görünmektedir; bu, gerçek Windows font kurulumu problemi değil, offscreen font dağıtım uyarısıdır. Önceki gerçek Windows UI doğrulamasında Segoe UI ve Türkçe karakterler normal görünmüştür.

## Benchmark özeti

Windows sentetik worker benchmarkında 2393 × 3056 uint16 yük için ortalama decode 9,539 ms, QImage dönüşümü 58,382 ms, worker round-trip 12,993 ms ve cache lookup 0,09 µs ölçülmüştür. Bu sentetik NumPy ölçümüdür; JPEG/JPEG 2000/RLE gibi gerçek transfer syntax codec sürelerinin yerine geçmez.

## Geri dönüş noktası

Entegrasyon öncesi yedek: `.restore_points\\dicom_preload_real_integration_20260819_010500\\`. Yeni geçici capture betiği release öncesi temizlenmelidir.
