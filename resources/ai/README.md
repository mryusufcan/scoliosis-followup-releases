# Yerel AI Cobb modeli

Uygulama bir modeli otomatik indirmez ve DICOM görüntülerini internete
göndermez. Doğrulanmış model kurulacaksa aşağıdaki iki dosya aynı klasöre
yerleştirilir:

```text
resources/ai/vertebra_cobb/
    manifest.json
    model.onnx
```

`manifest.example.json`, desteklenen sözleşmenin örneğidir. Model çıktısı
`[1, 4, 3]` veya `[4, 3]` biçiminde olmalıdır. Her satır sırasıyla normalize
`x`, normalize `y` ve güven değeridir. İlk iki nokta üst, son iki nokta alt
son-plağı temsil eder. Koordinatlar soldan sağa sıralanmalıdır.

Modelin SHA-256 özeti `manifest.json` içinde doğru değilse uygulama modeli
çalıştırmaz. Eğitim/verifikasyon bilgisi bulunmayan model klinik kullanım için
uygun kabul edilmez. AI sonucu yalnızca doğrulanmamış taslak olarak gösterilir;
ölçüm geçmişine otomatik kaydedilmez.
