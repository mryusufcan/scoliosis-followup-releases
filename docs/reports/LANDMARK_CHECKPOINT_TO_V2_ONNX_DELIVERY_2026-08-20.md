# Landmark Checkpoint → V2 ONNX Aday Paketi — Teslim Raporu

**Tarih:** 20 Ağustos 2026  
**Amaç:** Karantinadaki `model_last.pth` landmark checkpointini ONNX adayına dönüştürmek, PyTorch/ONNX çıktısını doğrulamak, örnek landmark test betiği sağlamak ve aktif uygulama modeline geçişi kabul kapılarıyla güvenli tutmak.

> Bu dönüşüm **teknik eşdeğerlik** kanıtıdır. Gerçek hasta görüntülerindeki landmark doğruluğunu veya Cobb ölçüm doğruluğunu doğrulamaz; klinik karar üretmez.

## Teslim edilen varlıklar

| Varlık | Konum | Durum |
|---|---|---|
| ONNX aday modeli | `.quarantine\landmark_lab\onnx_candidate\vertebra_landmarks_68.onnx` | Oluşturuldu; aktif değil. |
| ONNX dışa aktarma raporu | `onnx_export_report.json` | SHA-256, giriş/çıkış ve opset kaydedildi. |
| Eşdeğerlik raporu | `onnx_equivalence_report.json` | CPU üzerinde başarılı. |
| Örnek test | `example_landmark_test.py` | Sentetik veya ön işlenmiş `.npy` tensörü kabul eder; DICOM okumaz. |
| V2 aday paketi | `.quarantine\landmark_lab\v2_landmark_candidate` | Bilinçli olarak kabul edilmemiş, aktif değil. |
| Aktifleşme koruması | `ai/model_runtime.py` | Kabul edilmemiş V2 paketleri ve 68-landmark görevi mevcut dört noktalı Cobb runtime’ında engellenir. |

## Dönüşüm sözleşmesi

ONNX modeli sabit `float32 [1,3,1024,512]` girişini alır ve üç başlık döndürür:

| Çıktı | Şekil | Anlam |
|---|---|---|
| `hm` | `[1,1,256,128]` | Vertebra merkezi heatmap’i |
| `reg` | `[1,2,256,128]` | Merkez ofsetleri |
| `wh` | `[1,8,256,128]` | Dört vertebra köşesi için ofsetler |

Bu başlıklar karantina decoderı tarafından `17×11` satıra, ardından üstten alta sıralı `68×2` landmark dizisine dönüştürülür. Her vertebra için sıra **sol üst, sağ üst, sol alt, sağ alt** biçimindedir.

## Teknik doğrulama

| Denetim | Sonuç |
|---|---|
| Checkpoint yükleme | CPU üzerinde `weights_only=True` ile başarılı |
| ONNX kontrolü | ONNX opset 17 ile başarıyla dışa aktarıldı ve ONNX denetleyicisi geçti |
| PyTorch/ONNX giriş | Deterministik sentetik `1×3×1024×512` tensör |
| Ham başlık toleransı | En fazla `0.0002` mutlak fark sınırı içinde |
| Landmark toleransı | Decoder sonrası piksel koordinatında en fazla `0.0005` mutlak fark sınırı içinde |
| Decoder / landmark biçimi | `17×11` ve `68×2` doğrulandı |
| Modüler uygulama regresyonu | 131 test başarılı |

## V2 aday paketi neden etkinleştirilmedi?

Mevcut V2 kabul ön kontrolü, aktifleşmeden önce teknik bütünlüğün yanında kanıtlanmış veri/lisans ve hasta bazlı doğrulama ister. Aday paket bu koşullar eksik olduğu için tasarım gereği reddedilir:

| Eksik kapı | Neden |
|---|---|
| Ağırlık lisansı | Kaynak depodaki dış Google Drive ağırlığı için açık lisans belirtilmemiştir. |
| Veri seti lisansı | README kaynak veri setine atıf yapar; paket içinde yeniden kullanım/klinik kullanım hakkı doğrulanmış değildir. |
| Hasta bazlı ayrım | Landmark/Cobb doğrulaması için hasta bazlı ayrılmış değerlendirme seti yoktur. |
| Doğrulama metrikleri | Medyan landmark hatası ve Cobb MAE için izinli gerçek değerlendirme kanıtı yoktur. |
| Uygulama runtime uyumu | Mevcut `LocalCobbModel`, yalnızca dört noktadan oluşan Cobb son-plak taslağı görevini çalıştırır; yeni 68-landmark görevi için ayrı DICOM ön işleme ve landmark taslak runtime’ı gerekir. |

> Bu nedenle uygulamadaki model denetim ekranının “model kurulmamış” veya “kabul hazır değil” durumu bir hata değil, doğru güvenlik sonucudur.

## Örnek landmark test betiği

Laboratuvar kökünde şu komut ONNX modelini DICOM okumadan sentetik girdiyle test eder:

```powershell
$lab = '.quarantine\landmark_lab'
& "$lab\.venv\Scripts\python.exe" "$lab\example_landmark_test.py" `
  --onnx "$lab\onnx_candidate\vertebra_landmarks_68.onnx" `
  --report "$lab\onnx_candidate\example_landmark_report.json"
```

Gelecekte gözden geçirilmiş bir DICOM ön işleme modülü, yalnızca bellek içi görüntüden ürettiği sonlu `float32 [1,3,1024,512]` tensörü `.npy` biçiminde bu betiğe aktarabilir. Ham DICOM dosyası bu betik tarafından asla değiştirilmez veya açılmaz.

## Aktif uygulama modeline geçiş için sonraki teknik çalışma

1. DICOM uygunluk kapılarından geçen, tahribatsız **DICOM → üç kanallı model tensörü** adaptörü yazılmalıdır.
2. ONNX `hm/reg/wh` çıktısını `17×11 → 68×2` landmark taslağına dönüştüren, düşük güven ve geometri anomalilerini reddeden ayrı runtime eklenmelidir.
3. Landmarkların uzman tarafından düzenlenebildiği bir taslak ekranı kurulmalıdır; Cobb seçimi ve ölçüm kaydı ancak sonraki açık uzman onayı akışında gerçekleşmelidir.
4. İzinli hasta bazlı ayrılmış değerlendirme setiyle landmark hata ve Cobb MAE raporu hazırlanmalı, ağırlık/veri lisansları belgelendirilmelidir.
5. Bu kanıtlar sağlandığında V2 paket kabul ön kontrolü ancak **expert_review_poc** düzeyinde geçebilir; bu yine otomatik klinik karar veya otomatik kayıt yetkisi vermez.

## Geri yükleme noktası

`.restore_points\landmark_v2_active_gate_20260820_115531`

## Kaynaklar

[1] [yijingru/Vertebra-Landmark-Detection GitHub deposu](https://github.com/yijingru/Vertebra-Landmark-Detection)  
[2] [Kaynak depo README’si](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/README.md)  
[3] [MIT lisans metni](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/LICENSE)
