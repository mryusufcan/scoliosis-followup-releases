# Scoliosis Follow-Up 1.7.6

1.7.6, birleştirilmiş DICOM görüntülerinin doğru parlaklıkla yeniden açılmasını sağlayan ve proje bakım/yayın yapısını sadeleştiren bakım sürümüdür.

## Düzeltmeler

- PNG ile birlikte kaydedilen 8-bit DICOM çıktılara doğru `WindowCenter`, `WindowWidth`, rescale ve VOI LUT bilgileri eklendi.
- Pencere bilgisi bulunmayan eski 8-bit DICOM dosyalarının görüntüleyicide aşırı karanlık açılması giderildi.
- Etiketsiz 8-bit görüntüler için güvenli `WL 127.5 / WW 255` varsayılanı eklendi.

## Proje ve paketleme

- PyInstaller spec dosyası `packaging` altında toplandı ve bilgisayara özel mutlak yollar kaldırıldı.
- Proje araçları ve eski bakım kısayolları ilgili `tools` ve `scripts/maintenance` klasörlerine taşındı.
- Proje kökü sadeleştirilirken başlatma, Project Control Center, güvenlik denetimi ve kaynak arşivleme yolları güncellendi.
- Yeniden üretilebilir build/cache çıktıları ve eski yerel yayın kopyaları temizlendi; aktif modeller ve araştırma kaynakları korundu.

## Doğrulama

- Windows installer başarıyla üretildi.
- Installer SHA-256 özeti imzalı `update.json` ile eşleşti.
- GitHub'a yüklenen `update.json` yerel imzalı dosyayla birebir doğrulandı.
- `1.7.6` GitHub Releases üzerinde kararlı ve `latest` sürüm olarak yayımlandı.
