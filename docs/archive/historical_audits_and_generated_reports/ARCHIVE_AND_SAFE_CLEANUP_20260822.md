# Legacy Arşivleme ve Güvenli Cache/Log Temizliği

**Tarih:** 22 Ağustos 2026  
**Durum:** Arşivleme tamamlandı; onaylanan cache/log temizliği uygulandı. Kök geçici dosyalar için ayrıca dry-run varsayılanlı güvenli betik hazırlandı.

## Yapılan düzenlemeler

`scripts\maintenance` içindeki 11 tarihsel migration/stitching betiği şu klasöre taşındı:

```text
project_archives\legacy_maintenance_20260822
```

Bunlar günlük uygulama, test veya Proje Kontrol Merkezi akışında çağrılan güncel araçlar değildir. Orijinal dosyalar silinmedi; taşınmadan önce şu restore point’e kopyalandı:

```text
.restore_points\legacy_audit_organization_20260822
```

Eski proje boyutu, release, quarantine, restore point ve model denetim JSON’ları şu arşive taşındı:

```text
docs\archive\audits\2026-08
```

Arşiv klasörlerine içerik ve geri kullanım uyarılarını açıklayan `README.md` dosyaları eklendi.

## Güvenli cache/log betiği

Şu dosyalar oluşturuldu:

```text
scripts\maintenance\safe_cache_log_cleanup.py
scripts\maintenance\Temizle_Cache_ve_Test_Loglari.bat
```

Betiğin tarama kapsamı altındaki `__pycache__`, `.pytest_cache`, `.mypy_cache` ve `.ruff_cache` klasörlerini içerir. Ayrıca 14 günden eski ve adında `test`, `pytest`, `smoke`, `validation`, `benchmark` veya `acceptance` bulunan `.log`, `.txt` ve `.out` dosyalarını aday olarak raporlar.

`.git`, sanal ortamlar, quarantine, restore point, build/dist/installer/release ve security key alanları tarama dışında tutulur. Varsayılan çalışma dry-run’dır.

## Dry-run sonucu

| Aday türü | Sayı | Boyut |
|---|---:|---:|
| Cache klasörü | **23** | **2,58 MiB** |
| Eski test logu | **0** | 0 MiB |
| Toplam | **23** | **2,58 MiB** |

Dry-run raporu:

```text
docs\generated_cleanup_dry_run_20260822.json
```

Silme işlemini uygulamak için açık onay gereklidir:

```powershell
scripts\maintenance\Temizle_Cache_ve_Test_Loglari.bat --apply --confirm CLEAN_GENERATED_OUTPUTS
```

Onay olmadan `--apply` çalıştırıldığında betik silme yapmadan durur; bu güvenlik kapısı ayrıca doğrulandı.

## Uygulanan cache/log temizliği

Kullanıcının açık onayıyla şu komut çalıştırıldı:

```powershell
scripts\maintenance\Temizle_Cache_ve_Test_Loglari.bat --apply --confirm CLEAN_GENERATED_OUTPUTS
```

Sonuç olarak **23 cache klasörü ve toplam 2,58 MiB** silindi. Bu taramada eski test logu adayı bulunmadı. Uygulama sonrasında test/derleme araçlarının yeniden oluşturacağı `__pycache__` dosyaları normaldir ve bir sonraki cache bakımında tekrar aday olabilir.

İlk uygulama raporu:

```text
docs\generated_cleanup_applied_20260822.json
```

Tam derleme ve testlerden sonra oluşan cache’ler için aynı açık onayla ikinci uygulama da yapıldı. Bu ikinci turda **23 cache klasörü / 2,57 MiB** daha temizlendi; eski test logu yine **0** idi. Nihai uygulama raporu:

```text
docs\generated_cleanup_applied_post_validation_20260822.json
```

## Kök geçici dosya betiği

Kök dizinde kaynak veya dağıtım akışını etkilemeden bilinen geçici envanter/cleanup çıktıları ile kök `__pycache__` klasörünü aday olarak raporlayan yeni araçlar eklendi:

```text
scripts\maintenance\safe_root_temp_cleanup.py
scripts\maintenance\Temizle_Kok_Gecici_Dosyalar.bat
```

Bu araç `build`, `dist`, `installer`, `releases`, sanal ortamlar, quarantine, restore point, kaynak klasörleri, testler, dokümantasyon ve güvenlik anahtarlarını silmez. Varsayılan çalışma dry-run’dır. İlk taramada **0 aday / 0 MiB** bulundu. Gerçek silme için ayrı ve açık onay gerekir:

```powershell
scripts\maintenance\Temizle_Kok_Gecici_Dosyalar.bat --apply --confirm CLEAN_ROOT_TEMP
```

Onay kapısı ayrıca test edildi ve onaysız `--apply` reddedildi. Son taramada kök dizinde **0 aday / 0 MiB** bulundu; güncel rapor:

```text
docs\root_temp_cleanup_dry_run_post_validation_20260822.json
```

Betik eklenmeden önce mevcut maintenance klasörü şu restore point’e yedeklendi:

```text
.restore_points\root_cleanup_script_20260822
```

## Doğrulama

Arşivleme, uygulanan cleanup ve son doğrulamalar sonrasında:

```text
compileall: başarılı
UI_THEME_SMOKE_OK
182 passed, 5 warnings

Not: Tam test koşusu cache klasörlerini yeniden oluşturduğu için testten sonra ikinci cleanup turu ayrıca çalıştırıldı.
```

Uyarılar PySide6 font dizini ve pydicom/openjpeg deprecation bildirimleridir; testleri başarısız yapmadı. Güncel `scripts\build`, `scripts\release`, `scripts\admin`, `packaging`, `tools`, ana uygulama modülleri ve Proje Kontrol Merkezi yerinde bırakıldı.

## Geri alma

Taşınan legacy dosyalar `project_archives\legacy_maintenance_20260822` altında, taşınmadan önceki kopyalar ise `.restore_points\legacy_audit_organization_20260822` altında bulunur. Audit raporları `docs\archive\audits\2026-08` altından tekrar üst `docs` klasörüne taşınabilir. Cache/log temizliği için `--apply` kullanılmadığı sürece dosyalar korunur.
