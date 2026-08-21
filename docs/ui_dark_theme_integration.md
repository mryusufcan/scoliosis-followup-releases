# Karanlık Tema Entegrasyonu

## Değiştirilen kaynaklar

| Dosya | Değişiklik |
|---|---|
| `main.py` | Merkezi `DARK_THEME_QSS`, koyu `QPalette`, sekme/menü/panel/canvas stilleri, uygulama kökü ve status bar nesne adları eklendi. |
| `modular_app/run_modular.py` | Eski yerel menü, sekme ve genel widget stil blokları kaldırıldı; merkezi temanın üzerine yazılması engellendi. |
| `tests/smoke_ui_theme.py` | Tema token’ları, ana pencere kökü ve status bar için smoke test eklendi. |
| `docs/ui_dark_theme_smoke.png` | Karanlık tema ana pencere görsel doğrulama çıktısı. |

## Yedek

Değişikliklerden önce `main.py` ve `modular_app/run_modular.py` dosyaları `.restore_points/ui_dark_theme_YYYYMMDD_HHMMSS/` klasörüne kopyalandı. Geri dönüş gerektiğinde bu iki dosya eski konumlarına kopyalanabilir.

## Doğrulama

Aşağıdaki kontroller başarıyla tamamlandı:

```text
python -m py_compile .\main.py .\modular_app\run_modular.py
UI_THEME_SMOKE_OK
```

Karanlık tema, `#11161D` uygulama zemini, `#0B0F14` görüntü canvas’ı, `#171E27` panel yüzeyi ve `#36C5D8` turkuaz aktif durum rengi üzerine kuruludur. DICOM görüntü, ölçüm ve stitching mantığı değiştirilmemiştir.

## Çalıştırma

Proje kökünde mevcut çalışma yönteminizle uygulamayı başlatabilirsiniz. Genel Python çalıştırma komutu:

```powershell
python .\main.py
```

Uygulama paketlenmiş bir Windows kurulumundan çalıştırılıyorsa yeni kaynak değişikliklerinin görünmesi için önce kurulum/paketleme sürecinin yeniden çalıştırılması gerekir.
