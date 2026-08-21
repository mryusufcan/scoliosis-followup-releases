# Yol Haritası Faz 1 — Mevcut Ürün ve Mimari Denetim

## Denetim kapsamı

Bu denetim, onaylanan uzun vadeli ürün yol haritasının ilk uygulama adımı olarak mevcut veri sözleşmelerini, UI/domain ayrımını, longitudinal takip kapsamını, registration/stitching motorunu, PACS girişini, teknik DICOM kalite servislerini ve raporlama çıktısını inceler. Bu fazda çalışma zamanı davranışı değiştirilmemiştir; yalnızca mevcut durum ve sonraki iş paketleri belgelenmiştir.

## Mevcut ürün haritası

| Alan | Mevcut durum | Yol haritasına göre boşluk |
|---|---|---|
| Viewer | DICOM/görüntü açma, Window/Level, frame, zoom, anotasyon ve ölçüm akışları mevcut. | Görüntü state’i ile domain ölçüm/rapor sözleşmesi arasında ortak typed contract bulunmuyor. |
| Takip | Hasta/tetkik listesi, takip ağacı, Overlay/Yan Yana, Cobb ve takip uyarıları mevcut. | Hasta dashboard’u ve eğri bazlı tüm longitudinal bağlam henüz tek merkezde birleşmemiş. |
| Cobb | Dört noktalı manuel ölçüm, nokta kanıtı, PixelSpacing bağlamı, kilitleme/doğrulama ve tekrar ölçüm kalite kontrolü mevcut. | Genel `Measurement` sözleşmesi yok; Cobb dışı ölçümler için ortak kayıt/export/trend altyapısı henüz tanımlı değil. |
| Longitudinal trend | `ExamRepository.longitudinal_cobb_series`, tarih başına tek temsilci ölçüm ve yıllık değişim hesabı mevcut; `CobbTrendDialog` ayrı vertebra çiftlerini filtreliyor. | Eğri kimliği, eşleştirme güveni, referans tetkik, ölçüm yöntemi ve manuel onay durumu dashboard seviyesinde genellenmeli. |
| Registration | Stitching/Overlay motorunda otomatik offset, ROI dışı teknik skor, manuel offset ve kalite değerlendirmesi mevcut. | Pelvis/omurga ROI, otomatik+manuel hibrit provenance, düşük güven kapısı ve deformasyon fark haritası henüz bağımsız Registration domain’i değil. |
| Stitching | `StitchingEngine` saf sayısal motor olarak ayrılmış; overlap, exposure harmonization, seam/edge quality ve kalite özeti mevcut. | Çok parçalı iş akışı, distortion kontrolü ve engine sonuç sözleşmesi UI state’inden daha net ayrılmalı. |
| Raporlama | PDF; hasta profili, Cobb özeti/grafiği, tetkik geçmişi, Cobb kanıtı/kilit durumu, Overlay oturumları, vertebra etiketleri, notlar ve takip uyarılarını kapsıyor. | Rapor hâlâ Cobb-merkezli; ortak Measurement, kalite sonucu, genel trend ve gelecekte DICOM SR için şablon sözleşmesi gerekli. |
| PACS | `PacsDialog` bağlantı testi, Query, Retrieve ve C-STORE gönderimini tek pencereden başlatıyor; sonuçları tablo ve signal ile aktarıyor. | Patient→Study→Series yerel domain/cache modeli, audit persistence, background worker, retry/timeout ve doğrudan takip akışı eksik. |
| Teknik DICOM kalite | `DicomQualityItem`, validator wrapper, valid/warning özeti ve hasta etiketi içermeyen CSV export mevcut. | File-level validator; comparison-aware uyumluluk, PixelSpacing/ROI/projection kapısı, saturation/clipping ve registration öncesi quality gate eksik. |
| Veri tabanı | SQLite repository; exams, comparison_sessions, cobb_measurements, audit_events, patient_profiles, vertebra_labels, image_notes, app_users ve app_settings tabloları ile indeksler mevcut. | Patient/Study/Series/Curve/Measurement/RegistrationResult/QualityResult/Report için açık domain model ve migration/version contract yok. |
| Oturum | `app_session` dosya havuzu, viewer state, overlay, stitching slotları ve UI geometry’yi JSON olarak geri yüklüyor. | Çalışma oturumu ile klinik domain geçmişi ayrımı korunmalı; provenance ve audit state’i session’dan bağımsızlaştırılmalı. |
| Performans | DICOM decode/render cache, debounce, sınırlı cache, lazy selection preview ve benchmark scriptleri eklendi. | Registration/stitching CPU çalışmaları hâlâ GUI thread’inde; import/startup ve büyük compose için worker/benchmark bütçesi kalıcı CI kapısı olmalı. |

## Veri sözleşmesi bulguları

