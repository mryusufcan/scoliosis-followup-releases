# İkon, tooltip ve tema kontrastı görsel bulguları

## Kapsam

18 Ağustos 2026 tarihli icon/tooltip/contrast değişiklikleri sonrasında offscreen 1400×900 görsel smoke çıktıları incelendi. Koyu tema ve açık tema için görüntüleyici sekmesi yakalandı; ikonlar 20 px metadata ile yeniden üretildi ve ana action yüzeyleri tema renklerine göre kontrol edildi.

## Bulgular

| Kontrol | Sonuç |
|---|---|
| Görüntüleyici ana toolbar ikonları | 20 px; metinle birlikte okunabilir ve toolbar yüksekliğini artırmıyor |
| DICOM W/L, parlaklık ve kare kontrolleri | Görev odaklı tooltip ve erişilebilir ad eklendi |
| DICOM bilgi, araçlar, işaretleme, oturum ve dışa aktarma | Tooltip açıklamaları tamamlandı; primary dışa aktarma ikonu açık temada beyaz olarak yeniden üretiliyor |
| Açık tema primary action | Koyu teal zemin + beyaz metin/ikon ile güçlendirildi |
| Açık tema aktif ölçüm | Açık amber zemin + koyu amber metin/ikon ile korunuyor |
| Açık tema tooltip | Beyaz zemin, koyu metin ve teal sınır kullanıyor |
| Diğer sekmeler | Omurga Birleştirme parça, manuel mod, yön ve sonuç eylemleri ikon/tooltip standardına alındı; Takip slider ve W/L açıklamaları ayrıntılandırıldı |

## Final doğrulama

`python -m py_compile` tüm değişen Python dosyalarında başarılı oldu. `python tests/smoke_ui_theme.py` sonucu `UI_THEME_SMOKE_OK` verdi. Standart regresyon paketi yeni ikon/tooltip testleriyle birlikte **78/78 başarılı** tamamlandı.

## Bilinen smoke ortamı notu

Offscreen Windows Qt çalıştırmasında `QFontDatabase` font dizini uyarısı görüldü ve ekran görüntüsündeki Türkçe karakterler kutucuk olarak render edildi. Bu uyarı renk/ikon QSS değişikliğinden kaynaklanmıyor; gerçek Windows oturumunda sistem fontlarıyla ayrıca görsel doğrulama yapılmalı. Renk yüzeyleri, ikon konumları ve toolbar yükseklikleri smoke çıktısında kontrol edildi.

## Geri dönüş noktası

`.restore_points\\icon_tooltip_contrast_20260818_232228\\` klasörü.
