# Scoliosis Follow-Up — Proje Boyutu Temizlik Raporu

**Tarih:** 20 Ağustos 2026  
**Sürüm:** 1.6.0  
**Kapsam:** Yeniden üretilebilir paketleme çıktıları ve Python bytecode önbellekleri

## Sonuç

Proje klasörü temizlik öncesi **6.539,23 MiB** ölçüldü. `build`, `dist`, `installer` ve kök Python bytecode önbelleği temizlendikten sonra ölçüm **5.269,33 MiB** oldu. Toplam kazanım yaklaşık **1.269,90 MiB**, yani **%19,42** seviyesindedir.

| Alan | Temizlik öncesi | İşlem | Durum |
|---|---:|---|---|
| `dist` | 996,75 MiB | PyInstaller onedir çıktısı kaldırıldı | Temizlendi |
| `installer` | 223,47 MiB | Yeniden üretilebilir installer çıktısı kaldırıldı | Temizlendi |
| `build` | 49,65 MiB | PyInstaller geçici çalışma çıktısı kaldırıldı | Temizlendi |
| Kök `__pycache__` | 0,10 MiB | Python bytecode önbelleği kaldırıldı | Temizlendi |
| **Toplam** | **1.269,97 MiB** |  |  |

Ölçümdeki küçük fark, dosya taraması sırasında oluşan ve sonradan kaldırılan geçici envanter/bytecode dosyalarından kaynaklanabilir.

## Korunan alanlar

Kaynak kod, DICOM test verileri, deneysel model kaynakları, kullanıcı verisi olabilecek alanlar, geri alma noktaları ve dağıtım arşivleri silinmedi. Özellikle `.restore_points` yaklaşık 1.81 GiB, `.quarantine` yaklaşık 1.85 GiB, `.venv-build` yaklaşık 940.91 MiB ve `releases` yaklaşık 446.67 MiB olarak korunmaktadır.

| Korunan alan | Neden korundu |
|---|---|
| `.restore_points` | Önceki değişiklikleri geri alabilmek için yedek/restore point geçmişi |
| `.quarantine` | Deneysel landmark/AI içerikleri; gereksiz olduğu kesinleşmeden silinmedi |
| `.venv-build` | Windows PyInstaller ve codec paketleme ortamı; yeniden build için gerekli olabilir |
| `dev_data` | Gerçekçi/sentetik DICOM kabul ve benchmark dosyaları |
| `resources` | Uygulama marka, tema ve model kaynakları |
| `modular_app`, `tests`, `packaging` | Uygulamanın kaynak, test ve dağıtım kodu |
| `releases` | 1.6.0 installer, release ZIP, `VERSION` ve `update.json` arşivi |

## Doğrulama

Temizlik sonrasında kaynak doğrulama kapıları yeniden çalıştırıldı. Python kaynakları `py_compile` ile başarıyla derlendi, tema smoke testi `UI_THEME_SMOKE_OK` döndürdü ve **142/142 modüler test başarılı** oldu. Bu koşu, önceki 139 testlik doğrulamaya eklenen testlerle birlikte güncel test sayısını göstermektedir.

Önceki temizleme öncesi release doğrulamasında EXE, installer özeti ve bütünlük manifestosu başarıyla doğrulanmıştı. Bu temizlik adımında dağıtım çıktıları bilerek kaldırıldığı için temizlik sonrasında `verify_release.py` tekrar çalıştırılmamıştır; yeniden paketleme yapılınca release kabul kapısı yeniden çalıştırılmalıdır.

## Yeniden oluşturma

EXE ve installer çıktıları gerektiğinde aşağıdaki komutla yeniden üretilebilir:

```powershell
Set-Location 'C:\Users\yusuf\Desktop\Scoliosis Follow Up'
.\packaging\ci_release.ps1 -Clean -RunBenchmarks
```

Bu komut test, PyInstaller, installer, bütünlük doğrulaması ve worker benchmark akışını yeniden çalıştırır. GitHub Actions workflowu da temiz runner üzerinde aynı üretim kapılarını çalıştıracak şekilde korunmuştur.

## Geri alma notu

Silinenler kaynak kodu değildir; yeniden üretilebilir `build`, `dist`, `installer` ve Python önbelleği çıktılarıdır. Dağıtım dosyası gerektiğinde proje içindeki `releases\1.6.0` arşivinden kullanılabilir. Kaynak davranışında değişiklik yapılmadı; SQLite, DICOM metadata/piksel matrisi, export akışı ve restore point içeriği korunmuştur.

Temizlik öncesi karar ve hedef kayıtları `docs\project_cleanup_manifest_20260820.json` dosyasında tutulmaktadır.
