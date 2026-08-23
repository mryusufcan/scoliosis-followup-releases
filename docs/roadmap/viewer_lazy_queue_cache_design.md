# Ana viewer lazy/asenkron kuyruk ve cache tasarımı

**Durum:** Tasarım kararı; uygulama koduna tam scheduler entegrasyonu codec benchmarkından sonra yapılacaktır.

Bu tasarımın amacı, DICOM kaynağını ve tam çözünürlüklü ana viewer davranışını değiştirmeden ilk görüntüyü daha hızlı göstermek, seçim değişince eski işi güvenle geçersiz kılmak ve decode edilmiş büyük NumPy dizilerinin belleği sınırsız büyütmesini engellemektir. Seçim ekranındaki düşük çözünürlüklü preview yolu bu tasarımdan ayrıdır; ana viewer tam çözünürlüklü frame kullanmaya devam eder.

## Mevcut durum ve sınır

Mevcut `DicomPreloadController`, slot başına son isteği iptal etmeye çalışan ancak isteği doğrudan `QThreadPool.start()` ile başlatan bir FIFO akışıdır. Main viewer için ayrılmış havuzun thread sayısı 1'dir. Bu seçim, aynı anda iki büyük codec decode'unun RAM ve disk baskısı oluşturmasını önler; ancak FIFO kuyruğu görünür seçimi komşu prefetch işlerinin önüne almayı garanti etmez. Mevcut decoded-array cache anahtarı absolute path, `(mtime_ns, size)` imzası ve frame index içerir. View pixmap anahtarı ise henüz kaynak imzasını içermediği için aynı yola yeni dosya konulması durumunda stale pixmap testi eklenmelidir.

## Önerilen istek modeli

İstek GUI thread'inde oluşturulan immutable bir veri nesnesi olmalıdır. `path` normalize edilmiş absolute path, `source_signature` `(mtime_ns, size)`, `frame_index`, `priority`, `generation`, `reason` ve monoton `request_id` alanlarından oluşur. `reason` değerleri ölçüm telemetrisi için `current`, `frame-change`, `prefetch-next`, `prefetch-previous` ve `retry` gibi sabit etiketlerden seçilir. Decoder worker'a Qt widget veya QPixmap geçirilmez; worker yalnızca pydicom I/O, native codec çağrısı ve read-only contiguous NumPy array üretir.

| Alan | Önerilen anlam | Güvenlik/performance rolü |
|---|---|---|
| `path` | Normalize absolute path | Aynı dosyanın duplicate isteğini engeller |
| `source_signature` | `mtime_ns` ve `size`; mümkünse güvenli dosya değişimi tespiti | Değiştirilen dosyada eski decode/pixmap kullanılmasını engeller |
| `frame_index` | Tam çözünürlüklü frame | Multi-frame dedup ve doğru cache anahtarı |
| `priority` | `current=0`, frame-change=1, komşu=10, diğer=20 | Görünür seçimi prefetch önüne alır |
| `generation` | Seçim/frame değişiminde artan token | Stale worker sonucu scene'e uygulanmaz |
| `reason` | İsteğin nedenini açıklayan sabit etiket | Benchmark ve üretim telemetrisi |
| `request_id` | Monoton kimlik | Sinyal ve pending state eşleştirmesi |

## Scheduler davranışı

Önerilen scheduler GUI thread'inde küçük bir heap/priority queue tutar ve aynı anda yalnızca bir decoder runnable çalıştırır. Önce cache key ile hit aranır; hit varsa worker başlatılmaz. In-flight map aynı key için ikinci isteği engeller ve yüksek öncelikli current isteği mevcut düşük öncelikli isteğe bağlayarak duplicate decode üretmez. Yeni current isteği geldiğinde generation artırılır, düşük öncelikli bekleyen prefetch istekleri kuyruktan atılır ve çalışan düşük öncelikli decoder'a cancellation event verilir. Native codec cancellation'ı hemen desteklemese bile worker tamamlandığında generation ve source signature yeniden kontrol edilir.

QThreadPool'un numeric priority parametresi tek başına yeterli çözüm değildir. Tek thread'li pool'da Qt'nin dahili kuyruğu çalışsa bile queue eviction, in-flight dedup, generation ve telemetry mantığı uygulama tarafından yönetilmelidir. Bu nedenle scheduler kendi heap'ini yönetip pool'a yalnızca seçtiği bir runnable göndermelidir. Daha sonra güvenli paralellik ölçülürse iki ayrı decoder worker ancak codec ve RAM headroom kanıtlanırsa açılabilir; ilk production varsayılanı bir worker olarak kalmalıdır.

| Olay | Scheduler işlemi | Scene davranışı |
|---|---|---|
| Yeni dosya/frame seçildi | Generation artır, current isteği priority 0 ile ekle, prefetch kuyruğunu daralt | Önceki scene temizlenir; yalnızca current sonuç scene'i günceller |
| Current decode çalışırken yeni seçim geldi | Eski cancellation event set edilir, yeni current istek heap'in başına alınır | Eski sonuç gelse bile uygulanmaz |
| Current render tamamlandı | Cache'e yaz, GUI thread'de QPixmap oluştur, komşu adayları en fazla 2 adet ekle | Aktif frame gösterilir |
| W/L veya parlaklık değişti | Decode isteği yok; pixmap key değişir, source-array cache hit kullanılır | Mevcut source üzerinden görünüm yeniden üretilir |
| Dosya kaldırıldı/değişti | Path'e ait cache ve in-flight işler temizlenir; signature yeniden okunur | Eski sonuç scene'e uygulanmaz |
| Kapanış | Tüm cancellation event'leri set edilir, queue/pending temizlenir, pool beklenerek kapatılır | Kapanışta callback yeni UI state yazamaz |

