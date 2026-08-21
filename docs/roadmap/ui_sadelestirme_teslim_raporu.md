# Scoliosis Follow-Up — UI Sadeleştirme Teslim Raporu

**Tarih:** 18.08.2026  
**Amaç:** Kullanıcının uygulamayı açtıktan sonra doğru işlemi daha hızlı anlaması, yanlış butonlara daha az basması ve ölçüm/karşılaştırma/rapor sonucuna daha kısa sürede ulaşması.

## Uygulanan kullanıcı deneyimi düzenlemeleri

### Ana pencere, menü ve sekmeler

Üst menülerdeki sembol ve dil karışıklığı azaltıldı. Menü başlıkları artık **Hasta**, **Takip**, **Görüntüleme**, **Veri ve PACS**, **Raporlar**, **Gelişmiş** ve **Yardım** olarak düzenleniyor. Deneysel AI işlemleri klinik günlük akıştan ayrılarak **Gelişmiş** altında ve taslak niteliği açık metinle gösteriliyor.

Sekmeler görev odaklı adlandırıldı: **Görüntüleyici**, **Omurga Birleştirme** ve **Takip ve Karşılaştırma**. Her sekmeye kullanıcıya o ekranda ne yapabileceğini açıklayan tooltip eklendi; sekme düzeni korunurken başlıkların okunabilirliği artırıldı.

### Ortak UI açıklık katmanı

`modular_app/ui/ui_clarity.py` oluşturuldu. Bu katman, butonlara ortak birincil/ikincil/ölçüm/tehlike/sessiz eylem rolleri, erişilebilir adlar, açıklayıcı tooltip’ler ve dinamik QSS yenilemesi uygular. Aynı modül, sekmelerdeki bağlam satırlarını üretir.

Ana sekmelere “şimdi ne yapmalıyım?” satırları eklendi. Bu satırlar aktif işlemi ve sıradaki adımı açık metinle gösteriyor:

| Sekme | Kullanıcıya gösterilen akış |
|---|---|
| Görüntüleyici | Görüntü Aç → Sığdır → W/L veya ölçüm aracı |
| Takip ve Karşılaştırma | Tetkik Yükle → bir/iki görüntü seç → karşılaştır → hizala → ölç/raporla |
| Omurga Birleştirme | Parçaları yükle → Hizala ve Birleştir → kaliteyi kontrol et → sonucu onayla |

### Görüntüleyici

“Aç” yerine **Görüntü Aç**, “Liste” yerine **Listeyi Temizle**, “Sığdır” yerine **Görüntüyü Sığdır**, “DICOM” yerine **DICOM Bilgisi** kullanıldı. “Araçlar” düğmesi **Daha Fazla Araç**, “İşaretle” düğmesi **İşaretleme** olarak açıklaştırıldı. Ölçüm düğmeleri Cobb ve mesafe işlevini açıkça belirtiyor; kısayollar tooltip içinde gösteriliyor.

Aktif görüntü açıldığında dosya adı, piksel boyutu ve “W/L ayarla veya ölçüm aracı seç” sonraki adımı bağlam satırında gösteriliyor. Görüntü kaldırıldığında satır tekrar başlangıç yönlendirmesine dönüyor.

### Takip ve karşılaştırma

**Tetkik Yükle**, **Yan Yana Karşılaştır**, **Overlay Karşılaştırma**, **Cobb Ölç**, **Otomatik Hizala** ve **Hizalamayı Sıfırla** adları kullanıldı. Overlay dönüşüm değerleri artık `ΔX/ΔY/Z/R` gibi tek harflerle değil, **Yatay / Dikey / Ölçek / Döndürme** ifadeleriyle gösteriliyor.

Otomatik hizalama düğmesi, iki tetkik seçilmeden pasif durumda tutuluyor. Böylece kullanıcı kullanılabilir olmayan bir eyleme basıp uyarı beklemek zorunda kalmıyor. İki tetkik seçildiğinde aktifleşiyor; farklı hasta veya uyumsuz projeksiyon kontrolleri mevcut davranışını koruyor.

### Omurga birleştirme

Birleştirme akışı **Seçili Görüntülerden Parça Seç → Hizala ve Birleştir → Kaliteyi kontrol et → Sonucu Onayla ve Kayda Hazırla** şeklinde görünür hâle getirildi. Parça kaldırma, manuel düzeltme, kalite ve sonraki aşama metinleri tam ifadelerle güncellendi.

Kalite sonucu iyi, orta veya düşük olduğunda bağlam satırı doğrudan sonraki eylemi gösteriyor. Düşük kalite durumunda manuel hizalama gerektiği; iyi kalite durumunda dikiş bölgelerinin kontrol edilmesi gerektiği açıkça belirtiliyor.

### Sık kullanılan popup’lar

