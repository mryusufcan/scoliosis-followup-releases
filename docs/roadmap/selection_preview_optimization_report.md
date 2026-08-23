# DICOM Seçim Ekranı Önizleme Optimizasyonu

## Sorun

Seçim ekranında aynı DICOM dosyası için liste thumbnail'ı ve sağ paneldeki büyük önizleme ayrı worker'larda hazırlanıyordu. Bu nedenle aynı dosyanın Pixel Data'sı iki ayrı akışta decode edilebiliyor, ayrıca önizleme matrisi önce full çözünürlükte oluşturulup sonradan küçültülüyordu.

## Uygulanan düzenleme

| Alan | Yeni davranış |
|---|---|
| Preview çözünürlüğü | Seçim ekranı preview'ı uzun kenarda en fazla **640 px** olacak şekilde hazırlanıyor. |
| Worker paylaşımı | Aynı path için liste thumbnail'ı ve büyük preview tek bounded worker sonucunu paylaşıyor. |
| Duplicate prevention | `_preview_pending` set'i aynı dosya için ikinci preview worker'ının başlatılmasını engelliyor. |
| Liste thumbnail'ı | Sağ preview görüntüsü 68 px'e küçültülerek listede kullanılıyor; ikinci DICOM decode yapılmıyor. |
| Cache | Tamamlanan bounded preview ve metadata bilgisi sınırlı global cache'te tutuluyor. |
| Sıkıştırılmamış DICOM | Gri tonlu native Pixel Data'da yalnızca gerekli örnekleme aralığı alınarak full preview array oluşturulmadan 640 px örnek üretilebiliyor. |
| Sıkıştırılmış DICOM | Codec doğruluğu için pydicom'un standart tam decode yolu korunuyor; küçültme decode sonrasında yapılıyor. |
| Ana viewer | Seçim ekranı preview'ı düşük çözünürlüklüdür; ana viewer'ın full çözünürlüklü decode/cache akışı değiştirilmemiştir. |
| Kapanış | Dialog kapanırken bekleyen preview yolları geçersizleştirilir; geç callback görüntüyü kapalı pencereye yazmaz. |

> Önemli sınır: Sıkıştırılmış DICOM formatlarında dekoder çoğu zaman full frame'i çözmeden düşük çözünürlüklü sonuç üretemez. Bu nedenle 640 px sınırı bellek, QImage oluşturma ve GUI aktarım maliyetini azaltır; codec'in full frame decode süresi tamamen ortadan kalkmayabilir.

## Ölçüm

Gerçek `dev_data/dicom_samples` DICOM dosyalarıyla:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_selection_preview.py `
  --limit 4 `
  --output docs\roadmap\selection_preview_benchmark_raw.json
```

Dört gerçek DICOM dosyasının tamamında preview boyutu 640 px sınırının altında kaldı:

| Dosya | Preview boyutu | Ölçülen süre |
|---|---:|---:|
| IM00002 | 612 × 479 px | 2.893 s |
| IM00003 | 612 × 479 px | 2.082 s |
| IM00004 | 612 × 479 px | 2.981 s |
| IM00005 | 306 × 617 px | 1.721 s |
| Ortalama | — | 2.419 s |

Bu ölçüm full codec decode süresinin hâlâ baskın olabildiğini gösteriyor. Kullanıcı deneyimindeki esas iyileştirme, seçim listesinin hızlı görünmesi, duplicate preview decode'un engellenmesi ve sağ panelin full çözünürlükte QImage/QPixmap üretmemesidir. Sıkıştırılmış dosyalarda daha büyük hızlanma için codec/thumbnail altyapısı ayrıca değerlendirilmelidir.

## Ana viewer yükleme davranışı

Seçilen dosyalar ana viewer ağacına eklenirken artık her dosya için senkron full Pixel Data decode edilmez. Metadata header cache'ten alınır ve ilk aktif görüntünün full çözünürlüklü render'ı viewer preload akışında arka planda başlatılır. Böylece “Görüntüleyiciye Ekle” sonrasında tüm seçili dosyaların sırayla full decode edilmesi engellenir.

## Doğrulama

| Kontrol | Sonuç |
|---|---:|
| Tam pytest paketi | **196 geçti**, 5 uyarı |
| DICOM selector testleri | **4 geçti** |
| Viewer tree/layout odak testleri | **5 geçti** |
| Gerçek DICOM preview benchmarkı | **4/4 bounded** |
| `compileall` | **Başarılı** |
| Qt offscreen smoke | **Başarılı** (`UI_THEME_SMOKE_OK`) |

## Geri dönüş noktası

Bu değişiklik öncesi kaynak kopyaları:

`C:\Users\yusuf\Desktop\Scoliosis Follow Up\.restore_points\preview_load_20260822_232142`

## Kalan sınırlama ve sonraki seçenek

Eğer gerçek kullanıcı dosyaları JPEG 2000, JPEG-LS veya başka encapsulated transfer syntax kullanıyorsa, düşük çözünürlüklü preview'a rağmen decoder full frame çözebilir. Bir sonraki teknik seçenek, kurulu DICOM codec'inin desteklediği native thumbnail veya server-side thumbnail/pyramid üretimini ölçmektir. Bu seçenekler üretim PACS ve codec bilgisi olmadan varsayılan davranışa alınmamalıdır.
