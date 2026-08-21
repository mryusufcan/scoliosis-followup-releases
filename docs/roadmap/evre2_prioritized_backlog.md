# Evre 2 — Önceliklendirilmiş Uygulama Backlog’u

## Önceliklendirme sonucu

İlk Evre 2 geliştirmesi doğrudan AI veya PACS entegrasyonu değil, **ölçüm ve takip bağlamını sağlamlaştıran** bir iş paketi olmalıdır. Mevcut repository zaten Cobb provenance’ı, curve end-vertebra alanları ve longitudinal seri yardımcılarını taşıyor. Bu nedenle ilk kullanıcı değeri, mevcut veriyi daha tutarlı bir hasta/tetkik dashboard’una dönüştürmekten gelir.

## Önerilen sıra

| Sıra | İş paketi | Kapsam | Bağımlılıklar | Kabul ölçütü |
|---|---|---|---|---|
| E2-01 | Curve identity ve measurement adapter | Legacy Cobb kayıtlarını `MeasurementRecord`’a dönüştür; eğri anahtarını normalize et; eski kayıtları “legacy/eksik provenance” olarak işaretle | Domain contracts, repository adapter | Aynı hasta içindeki farklı üst-alt vertebra çiftleri ve yönler tek eğride birleşmez. Round-trip export değişmez. |
| E2-02 | Longitudinal takip merkezi | Hasta özeti, tetkik timeline’ı, eğri filtresi, ilk/son değer, delta, yıllık değişim ve tekrar ölçüm uyarısı | E2-01, mevcut `cobb_trend.py` | Kullanıcı hasta seçtiğinde tüm eğrileri, tetkikleri, ölçüm durumlarını ve takip tarihini tek akışta görür. |
| E2-03 | Registration v2 proposal flow | Pelvis/omurga ROI, otomatik offset, score, teknik uyumluluk ve manuel override | RegistrationResult, QualityResult, background boundary | Düşük skor kullanıcıdan onay almadan kabul edilmez; manuel düzeltme provenance’a yazılır. |
| E2-04 | Technical quality gate | PixelSpacing, projection, frame, dimensions, MONOCHROME, saturation/clipping ve karşılaştırma uyumluluğu | QualityResult, DICOM service | Registration/stitching başlamadan önce uyarılar açıklanır; kullanıcı override’ı audit’e gider. |
| E2-05 | General Measurement registry | Cobb dışı koronal balance, C7 plumb line, trunk shift, pelvic obliquity, shoulder height | E2-01, report adapter | Yeni ölçüm tipi UI/DB/trend/export katmanlarında ortak sözleşmeyle eklenebilir. |
| E2-06 | Longitudinal report v2 | Genel ölçüm tablosu, trend grafikleri, quality/registration sonuçları, kaynak görüntü ve onay durumu | E2-02, E2-04, report DTO | PDF/CSV raporları Cobb dışı ölçümleri de provenance ile ayırır. |
| E2-07 | PACS workflow foundation | Patient→Study→Series DTO, background Query/Retrieve, local index, audit ve direct follow-up handoff | Repository migration, worker boundary | Ağ hatası UI’ı kilitlemez; retrieve edilen tetkik local index’e açık bağlamla eklenir. |
| E2-08 | Difference/overlay analysis | Difference map, edge/landmark overlay, synchronized zoom/pan, color-coded change areas | RegistrationResult, quality gate | Ham görüntü değişmeden katmanlar açılıp kapanır ve işlem provenance’a yazılır. |

## İlk uygulama dilimi

İlk dilim E2-01 ve E2-02’den oluşmalıdır. E2-01 veri dönüşümünü ve curve identity tutarlılığını sağlar; E2-02 bunun üzerine kullanıcıya doğrudan değer sunar. Bu iki iş paketi tamamlanmadan dashboard’a AI skoru, registration sonucu veya PACS durumu eklenmemelidir.

İkinci dilim E2-03 ve E2-04’tür. Registration v2 ile teknik quality gate birlikte yapılmalıdır; aksi halde düşük kaliteli veya uyumsuz görüntüler için otomatik hizalama sonucunun güvenilirliği kullanıcıya yanlış aktarılabilir.

Üçüncü dilim E2-05 ve E2-06’dır. Genel Measurement registry kurulmadan raporlamayı büyütmek, her yeni ölçüm için ayrı kod ve tablo yolu açarak mimari borcu artırır.

Dördüncü dilim E2-07 ve E2-08’dir. PACS ağ iş akışı ve gelişmiş görsel karşılaştırma, önceki veri ve kalite sözleşmelerine bağlanmalıdır.

## İş paketi tanım şablonu

Her yeni iş paketi şu bölümlerle açılmalıdır:

1. **Klinik olmayan teknik amaç:** Özelliğin hangi kullanıcı akışını kısalttığı veya hangi veri bütünlüğü sorununu çözdüğü.
2. **Domain değişikliği:** Yeni/etkilenen contract, enum, adapter veya migration.
3. **UI akışı:** Kullanıcının göreceği bağlam, loading, hata, düşük güven ve iptal durumları.
4. **Provenance:** Kaynak görüntü, PixelSpacing, yöntem, sürüm, kullanıcı ve onay durumu.
5. **Test matrisi:** Unit, gerçek anonim DICOM, UI smoke, export ve round-trip testleri.
6. **Performans bütçesi:** Cold/warm, memory, GUI block süresi ve cache davranışı.
7. **Geri dönüş:** Restore point, migration rollback ve eski kayıtların okunabilirliği.

## İlk iş paketi için hazır durum

E2-01’e başlamak için ortak sözleşmeler, fixture’lar, performans bütçeleri ve modül sınırı dokümantasyonu hazırlandı. Bir sonraki kod turunda yalnızca repository adapter ve round-trip testleri eklenmeli; mevcut `ExamRepository` tabloları ve UI callback’leri korunmalıdır.
