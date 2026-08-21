# Kompakt Viewer / Takip Toolbar Teslim Notu

Viewer ve Takip/Karşılaştırma sekmelerindeki toolbar dikey alan kullanımı azaltıldı. Buton metinleri ve görev açıklıkları korunurken ikon boyutu 26 px’den 20 px’e indirildi; kompakt butonların minimum yüksekliği 27 px’den 21 px’e çekildi. Buton iç boşlukları, grup iç boşlukları, ribbon aralıkları ve dış layout margin’leri sıkılaştırıldı.

Viewer toolbar’ın iki satırlı yapısı korunmuştur; bu nedenle Window/Level, DICOM bilgi, araç, oturum ve dışa aktarma işlevleri hızlı erişilebilir kalır. Yalnızca dikey boşluk azaltılmıştır. Ölçüm butonlarının amber active state’i, ana eylemlerin turkuaz rengi ve açıklayıcı metinleri korunmuştur.

Görsel smoke capture’da 1919×1033 pencere görünümünde toolbar’ın önceki geniş/dolgun yerleşime göre daha kısa olduğu ve DICOM görüntü alanının daha fazla dikey alan kazandığı doğrulanmıştır. Offscreen ortamındaki eksik font uyarısı non-fatal’dir.

| Kontrol | Sonuç |
|---|---:|
| Python derleme | Başarılı |
| UI tema smoke | `UI_THEME_SMOKE_OK` |
| Standart regresyon | `77/77 OK` |
| Görsel smoke | Başarılı |

Geri dönüş noktası: `.restore_points\\compact_toolbar_20260818_230224`.
