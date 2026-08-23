# Alt Klasörlerde Sadeleştirme Denetimi

**Tarih:** 22 Ağustos 2026  
**Kapsam:** `scripts`, `tools`, `packaging`, `docs` ve `artifacts` alt klasörleri  
**Durum:** Yalnızca sınıflandırma yapıldı; bu denetimde dosya silinmedi veya taşınmadı.

## Kısa sonuç

Evet, alt klasörlerde uygulamanın günlük çalışması için zorunlu olmayan dosyalar var. Bunların bir bölümü tarihsel migration/stitching betikleri, bir bölümü benchmark ve kabul testleri, bir bölümü de log veya Python önbelleği. Ancak bunlar proje boyutunu büyük ölçüde artıran alanlar değildir. Büyük kazanım hâlâ deneysel model/venv, release ve restore alanlarının arşivlenmesinden gelir.

## Güvenli ve düşük riskli adaylar

| Konum | İçerik | Önerilen işlem | Risk |
|---|---|---|---|
| `scripts\maintenance\__pycache__` ve diğer alt klasör `__pycache__` dizinleri | Python bytecode önbelleği | Silinebilir; Python yeniden oluşturur | Çok düşük |
| `scripts\dev\Otomatik_Testleri_Calistir_20260821_213916.txt` | Test çalışma çıktısı/log | `artifacts\logs` altına arşivlenebilir veya silinebilir | Çok düşük |
| `artifacts\release_logs` içindeki eski release günlükleri | Dağıtım işlem kayıtları | Son release ve son doğrulama korunarak eski loglar arşivlenebilir | Düşük |
| `docs\__pycache__` veya analiz önbellekleri | Geçici bytecode | Silinebilir | Çok düşük |

## Arşivlenmesi uygun, runtime için gerekmeyen dosyalar

`scripts\maintenance` içindeki `01_Risksiz_Proje_Temizligi.ps1`, `02B_Asama2_Devam_Duzeltme.ps1`, `03B_Proje_Yapisini_Duzenle_Duzeltilmis.ps1`, `04_Branding_Packaging_Duzenle.ps1` ve `05_Merkezi_Path_Sistemi.py` tarihsel bakım/migration betikleridir. `06_Stitching_Engine_Asama1.py` ile `11_Stitch_Controller_Asama6.py` arasındaki numaralı dosyalar da aşamalı geliştirme betikleri görünümündedir. Bunlar Proje Kontrol Merkezi’nin günlük action listesinde çağrılan güncel araçlar değildir; yine de geçmiş değişiklikleri tekrar üretme ihtimali nedeniyle doğrudan silinmemeli, `project_archives\legacy_maintenance_20260822` gibi bir arşiv klasörüne taşınmalıdır.

`tools` altındaki benchmark, codec acceptance, Windows viewer acceptance ve restore yardımcıları ana uygulamanın çalışma zamanı için gerekli değildir. Ancak performans, release ve klinik kabul testleri için değerlidir. Bunların silinmesi yerine `tools` altında tutulması veya Explorer’da gizlenmesi önerilir. `tools\README.md` mutlaka korunmalıdır.

`docs` altındaki raporların hiçbiri normal uygulama açılışı için gerekli değildir; fakat performans, release, DICOM codec ve proje karar geçmişini belgeler. Sade görünüm için `docs\archive\audits\2026-08` altında tarihsel JSON/Markdown raporları gruplanabilir. `docs\Proje_Rehberi.html`, kontrol merkezi tarafından açıldığı için korunmalıdır.

## Korunması gereken dosyalar

`packaging` altındaki `ci_release.ps1`, `build_windows.ps1`, `verify_release.py`, installer tanımı ve `README_PACKAGING.md` release üretimi için korunmalıdır. `scripts\build` ve `scripts\release` altındaki mevcut action dosyaları Proje Kontrol Merkezi tarafından çağrıldığı için taşınmamalıdır.

`scripts\admin\Lisans_Yonetimi_Anahtar_Kaydet.ps1`, `packaging\generate_integrity_key.py`, `security_keys` ve lisans/entitlement dosyaları özel güvenlik kapsamındadır. Bunlar ZIP paylaşımına dahil edilmemeli, içerikleri okunmadan silinmemeli ve kaynak koda gizli anahtar eklenmemelidir.

`requirements.txt`, `requirements-dev.txt`, `resources`, `main.py`, `modular_app`, `ai`, `dicom`, `pacs`, `anonymization`, `tests`, `ScoliosisFollowUp.spec` ve `project_control_center.py` temel çalışma/geliştirme alanlarıdır. Bunların alt klasörlerden taşınması önerilmez.

## Önerilen sade klasör yapısı

Kök dizinde yalnızca uygulama kaynakları, kontrol merkezi, başlatma dosyası ve temel yapılandırma görünür tutulabilir. `scripts` altında `admin`, `build`, `dev`, `maintenance` ve `release` ayrımı zaten iyi bir sınır oluşturuyor. Burada yalnızca tarihsel numaralı maintenance betikleri `project_archives\legacy_maintenance_20260822` altında toplanmalıdır.

`artifacts`, `build`, `dist`, `installer`, `releases`, `project_archives`, `.quarantine`, `.restore_points`, `.venv`, `.venv-build`, `dev_data` ve `security_keys` yerel/üretilmiş alanlardır. Bunların kökte kalması teknik olarak sorun değildir; Explorer görünürlüğü veya arşivleme ile ana görünümden ayrılabilirler.

## Önerilen güvenli sıra

İlk adım olarak tüm `__pycache__` klasörleri ve tarihli test logları temizlenebilir. İkinci adım olarak numaralı legacy maintenance betikleri arşiv klasörüne taşınabilir; taşımadan önce `scripts\maintenance` ve `project_control_center.py` yedeklenmelidir. Üçüncü adımda eski audit raporları `docs\archive` altında gruplanabilir. Büyük alan kazanımı için ise daha sonra checksum doğrulamalı release ve deneysel model/venv arşivleme yapılmalıdır.

Bu rapor sınıflandırma amaçlıdır. Uygulama kaynakları, DICOM verileri, SQLite verileri, aktif AI resources modelleri ve güvenlik anahtarları üzerinde işlem yapılmamıştır.
