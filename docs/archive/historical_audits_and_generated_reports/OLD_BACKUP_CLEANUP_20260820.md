# Eski Restore Point Temizliği — 20 Ağustos 2026

## Uygulanan politika

Proje içindeki restore point'ler tarih, adlandırma ve boyut açısından incelendi. **48 saatten eski ve açıkça manual sürüm snapshot'ı olan** iki yedek temizlendi. Son iki gün içinde oluşturulan özellik restore point'leri, aynı gün oluşturulan büyük deneysel yedek ve `releases\1.6.0` dağıtım arşivi korunmuştur.

| Silinen restore point | Boyut | Gerekçe |
|---|---:|---|
| `.restore_points\manual_20260817_232019_v1.5.1` | 101,66 MiB | Eski v1.5.1 manual snapshot; güncel 1.6.0 release arşivi mevcut. |
| `.restore_points\manual_20260818_000432_v1.6.0` | 101,71 MiB | 48 saatten eski manual v1.6.0 snapshot; aynı sürümün dağıtım arşivi mevcut. |
| **Toplam geri kazanım** | **203,37 MiB** |  |

Silme öncesi envanter `docs\restore_point_inventory_20260820.json`, silme hedefleri ve politika ise `docs\old_restore_cleanup_manifest_20260820.json` içinde kaydedilmiştir.

## Son durum

Eski yedekler temizlendikten ve test çalışmaları sırasında yeniden oluşan `build`/`dist` çıktıları tekrar kaldırıldıktan sonra proje klasörü **5.066,26 MiB** ve 68.339 dosya olarak ölçüldü.

| Kalan büyük alan | Boyut | Karar |
|---|---:|---|
| `.quarantine` | 1.854,92 MiB | Korundu; deneysel landmark laboratuvarı ve model adayları içeriyor. |
| `.restore_points` | 1.609,21 MiB | Korundu; güncel geri alma noktaları ve büyük aynı-gün deneysel restore point mevcut. |
| `.venv-build` | 940,91 MiB | Korundu; Windows PyInstaller/codec paketleme ortamı. |
| `releases` | 446,67 MiB | Korundu; 1.6.0 installer ve release ZIP arşivi. |
| `dev_data` | 99,42 MiB | Korundu; DICOM kabul ve benchmark verileri. |
| `resources` | 93,40 MiB | Korundu; uygulama kaynakları ve deneysel model. |
| `build`, `dist`, `installer` | Yok | Yeniden üretilebilir çıktılar temizlendi. |

## Doğrulama

Restore point silme işleminden sonra kaynak `py_compile`, tema smoke testi ve regresyon testleri çalıştırıldı. Sonuçlar: **146/146 test başarılı**, `UI_THEME_SMOKE_OK` ve `PY_COMPILE_OK`. Font dizini uyarısı smoke testini başarısız kılmadı.

Testler sırasında PyInstaller/uygulama test akışının oluşturduğu `build` ve `dist` klasörleri final ölçümden önce tekrar kaldırılmıştır. Bu nedenle dağıtım doğrulaması yeniden paketleme sonrasında çalıştırılmalıdır; dağıtım arşivi `releases\1.6.0` içinde korunmaktadır.

## Sonraki güvenli optimizasyon adayları

En yüksek tasarruf potansiyeli `.quarantine\landmark_lab\.venv` klasöründedir; tek başına yaklaşık 1.488 GiB yer kaplar. Bu alan uygulama runtime'ı değil, deneysel landmark laboratuvarının sanal ortamıdır. Silmeden önce deneyin tekrar üretilebilir olduğuna ve gerekli Python paketlerinin `requirements.txt` veya ayrı bir deney gereksinim dosyasında tanımlı olduğuna bakılmalıdır.

İkinci büyük aday, `.restore_points\landmark_lab_adapter_20260820_114227` içindeki yaklaşık 1.6 GiB'lık aynı-gün restore point'tir. Bu restore point `.quarantine` ve deneysel sanal ortamın büyük bir kopyasını içeriyor. Bu alanı silmek 1.6 GiB daha kazandırabilir; ancak aktif deneysel landmark çalışmasının geri alma kopyası olduğu için ayrı onay veya harici arşivleme olmadan temizlenmemiştir.

`.venv-build` yaklaşık 941 MiB'tır ve paketleme yapılmayacak dönemlerde dışarı taşınabilir veya silinebilir. Ancak silinirse Windows release üretiminden önce build ortamının yeniden kurulması gerekir. `releases\1.6.0`, `dev_data` ve `resources` ise doğrudan silinmemelidir.
