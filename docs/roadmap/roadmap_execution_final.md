# Scoliosis Follow-Up — Yol Haritası İlerleme Raporu

## Kapsam

Bu turda kullanıcıdan ek bilgi istenmeden gerçek Windows UI doğrulaması, DICOM performans kapıları, Cobb ölçüm güvenliği, Longitudinal Takip Merkezi, DICOM kalite kontrolleri, raporlama/export akışları, test kapsamı ve Windows release kabulü birlikte gözden geçirildi.

## Tamamlanan teknik işler

| Alan | Sonuç |
|---|---|
| Gerçek Windows UI | Segoe UI dahil sistem fontları doğrulandı; Türkçe karakterler gerçek Windows ekranında açık/koyu tema görüntülerinde kontrol edildi. |
| DICOM performans bütçesi | DICOM okuma, piksel decode, display render ve cache hit birbirinden ayrıldı; test artık aynı viewer dataset/cache davranışını ölçüyor. |
| Cobb UX | Dört noktalı akışta kalan nokta sayısı gösteriliyor; sıfır uzunluklu çizgi reddediliyor; yarım preview çizimleri kalıcı ölçüm çizimlerinden ayrılıyor. |
| Cobb provenance | Manuel sonuçlar `manual`, `draft`, `unit=°` ve klinik doğrulama notuyla kaydediliyor; otomatik/AI sonuçları kesin klinik sonuç gibi işaretlenmiyor. |
| PixelSpacing | Eksik, sıfır, negatif veya sonlu olmayan PixelSpacing değerleri güvenilir mm/cm ölçümü olarak kullanılmıyor; mesafe px olarak açıkça bildiriliyor. |
| Legacy kayıt adapter’ı | SQLite/API’den gelebilecek `"0"` ve `"1"` string değerleri artık Python truthiness hatasına düşmeden doğru DRAFT/VERIFIED durumuna çevriliyor. |
| Longitudinal | Eğri ayrımı, `locked_only`, aynı tarihli tekrarların doğrulanmış kaydı tercih etmesi, panel grafiği ve Overlay callback akışları doğrulandı. |
| DICOM kalite | PixelSpacing, projeksiyon, PatientID, StudyInstanceUID, tarih, çok kareli veri, matris ve görüntü kalite uyarıları mevcut testlerle doğrulandı. |
| Paketleme ortamı | `pyqtgraph` requirements içinde bulunmasına rağmen build venv’e eksik kurulabildiği görüldü; bağımlılık ortam kapısına eklendi ve build venv’e kuruldu. |

## Performans ölçümleri

Gerçek `dev_data/dicom_samples` DICOM örnekleri üzerinde, 2393 × 3056 piksel görüntü için ölçülen değerler şöyledir:

| Metrik | Ölçülen ortalama | Bütçe | Durum |
|---|---:|---:|---|
| Metadata/DICOM okuma | 4,73 ms | 15 ms | Geçti |
| Piksel decode | 1004,47 ms | 1200 ms | Geçti |
| Decoded array’dan display render | 51,53 ms | 300 ms | Geçti |
| Viewer cache hit | 0,05 ms | 1 ms | Geçti |
| Viewer render debounce | 45 ms | — | Uygulandı |

Piksel decode, JPEG/codec katmanında ilk görüntü açılışının baskın maliyetidir. Display render ve cache bütçeleri korunuyor; ilk decode hâlâ ana GUI thread’inde gerçekleştiği için çok büyük görüntülerde gelecekteki en önemli iyileştirme, decode ve ilk preview üretimini worker tabanlı hale getirmek olacaktır. Bu turda ham DICOM piksel matrisi veya metadata değiştirilmedi.

## Doğrulama sonuçları

| Kontrol | Sonuç |
|---|---:|
| Sistem Python tam modüler regresyon | **94/94 başarılı** |
| Release/build venv tam modüler regresyon | **93/93 başarılı** |
| Longitudinal ve adapter hedef testleri | **11/11 başarılı** |
| Performans bütçesi testleri | **6/6 başarılı** |
| UI tema smoke | **UI_THEME_SMOKE_OK** |
| Python derleme kontrolü | Başarılı |
| Windows release bütünlük/kabul denetimi | **Başarılı** |
| Geçici capture/benchmark/profile/check dosyaları | Temizlendi |

## Release durumu

Güncel onedir paketinde `pyqtgraph` bulunuyor. `ScoliosisFollowUp.exe`, `runtime_integrity.json`, installer ve `update.json` mevcut. Proje kökünden çalıştırılan `verify_release.py --root .` denetimi; dağıtım bütünlüğünü, installer özetini ve yerel güncelleme bildirimini başarıyla doğruladı.

> Release kabulü başarılıdır; ancak ilk DICOM piksel decode işleminin yaklaşık 1 saniye sürebilmesi, büyük görüntüler için sonraki performans iterasyonunun ana teknik riskidir. Bu süre ölçüm bütçesinde ayrı bir decode kapısı olarak tutulmuştur.

## Geri dönüş noktaları

Değişikliklerden önce aşağıdaki yedekler oluşturuldu:

- `.restore_points/cobb_ux_safety_20260818_235800/`
- `.restore_points/measurement_status_boolean_20260819_000400/`
- `.restore_points/packaging_pyqtgraph_gate_20260819_001500/`

## Değişen ana dosyalar

`main.py`, `modular_app/ui/viewer_core.py`, `modular_app/ui/viewer_records.py`, `modular_app/domain/measurement_adapter.py`, `tests/test_modular_ui_clarity.py`, `tests/test_measurement_adapter.py`, `tests/test_performance_budgets.py`, `tests/verify_environment.py` ve `docs/roadmap/performance_budgets.json` güncellendi. Ölçüm ve görsel kanıtlar `docs/roadmap/` altında saklandı.

## Önerilen sonraki teknik iterasyon

Bir sonraki çalışma, DICOM ilk decode işlemini GUI thread’inden ayıran güvenli bir worker/preload akışı olmalıdır. Worker yalnızca pydicom dataset ve NumPy array üretmeli; `QPixmap`, `QImage` ve tüm QWidget işlemleri GUI thread’inde kalmalıdır. Eski path/cache anahtarları ve çok kareli frame yaşam döngüsü korunarak önce bir placeholder/önizleme, ardından tam görüntü yaklaşımı test edilmelidir.
