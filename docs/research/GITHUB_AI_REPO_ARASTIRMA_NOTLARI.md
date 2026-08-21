# GitHub Skolyoz AI Araştırma Notları

Bu notlar, dış kaynak kodunun doğrudan çalıştırılmayacağı; yalnızca lisans, mimari ve entegrasyon değerlendirmesi için incelendiği araştırma kaydıdır.

| Aday | Doğrulanan yaklaşım | Lisans / yeniden kullanım durumu | İlk değerlendirme |
|---|---|---|---|
| `mazurowski-lab/Scoliosis_project` | Segmentasyon, en eğik omur tespiti ve Cobb açı ölçümü için akademik derin öğrenme akışı; örnek vaka, eğitim ve çıkarım not defterleri, model ağırlığı bağlantısı bulunuyor. | GitHub sayfasında Apache-2.0 lisansı belirtiliyor. | Kod ve model sözleşmesinin ONNX/PySide6 adaptörüne çevrilmesi potansiyel olarak değerlendirilebilir; ağırlıklar ve veri lisansı ayrıca doğrulanmalı. |
| `Blankeos/scoliovis` | AP omurga röntgenlerinde Keypoint RCNN ile çoklu örnek anahtar nokta tespiti ve Cobb hesaplama. | Depoda `DISCLAIMER.md` ve “No License” ifadesi görülüyor; açık lisans görünmüyor. | Eğitim/veri akışı için fikir kaynağı olabilir; kod veya model ağırlığı projeye doğrudan alınmamalı. |
| `yijingru/Vertebra-Landmark-Detection` | ISBI 2020 çalışmasına dayanan omur-fokuslu landmark tespiti; değerlendirme ve Cobb hesaplama yardımcıları bulunuyor. | GitHub sayfasında MIT lisansı belirtiliyor. | En güçlü teknik aday: eski PyTorch/Python ortamını çalıştırmak yerine, landmark sözleşmesi ve değerlendirme mantığı ONNX odaklı mevcut adaptöre taşınmalı. |
| `zc402/Scoliosis` | Non-directional part-affinity field yaklaşımıyla omur landmarkı ve spinal eğrilik çıkarımı. | GitHub sayfasında GPL-3.0 lisansı belirtiliyor. | Mimari fikir ve test kriteri kaynağı olabilir; GPL etkisi nedeniyle kaynak kodu mevcut uygulamaya alınmamalı. |
| `farah-bermudez/cobb-angle-estimation` | AP omurga röntgenlerinde 17 torakal/lomber omurun 68 köşe noktasını YOLOv11-Pose ile tespit edip üç Cobb açısı hesaplıyor. | Depo MIT lisanslı; ancak önerilen Ultralytics bağımlılığı AGPL-3.0 ve ticari kullanım için ayrı lisans bildiriyor. | Güncel bir konsept referansı; PyTorch/Ultralytics bağımlılık ve lisans etkisi nedeniyle mevcut uygulamaya doğrudan eklenmemeli. Model mimarisi ancak bağımsız ONNX çıkarımı ve ayrı lisans doğrulamasıyla değerlendirilebilir. |

## Güvenlik ve klinik sınır

Her aday, yalnızca **taslak ölçüm önerisi** üretecek şekilde ele alınmalıdır. Kullanıcı doğrulaması, dört noktalı görsel kanıt, ölçüm provenance bilgisi, model sürümü ve güven eşiği korunmadan klinik kullanım akışına eklenmeyecektir.

## Öncelik kararı

`mazurowski-lab/Scoliosis_project`, Apache-2.0 lisansı ve açık model ağırlığı bağlantısı nedeniyle lisans açısından değerlendirilebilir olsa da Python 3.8, PyTorch 1.7 ve MMDetection 2.16 gibi eski bağımlılıklara dayanır. Bu kodun çalıştırılması veya bağımlılıklarının masaüstü uygulamaya alınması önerilmez. `yijingru/Vertebra-Landmark-Detection` MIT lisanslıdır; ancak Python 3.6 ve PyTorch 1.1 tabanlıdır. Bu nedenle doğrudan entegrasyon yerine, landmark hedefi, veri şeması ve hata ölçümü mantığı **referans alınarak** modern, izole ve ONNX tabanlı bir adapter oluşturulmalıdır.

Model ağırlıkları, veri lisansı ve uyumluluğu ana depodaki kod lisansından bağımsız olarak doğrulanmadıkça indirilmeyecek veya çalıştırılmayacaktır.

## Kaynaklar

1. https://github.com/mazurowski-lab/Scoliosis_project
2. https://github.com/Blankeos/scoliovis
3. https://github.com/yijingru/Vertebra-Landmark-Detection
4. https://github.com/zc402/Scoliosis
5. https://github.com/farah-bermudez/cobb-angle-estimation
6. https://github.com/ultralytics/ultralytics
