# Scoliosis Follow-Up 1.7.4

1.7.4, Windows kurulumundaki lisans ve cihaz kimliği doğrulamasını düzelten bir bakım sürümüdür.

## Düzeltmeler

- Paketlenmiş EXE ile kaynak çalışma ortamının aynı Windows cihaz kimliğini üretmesi sağlandı.
- Windows sistem yolu uygulama ortamında bulunmadığında oluşabilen yanlış “başka cihaza ait” lisans uyarısı giderildi.
- Geçersiz veya bulunmayan lisans durumunda eski son kullanım tarihinin gösterilmesi engellendi.
- Lisans sunucusu cihaz için etkin lisans bulunmadığını doğruladığında eski yerel lisans önbelleğinin temizlenmesi sağlandı.
- Lisans yönetimi ekranı ile uygulama başlangıcının aynı lisans politikasını kullanması sağlandı.

## Korunan davranışlar

- Mevcut lisans ve deneme kayıtları silinmez veya kendiliğinden başka cihaza aktarılmaz.
- Çevrimdışı kullanım toleransı ve yerel kayıt bütünlüğü denetimi korunur.
- Görüntüleyici, Görüntü Birleştirme, takip/karşılaştırma ve yerel AI işlevlerinde davranış değişikliği yapılmadı.

## Doğrulama

- Windows cihaz kimliği yolu için yeni regresyon testi eklendi.
- Lisans politikası ve ilgili uygulama iş akışı testleri başarılı.
- Paket, kurulum ve imzalı güncelleme bildirimi yayın öncesi bütünlük denetiminden geçirildi.
