# Yol Haritası Modül Sınırları

## Amaç

Bu belge, mevcut `main.py` orkestrasyonunu zaman içinde daha ince application service bağlarına dönüştürmek için modüllerin sorumluluklarını ve bağımlılık kurallarını tanımlar. İlk uygulama adımında mevcut dosya yapısı korunur; yeni özellikler bu sınırları takip ederek eklenir.

## Modül matrisi

| Modül | Sorumluluk | Doğrudan kullanabileceği katmanlar | Kullanamayacağı sorumluluklar |
|---|---|---|---|
| **Viewer** | DICOM açma, frame, görünüm state’i, zoom/pan, ölçüm overlay çizimi | Imaging service, domain contracts, Qt UI | SQLite SQL, PACS ağ çağrısı, rapor PDF üretimi |
| **Tracking** | Hasta/tetkik ağacı, longitudinal trend, curve selection, follow-up dashboard | Repository adapter, Measurement contract, Qt UI | Ham DICOM decode, PACS transport, AI model çalıştırma |
| **Stitching** | Çoklu görüntü compose, overlap, registration önerisi, kalite sonucu | Imaging arrays, RegistrationResult, QualityResult | Hasta kartı layout’u, kullanıcı rolü, doğrudan rapor PDF yazımı |
| **PACS** | Query/Retrieve/C-STORE adapter, timeout/retry, transfer durumu | PACS transport client, Study/Series DTO, audit service | Viewer scene çizimi, doğrudan klinik ölçüm, sessiz import |
| **Reporting** | PDF/CSV/gelecekte DICOM SR çıktısı | Measurement, QualityResult, RegistrationResult, Patient/Study DTO | Yeni ölçüm hesaplamak, DICOM pixel array değiştirmek |
| **AI** | Model inference, öneri, confidence, model provenance | SourceContext, MeasurementRecord, model registry | Kullanıcı onayı olmadan verified state yazmak, DICOM’a yazmak |
| **Quality Control** | DICOM metadata/PixelSpacing/teknik uyumluluk, quality gate | DICOM validator, QualityResult | Klinik yorum, otomatik tedavi/diagnosis kararı |
| **Repository** | SQLite persistence, indexes, migration, audit | Domain adapters, database driver | Qt widget, görüntü decode, PACS socket |
| **Application services** | Open study, compare, measure, report, retrieve use-case’leri | Domain + repository + adapters | Büyük UI widget layout’ları, ham SQL’in UI içinde dağılması |

## Bağımlılık yönü

Önerilen bağımlılık yönü aşağıdaki gibidir:

```text
Qt UI
  -> Application Services
      -> Domain Contracts
      -> Repository Adapters
      -> Imaging / PACS / AI / Quality Adapters

Reporting -> Domain Contracts + Read-only DTOs
Imaging   -> Domain Contracts (SourceContext, QualityResult)
AI        -> Domain Contracts (MeasurementRecord, Provenance)
```

Domain contracts hiçbir zaman PySide6, pydicom, reportlab, SQLite veya PACS client import etmemelidir. Bu kural, geometri ve provenance testlerinin GUI olmadan çalışmasını sağlar.

## UI ile iş mantığı arasında command sınırı

Yeni bir iş akışı eklenirken UI callback’i doğrudan repository veya engine çağırmamalıdır. Önerilen akış `UI event → application command → domain/service result → state update → audit/report` şeklindedir. İlk geçişte mevcut `main.py` facade metotları korunabilir; fakat yeni davranışın hesaplama kısmı ayrı bir service fonksiyonuna taşınmalıdır.

Örnek komutlar:

| Komut | Girdi | Çıktı |
|---|---|---|
| `CreateManualMeasurement` | SourceContext, dört nokta, MeasurementType | Draft `MeasurementRecord` |
| `ProposeRegistration` | Reference/Moving SourceContext, ROI, algorithm settings | Proposed `RegistrationResult` |
| `AcceptRegistration` | Proposed result, user, optional correction | Accepted/ManualOverride `RegistrationResult` |
| `BuildLongitudinalSeries` | patient_id, curve key | Tarihe göre MeasurementRecord listesi |
| `RunQualityGate` | DICOM path(s), comparison context | `QualityResult` |
| `BuildFollowUpReport` | patient, measurements, quality, registration | Read-only report DTO / PDF export |

## Threading sınırı

DICOM decode, registration, stitching, PACS Query/Retrieve ve AI inference GUI thread’inde bloklayıcı biçimde çalıştırılmamalıdır. UI thread yalnızca komutu başlatmalı, progress/error/cancel sinyallerini tüketmeli ve sonucu state’e uygulamalıdır. İlk uygulama adımında mevcut synchronous yolların davranışı değiştirilmez; yeni background worker geçişi benchmark ve sonuç eşitliği testleriyle yapılır.

## Veri güvenliği sınırı

DICOM kaynağı hiçbir modül tarafından ölçüm, filtre veya rapor üretimi sırasında yerinde değiştirilmez. Kalıcı kayıtlar lokal repository’ye, kullanıcı onaylı export’lar ayrı çıktı yoluna yazılır. PACS gönderimi, DICOM SR ve Secondary Capture işlemleri açık kullanıcı onayı, hedef bilgisi ve audit kaydı gerektirir.
