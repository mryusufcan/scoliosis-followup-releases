# Gerçek DICOM Piksel Decode Optimizasyon Raporu

## Sonuç

Viewer pipeline'ına **frame/source imzasıyla sınırlı decoded-array cache** ve **tek iş parçacığıyla sınırlı özel preload havuzu** eklendi. Window/Level, parlaklık, invert ve diğer görünüm değişiklikleri ham DICOM piksel verisini değiştirmeden aynı decoded array'i yeniden kullanır; yalnızca görünüm katmanı yeniden işlenir.

> En büyük kazanç, aynı görüntünün görünüm ayarları değişirken DICOM codec/decode aşamasını tekrar çalıştırmamaktır. Paralel decode ise yalnızca bağımsız birden çok görüntü hazırlanırken anlamlı olabilir; tek aktif görüntü için bellek baskısı ve thread overhead'i nedeniyle varsayılan yapılmadı.

## Uygulanan yöntemler

| Yöntem | Uygulama | Karar |
|---|---|---|
| Frame/source decoded-array cache | Anahtar: absolute path + dosya `mtime_ns` + byte boyutu + frame index. Limit: 2 entry ve 128 MiB. | **Uygulandı.** W/L/parlaklık değişimlerinde decode tekrarı önlenir. |
| Pixmap cache | Mevcut görünüm-state anahtarı korunuyor; görünüm değişince pixmap miss, decoded array hit oluyor. | **Korundu ve tamamlandı.** |
| Header-only fallback | Decoded array hit ancak Dataset cache miss olduğunda yalnızca `stop_before_pixels=True` header okunur. | **Uygulandı.** Metadata için full Pixel Data okuması yapılmaz. |
| Preload pool sınırı | Viewer preload için global havuz yerine `QThreadPool` ve `maxThreadCount=1`. | **Uygulandı.** Aynı anda birden fazla büyük decode ile bellek taşması riski azaltılır. |
| Stale/cache invalidation | Dosya kaldırıldığında decoded array cache path bazında temizleniyor; kapanışta preload kuyruğu boşaltılıyor. | **Uygulandı.** |
| ThreadPoolExecutor | Gerçek DICOM benchmarkında 2 veya 4 thread anlamlı hız kazancı göstermedi. | **Viewer default olarak uygulanmadı.** |
| ProcessPoolExecutor | Bağımsız decode işlerinde 4 worker yaklaşık 2,24× hızlandı; process başlatma ve bellek maliyeti var. | **Toplu offline/preload için aday; tek viewer decode için uygulanmadı.** |

## Gerçek DICOM benchmarkı

Benchmarklar `dev_data/dicom_samples` altındaki gerçek DICOM dosyalarıyla çalıştırıldı; sentetik piksel verisi kullanılmadı.

### Cache yeniden kullanım ölçümü

Komut:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_decode_cache.py `
  --limit 4 `
  --view-changes 3 `
  --output docs\roadmap\decode_cache_benchmark_latest.json
```

| Metrik | Sonuç |
|---|---:|
| Gerçek DICOM dosyası | 4 |
| Cold decode + render ortalaması | 983,569 ms |
| Yalnızca görünüm değişimi render ortalaması | 40,769 ms |
| Ölçülen decoded-array yeniden kullanım farkı | **24,125×** |
| Cache sonrası dosya başına decoded entry | 1 |

Ölçüm protokolünde cold koşulda dataset/header/pixmap/decoded cache temizlendi. Görünüm değişimi koşulunda yalnızca pixmap ve dataset cache temizlendi, parlaklık değiştirildi ve decoded array korundu.

### Serial/thread/process karşılaştırması

Komut:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_decode_strategies.py `
  --limit 4 `
  --repeats 2 `
  --workers 1,2,4 `
  --output docs\roadmap\decode_strategy_benchmark_latest.json
```

| Strateji | Ortalama süre | Serial'e göre |
|---|---:|---:|
| Serial | 4.117,5 ms | 1,00× |
| Thread, 2 worker | 4.049,1 ms | 1,017× |
| Thread, 4 worker | 4.131,6 ms | 0,997× |
| Process, 2 worker | 2.680,2 ms | 1,536× |
| Process, 4 worker | 1.835,5 ms | **2,243×** |

Bu sonuçlar 4 bağımsız gerçek DICOM dosyasının batch decode senaryosuna aittir. Process sonuçları yalnızca scalar boyut bilgisi döndürerek IPC ile büyük NumPy array taşınmasını ölçüme dahil etmez; gerçek uygulama entegrasyonunda worker-to-GUI veri aktarımı ve toplam resident memory ayrıca ölçülmelidir.

## Neden process pool viewer default olmadı?

Tek görüntü açma akışında process havuzu başlatma maliyeti, ayrı process bellek kullanımı ve Qt GUI'ye güvenli veri aktarımı kazanımı azaltabilir. Ayrıca aynı anda dört büyük full-spine array'i üretmek RAM kullanımını artırabilir. Bu nedenle interaktif viewer için en güvenli sıra **decoded-array cache → tek bounded preload worker → stale request iptali** olarak seçildi. Process pool, kullanıcı birden çok bağımsız görüntüyü toplu önizlemek veya offline export hazırlamak istediğinde ayrı bir batch servisi olarak değerlendirilebilir.

## Kod ve test kapsamı

| Dosya | Değişiklik |
|---|---|
| `main.py` | Frame/source imzalı decoded array cache, preload pool sınırı ve preload cache kaydı |
| `modular_app/ui/viewer_core.py` | Decoded array cache path temizliği |
| `modular_app/core/app_session.py` | Preload pool kapanış temizliği ve fallback cache temizliği |
| `tools/benchmark_decode_cache.py` | Gerçek viewer cold/view-change benchmarkı |
| `tools/benchmark_decode_strategies.py` | Serial/thread/process gerçek DICOM benchmarkı |
| `tests/test_performance_budgets.py` | Cache hit, byte/entry limit ve bounded preload regresyonları |

Son doğrulama: **195 test geçti**, 5 uyarı. `compileall` başarılıdır; Qt offscreen smoke testi `UI_THEME_SMOKE_OK` ile tamamlanmıştır. Font diziniyle ilgili Qt uyarısı smoke sonucunu başarısız kılmamıştır.

## Güvenlik ve klinik veri sınırları

Decoded array cache ham DICOM dosyasına yazmaz ve görüntü state'ini DICOM metadata'sından ayrı tutar. Cache anahtarı dosya değişimini `mtime_ns` ve boyut ile kontrol eder; dosya kaldırma yolunda path bazlı temizleme yapılır. PixelSpacing, Window/Level, PhotometricInterpretation ve diğer render metadata akışı korunur. Cache veya otomatik decode sonucu klinik ölçüm ya da tanı yerine geçmez; Cobb ölçümü ve export akışları mevcut manuel doğrulama sınırlarıyla çalışır.

## Geri dönüş noktası

Değişiklik öncesi kopyalar:

`C:\Users\yusuf\Desktop\Scoliosis Follow Up\.restore_points\decode_optimization_20260822_225909`

## Sonraki adımlar

Daha ileri hızlandırma için önce 10–20 adet gerçek full-spine DICOM içeren farklı boyut sınıflarıyla cold-cache/warm-cache benchmarkı tekrarlanmalıdır. Daha sonra yalnızca gerçek workload gerekçesi oluşursa batch process pool, memory pressure ölçümü ve codec bazlı ayrı profilleme değerlendirilebilir. Hasta verisi içeren üretim veritabanı veya PACS endpoint'i paylaşılmadan sentetik ölçek sonucu raporlanmamalıdır.
