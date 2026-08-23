# Scoliosis Follow-Up Son Proje Denetimi

**Denetim tarihi:** 22 Ağustos 2026  
**Denetim kapsamı:** Kullanıcının son değişiklikleri; sürüm 1.7.5, lisans/trial, güncelleme akışı, testler, release paketleri, deneysel AI alanları ve proje boyutu  
**İşlem türü:** Denetim; kaynak veya veri silinmedi

## Genel sonuç

Proje 1.6.0 döneminden 1.7.5 sürümüne ilerlemiş. En önemli yeni geliştirme, **çevrimiçi lisans/trial kurtarma politikası**, HWID bağlı trial doğrulaması, saat geri alma kontrolü, imzalı yerel durum dosyası, güvenli update manifest doğrulaması ve Windows Qt test kararlılığıdır.

Son kullanıcı sanal ortamı kullanılarak tema smoke ve tam pytest paketi başarıyla tamamlandı. Release kabul denetimi de başarılıdır. Ancak sistemdeki global Python ile çalıştırılan smoke/pytest komutları güvenilir değildir: global Python’da `scipy` ve `pytest` yoktur. Doğru çalışma ortamı proje içindeki `.venv` klasörüdür.

| Kontrol | Sonuç |
|---|---|
| `.venv` ile UI smoke | `UI_THEME_SMOKE_OK` |
| `.venv` ile pytest | **182 passed**, 5 uyarı |
| Kaynak derleme | `compileall` başarılı |
| Release verify | **KABUL DENETİMİ BAŞARILI** |
| Güncel sürüm | `1.7.5` |
| DICOM/SQLite üzerinde denetim sırasında değişiklik | 0 |

## Son sürümde yapılan yeni işler

`docs\RELEASE_NOTES_1.7.5.md` ve `modular_app\services\license_policy.py` incelendi. 1.7.5 bakım sürümünde yerel lisans/trial kaydı bozulsa bile aynı cihaz için sunucu doğrulamasıyla güvenli onarım yapılması, sunucudaki trial başlangıç tarihinin korunması, yeniden kurulum veya yerel kayıt silmenin trial süresini sıfırlayamaması ve offline tolerans sınırlarının korunması hedeflenmiş.

Lisans state dosyası HWID ve HMAC imzasıyla korunuyor. Uygulama saat geri alma girişimini, bozuk state dosyasını, cihaz uyuşmazlığını ve sunucu tarafından doğrulanmayan lisans durumunu ayrı modlarda ele alıyor. İlk lisanssız trial başlangıcı çevrimdışı yapılmıyor; çevrimdışı kullanım yalnızca daha önce sunucuyla senkronize edilmiş state için tanınıyor.

Güncelleme akışında HTTPS, SHA-256 ve imzalı update manifest doğrulaması var. İndirme tamamlanmadan installer çalıştırılmıyor; hash uyuşmazlığında geçici dosya siliniyor. Güncelleme kullanıcı onayıyla başlatılıyor ve otomatik indirme/kurulum yapılmıyor.

`run_modular.py` içinde açılış bütünlük kontrolü, salt okunur SQLite health check, lisans kapısı, lisans süresi dolduğunda yeniden kontrol ve startup DICOM açma akışı bulunuyor. Menü yapısı Hasta, Takip, Görüntüleme, Veri/PACS, Raporlar, Gelişmiş ve Yardım kategorilerine ayrılmış. Mazurowski AI, 68-landmark asistanı, AI taslak inceleme, model aday inceleme, eğitim verisi, DICOM kalite kontrolü, PACS, anonimleştirme, audit history ve longitudinal merkez menüye bağlanmış.

## Boyut değişimi

Son envanterde proje toplamı **17.277,10 MiB**, yani yaklaşık **16,87 GiB** olarak ölçüldü. Önceki 5 GiB seviyesine göre artışın ana nedeni kaynak kodu değil; yeni deneysel AI projesi, birden fazla full release paketi, iki sanal ortam ve yeniden oluşan build/dist/installer çıktılarıdır.

