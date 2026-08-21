# Scoliosis Follow-Up 1.7.5

1.7.5, çevrimiçi lisans kurtarma akışını ve Windows Qt test kararlılığını düzelten bakım sürümüdür.

## Düzeltmeler

- Yerel lisans/deneme kaydı geçersiz göründüğünde uygulamanın sunucuya hiç başvurmadan erişimi reddetmesi düzeltildi.
- Yerel kayıt hatalı olsa bile sunucu aynı cihaz için etkin lisansı çevrimiçi doğrularsa uygulamanın güvenli biçimde açılması sağlandı.
- Etkin lisans bulunmayan cihazlarda sunucudaki HWID-bağlı deneme başlangıcı yetkili kaynak kabul edilerek yerel deneme kaydının güvenli biçimde onarılması sağlandı.
- Sunucu üzerinden onarım yapılırken deneme başlangıç tarihi korunur; uygulamayı yeniden kurmak veya yerel veriyi silmek deneme süresini sıfırlamaz.
- Sunucu etkin lisans doğrulamazsa erişimin kapalı kalması ve çevrimdışı tolerans verilmemesi korundu.
- Geçersiz yerel kayıt uyarısında eski lisans son kullanım tarihinin gösterilmesi engellendi.
- Pytest sırasında Qt uygulama ve tema nesnelerinin yeniden oluşturulmasından kaynaklanan Windows `0xC0000374` çökmesi giderildi.
- Aynı tema zaten etkinse native Qt stilinin gereksiz yere yeniden kurulması önlendi.

## Doğrulama

- Tam pytest paketi: **181/181 başarılı**.
- Paketleme ortamındaki modüler testlerin tamamı başarılı.
- EXE, installer, imzalı `update.json` ve SHA-256 eşleşmesi yerel kabul denetiminden geçti.
