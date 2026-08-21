# V2 ONNX Model Paketi Şablonu

Bu klasör yeni bir yerel ONNX modelinin **çalıştırılmadan önce** hangi dosyaları ve açıklamaları taşıması gerektiğini gösterir. `model.onnx` şablona dahil değildir. Gerçek model dosyası yalnızca lisansı, model kaynağı, ağırlık hakları ve veri kullanım koşulları belgelenmişse eklenmelidir.

Paket klasöründe şu dosyalar bulunmalıdır:

| Dosya | Görev |
|---|---|
| `manifest.json` | Model kimliği, bütünlük özeti, giriş-çıkış sözleşmesi ve model kartı |
| `model.onnx` | Yerel ONNX dosyası |
| `validation_report.json` | Hasta bazlı ayrılmış doğrulama, veri yönetişimi ve inceleme bilgisi |

Şablonlardaki `replace-with-...` alanları doldurulmadan paket kabul edilmez. Modeli indirmeden veya çalıştırmadan denetlemek için aşağıdaki komut kullanılabilir:

```powershell
python tools/validate_ai_model_package.py C:\model_paketi --json
```

Başarılı sonuç yalnızca modelin **uzman incelemeli POC** için teknik olarak hazır olduğunu gösterir. Uygulama her sonuçta taslak üretir; klinik ölçüm kaydı için uzman onayı gerekir.
