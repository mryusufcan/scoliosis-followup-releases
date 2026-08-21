# Scoliosis Follow-Up 1.7.2

Yayın tarihi: 21 Ağustos 2026

## Düzeltilenler

- Kurulu 1.7.1 uygulamasının güncelleme penceresinde mevcut sürümü `0.0.0` göstermesine neden olan paketleme hatası düzeltildi.
- `VERSION` dosyası Windows dağıtım paketine zorunlu çalışma verisi olarak eklendi.
- Paketlenmiş uygulamanın sürüm ve kaynak yolları PyInstaller çalışma dizininden güvenli biçimde çözümlenecek şekilde güncellendi.
- Temiz dağıtım denetimi, paket içinde sürüm bilgisinin bulunmadığı yayınları artık reddeder.

## Doğrulama

- Kaynak çalışma ve kurulu PyInstaller çalışma biçimleri için sürüm okuma regresyon testleri eklendi.
- Güncelleme penceresinin mevcut sürümü `1.7.2` olarak okuyabilmesi paketlenmiş dağıtım üzerinde doğrulanır.

## 1.7.1 özellikleri

Docker gerektirmeyen yerel ONNX AI Cobb taslağı, zorunlu uzman onayı ve 1.7.1 sürümündeki diğer işlevler aynen korunur.
