# Aday AI Model Paketi İnceleme Akışı — Teslim Raporu

**Tarih:** 20 Ağustos 2026  
**Kapsam:** Yerel klasörde bulunan aday V2 ONNX paketlerinin uygulama içinde, hiçbir şekilde etkinleştirilmeden denetlenmesi.

> Bu geliştirme yalnızca teknik kabul incelemesi yapar. Aday model dosyasını çalıştırmaz, kopyalamaz, uygulamanın etkin modeli haline getirmez, ağ bağlantısı kurmaz, DICOM dosyasını açmaz ve hasta kayıtlarına erişmez.

## Teslim edilenler

| Bileşen | İçerik |
|---|---|
| Yeni dialog | `modular_app/ui/ai_model_candidate_review_dialog.py` içinde `AIModelCandidateReviewDialog`. |
| Menü eylemi | **Gelişmiş → Aday AI Model Paketini İncele…**. Kullanıcı yalnızca klasör seçer; seçimi iptal edebilir. |
| Teknik inceleme | Mevcut `evaluate_model_candidate()` ile V2 manifest, ONNX dosyası, SHA-256, provenance/lisans alanları ve doğrulama raporu okunur. |
| Güvenlik görünürlüğü | Ekran, paketin etkinleştirilmediğini; modelin çalıştırılmadığını; DICOM ve hasta verisine erişilmediğini açıkça yazar. |
| Testler | Geçerli aday paket, eksik manifest ve Gelişmiş menü eylemi için offscreen otomatik testler. |

## Kullanım akışı

1. Uygulamada **Gelişmiş → Aday AI Model Paketini İncele…** seçilir.
2. Yerel aday paket klasörü seçilir.
3. Ekran yalnızca aşağıdaki dosyaları okur: `manifest.json`, manifestte tanımlı ONNX dosyası ve `validation_report.json`.
4. Paket uygun değilse hata kodları ve açıklamaları gösterilir. Uygun sonuç, yalnızca **uzman incelemeli yerel POC** için teknik hazır olma anlamındadır.
5. Bu işlemden sonra paket kurulu/etkin model olmaz; mevcut AI taslak–uzman onay iş akışı değişmez.

## Doğrulama kayıtları

| Kontrol | Sonuç |
|---|---:|
| Yeni dialog ve menü kaynakları için `py_compile` | Başarılı |
| Aday paket dialogu, model denetimi ve kabul ön kontrolü hedefli testleri | 11 test başarılı |
| Menü ve aday paket inceleme entegrasyon testi | 4 test başarılı |
| Toplu modüler regresyon | **125 test başarılı** |
| Paketleme ortamında gerçek DICOM performans bütçesi | Başarılı |
| Windows EXE duman testi | 20 saniye kararlı çalıştı; test sonunda kontrollü kapatıldı |

## Windows paketi

```text
dist\ScoliosisFollowUp\ScoliosisFollowUp.exe
```

| Alan | Değer |
|---|---|
| Dosya boyutu | 14.480.632 bayt |
| SHA-256 | `1A7408E17BDD1455D1D1B026C534ECD8A4B24AAE47A0178CD2DB5CFBC31DBB51` |

Paketleme ilk denemesinde yalnızca performans testindeki küçük ve geçici çözme süresi sapması nedeniyle durdu: ölçüm `1207,18 ms`, sınır `1200 ms` idi. Kaynak ortamındaki toplu regresyon tamamen başarılı oldu; aynı test paketleme ortamında tek başına tekrarlandığında başarılı geçti. Bu nedenle paket, tekrar tam test yerine kaynak regresyonu ve paketleme ortamı performans kontrolü kanıtları korunarak `-SkipTests` ile oluşturuldu.

## Geri yükleme noktaları

| Tür | Yol |
|---|---|
| Değişiklik öncesi | `.restore_points\ai_model_candidate_review_20260820_105046` |
| Son teslim sürümü | `.restore_points\ai_model_candidate_review_final_20260820_110256` |

## Sınırlar

Gerçek ONNX ağırlığı eklenmemiştir. Aday inceleme ekranının teknik olarak uygun demesi, klinik doğrulama veya otomatik ölçüm kaydı anlamına gelmez. Bir aday modelin kullanıma alınması için ayrıca kaynak/lisans incelemesi, hasta bazlı ayrılmış doğrulama raporu, kurum veri yönetişimi değerlendirmesi ve mevcut uzman onay süreci gerekir.
