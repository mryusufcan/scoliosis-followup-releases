# Yol Haritası Domain Sözleşmeleri

## Amaç

`modular_app/domain/contracts.py`, Viewer/Tracking/Stitching/PACS/Reporting/AI/Quality Control modüllerinin ortak veri dili için Qt ve SQLite’dan bağımsız value object’ler sağlar. Bu dosya mevcut repository’yi hemen değiştirmez; mevcut `cobb_measurements`, `comparison_sessions` ve kalite kayıtları için güvenli bir adapter/migration katmanının temelidir.

## Ana sözleşmeler

| Sözleşme | Sorumluluk | Mevcut karşılık |
|---|---|---|
| `SourceContext` | Hasta, tetkik/seri, SOP, dosya, frame, boyut, PixelSpacing ve koordinat sistemi | `patient_id`, `dicom_path`, `source_sop_instance_uid`, viewer state |
| `Provenance` | Manuel/otomatik/AI/import kaynağı, yöntem, sürüm, kullanıcı ve zaman | `measurement_method`, `measurement_version`, `created_by`, verify alanları |
| `MeasurementRecord` | Cobb ve ilerideki koronal/sagittal ölçümler | `cobb_measurements` tablosu |
| `QualityResult` | Teknik görüntü/karşılaştırma kalite sonucu | `DicomQualityItem`, stitching quality sözlükleri |
| `RegistrationResult` | Reference/moving görüntü, dönüşüm, ROI, skor, kalite ve durum | `comparison_sessions`, overlay state, auto-align cache |

## Enum kararları

`MeasurementType` Cobb, koronal denge, C7 plumb line, trunk shift, pelvic obliquity, omuz yüksekliği farkı ve sagittal vertical axis için sabit değerler taşır. `MeasurementSource` manuel, otomatik, AI önerisi ve import kaynaklarını ayırır. `MeasurementStatus` taslak, doğrulanmış ve reddedilmiş durumları ayırır. `CoordinateSystem` piksel, Qt scene ve patient-mm koordinatlarını birbirine karıştırmayı engellemek için açıkça saklanır.

## Validasyon sınırları

Sözleşmeler `validate()` ile ihlal listesini döndürür; constructor mevcut legacy kayıtların yüklenmesini zorunlu olarak engellemez. Manuel Cobb kaydı dört nokta içermelidir. Patient-mm koordinatları için PixelSpacing gerekir. AI önerilerinde model sürümü zorunludur. Doğrulanmış ölçümde doğrulayan kullanıcı bulunmalıdır. Bu validasyonlar klinik yorum üretmez; yalnızca kayıt bütünlüğünü ve provenance eksiklerini yakalar.

## SQLite adapter stratejisi

İlk migration mevcut tabloyu kırmamalıdır. Adapter aşağıdaki dönüşümleri yapmalıdır:

| Yeni alan | Legacy kaynak |
|---|---|
| `MeasurementRecord.patient_id` | `cobb_measurements.patient_id` |
| `SourceContext.dicom_path` | `cobb_measurements.dicom_path` |
| `SourceContext.sop_instance_uid` | `source_sop_instance_uid` |
| `MeasurementRecord.value` | `angle_degrees` |
| `MeasurementRecord.measurement_type` | `cobb_angle` sabit değeri |
| `MeasurementRecord.coordinates` | `point_data` JSON |
| `MeasurementRecord.provenance.method` | `measurement_method` |
| `MeasurementRecord.provenance.app_version` | `measurement_version` |
| `MeasurementRecord.provenance.created_by` | `created_by` |
| `MeasurementRecord.status` | `is_locked` → `verified`, aksi halde `draft` |
| `MeasurementRecord.verified_by` | `verified_by` |
| `curve_key` | `upper_vertebra + lower_vertebra + curve_direction` |

Yeni ölçüm tipleri için ayrı tabloya hemen geçmek yerine versioned JSON/adapter prototipiyle başlamak, legacy Cobb export’larının bozulma riskini azaltır. Kalıcı schema migration, gerçek örnek veriler üzerinde round-trip testleri tamamlandıktan sonra yapılmalıdır.

## Klinik ve güvenlik sınırı

Bu sözleşmeler otomatik sonuçları kesin klinik sonuç olarak işaretlemez. `MeasurementSource.AI_SUGGESTION`, `RegistrationStatus.PROPOSED` ve `MeasurementStatus.DRAFT` durumları kullanıcı onayı olmadan raporda doğrulanmış sonuç gibi gösterilmemelidir. Kaynak DICOM dosyası ve ham piksel verisi bu sözleşmeler tarafından değiştirilmez.
