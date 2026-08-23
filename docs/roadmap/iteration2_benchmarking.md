# İkinci İterasyon Benchmark Kılavuzu

Bu kılavuz PACS, rapor üretimi, longitudinal snapshot yükleme ve gerçek DICOM decode ölçümlerini aynı JSON sözleşmesinde toplar. Benchmarklar ölçüm sırasında ham DICOM piksel verisini değiştirmez. Veritabanı benchmarkı için uygulamanın üretim veritabanı varsayılan olarak kullanılmaz; açıkça verilen bir SQLite yolu veya gerçek DICOM header'larından oluşturulup işlem sonunda silinen geçici fixture kullanılır.

## Mevcut gerçek veri kapsamı

| Ölçüm kaynağı | Kapsam |
|---|---:|
| `dev_data/dicom_samples` içindeki dosyalar | 20 |
| Görüntü geometrisi okunabilen gerçek DICOM | 16 |
| Seçili dosya toplamı | yaklaşık 99,4 MB |
| Decode edilen son koşudaki piksel sayısı | 138.546.440 |
| Longitudinal geçici fixture tetkik sayısı | 7 |
| Geçici fixture içindeki Cobb ölçümü | 0 |

### Gerçek DICOM ölçümü

```powershell
.\.venv\Scripts\python.exe tools\benchmark_iteration2.py `
  --repeats 3 `
  --decode `
  --derive-db-from-dicom `
  --output docs\roadmap\iteration2_benchmark_real_dicom_decode.json
```

Son gerçek veri koşusunda 16 DICOM için metadata taraması ortalama **17,919 ms**, seri piksel decode ortalama **19.516,137 ms** ve dosya başına decode ortalaması **1.219,759 ms** ölçüldü. Bu değerler makine, disk önbelleği, codec ve dosya boyutuna bağlıdır; klinik kullanıcı deneyimi için aynı cihaz profiliyle tekrar edilmelidir.

### Açıkça seçilmiş longitudinal ve rapor veritabanı

Üretim veritabanına dokunmadan, yalnızca kullanıcı tarafından seçilmiş anonim benchmark kopyasıyla çalıştırılır:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_iteration2.py `
  --repeats 5 `
  --db "D:\Benchmark\anonymized_scoliosis.db" `
  --patient-id "BENCHMARK-P001" `
  --output docs\roadmap\iteration2_benchmark_large_db.json
```

Bu koşulda longitudinal snapshot, CSV ve PDF gerçek kayıt hacmiyle ölçülür. 100 veya 1000 tetkik/zaman noktası hedefi için bu hacimleri içeren anonimleştirilmiş benchmark kopyası gerekir; mevcut geliştirme DICOM klasörü tek başına bu kayıt hacmini temsil etmiyor.

### PACS ölçümü

PACS ağı varsayılan olarak hiç çağrılmaz. Yer tutucu yapılandırma dosyası:

```json
{
  "host": "PACS_HOST",
  "port": 104,
  "called_ae_title": "REMOTE_AE",
  "calling_ae_title": "SCOLIOSIS_APP",
  "timeout_seconds": 15
}
```

Yalnızca yapı doğrulaması için:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_iteration2.py `
  --pacs-config docs\roadmap\pacs_benchmark_config.example.json `
  --output docs\roadmap\iteration2_benchmark_pacs_validation.json
```

Gerçek association/query ölçümü için kullanıcı tarafından doğrulanmış endpoint ve AE Title bilgileriyle ayrıca `--live-pacs` verilmelidir:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_iteration2.py `
  --pacs-config "D:\Benchmark\pacs_config.json" `
  --live-pacs `
  --pacs-patient-id "ANON-P001" `
  --pacs-study-date "20240101-20251231" `
  --output docs\roadmap\iteration2_benchmark_pacs_live.json
```

C-GET için `--retrieve-study-uid` ve yazılabilir, ayrı bir `--retrieve-destination` eklenmelidir. Benchmark sonucu DICOM dosyalarını otomatik olarak üretim havuzuna import etmez.

## Uygulanan optimizasyonlar

PACS query/retrieve/send işlemleri tek iş parçacıklı Qt worker havuzunda çalışır; GUI thread'i ağ timeout'u boyunca bloke edilmez. Longitudinal snapshot yenilemesi de tek worker kuyruğuna taşınmıştır. Debounce sonrasında eski sonuçlar generation token ile yok sayılır ve panel kapanışında bekleyen sonuçlar geçersizleştirilir.

Longitudinal servisinde ölçüm kayıtları path anahtarıyla bir kez indekslenir, overlay oturumları path başına sayılır ve kaynak dosyası varlığı tek geçişte hesaplanır. Böylece her tetkik için bütün ölçüm/overlay listesini tekrar tarayan sıcak yol azaltılmıştır.

CSV ve PDF üretimi ortak `get_follow_up_report_bundle()` sorgusunu kullanır. Profil, ölçümler, tetkikler, overlay oturumları, vertebra etiketleri, görüntü notları ve takip uyarıları tek SQLite bağlantısında salt-okunur olarak toplanır. PDF Unicode font kaydı da süreç içinde bir kez cache edilir.

## Ölçülen yön değişimi

Aynı geliştirme makinesi ve aynı gerçek-DICOM header türevi 7 tetkiklik geçici fixture üzerinde, üç warm-up sonrası üç raporlanan tekrar kullanıldı:

| İşlem | Önceki ölçüm | Bundle/font cache sonrası ölçüm | Yorum |
|---|---:|---:|---|
| PDF üretimi | 41,478 ms | 29,890 ms | Küçük fixture'da yaklaşık %28 daha düşük ortalama |
| CSV üretimi | 2,124 ms | 1,570 ms | Küçük fixture'da yaklaşık %26 daha düşük ortalama |
| Longitudinal snapshot | 2,168 ms | 2,133 ms | Bu hacimde fark ölçüm gürültüsü düzeyinde |

Bu karşılaştırma yön göstericidir. Büyük gerçek longitudinal kayıt hacmi ve gerçek rapor not/overlay/ölçüm dağılımı sağlandığında aynı komutla yeniden ölçülmelidir.

## Test kapısı

| Kontrol | Sonuç |
|---|---:|
| Tam pytest paketi | **193 geçti**, 5 uyarı |
| İkinci iterasyon odak testleri | **21 geçti** |
| Cobb end-to-end zinciri | **3 geçti** |
| `compileall` | **Başarılı** |
| Ortam doğrulaması | **Başarılı** |
| Qt offscreen smoke | **Başarılı** |

## Gizlilik ve güvenlik sınırları

Benchmark JSON'u hasta kimlik değerlerini ve tam kaynak yollarını yazmaz; yalnızca seçilen dosya adlarını ve sayısal performans özetlerini tutar. Geçici SQLite fixture yalnızca DICOM header'larından oluşturulur ve koşu sonunda silinir. PACS canlı çağrısı, config ve `--live-pacs` olmadan çalışmaz. Rapor PDF'si hasta bağlamı içerdiğinden yalnızca yetkili kullanıcıların seçtiği hedefe yazılmalıdır.
