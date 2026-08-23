# Scoliosis Follow-Up

PySide6 tabanlı Windows masaüstü uygulaması. DICOM görüntüleme, Cobb ölçümü, longitudinal takip, karşılaştırma/Overlay, raporlama ve kontrollü deneysel AI araçlarını destekler.

**Güncel sürüm: 1.7.7** — Ana viewer için iptal edilebilir lazy queue, bellek bütçeli cache, düşük çözünürlüklü seçim önizlemeleri ve transfer-syntax bazlı native codec seçimi içerir.

> Bu uygulama klinik tanı veya tedavi kararının yerine geçmez. Otomatik ve AI sonuçları yalnızca taslak/yardımcı sonuç olarak değerlendirilir ve uzman tarafından manuel doğrulanmalıdır.

## Hızlı başlatma

Windows’ta uygulamayı çalıştırmak için kökteki `Uygulamayi_Baslat.bat` dosyasını kullanın. Geliştirme ortamı hazır değilse önce `requirements-dev.txt` içindeki bağımlılıkları proje içindeki `.venv` ortamına kurun.

```powershell
.\.venv\Scripts\python.exe modular_app\run_modular.py
```

## Görünür kaynak alanları

| Klasör/dosya | Görevi |
|---|---|
| `main.py` | Ana uygulama ve merkezi tema |
| `modular_app` | UI, veritabanı, timeline, viewer ve servis modülleri |
| `ai` | Kontrollü AI runtime ve taslak akışları |
| `dicom` | DICOM yardımcıları ve kalite kontrolleri |
| `pacs` | PACS/DICOM ağ bağlantısı yardımcıları |
| `anonymization` | Araştırma kopyası ve anonimleştirme |
| `resources` | Uygulamanın aktif logo, ikon ve model kaynakları |
| `tests` | Otomatik testler |
| `scripts` | Bakım ve geliştirici komutları |
| `tools` | Benchmark ve kabul testi araçları |
| `docs/RELEASE_NOTES_1.7.7.md` | 1.7.7 sürüm notları |
| `packaging` | PyInstaller, installer ve release betikleri |
| `docs` | Teknik raporlar ve kullanım notları |
| `requirements.txt` | Çalışma bağımlılıkları |
| `requirements-dev.txt` | Çalışma bağımlılıkları + pytest |
| `requirements-lock.txt` | Doğrulanmış ortamın sabitlenmiş tam paket sürümleri |
| `VERSION` | Uygulama sürümü |
| `packaging/ScoliosisFollowUp.spec` | PyInstaller paketleme tanımı |
| `Uygulamayi_Baslat.bat` | Uygulamayı başlatan kısa yol |

## Yerel ve üretilen alanlar

`build`, `dist`, `installer`, `releases` ve `artifacts` klasörleri yeniden üretilebilir paketleme/dağıtım çıktılarıdır. `.venv` ve `.venv-build` Python ortamlarıdır. `.quarantine`, `.restore_points`, `dev_data` ve `project_archives` yerel deney, test veya geri alma alanlarıdır. Hasta verisi `%LOCALAPPDATA%\ScoliosisFollowUp` altında; özel anahtarlar bunun `security_keys` alt klasöründe tutulur ve proje/Git ağacına konmaz.

## 1.7.7’de öne çıkanlar

Ana viewer artık görünür current görüntüyü düşük öncelikli komşu prefetch işlerinin önüne alan, iptal edilebilir ve bounded bir queue kullanır. Aynı dosya/frame/signature için devam eden duplicate decode istekleri yeniden kullanılabilir; eski generation sonuçları scene’e uygulanmaz. Tam çözünürlüklü decoded array ve view pixmap cache’leri byte bütçeleriyle sınırlıdır ve dosya aynı path üzerine değiştirildiğinde stale entry’ler temizlenir.

Seçim ekranındaki thumbnail ve büyük preview aynı worker sonucunu paylaşır. Preview uzun kenarı 640 px ile sınırlıdır; bu nedenle seçim akışı ana viewer’ın klinik tam çözünürlüklü render davranışından bağımsız olarak daha düşük bellek ve decode maliyetiyle çalışır. Ana viewer’da path-based tek-frame lazy decode kullanılır.

Sıkıştırılmış DICOM dosyalarında Transfer Syntax’a göre `pylibjpeg`/`pylibjpeg-libjpeg`, JPEG 2000 için `pylibjpeg-openjpeg` ve JPEG-LS için `pyjpegls` preferred yolları tanınır. Preferred decoder başarısız olursa pydicom fallback akışı korunur. Ayrıntılı ölçümler ve sınırlamalar `docs/RELEASE_NOTES_1.7.7.md` ile `docs/roadmap/viewer_lazy_queue_codec_report.md` dosyalarındadır.

## Test

Testleri sistem Python’ı yerine proje sanal ortamıyla çalıştırın:

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py modular_app ai dicom pacs anonymization scripts tools packaging tests
.\.venv\Scripts\python.exe tests\smoke_ui_theme.py
.\.venv\Scripts\python.exe -m pytest -q
```

## Paketleme

Windows release akışı için `packaging\ci_release.ps1` kullanılabilir. Release öncesi test, PyInstaller build, installer, SHA-256/integrity ve update manifest doğrulama kapıları atlanmamalıdır. 1.7.7 değişiklik özeti için `docs\RELEASE_NOTES_1.7.7.md` dosyasını inceleyin; yayımlanan kurulum paketi [GitHub Releases](https://github.com/mryusufcan/scoliosis-followup-releases/releases) alanından sunulur.

## Güvenli bakım

Karantina model tekrarları için `scripts\maintenance\Temizle_Karantina_Modelleri.bat` varsayılan olarak dry-run çalışır. Restore point temizliği, model/venv silme ve eski release arşivleme işlemleri yalnızca checksum, yedek ve yeniden kurulum doğrulaması sonrasında yapılmalıdır. Ayrıntılar `docs` klasöründeki güncel raporlardadır.