| Alan | Boyut | Dosya | Denetim yorumu |
|---|---:|---:|---|
| `.quarantine` | **8.570,35 MiB** | 56.937 | En büyük artış burada; deneysel projeler ve model ağırlıkları. |
| `releases` | **3.182,81 MiB** | 20 | 1.7.0, 1.7.2, 1.7.3, 1.7.4, 1.7.5 full paketleri. |
| `.restore_points` | **1.462,54 MiB** | 7 | Beş adet yaklaşık 243,75 MiB ZIP restore point. |
| `.venv` | **1.089,10 MiB** | 16.347 | Çalışma/test ortamı. |
| `.venv-build` | **1.069,13 MiB** | 13.783 | PyInstaller/release ortamı. |
| `installer` | **705,99 MiB** | 2 | Güncel installer ve 1.7.1 installer kopyası. |
| `dist` | **674,11 MiB** | 1.558 | Güncel onedir paketinin yeniden üretilebilir çıktısı. |
| `resources` | **261,16 MiB** | 16 | Aktif AI/model kaynakları ve branding. |
| `dev_data` | **99,42 MiB** | 20 | DICOM kabul/benchmark verileri. |
| `project_archives` | **88,08 MiB** | 1 | v1.6.0 kaynak ZIP arşivi. |
| `build` | **69,25 MiB** | 66 | PyInstaller ve release-site ara çıktıları. |

## Yeni deneysel AI alanları

`.quarantine\mazurowski_scoliosis_project` tek başına **6.675,46 MiB** ve 23.365 dosya kullanıyor. Bu alanın dağılımı şöyledir:

| Alt alan | Boyut | Değerlendirme |
|---|---:|---|
| `.venv` | **4.628,12 MiB** | Yeniden kurulabilir deneysel Python ortamı; en büyük temizleme adayı. |
| `onnx_candidate` | **1.342,09 MiB** | 8 ONNX aday dosyası; aktif model ve adaylar tekilleştirilmeli. |
| `downloaded_weights` | **670,81 MiB** | Ham `.pth` ağırlıkları; model seçimi tamamlanmadan silinmemeli. |
| `comparison_outputs` | 6,02 MiB | PNG karşılaştırma çıktıları; araştırma çıktısı. |
| `patient_outputs` | 6,01 MiB | Hasta/örnek çıktı adayı; gizlilik açısından özel incelenmeli. |
| `.git` | 5,73 MiB | Deneysel alt projenin kendi Git geçmişi. |
| `smoke_outputs` | 4,47 MiB | Smoke test sonuçları. |
| Notebook/etiket/örnek verileri | yaklaşık 10 MiB | Eğitim, doğrulama ve deney kayıtları. |

`.quarantine\landmark_lab` **1.851,47 MiB** kullanıyor. Bunun **1.488,45 MiB**’ı deneysel `.venv`, yaklaşık 184,68 MiB’ı iki ONNX/model adayı ve 178,13 MiB’ı ağırlık arşivi.

`resources\ai` içinde aktif kullanım için seçilmiş Mazurowski modelinin yaklaşık 167,76 MiB ve deneysel landmark model alanının yaklaşık 92,34 MiB olduğu görüldü. Bu nedenle quarantine içindeki tüm model adaylarını aktif resources alanıyla karşılaştırmadan silmek doğru değildir.

## Release ve dağıtım durumu

`releases` altında 1.7.0, 1.7.2, 1.7.3, 1.7.4 ve 1.7.5 sürümleri tutuluyor. 1.7.2–1.7.5 klasörlerinin her biri yaklaşık 705 MiB; her birinde installer EXE, release ZIP, `update.json` ve `VERSION` bulunuyor. 1.7.0 yaklaşık 361 MiB.

`installer` kökünde güncel `ScoliosisFollowUp_Setup.exe` ve eski `ScoliosisFollowUp_Setup_1.7.1.exe` bulunuyor. Güncel installer ayrıca `releases\1.7.5` altında tutuluyor. Bu nedenle kök installer alanında eski 1.7.1 dosyası, doğrulama sonrası arşivlenebilecek belirgin bir tekrar adayıdır.

`update.json` ile `releases\1.7.5\update.json` aynı sürümü, aynı HTTPS adresini, aynı SHA-256 özetini ve aynı imzayı gösteriyor. `verify_release.py` çıktısı EXE bütünlüğünü, installer özetini ve yerel güncelleme bildirimini başarılı doğruladı.

## Test bulgusu ve önemli tutarsızlık

`.venv` kullanılarak çalıştırılan güncel pytest paketi **182 test geçti**. Release notlarında ise 1.7.5 için **181/181** yazıyor. Bu fark muhtemelen release paketinden sonra yerel çalışma ağacına bir test eklenmesinden kaynaklanıyor; ancak sonraki release öncesi release notes sayısı güncel test sayısıyla eşleştirilmelidir.

