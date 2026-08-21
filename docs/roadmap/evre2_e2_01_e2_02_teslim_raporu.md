# Evre 2 — E2-01 ve E2-02 Teslim Raporu

**Tarih:** 18.08.2026  
**Kapsam:** Legacy Cobb adapter, eğri bazlı Longitudinal Takip Merkezi, performans bütçesi ve modül sınırı entegrasyon testleri.

## Uygulanan değişiklikler

### E2-01 — Legacy Cobb adapter

`modular_app/domain/measurement_adapter.py` oluşturuldu. Adapter, mevcut `cobb_measurements` SQLite tablosunu değiştirmeden legacy satırları ortak `MeasurementRecord` sözleşmesine çeviriyor. `point_data` JSON alanı dört noktalı `coordinates` tuple’ına dönüştürülüyor; bozuk veya eksik point verisi uygulamayı durdurmadan boş tuple olarak ele alınıyor. `is_locked` alanı `VERIFIED`/`DRAFT` durumuna, legacy ölçüm yöntemi provenance alanına, `source_sop_instance_uid`, kullanıcı, algoritma sürümü, vertebra çifti ve eğri yönü kaynak/provenance alanlarına taşınıyor.

`curve_key` kanonik biçimde `upper|lower|direction` olarak üretiliyor. Adapter’ın `insert()` yolu mevcut `add_cobb_measurement()` API’sini kullanıyor; doğrulanmış kayıtlar sonrasında mevcut `verify_and_lock_cobb_measurement()` ile kilitleniyor. Yeni tablo, migration veya DICOM yazma işlemi eklenmedi. Adapter’ın runtime import’unda SQLite bağımlılığı tutulmadı; repository tipi yalnızca `TYPE_CHECKING` altında kullanılıyor.

### E2-02 — Longitudinal Takip Merkezi

`modular_app/timeline/longitudinal_center.py` içinde Qt bağımsız servis katmanı oluşturuldu. Servis, Cobb ölçümlerini `(üst vertebra, alt vertebra, yön)` anahtarına göre ayrı eğrilere grupluyor, aynı sınav tarihindeki tekrarları tek zaman noktası hâline getiriyor ve aynı tarihte doğrulanmış kaydı tercih ediyor. İlk/son değer, sayısal delta, tarih aralığı ve yıllıklandırılmış değişim hesaplanıyor. Bu hesaplar klinik tanı, prognoz veya otomatik tedavi önerisi olarak sunulmuyor.

`modular_app/timeline/longitudinal_center_dialog.py` içinde hasta seçici, eğri filtresi, doğrulanmış kayıt filtresi, mevcut karanlık tema ile uyumlu metrik kartları, `CobbTrendWidget` tabanlı grafik ve `Overlay'e Gönder` akışı eklendi. Overlay callback’i son longitudinal ölçümün DICOM yolunu mevcut `_activate_viewer_path_for_tracking` facade’ına gönderiyor. Sol navigasyon paneli ve mevcut sekme düzeni değiştirilmedi.

`modular_app/run_modular.py` içindeki **▥ Takip** menüsüne **Longitudinal Takip Merkezi** action’ı eklendi.

## Test sonuçları

| Kontrol | Sonuç |
|---|---:|
| `python -m py_compile` — değişen kaynak ve test dosyaları | Başarılı |
| `python tests/smoke_ui_theme.py` | `UI_THEME_SMOKE_OK` |
| E2-01 adapter testleri | 4/4 başarılı |
| Longitudinal servis testleri | 5/5 başarılı |
| Longitudinal dialog smoke testi | 1/1 başarılı |
| Longitudinal menü entegrasyon testi | 1/1 başarılı |
| Performans bütçesi entegrasyon testleri | 6/6 başarılı |
| Standart runner | **70 test, 70 başarılı** |

## Güncel performans ölçümü

Ölçüm gerçek `dev_data/dicom_samples` dosyalarıyla, mevcut optimizasyon profilleri kullanılarak yapıldı.

| Metrik | Güncel sonuç | Bütçe | Durum |
|---|---:|---:|---|
| DICOM okuma ortalaması | 11.52 ms | 15.00 ms | Başarılı |
| 8-bit render ortalaması | 275.52 ms | 300.00 ms | Başarılı |
| En büyük tek görüntü render’ı | 844.61 ms | 900.00 ms | Başarılı |
| Viewer cache-hit ortalaması | 0.07 ms | 1.00 ms | Başarılı |
| Startup import | 676.46 ms | 800.00 ms | Başarılı |
| Pencere kurulumu | 109.43 ms | 250.00 ms | Başarılı |
| İlk paint | 17.46 ms | 50.00 ms | Başarılı |

Cache limitleri için entegrasyon testleri viewer dataset entry, pixmap entry, NumPy array byte bütçesi ve oversized array eviction davranışlarını kontrol ediyor. Klasör tarama metadata akışı `stop_before_pixels=True` ile piksel matrisi decode etmiyor.

## Geri dönüş noktaları

Aşağıdaki tarih damgalı kopyalar oluşturuldu:

- `.restore_points\\e2_02_longitudinal_center_20260818_214647`
- `.restore_points\\e2_02_menu_integration_20260818_214741`
- `.restore_points\\e2_02_test_runner_20260818_214936`
- `.restore_points\\e2_02_ui_smoke_20260818_215303`

## Korunan kısıtlar

Mevcut SQLite tabloları ve eski export akışları korunmuştur. DICOM piksel matrisi, metadata ve dosyaları hiçbir yeni akış tarafından değiştirilmez. Taslak, AI ve otomatik sonuçlar doğrulanmış klinik sonuç olarak işaretlenmez. Domain contracts ve longitudinal servis Qt, pydicom, SQLite, reportlab veya OpenCV import etmez. Offscreen Qt çalıştırmalarındaki mevcut PySide6 font-directory uyarısı non-fatal olup smoke ve test sonuçlarını etkilememiştir.

## Çalıştırılan profil komutları

```text
python tests/perf_profile.py --limit 10 --repeats 3
python tests/perf_cache_profile.py
python tests/perf_startup_profile.py
python tests/run_modular_tests.py
python tests/smoke_ui_theme.py
```
