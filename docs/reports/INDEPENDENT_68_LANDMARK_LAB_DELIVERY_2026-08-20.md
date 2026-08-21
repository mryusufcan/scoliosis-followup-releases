# Bağımsız 68-Landmark Laboratuvarı — Teslim Raporu

**Tarih:** 20 Ağustos 2026  
**Hedef:** `yijingru/Vertebra-Landmark-Detection` kaynak modelini ana Scoliosis Follow-Up uygulamasından bağımsız olarak Windows üzerinde çalıştırmak ve 17 vertebra adayı üzerinden 68 landmark üretim sözleşmesini teknik olarak doğrulamak.

> Bu çalışma bir **teknik landmark duman testidir**. Tanı, tedavi önerisi, klinik doğruluk iddiası veya otomatik Cobb kaydı üretmez.

## Sonuç özeti

| Alan | Sonuç |
|---|---|
| Kaynak depo | `yijingru/Vertebra-Landmark-Detection`, sabit commit: `b9fc05c215ea2b006564a3feb509634183a63f82`. |
| Kod lisansı | Depoda MIT lisansı bulunuyor. Ağırlıklar ve kaynak veri seti için ayrı ve açık bir yeniden dağıtım/klinik kullanım lisansı depoda görünmüyor. [1] [2] |
| Deneme ortamı | Ana uygulamadan ayrık Python 3.8.10 laboratuvarı; PyTorch 2.1.2 CPU; GPU yoluna güvenilmedi. |
| Ağırlık | README’nin işaret ettiği paylaşılmış `weights.zip` karantinaya alındı; arşiv ve dosya SHA-256 özetleri kaydedildi. [2] |
| Güvenli checkpoint denetimi | Pickle biçimli `model_last.pth`, yalnızca `torch.load(..., weights_only=True, map_location="cpu")` ile incelendi. Kaynak repo import edilmedi, model kurulmadı, DICOM açılmadı. |
| Bağımsız model smoke | Ağırlıklar CPU’da güvenli yükleme kısıtıyla, ön eğitimli ağ indirmesi kapalı olarak test edildi. Sentetik `1×3×1024×512` girişte ağ başlıkları ve decoder doğrulandı. |
| Çıktı | `17×11` decoder satırı → üstten alta sıralı `68×2` landmark. |
| Ana uygulama | Model **etkinleştirilmedi**, EXE’ye eklenmedi ve AI Model Paketi Denetimi ekranında görünmesi beklenmiyor. |

## Karantina ve bütünlük kayıtları

| Varlık | Yol / Değer |
|---|---|
| Kaynak karantinası | `.quarantine\Vertebra-Landmark-Detection_b9fc05c` |
| Laboratuvar | `.quarantine\landmark_lab` |
| Kaynak arşivi SHA-256 | `B380729E6892D2B8959A2041439EC6E2DC238292B8ABAE6471BF70E5613F218` |
| Ağırlık arşivi SHA-256 | `1B088004614C09AD6605F444C39B160144B07704B58BAE13F21DD19665D7A1D2` |
| `model_last.pth` SHA-256 | `6A779E01B9A41601334E0A9541278FC557A95BD650C6C8DE311204821509D19B` |
| Checkpoint içeriği | `epoch=25`; 270 `state_dict` tensör girdisi |

## Teknik çıktı sözleşmesi

Kaynak model, tek merkez heatmap’i ile dört köşe ofsetini birleştirir. Decoder, 17 satır üretir. Her satır şu biçimdedir:

```text
cen_x, cen_y,
tl_x, tl_y,
tr_x, tr_y,
bl_x, bl_y,
br_x, br_y,
score
```

Her vertebranın dört köşesi sırasıyla **sol üst, sağ üst, sol alt, sağ alt** olarak alınır. Üstten alta sıralanmış 17 vertebra × 4 köşe ile 68 landmark üretilir. `landmark_contract.py`, şekil, sonlu sayı ve 0–1 güven kontrolü yapar; 4 otomatik sözleşme testi başarılıdır.

## Doğrulama sonuçları

| İşlem | Sonuç |
|---|---:|
| Karantina kaynakları için Python 3.8 sözdizimi derlemesi | 18 dosya başarılı |
| Güvenli checkpoint denetimi | Başarılı |
| CPU `17×11 → 68×2` landmark duman testi | Başarılı |
| Landmark sözleşmesi testleri | 4/4 başarılı |
| DICOM erişimi | Yok |
| Model `forward()` çağrısı | Yalnızca sentetik tensör üzerinde, ana uygulama dışında yapıldı |
| Ana uygulama / EXE değişikliği | Yok |

## Neden ana uygulamadaki model ekranı hâlâ “kurulmamış” görünüyor?

Uygulamadaki mevcut AI ekranı, güvenli V2 **ONNX** paket sözleşmesini arar. Bu deneme modeli ise PyTorch `.pth` checkpoint biçimindedir ve henüz gerçek DICOM ön işleme, landmark kalite kapıları, ONNX dönüştürmesi, model kartı, doğrulama raporu ve uzman onaylı POC paketi aşamalarından geçmemiştir. Bu nedenle etkin model klasörüne kopyalanmadı; ekranın “model kurulmamış” durumu doğru ve güvenlidir.

## Cobb taslağına geçmek için zorunlu sonraki koşullar

| Sıra | Zorunlu çalışma | Güvenlik sınırı |
|---:|---|---|
| 1 | DICOM → model girdisi adaptörü | DICOM yalnızca bellek içinde, tahribatsız okunur; modalite/projeksiyon/çok-kare/piksel geçerliliği mevcut kalite kapılarından geçer. |
| 2 | İzinli veya sentetik dışı olmayan test seti üzerinde landmark kalite kontrolü | Gerçek hasta verisi için kurum izni ve veri yönetişimi gerekir. |
| 3 | Landmark → end vertebra → Cobb taslak adaptörü | Önce tek/çok eğri belirsizliği ve düşük güven durumları reddedilir. |
| 4 | ONNX veya güvenli yerel runtime paketi | Manifest, hash, model kartı, ağırlık lisansı ve hasta bazlı doğrulama raporu zorunludur. |
| 5 | Uygulama içi AI taslağı | Kullanıcı landmarkları düzeltebilir; yalnızca uzman onayıyla ölçüm kayda dönüşebilir. |

> 68 noktanın teknik olarak üretilmiş olması, görüntüde doğru anatomik noktaları bulduğu veya Cobb açısının klinik olarak doğru olduğu anlamına gelmez. Bu doğruluk, izinli ayrılmış bir değerlendirme seti ve uzman incelemesiyle ayrıca gösterilmelidir.

## Geri yükleme noktaları

| Tür | Yol |
|---|---|
| Adapter öncesi | `.restore_points\landmark_contract_20260820_114630` |
| Son laboratuvar sürümü | `.restore_points\landmark_lab_final_20260820_114729` |

## Kaynaklar

[1] [yijingru/Vertebra-Landmark-Detection GitHub deposu](https://github.com/yijingru/Vertebra-Landmark-Detection)  
[2] [Kaynak depo README’si](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/README.md)  
[3] [MIT lisans metni](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/LICENSE)  
[4] [Vertebra-Focused Landmark Detection for Scoliosis Assessment, arXiv](https://arxiv.org/pdf/2001.03187.pdf)
