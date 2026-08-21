# V2 Model Kabulü — Klinik Metrik ve Lisans Kanıt Matrisi

**Tarih:** 20 Ağustos 2026  
**Kapsam:** `vertebra_landmark_detection` ONNX adayının ancak uzman incelemeli POC düzeyine geçebilmesi için gereken kanıtlar. Bu belge, otomatik klinik karar veya üretim/klinik kullanım yetkisi vermez.

> V2 kabulünün amacı, modelin teknik bütünlüğü ile doğrulama kanıtının izlenebilir olmasını sağlamaktır. **Kabul**, tanı, tedavi önerisi veya otomatik ölçüm kaydı anlamına gelmez.

## Uygulamanın zorunlu V2 kabul alanları

Mevcut `ai/model_acceptance.py`, `validation_report.json` içinde aşağıdaki alanları hata düzeyinde zorunlu tutar.

| Kanıt alanı | V2 kabulü için zorunlu içerik | Mevcut aday durumu |
|---|---|---|
| Paket bütünlüğü | ONNX SHA-256’nin manifest ve raporla eşleşmesi | Teknik olarak mevcut |
| Hasta bazlı ayrım | `patient_level_split: true`; aynı hastanın görüntüleri train/valid/test setlerine dağılmamalı | Eksik |
| İnceleyen | `reviewed_by` alanında sorumlu uzman/ekip ve inceleme tarihi | Eksik |
| Veri yönetişimi | Kaynak kurum, izin/etik süreç, de-identifikasyon, erişim sınırı ve saklama yaklaşımı | Eksik |
| Amaç sınırı | `intended_status: expert_review_poc` ve yalnızca uzman onaylı taslak kullanımı | Eksik |
| Landmark metriği | `landmark_error_px_median` — hasta bazlı ayrılmış değerlendirme setinde medyan piksel hatası | Eksik |
| Cobb metriği | `cobb_mae_degrees` — uzman referansı ile karşılaştırılmış ortalama mutlak Cobb farkı | Eksik |

## Önerilen klinik doğrulama metriği seti

| Katman | Raporlanacak metrik | Neden |
|---|---|---|
| Landmark doğruluğu | Medyan, ortalama ve %95 persentil nokta hatası (px); tanımlı yarıçaplarda SDR/PCK | Landmark tabanlı yöntemlerde önce dört köşe/vertebra noktaları, sonra kural tabanlı Cobb hesabı üretilir. [1] |
| Landmark geometrisi | Sınır dışı oranı, sol–sağ köşe sırası ihlali, vertebra sırası hatası, düşük güven oranı | Teknik taslakların neden engellendiğini veya uzman incelemesine düştüğünü görünür kılar. |
| End-vertebra seçimi | Uzman referansıyla end-vertebra uyum oranı; tek/çok eğri ve atlanan eğri sayısı | Landmarktan Cobb’a geçişte end-vertebra seçimi ayrı hata kaynağıdır. [1] |
| Cobb doğruluğu | MAE (°), medyan mutlak hata, %95 sınırları; Bland–Altman fark grafiği | Cobb tahmininin uzman referans ölçümüyle sayısal uyumunu gösterir. Cobb AI çalışmalarında MAE ve Bland–Altman/uyum ölçümleri yaygındır. [2] |
| Uzmanlar arası uyum | ICC ve güven aralığı; mümkünse iki bağımsız uzman ve uzlaşma kuralı | Referans standardının belirsizliğini ve modelin uzmanla uyumunu açıklar. [2] |
| Alt grup analizi | Görüntü kaynağı/cihaz, AP–PA, yaş grubu, cinsiyet, Cobb şiddeti, donanım varlığı, görüntü boyutu/kalitesi | Genel performansın alt gruplardaki performans sorunlarını gizlemesini önler. [2] |
| Dış doğrulama | Eğitimden bağımsız kurum/cihaz/seri üzerinde aynı metrikler | Genellenebilirlik yalnızca eğitim/hold-out setinden çıkarılamaz; dış doğrulama ayrı raporlanmalıdır. [3] |