`ExamRepository` mevcut ürünün en güçlü temelidir. `cobb_measurements` tablosunda `source_sop_instance_uid`, `point_data`, `measurement_method`, `measurement_version`, `created_by`, `upper_vertebra`, `lower_vertebra`, `curve_direction`, `is_locked`, `verified_by` ve `verification_note` alanları bulunuyor. Bu alanlar ileride genel bir provenance modeline taşınabilir.

Bununla birlikte kayıtların ana sözleşmesi hâlâ tabloya ve Cobb’a özgü metotlara dayanıyor. İlk mimari iş paketi, mevcut tabloyu bozmayacak biçimde ortak bir `MeasurementRecord`/`Measurement` veri sözleşmesi tanımlamak olmalıdır. Bu sözleşme en azından `measurement_id`, `patient_id`, `study_id` veya mevcut tetkik yolu, `series_id` veya SOP bağlamı, `measurement_type`, `value`, `unit`, `coordinates`, `pixel_spacing`, `method`, `status`, `source`, `algorithm_version`, `created_by`, `verified_by`, `created_at` ve `notes` alanlarını taşımalıdır.

## Mimari bulgular

UI modülleri `viewer_widget.py`, `workspace_widget.py` ve ilgili action/core/record modüllerine bölünmüş durumda; bu, yol haritasındaki modülerleşme için iyi bir başlangıçtır. Ancak `main.py` hâlâ çok sayıda facade, state alanı ve modül bağlantısını orkestre ediyor. Yeni özellikler doğrudan `main.py` içine eklenmek yerine application service ve domain sözleşmeleri üzerinden bağlanmalıdır.

`StitchingEngine` UI’dan ayrılmış saf sayısal motor niteliğinde. Buna karşılık `stitch_io.update_stitched_spine` cache, quality, status label, render ve kullanıcı bildirimini aynı akışta yönetiyor. Registration v2 için engine sonucu `RegistrationResult` benzeri immutable bir sonuç olarak tanımlanmalı; UI yalnızca sonucu görselleştirmeli ve manuel düzeltmeyi ayrı bir command/provenance kaydı olarak yazmalıdır.

`PacsDialog` şu anda iyi bir kullanıcı giriş noktasıdır fakat PACS workflow domain’i değildir. Ağ çağrıları UI thread’inde çalışıyor ve sonuçlar kalıcı yerel Patient→Study→Series indeksine yazılmıyor. PACS genişletmesi başlamadan önce adapter/service sözleşmesi ve background worker sınırı tanımlanmalıdır.

## Öncelikli boşluklar

| Sıra | İş paketi | Bağımlılık | Kabul ölçütü |
|---|---|---|---|
| 1 | Ortak domain/provenance sözleşmeleri | Mevcut repository şeması | Cobb kaydı bozulmadan genel Measurement ve Quality/Registration sonuçları temsil edilebiliyor. |
| 2 | Performans bütçeleri ve gerçek anonim fixture kataloğu | Mevcut benchmark’lar | Cold render, cache hit, folder scan, registration ve stitching eşikleri kaydediliyor. |
| 3 | Eğri kimliği ve longitudinal dashboard modeli | Measurement sözleşmesi | Farklı eğriler aynı hastada birbirine karışmadan trendleniyor. |
| 4 | Registration v2 service | Measurement/quality sözleşmesi | ROI, güven skoru, manuel override ve provenance tek sonuç modelinde saklanıyor. |
| 5 | Quality gate service | DICOM quality + registration sözleşmesi | Uyumsuz PixelSpacing/projection/frame durumları otomatik hizalama öncesinde açıklanıyor. |
| 6 | PACS service ve yerel Patient→Study→Series indeks | Repository migration + worker altyapısı | Query/Retrieve UI’dan bağımsız, audit’li, timeout/retry destekli ve doğrudan takip akışına bağlanıyor. |
| 7 | Genel rapor sözleşmesi | Measurement/Quality/Registration | PDF/CSV aynı genel measurement ve provenance kayıtlarını tüketiyor. |

## Faz 1 kararı

Ürün, temel klinik araç aşamasını büyük ölçüde tamamlamış; ancak Evre 2’ye geçiş için önce **genel veri sözleşmesi + performans/test bütçesi + registration/quality ayrımı** sabitlenmelidir. İlk doğrudan kullanıcı özelliği olarak longitudinal dashboard geliştirmek anlamlıdır; fakat dashboard’un kalıcı ve ileride AI/PACS ile uyumlu olması için bu sözleşmelerden önce yalnızca UI prototipi yapılmalıdır.

## Bir sonraki faz

Faz 2’de mevcut SQLite şemasını bozmadan domain veri sözleşmeleri, provenance alanları, measurement type registry, performance budget dosyası ve migration stratejisi hazırlanacaktır. Bu fazda çalışma zamanı algoritmaları değiştirilmeden yalnızca yeni sözleşmeler ve test edilebilir yardımcılar eklenmesi tercih edilecektir.
