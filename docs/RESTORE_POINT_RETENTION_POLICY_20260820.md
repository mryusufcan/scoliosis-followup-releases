# Restore Point Retention Politikası

## Varsayılan politika

Restore point bakımı artık aşağıdaki kurallara göre raporlanır:

| Kural | Varsayılan değer | Davranış |
|---|---:|---|
| Son gün koruması | 7 gün | Son 7 gün içinde oluşturulan tüm restore point'ler korunur. |
| Minimum son kayıt sayısı | 10 | Tarihi daha eski olsa bile en yeni 10 restore point korunur. |
| Otomatik silme üst sınırı | 500 MiB | Bu boyutu aşan restore point'ler otomatik silme adayı olmaz; manuel inceleme gerekir. |
| Varsayılan çalışma modu | Dry-run | Hiçbir dosya silinmez; JSON raporu üretilir. |

Bu politika, özellik geliştirmeleri sırasında oluşturulan güncel restore point'leri korur ve gelecekte eski/küçük restore point'lerin birikmesini raporlayabilir. Büyük deneysel veya model içeren restore point'ler otomatik silinmez.

## Kullanım

Proje kökünden dry-run çalıştırmak için:

```powershell
Set-Location 'C:\Users\yusuf\Desktop\Scoliosis Follow Up'
python scripts\maintenance\restore_point_retention.py `
  --keep-days 7 `
  --keep-last 10 `
  --max-auto-delete-mib 500 `
  --report docs\restore_point_retention_dry_run.json
```

Alternatif olarak `scripts\maintenance\Restore_Point_Retention.bat` dosyası çalıştırılabilir. Bu batch dosyası da yalnızca dry-run yapar ve kullanıcıya rapor yolunu gösterir.

## Silme davranışı

Bakım aracında silme, iki ayrı koşul olmadan gerçekleşmez:

```powershell
python scripts\maintenance\restore_point_retention.py `
  --keep-days 7 `
  --keep-last 10 `
  --max-auto-delete-mib 500 `
  --apply `
  --confirm RETENTION_SIL
```

`--apply` verilmezse yalnızca rapor üretilir. `--apply` verilse bile `--confirm RETENTION_SIL` eksikse işlem durur. Büyük restore point'ler `large_protected` olarak raporlanır ve otomatik silinmez.

## İlk dry-run sonucu

20 Ağustos 2026 tarihli ilk dry-run sonucunda 32 restore point incelendi. Hepsi son 7 gün içinde oluşturulduğu veya retention kurallarıyla korunduğu için otomatik silme adayı oluşmadı:

```text
Toplam: 32 | Korunan: 32 | Aday silme: 0 | Aday alan: 0.00 MiB
```

Bu sonuç beklenmektedir; retention aracı mevcut güncel restore point'leri silmez. Eski restore point'ler ilerleyen günlerde retention süresi dışına çıktığında küçük olanlar `candidate_delete`, büyük olanlar `large_protected` olarak raporlanacaktır.

## Koruma sınırları

Araç yalnızca `.restore_points` altındaki doğrudan alt klasörleri sınıflandırır. `.quarantine`, `dev_data`, `resources`, SQLite verileri, DICOM kaynakları ve proje kaynak kodu bu araç tarafından hedeflenmez. Yıkıcı uygulama öncesinde JSON raporu ve kullanıcı onayı incelenmelidir.