Bu metrikler için önceden belirlenmiş eşik, popülasyon ve analiz planı gerekir. Eşikler bu belgede uydurulmamıştır; kurum, klinik sorumlular ve doğrulama protokolü tarafından referans manuel ölçüm değişkenliği dikkate alınarak onaylanmalıdır.

## Lisans ve veri kanıt paketi

| Varlık | Gerekli kanıt | Mevcut aday durumu |
|---|---|---|
| Kaynak kod | Sabit repo URL/commit, lisans metni kopyası, değişiklik/provenance kaydı | Kaynak repo MIT lisanslı; commit kaydedildi. [4] [5] |
| Eğitilmiş ağırlık | Sağlayıcının açık lisansı veya yazılı izni; kullanım kapsamı, değişiklik/dağıtım ve yerel POC hakkı; indirme URL’si, dosya adı, SHA-256, indirme tarihi | **Eksik:** Google Drive ağırlık klasöründe ayrı lisans/izin görünmüyor. [5] |
| Eğitim/validasyon verisi | Veri seti lisansı veya Data Use Agreement, izin/etik/IRB referansı gerektiğinde, de-identifikasyon ve saklama/erişim kuralları | **Eksik:** README kaynak veri setine atıf yapıyor ancak aday pakette yeniden kullanım ve klinik POC kanıtı yok. [5] |
| Yerel DICOM test verisi | Kurumsal kullanım izni, uygun de-identifikasyon veya güvenli kurum içi çalışma; hasta bazlı split kaydı; veri sorumlusunun onayı | Bu laboratuvarda gerçek DICOM kullanılmadı. |
| Üçüncü taraf bağımlılıkları | ONNX Runtime, PyTorch, OpenCV ve pydicom sürümü/lisans envanteri | Sürüm pinleri laboratuvar `requirements-cpu-py38.txt` dosyasında kayıtlı; dağıtım öncesi ayrı SBOM/lisans taraması gerekir. |

> Kod lisansının açık olması, ağırlıkların veya veri setinin aynı haklarla kullanılabildiği anlamına gelmez. Ağırlık ve veri için bağımsız kanıt gerekir.

## Asgari kabul raporu iskeleti

```json
{
  "format": "ScoliosisFollowUpAIValidationReportV1",
  "model_version": "...",
  "model_sha256": "...",
  "patient_level_split": true,
  "reviewed_by": "uzman/ekip, tarih ve rol",
  "data_governance": "izin, de-identifikasyon, erişim ve saklama özeti",
  "intended_status": "expert_review_poc",
  "metrics": {
    "landmark_error_px_median": 0.0,
    "cobb_mae_degrees": 0.0
  },
  "evidence_links": {
    "weights_license": "...",
    "dataset_permission": "...",
    "protocol_or_review_record": "..."
  }
}
```

Örnekteki `0.0` değerleri yer tutucudur; gerçek hasta bazlı değerlendirme sonuçlarıyla değiştirilmelidir. Uydurulmuş metrikle rapor doldurmak kabul sürecini geçersiz kılar.

## Aday paket için geçiş kararı

`v2_landmark_candidate` şu an teknik dönüşüm açısından izlenebilir olsa da **kabul edilmemiştir**. Eksik ağırlık/veri lisansı, hasta bazlı ayrılmış test, iki temel doğrulama metriği ve uzman incelemesi tamamlanmadığı sürece aktif model dizinine taşınmamalıdır.

## Kaynaklar

[1] [Yang, Wang, Meng. A Landmark-aware Network for Automated Cobb Angle Estimation Using X-ray Images](https://arxiv.org/html/2405.19645v1)  
[2] [Suri et al. Conquering the Cobb Angle: A Deep Learning Algorithm for Automated, Hardware-Invariant Measurement of Cobb Angle on Radiographs in Patients with Scoliosis](https://pmc.ncbi.nlm.nih.gov/articles/PMC10388214/)  
[3] [Hernandez-Boussard et al. MINIMAR: Minimum Information for Medical AI Reporting](https://academic.oup.com/jamia/article/27/12/2011/5864179)  
[4] [yijingru/Vertebra-Landmark-Detection deposu](https://github.com/yijingru/Vertebra-Landmark-Detection)  
[5] [Kaynak depo README’si ve ağırlık bağlantısı](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/README.md)
