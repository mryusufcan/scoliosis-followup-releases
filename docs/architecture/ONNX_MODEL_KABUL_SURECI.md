# ONNX Model Kabul Süreci

Bu uygulama, model dosyasını internetten indirmez ve model paketini kullanıcı onayı olmadan değiştirmez. Yeni bir ONNX model dosyası uygulamaya eklenmeden önce teknik kabul ön kontrolünden geçirilir.

> Ön kontrolün başarılı olması modelin tanı koyduğu, tedavi önerdiği veya klinik olarak genel kullanıma hazır olduğu anlamına gelmez. Başarılı sonuç yalnızca modelin **uzman incelemeli yerel POC** için teknik pakete sahip olduğunu gösterir.

## Kabul sırası

| Adım | Kontrol | Başarısızlıkta davranış |
|---:|---|---|
| 1 | `manifest.json` V2 sözleşmesine uyuyor mu? | Paket reddedilir; model çalıştırılmaz |
| 2 | ONNX dosyası mevcut mu ve SHA-256 özeti manifest ile aynı mı? | Paket reddedilir; model çalıştırılmaz |
| 3 | Kaynak, commit, kod/ağırlık/veri lisansları belirtilmiş mi? | Paket reddedilir |
| 4 | `validation_report.json` hasta bazlı ayrılmış doğrulamayı, veri yönetişimini ve inceleyen kişiyi içeriyor mu? | Paket reddedilir |
| 5 | Landmark ve Cobb hata metrikleri girilmiş mi? | Paket reddedilir |
| 6 | Uygulama içi AI taslağı dört noktalı geometri ve DICOM uygunluk kapılarından geçiyor mu? | Taslak oluşturulmaz |
| 7 | Hekim/Yönetici taslağı onaylıyor mu? | Onay yoksa ölçüm kaydedilmez |

## Paket dosyaları

| Dosya | Açıklama |
|---|---|
| `model.onnx` | Yerel model dosyası. Modeli çalıştırmadan önce hash ile doğrulanır. |
| `manifest.json` | Model sürümü, bütünlük özeti, model kartı, kaynak ve lisans bilgileri. |
| `validation_report.json` | Hasta bazlı doğrulama, veri yönetişimi, inceleyen kişi ve ölçüm metrikleri. |
| `acceptance_result.json` | İsteğe bağlı; ön kontrol komutunun oluşturduğu teknik kabul kaydı. |

## Yerel ön kontrol komutu

```powershell
python tools/validate_ai_model_package.py C:\model_paketi --json --output C:\model_paketi\acceptance_result.json
```

Komut model çıkarımı yapmaz ve DICOM verisi okumaz. Yalnızca manifest, ONNX dosyası, hash ve doğrulama raporunu yerelde denetler.

## Uygulama içindeki kontrol

**Gelişmiş → AI Model Paketini Denetle** ekranı, modelin durumu ile model kartını gösterir. V2 paketlerde kabul ön kontrol sonucu ve doğrulama raporundaki mevcut metrikler de görünür. Hata varsa uygulama modelin neden POC için hazır olmadığını metinle belirtir.