Global sistem Python ile yapılan ilk doğrulama gerçek bir uygulama hatası değil, ortam eksikliğini gösterdi:

```text
ModuleNotFoundError: No module named 'scipy'
No module named 'pytest'
```

Proje `.venv` ortamında `scipy==1.18.0` ve `pytest==9.1.1` bulunduğu için aynı testler bu ortamda başarılıdır. Bundan sonra test komutları açıkça şu biçimde çalıştırılmalıdır:

```powershell
.\.venv\Scripts\python.exe tests\smoke_ui_theme.py
.\.venv\Scripts\python.exe -m pytest -q
```

Smoke sırasında Qt’nin font dizini hakkında uyarı görüldü; buna rağmen smoke sonucu başarılıdır. Release paketi kendi Qt kaynaklarını taşıdığı için temiz Windows kurulumunda ayrıca görsel kontrol yapılmalıdır.

## Veri ve güvenlik değerlendirmesi

`.gitignore` güncel olarak `.venv-build`, build/dist/installer, restore point, quarantine, security keys, DICOM, veritabanı, ZIP ve log alanlarını dışlıyor. Bu Git’e yanlışlıkla büyük veya hassas dosya eklenmesini azaltır.

Bununla birlikte `.gitignore` yalnızca Git takibini önler; dosyaları diskten veya yedekleme hizmetlerinden silmez. `.quarantine\mazurowski_scoliosis_project\patient_outputs`, `dev_data` ve DICOM benzeri alanlar hasta verisi içerebileceğinden proje klasöründe tutulmadan önce anonimleştirme ve erişim kontrolü değerlendirilmelidir. Bu denetimde içerik okunmadı ve hiçbir veri silinmedi.

## Önerilen temizlik sırası

| Sıra | Aday | Tahmini alan | Önerilen işlem |
|---:|---|---:|---|
| 1 | Eski `installer\ScoliosisFollowUp_Setup_1.7.1.exe` | 352,95 MiB | 1.7.5 release verify ve checksum sonrası arşivle/kaldır. |
| 2 | Eski release klasörleri | 2 GiB’den fazla | En az son iki sürümü tut; eskileri harici arşive taşı. |
| 3 | Mazurowski `.venv` | 4.628 MiB | Lock dosyası/rebuild smoke doğrulanmadan silme. |
| 4 | Landmark `.venv` | 1.488 MiB | Daha önce rebuild testi yapılmış olsa da model deneyinin kapandığı doğrulanmalı. |
| 5 | Mazurowski ONNX adayları ve ham weights | yaklaşık 2 GiB | Aktif model checksum’ı kesinleştikten sonra tekilleştir. |
| 6 | `.venv` ve `.venv-build` | yaklaşık 2.158 MiB | Proje dışına taşı veya yeniden kurulum dokümanı hazırsa sil. |
| 7 | Eski restore ZIP’leri | yaklaşık 1.2 GiB | Retention politikasıyla son iki restore point’i tut; büyükleri harici arşivle. |

Hiçbir aday bu denetim sırasında silinmedi. En güvenli büyük kazanım, önce release arşivlerini ve sanal ortamları lock/checksum ile doğrulamak; hasta/deney verilerini ise klinik ve araştırma gereksinimleri netleşmeden korumaktır.

## Son karar

Kod tarafında 1.7.5 sürümü güçlü bir noktaya gelmiş: lisans/trial güvenliği, update doğrulama, SQLite preflight health check, AI taslak ayrımı, DICOM kalite akışı, longitudinal takip ve release doğrulama birlikte çalışıyor. Son değişikliklerin çalışma ortamında **182/182 test geçmesi** ve release verify’ın başarılı olması olumlu.

Şu anki en önemli teknik konu yeni özellik eksikliği değil, proje alanı ve ortam yönetimidir. Proje boyutu yaklaşık 5 GiB’den 16,87 GiB’ye yükselmiş. Bunun yaklaşık 6,68 GiB’ı yeni Mazurowski deney alanı, 3,18 GiB’ı full release arşivleri ve 2,16 GiB’ı iki Python ortamıdır. Bir sonraki adımda silme değil, önce model/venv/release retention manifesti ve hasta verisi erişim politikasının netleştirilmesi önerilir.
