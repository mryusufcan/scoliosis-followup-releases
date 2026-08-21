# Windows Dağıtımı ve CPU/Çoklu Çekirdek Test Rehberi

## Amaç

Bu proje için iki dağıtım yolu hazırlanmıştır. İlki, GitHub'a `vX.Y.Z` etiketi gönderildiğinde Windows runner üzerinde otomatik build, test, bütünlük doğrulama, installer üretimi ve GitHub Release yayınlayan akıştır. İkincisi, aynı kapıları yerel Windows bilgisayarda tek PowerShell komutuyla çalıştıran daha basit seçenektir.

| Yaklaşım | Artısı | Eksisi | Maliyet | Kurulum karmaşıklığı |
|---|---|---|---|---|
| GitHub Actions | Etiket gönderildiğinde tekrar edilebilir otomatik dağıtım; artifact ve log arşivi; ekip paylaşımı | Windows runner süresi ve GitHub secret ayarı gerekir | GitHub planına bağlı runner dakikaları | Orta |
| Yerel `ci_release.ps1` | İnternetsiz/kurum içi build, hızlı deneme ve tam kontrol | Dağıtımı başlatan bilgisayar açık ve hazır olmalıdır | Ek servis maliyeti yok | Düşük |

> Klinik/pilot dağıtımda otomatik yayın kapısı, test ve `verify_release.py` başarılı olmadan EXE veya installer yayınlamaz.

## GitHub Actions kullanımı

Workflow dosyası `.github/workflows/windows-release.yml` konumundadır. `VERSION` örneğin `1.6.0` ise önce yerel doğrulama yapılır, ardından `v1.6.0` etiketi GitHub'a gönderilir:

```powershell
$version = (Get-Content .\VERSION -Raw).Trim()
git tag "v$version"
git push origin "v$version"
```

Etiket push edildiğinde workflow şu adımları çalıştırır:

1. Windows 2022 runner ve Python 3.13 hazırlanır.
2. Inno Setup kurulur.
3. `packaging\ci_release.ps1 -Clean` çağrılır.
4. `build_windows.ps1`, tam regresyon kapıları ve PyInstaller onedir build çalışır.
5. `build_installer.ps1` installer üretir.
6. `verify_release.py` EXE, installer ve update metadata bütünlüğünü doğrular.
7. EXE, installer, bütünlük manifesti ve CI logları artifact olarak saklanır.
8. Etiket push tetikleyicisinde GitHub Release oluşturulur.

İsteğe bağlı olarak Windows kod imzalama için şu repository secrets tanımlanabilir:

| Secret | Kullanım |
|---|---|
| `WINDOWS_CERTIFICATE_THUMBPRINT` | EXE ve installer imzalama sertifikasının thumbprint değeri |
| `INTEGRITY_PRIVATE_KEY` | Dağıtım bütünlük manifesti için özel anahtar; yalnızca secret olarak tutulur |

Özel anahtar dosyaya veya release artifact'ına eklenmez. Secret tanımlı değilse CI imzasız bir paket üretebilir; bu durumda klinik/pilot dağıtımdan önce imzalama kapısı ayrıca tamamlanmalıdır.

## Yerel kullanım

Yerel Windows bilgisayarda tam release akışı:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\ci_release.ps1 -Clean
```

Sadece hızlı EXE ve verify denemesi:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\ci_release.ps1 -SkipTests -SkipInstaller
```

Yerel GitHub Release yayınlamak için `gh auth login` ve uygun repository yetkisi gerekir:

```powershell
$env:GITHUB_TOKEN = "..."
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\ci_release.ps1 -PublishGitHubRelease -Tag v1.6.0
```

Token, sertifika özel anahtarı ve bütünlük özel anahtarı kaynak koda veya log dosyasına yazılmamalıdır.

## CPU ve çoklu çekirdek benchmarkı