Tetkik Geçmişi, Cobb Ölçüm Geçmişi, Hasta Takip Özeti, Cobb Trend Grafiği ve Longitudinal Takip Merkezi dialoglarında ortak bağlam satırı, açıklayıcı alt başlık, belirgin birincil eylem ve daha anlaşılır kapatma/yenileme metinleri kullanıldı. Hasta Takip Özeti’nde tek satır seçiminin açma, iki satır seçiminin Overlay karşılaştırma anlamına geldiği seçim sayısına göre dinamik olarak gösteriliyor.

Cobb geçmişinde **Doğrula ve Kilitle** birincil eylem, **Seçili Ölçümü Kaldır** tehlikeli eylem, kanıt görüntüleme ise ikincil/sessiz eylem olarak ayrıştırıldı. Bu görsel hiyerarşi ölçüm verisinin yanlışlıkla silinmesi riskini azaltır; repository kilitleme kuralları değiştirilmemiştir.

## Değişen temel dosyalar

| Dosya | Değişiklik |
|---|---|
| `main.py` | Merkezi QSS action/dialog rolleri; doğrudan açılış menüleri |
| `modular_app/run_modular.py` | Menü ve sekme adları, tab tooltip’leri |
| `modular_app/ui/ui_clarity.py` | Yeni ortak UI açıklık yardımcıları |
| `modular_app/ui/viewer_widget.py` | Görüntüleyici bağlam satırı ve açıklayıcı butonlar |
| `modular_app/ui/viewer_core.py` | Aktif görüntü/sonraki adım bağlam güncellemesi |
| `modular_app/ui/workspace_widget.py` | Takip bağlam satırı, tam eylem adları |
| `modular_app/ui/workspace_actions.py` | Seçim bağlamı, otomatik hizalama etkinlik kuralı, tam overlay değerleri |
| `modular_app/ui/stitch_widget.py` | Birleştirme adımları ve birincil eylem metinleri |
| `modular_app/ui/stitch_io.py` | Kalite sonucuna göre sonraki adım bağlamı |
| `modular_app/timeline/exam_timeline.py` | Tetkik geçmişi popup açıklığı |
| `modular_app/timeline/cobb_history.py` | Cobb eylem hiyerarşisi |
| `modular_app/timeline/follow_up_summary.py` | Tek/çift tetkik seçim yönlendirmesi |
| `modular_app/timeline/cobb_trend.py` | Dialog başlığı ve yenileme eylemi |
| `modular_app/timeline/longitudinal_center_dialog.py` | Ortak dialog eylem rolleri |
| `tests/test_modular_ui_clarity.py` | Sekme, menü, bağlam satırı ve buton regresyon testleri |

## Doğrulama

| Kontrol | Sonuç |
|---|---:|
| UI açıklık regresyon testleri | **3/3 başarılı** |
| Longitudinal dialog smoke testi | **1/1 başarılı** |
| Longitudinal menü testi | **1/1 başarılı** |
| Standart test runner | **73 test, 73 başarılı** |
| `python -m py_compile` | Başarılı |
| `python tests/smoke_ui_theme.py` | `UI_THEME_SMOKE_OK` |
| Cache profili | Ortalama hit **0.07 ms** |
| Startup profili | Import **713.39 ms**, construct **129.23 ms**, first paint **22.36 ms** |

Startup değerleri eklenen bağlam satırları ve açıklayıcı kontroller nedeniyle önceki profile göre bir miktar yükselmiş olsa da mevcut bütçelerin altındadır: import 800 ms, construct 250 ms ve first paint 50 ms. Cache-hit performansı korunmuştur.

Offscreen Qt çalıştırmalarında görülen PySide6 font-directory uyarısı non-fatal’dır; smoke ve tüm testler başarılıdır.

## Veri ve iş mantığı güvenliği

Bu iterasyonda DICOM piksel matrisi, DICOM metadata’sı, SQLite şeması, Cobb hesaplama geometrisi, undo/redo, export akışları ve cache veri politikası değiştirilmedi. Değişiklikler UI metinleri, bağlam göstergeleri, buton etkinlik durumu ve popup düzeniyle sınırlıdır. AI/otomatik ölçüm sonuçlarının taslak ve klinik doğrulama gerektiren statüsü korunmuştur.

## Geri dönüş noktası

Değişiklik öncesi yedek:

`.restore_points\\ui_clarity_flow_20260818_220342`

Önceki E2-02 yedekleri de korunmuştur. Sadeleştirme değişikliklerini geri almak için bu klasördeki dosyalar kullanılabilir.

## Kaynak dosya referansları

[1]: ../../main.py "Ana pencere ve merkezi tema"
[2]: ../../modular_app/run_modular.py "Modüler başlatıcı ve menüler"
[3]: ../../modular_app/ui/ui_clarity.py "Ortak UI açıklık yardımcıları"
[4]: ../../modular_app/ui/viewer_widget.py "Görüntüleyici sekmesi"
[5]: ../../modular_app/ui/workspace_widget.py "Takip ve karşılaştırma sekmesi"
[6]: ../../modular_app/ui/stitch_widget.py "Omurga birleştirme sekmesi"
