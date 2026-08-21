# Scoliosis Follow-Up 1.7.3

1.7.3; görüntü seçimi, ortak görüntü birleştirme ve genel kararlılık üzerine odaklanan bir bakım ve iş akışı sürümüdür.

## Yenilikler

- `Omurga Birleştirme` modülü genel amaçlı `Görüntü Birleştirme` modülüne dönüştürüldü.
- Üst, Orta ve Alt görüntülere ek olarak isteğe bağlı 4. parça desteği eklendi.
- İki, üç veya dört görüntü otomatik ya da manuel hizalamayla birleştirilebilir.
- Dört görüntülü çalışmada üç birleşim bölgesi ayrı ayrı kalite kontrolünden geçirilir.
- Açık görüntülerin birleştirme sırasına kullanıcı tarafından atanması sağlandı.
- Görüntü seçicisindeki dosya listesine küçük önizlemeler eklendi.
- Dosya satırları beklemeden gösterilir; DICOM bilgisi ve önizlemeler arka planda hazırlanır.
- Seçilen büyük önizleme arayüzü kilitlemeden ve sıradaki küçük önizlemelerden öncelikli hazırlanır.
- Küçük ve büyük önizlemeler kontrollü bellek önbelleğinde tutulur.
- Görüntü önizleme işçi sayısını yanlışlıkla ikiyle sınırlayan eski ayar kaldırıldı.
- Ayrı bacak uzunluk modülü kaldırıldı; uzun görüntüler ortak Görüntü Birleştirme akışında kullanılabilir.

## Korunan davranışlar

- Manuel birleştirme geometrisi ve mevcut nokta tabanlı hizalama hesapları değiştirilmedi.
- Docker gerektirmeyen yerel ONNX AI Cobb taslağı ve zorunlu uzman onayı korunur.
- DICOM görüntüleyici, takip/karşılaştırma, Overlay/Blink, mm/cm ölçümü ve PDF/CSV raporlama davranışları korunur.

## Doğrulama

- Tam otomatik test paketi: **154/154 başarılı**.
- DICOM seçim, önizleme, preload, render ve performans testleri başarılı.
- Başlangıç profili, önbellek bellek sınırları ve tüm Python modüllerinin derlenebilirliği doğrulandı.