`tools\benchmark_worker_concurrency.py` yalnızca gerçek DICOM decode katmanını ölçer. QImage/QPixmap oluşturmaz; böylece GUI etkisi ayrı tutulur. İlk ölçümde 16 mantıksal CPU bulunan Windows makinede 8 gerçek DICOM dosyası kullanıldı:

| Worker | Ortalama duvar süresi | 1 worker'a göre hızlanma | Sonuç |
|---:|---:|---:|---|
| 1 | 1.465 s | 1,00× | En iyi mevcut sonuç |
| 2 | 1.691 s | 0,87× | Thread yönetimi ve kaynak paylaşımı maliyeti var |
| 4 | 1.585 s | 0,92× | Bu veri setinde 1 worker'dan iyi değil |

Bu sonuç, worker sayısını kör biçimde artırmak yerine adaptif bir havuz ve gerçek makine ölçümü gerektiğini gösterir. JPEG/DICOM codec kütüphaneleri, disk erişimi ve bellek bant genişliği aynı anda sınırlayıcı olabilir.

Benchmark komutu:

```powershell
python .\tools\benchmark_worker_concurrency.py --limit 8 --repeats 2 --workers 1,2,4
```

## Önerilen ek senaryolar

| Senaryo | Ölçülecek değer | Başarı koşulu |
|---|---|---|
| Soğuk disk cache ve sıcak disk cache | İlk decode ile tekrar decode arasındaki duvar süresi | Sıcak cache sonucu ayrı raporlanır; soğuk sonucu gizlemez |
| 1/2/4/8 worker taraması | Throughput, speedup, CPU/wall oranı | En iyi worker sayısı gerçek veri setinde seçilir |
| Küçük + büyük görüntü karışımı | Kuyruk adaleti ve tail latency p95/p99 | Küçük görüntülerin büyük dosya arkasında uzun süre beklememesi |
| Aynı seri içinde çoklu frame | Frame başına decode süresi ve retained array bytes | Yanlış frame/stale sonuç olmaması |
| GUI heartbeat + preload | Maksimum heartbeat aralığı ve scene hazır olma süresi | GUI kabul sınırı korunur; worker artışı GUI'yi bloklamaz |
| Cache contention | Eşzamanlı path değişimi, W/L ve zoom sırasında lock/eviction | Cache byte ve giriş bütçeleri aşılmaz |
| İptal/stale yük | Eski isteklerin iptal edilmesi ve yeni isteğin süresi | Eski sonuç scene'e uygulanmaz |
| Bellek baskısı | Eşzamanlı retained NumPy array bytes ve cache bytes | Dataset 32 MiB, pixmap 128 MiB sınırları korunur |
| Uzun süreli seri tarama | 50/100 dosya ardışık açılışta bellek trendi | Sürekli yükselen bellek eğrisi olmaması |
| ProcessPool karşılaştırması | GIL/codec etkisi için süreç tabanlı throughput | ThreadPool kazanç vermiyorsa gereksiz karmaşıklık eklenmez |

Bu senaryoların her biri gerçek DICOM fixture'larıyla, aynı dosya listesi ve aynı ölçüm tekrarıyla çalıştırılmalıdır. Sentetik rastgele array sonuçları klinik veya dağıtım kararı için kullanılmamalıdır.

## Kanıt dosyaları

| Dosya | İçerik |
|---|---|
| `packaging\ci_release.ps1` | Yerel/CI build, installer, verify ve opsiyonel GitHub Release akışı |
| `.github\workflows\windows-release.yml` | Windows otomatik dağıtım workflow'u |
| `tools\benchmark_worker_concurrency.py` | Gerçek DICOM 1/2/4/çoklu worker ölçümü |
| `docs\roadmap\worker_concurrency_benchmark_20260820.json` | Son worker benchmark çıktısı |
| `docs\roadmap\cache_memory_benchmark_20260820.json` | 16 gerçek DICOM sonrası cache byte ölçümü |
