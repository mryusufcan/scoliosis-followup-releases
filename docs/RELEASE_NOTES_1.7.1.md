# Scoliosis Follow-Up 1.7.1

Yayın tarihi: 21 Ağustos 2026

## Yenilikler

- Mazurowski Lab omurga maskeleme modeli Docker bağımlılığından çıkarılarak taşınabilir ONNX Runtime ile uygulamaya dahil edildi.
- AI analizi tamamen yerel ve çevrimdışı çalışacak biçimde güncellendi; görüntüler bilgisayar dışına gönderilmez.
- AI Cobb sonucu yalnızca taslak olarak gösterilir; otomatik kayıt kapalıdır ve kaydetme öncesinde Hekim rolüyle uzman onayı zorunludur.
- AI analizi arka plan iş parçacığına taşındı; uzun analiz sırasında arayüzün “Yanıt Vermiyor” durumuna geçmesi önlendi.
- ONNX model bütünlüğü, güven eşiği, DICOM uygunluğu ve çizgi geometrisi kontrolleri eklendi.
- AI tanjant çizgileri omurga çevresinde daha okunabilir uzunlukta gösterilecek şekilde düzenlendi.
- Uygulama içi AI yardım metinleri ve çalışma durumu Docker gerektirmeyen yeni yapıya göre güncellendi.
- SciPy çalışma bağımlılığı ve ONNX modelinin Windows dağıtım paketine dahil edilmesi sağlandı.

## Güvenlik ve kullanım sınırları

- AI çıktısı tanı veya otomatik klinik ölçüm değildir.
- AI çizgileri ve Cobb değeri yetkili hekim tarafından görüntü üzerinde doğrulanmadan kaydedilemez.
- Harici model ağırlıklarının veri/ağırlık lisansı kaynak depoda açıkça belirtilmediği için ilgili uyarı korunur.
- Uygun olmayan veya düşük güvenli görüntüler güvenlik eşiğinde reddedilir.

## Doğrulama

- Tüm otomatik test paketi: **174 geçti, 0 hata**.
- Docker’sız ONNX model Windows ONNX Runtime 1.29.0 ile açıldı.
- Gerçek anonim tam omurga DICOM testinde model güveni **%99,86** olarak ölçüldü.
- Windows PyInstaller paketi başarıyla oluşturuldu ve paket içindeki ONNX model dosyası doğrulandı.

## Bilinen sınırlama

ONNX dönüşümünün maske çıktısı eski Linux/MMCV çalışma ortamıyla piksel düzeyinde birebir değildir. Bu nedenle AI Cobb taslağı eski Docker çıktısından farklı olabilir. Özellik uzman incelemeli deneysel taslak olarak sunulur ve otomatik kayıt oluşturmaz.
