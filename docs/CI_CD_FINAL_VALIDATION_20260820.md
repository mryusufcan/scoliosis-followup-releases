# Scoliosis Follow-Up — CI/CD Final Doğrulama Raporu

**Tarih:** 20 Ağustos 2026  
**Sürüm:** 1.6.0  
**Etiket:** `v1.6.0`  
**Platform:** Windows, Python 3.13.15, 16 CPU

## Sonuç

Temizlenmiş `dist` klasörüyle aşağıdaki release akışı başarıyla tamamlandı:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\ci_release.ps1 `
  -Clean -SkipTests -SkipInstaller -RunBenchmarks
```

PyInstaller `onedir` EXE üretimi, bütünlük manifestosu, release kabul denetimi ve gerçek DICOM worker benchmarkı başarılı oldu. Sonrasında bağımsız doğrulama kapıları ayrıca çalıştırıldı: `py_compile` başarılı, `UI_THEME_SMOKE_OK` başarılı ve **139/139 modüler test başarılı**.

## Doğrulama kapıları

| Kapı | Sonuç | Not |
|---|---:|---|
| Python sözdizimi derlemesi | Başarılı | Ana uygulama, viewer, kayıt, render, doğrulama ve benchmark modülleri derlendi. |
| UI tema smoke testi | Başarılı | `UI_THEME_SMOKE_OK`; Qt font dizini uyarısı görüldü ancak smoke sonucu başarısız olmadı. |
| Modüler regresyon testleri | **139/139 başarılı** | Süre: 87.157 saniye. |
| Release kabul denetimi | Başarılı | EXE, installer özeti ve yerel update bildirimi doğrulandı. |
| EXE bütünlük manifestosu | Başarılı | İmzalı/üretilmiş EXE için SHA-256 kaydı oluşturuldu. |
| Worker concurrency benchmarkı | Başarılı | 8 gerçek DICOM, 1/2/4 worker, iki tekrar, sıfır decode hatası. |

## Worker concurrency benchmarkı

Final JSON çıktısındaki ortalama süre ve throughput değerleri şöyledir:

| Worker | Ortalama süre | Dosya throughput | Megapiksel throughput | One-worker speedup |
|---:|---:|---:|---:|---:|
| 1 | 8.295 s | 0.992 dosya/s | 6.416 MP/s | 1.000x |
| 2 | 8.414 s | 0.958 dosya/s | 6.197 MP/s | 0.986x |
| 4 | **7.412 s** | **1.093 dosya/s** | **7.068 MP/s** | **1.119x** |

Bu final koşusunda 4 worker, 1 worker'a göre yaklaşık **%11.9 daha hızlı** ölçüldü. Sonuçlar yalnızca pydicom + NumPy decode katmanını ölçer; QImage/QPixmap veya GUI thread işlemleri benchmarka dahil değildir. Her worker seviyesinde 8 dosyanın tamamı çözüldü ve hata listesi boş kaldı. Önceki ölçümlerin farklı süreler vermesi, disk önbelleği ve Windows çalışma koşullarının benchmarkı etkileyebileceğini gösterir; bu nedenle sonuçlar aynı makine, aynı dosya kümesi ve aynı tekrar sayısıyla karşılaştırılmalıdır.

## Üretilen artifact özeti

| Artifact | Boyut | SHA-256 |
|---|---:|---|
| `dist\\ScoliosisFollowUp\\ScoliosisFollowUp.exe` | 14,548,921 bayt | `6462824e1e77982a6ae8a7dda7deaa411beed777cf88951e4f30411fe5edefe6` |
| `dist\\ScoliosisFollowUp\\runtime_integrity.json` | 841,202 bayt | `a60fa1aeb29a87ff90eee188f187988584dd9c9a51a1d73bee918adb3b44a2cb` |
| `installer\\ScoliosisFollowUp_Setup.exe` | 234,322,871 bayt | `613691f813cf255d7d7d44cd5d92c0c4e0bfe57ff061bc15fc88e520663e1ab6` |

## Teşhis ve kapsam notu

İlk uzun koşu, PyInstaller analizinde takılmamış; `dist\\ScoliosisFollowUp\\_internal\\charset_normalizer\\cd.cp313-win_amd64.pyd` dosyası Windows tarafından kilitli olduğu için `PermissionError [WinError 5]` ile durmuştu. Kaynak kodda değişiklik yapmadan eski `dist\\ScoliosisFollowUp` çıktısı ve ilgili uygulama süreçleri temizlendi. Temiz koşuda aynı paketleme akışı başarıyla tamamlandı; bu nedenle mevcut CI scriptinde kaynak kod değişikliği gerektiren bir hata tespit edilmedi.

Bu yerel final koşusunda `-SkipInstaller` kullanıldığı için installer yeniden derlenmedi; mevcut installer artifactı release kabul denetiminde doğrulandı. GitHub Actions workflowu ise temiz runner üzerinde `-Clean -RunBenchmarks` ile installer adımını atlamadan çalışacak şekilde korunmuştur.

## Değişen kaynak kapsamı

Final doğrulama sırasında uygulama kaynak koduna yeni değişiklik yapılmadı. Önceden tamamlanan değişiklikler korunarak yalnızca build çıktısı temizlendi ve yeniden üretildi. Yedekleme/restore-point düzeni korunmaktadır.

## Teslim edilen dosyalar

- `packaging\\ci_release.ps1`
- `.github\\workflows\\windows-release.yml`
- `docs\\CI_CD_RELEASE_AND_PERFORMANCE.md`
- `docs\\roadmap\\worker_concurrency_benchmark_20260820.json`
- `build\\ci-release\\artifacts.json`
- `docs\\roadmap\\verification_release_report_20260820.md`
- `docs\\CI_CD_FINAL_VALIDATION_20260820.md`
