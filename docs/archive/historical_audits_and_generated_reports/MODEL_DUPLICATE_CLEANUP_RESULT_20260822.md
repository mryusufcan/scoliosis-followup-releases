# Model Duplicate Temizliği Sonucu

**Tarih:** 22 Ağustos 2026  
**İşlem:** SHA-256 ile doğrulanmış quarantine model tekrarlarının temizlenmesi  
**Kapsam:** Yalnızca 6 birebir kopya; `.venv`, aktif resources modelleri ve benzersiz adaylar korunmuştur.

## Disk kazanımı

| Ölçüm | Temizlik öncesi | Temizlik sonrası | Fark |
|---|---:|---:|---:|
| `.quarantine` | 8.570,35 MiB | **7.547,42 MiB** | **1.022,93 MiB** |
| Yaklaşık GiB | 8,37 GiB | **7,37 GiB** | **yaklaşık 1,00 GiB** |
| Dosya sayısı | 56.937 | **56.931** | **6 dosya** |

Silinen 6 dosyanın tamamı aktif model veya aynı quarantine hash grubundaki birebir kopyaydı. Aktif modellerin bulunduğu `resources\ai` alanı değişmedi.

## Korunan alanlar

İki deneysel sanal ortam korunmuştur:

- `.quarantine\mazurowski_scoliosis_project\.venv`: yaklaşık 4.628,12 MiB.
- `.quarantine\landmark_lab\.venv`: yaklaşık 1.488,45 MiB.

Benzersiz ONNX adayları, `model_last.pth`, `weights.zip`, canonical `epoch_24.pth`, aktif Mazurowski ONNX modeli ve aktif 68-landmark ONNX modeli korunmuştur.

## Son doğrulama

Temizlik sonrasında `.venv` ile aşağıdaki kapılar başarıyla tamamlanmıştır:

```text
compileall: başarılı
UI_THEME_SMOKE_OK
182 passed, 5 warnings
```

Qt font dizini hakkında bir uyarı ve pydicom/openjpeg tarafında Python 3.15 deprecation uyarıları görüldü; bunlar test başarısını etkilemedi. Temizlik işlemi DICOM piksel verisini, metadata’yı, SQLite tablolarını veya uygulama kodunu değiştirmemiştir.

## Sonraki adaylar

Bir sonraki büyük alan adayları hâlâ deneysel Mazurowski `.venv` alanı, landmark `.venv`, benzersiz ONNX adayları, eski release paketleri ve `.restore_points` ZIP’leridir. Bu alanlar duplicate temizliğinden farklı olarak benzersiz veya geri alma amaçlı içerik taşıdığı için yeniden kurulum/checksum/arşiv doğrulaması olmadan silinmemelidir.
