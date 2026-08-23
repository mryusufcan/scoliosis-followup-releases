# Proje Klasörü Sadeleştirme

**Tarih:** 22 Ağustos 2026  
**Amaç:** Windows Explorer’da proje kökünü daha anlaşılır hale getirmek ve teknik/yerel alanları ana kaynak görünümünden ayırmak.

## Yeni görünüm

Kök dizinde kullanıcı için temel alanlar görünür bırakıldı:

- `README.md`
- `main.py`
- `modular_app`
- `ai`
- `dicom`
- `pacs`
- `anonymization`
- `resources`
- `tests`
- `scripts`
- `tools`
- `packaging`
- `requirements.txt`
- `VERSION`
- `ScoliosisFollowUp.spec`
- `Uygulamayi_Baslat.bat`
- `.gitignore`

Yerel, teknik veya yeniden üretilebilir alanlar Windows’ta gizlendi; dosyalar silinmedi:

- `.quarantine`
- `.restore_points`
- `.venv`
- `.venv-build`
- `build`
- `dist`
- `installer`
- `releases`
- `artifacts`
- `project_archives`
- `security_keys`
- `dev_data`
- `project_control_center.py`
- `Proje_Temizlik_Merkezi_v2.bat`
- `guncel_proje_zip.bat`
- `Proje_Araclari.bat`
- `requirements-dev.txt`

## Görünürlük kontrolü

Görünürlük işlemi `scripts\maintenance\Proje_Gorunurluk.bat` ile yapılır. Varsayılan çağrı teknik alanları gizler:

```powershell
scripts\maintenance\Proje_Gorunurluk.bat
```

Tüm alanları yeniden göstermek için:

```powershell
scripts\maintenance\Proje_Gorunurluk.bat show
```

Bu işlem yalnızca Windows dosya attribute’larını değiştirir. Kaynak kod, DICOM, SQLite, model veya restore point içeriği değiştirilmez.

## Klasör görevleri

`README.md` kök dizine eklendi ve temel dosyaların görevlerini, çalıştırma komutlarını, test akışını ve güvenlik uyarılarını açıklıyor. Böylece kullanıcı Explorer’da yalnızca klasör adlarına bakarak hangi alanın kaynak, test, paketleme veya bakım amacı taşıdığını anlayabilir.

## Geri alma noktası

Yapılandırma ve yol dosyaları şu restore point’e kopyalandı:

```text
.restore_points\project_structure_cleanup_20260822
```

Kopyalanan dosyalar `.gitignore`, `ScoliosisFollowUp.spec`, `modular_app\config\paths.py` ve görünürlük betiğinin düzeltme öncesi sürümüdür.

## Bilinen sınır

Windows Explorer’da “Gizli öğeler” seçeneği açıksa gizlenen klasörler yine görülebilir. Bu normaldir. Görünürlük betiği tekrar çalıştırılarak görünüm her zaman geri alınabilir.