## Prefetch politikası

İlk current frame gösterilmeden prefetch başlatılmamalıdır. Başarılı current render sonrasında viewer tree içindeki komşu DICOM dosyalarından en fazla bir önceki ve bir sonraki aday seçilir. Tercihen aynı study/series bağlamı korunur; komşu aday metadata üzerinden farklı study/series ise prefetch yapılmaz veya daha düşük bir priority ile tutulur. Prefetch yalnızca decoded-array cache'e yazar; QPixmap üretip GUI cache'ini doldurmaz. Böylece ana viewer ilk açılışında komşu işlerin gereksiz UI nesnesi oluşturması engellenir.

Queue invariant'ları `current + 2 neighbors` sınırını aşmamalıdır. Kullanıcı hızla dosya değiştirirse eski generation'a ait bekleyen prefetch'ler silinir. Cache'te zaten bulunan komşu için yeni istek eklenmez. Bu politika, tüm klasörü arka planda decode eden agresif preloading yerine kullanıcının gerçek gezinme yönüne yakın düşük maliyetli bir warm-up sağlar.

## Cache katmanları ve bellek bütçesi

Decoded-array cache, tam çözünürlüklü read-only contiguous NumPy frame'leri `(path, source_signature, frame_index)` anahtarıyla saklar. View pixmap cache aynı signature'a ek olarak Window/Level, brightness, frame, rotation, flip ve invert durumunu anahtara dahil eder. Bir dosyanın aynı absolute path'e kopyalanması halinde yalnızca path'e dayalı pixmap hit kabul edilmemeli; stat signature değiştiğinde eski entry lookup'ta geçersiz sayılmalı veya açıkça evict edilmelidir.

| Katman | İçerik | Başlangıç bütçesi | Oversize davranışı |
|---|---|---:|---|
| Header/metadata | Pixel Data içermeyen DICOM bilgisi | Mevcut 32 entry ve path/signature doğrulaması | En eski entry atılır |
| Dataset | En fazla bir decoded Dataset | Mevcut 32 MiB / 1 entry | Bütçeyi aşarsa cache'e alınmaz |
| Decoded frame | Read-only NumPy full frame | Mevcut 128 MiB / 2 entry | Tek frame bütçeyi aşıyorsa cache'e alınmaz |
| View pixmap | GUI thread'de üretilen görünüm | Mevcut 128 MiB / 10 entry | Tek pixmap bütçeyi aşıyorsa cache'e alınmaz |

Byte hesabı gerçek `nbytes` veya Qt `sizeInBytes()` üzerinden yapılmalı; yalnızca entry sayısına güvenilmemelidir. Decoder worker'ın private array'i cache'e girmeden önce `writeable=False` yapılmalıdır. Cache insertion, signature ve generation doğrulamasından sonra GUI thread'inde gerçekleştirilmelidir. Current frame için oversize array cache'e girmese bile görünüm tek seferlik üretilebilir; bu durumda sonraki W/L değişikliği yeniden decode eder ve kullanıcıya sessizce yanlış görüntü gösterilmez.

Tek worker ve iki büyük cache, mevcut gerçek görüntülerde ölçülen yaklaşık 16-bit frame boyutlarıyla uyumludur. Ancak `process_dicom_array()` içinde geçici float32 kopya oluştuğu için decoded-array limitini yükseltmek otomatik olarak daha hızlı değildir. RAM headroom ölçülmeden 256 MiB veya çoklu worker varsayılan yapılmamalıdır.

## Cancellation ve stale-result sözleşmesi

Cancellation bir hız optimizasyonudur, doğruluk mekanizması değildir. Her worker sonucu GUI callback'e geldiğinde üç kontrol yapılmalıdır: request generation hâlâ aktif mi, path/frame hâlâ current mı ve dosyanın mevcut `(mtime_ns, size)` signature'ı request signature ile aynı mı? Bu kontrollerden biri başarısızsa scene, annotation veya aktif viewer state güncellenmez. Dosya kaldırılmışsa sonuç cache'e de yazılmamalıdır. Kullanıcı yalnızca başka dosyaya geçtiyse ve source signature hâlâ geçerliyse stale sonuç decoded cache'e düşük maliyetli warm entry olarak kabul edilebilir; ancak bu tercih telemetriyle doğrulanmalı ve current UI'ya uygulanmamalıdır.

## Telemetri ve kabul eşikleri

Scheduler `queue_depth`, `inflight`, `cache_hits`, `cache_misses`, `evictions`, `cancelled`, `stale_results`, `decode_ms`, `render_ms`, `pixmap_ms`, `reason` ve `transfer_syntax_uid` alanlarını PHI içermeden kaydetmelidir. Dosya adı yerine hash veya yalnızca transfer syntax/ölçü bilgisi kullanılabilir. İlk kabul hedefi current selection'ın bekleyen prefetch önüne geçmesi, stale scene update sayısının sıfır olması ve cache bütçelerinin her istekten sonra korunmasıdır. Mutlak milisaniye hedefi gerçek DICOM benchmarkından sonra belirlenmelidir.

## Uygulama sırası

Önce scheduler ve cache için saf Python testleri eklenmeli, ardından mevcut `DicomPreloadController` sinyal sözleşmesi korunarak yeni controller'a bağlanmalıdır. İkinci adımda viewer tree komşu adayları ve path invalidation bağlanır. Üçüncü adımda codec-specific benchmark sonuçları olumluysa `decoding_plugin` seçimi ve startup diagnostics eklenir. Son aşamada PyInstaller onedir paketinde native DLL, hidden import ve fallback davranışı doğrulanır. Bu sıralama, codec kurulumu ile queue refactor'un aynı anda bozulmasını önler.
