# Dağıtım kabul denetimi

Bu denetim kurulum programını çalıştırmaz ve hasta verilerine dokunmaz. EXE
klasörünün imzasını, kurulum dosyasının SHA-256 özetini ve imzalı
`update.json` bilgisini doğrular.

Önce EXE ve kurulum paketini üretin. Ardından `app` klasöründe aşağıdaki
komutu çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\release_acceptance.ps1
```

GitHub'da yayımlanan güncelleme bildirimini de denetlemek için:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\release_acceptance.ps1 `
  -FeedUrl "https://github.com/mryusufcan/scoliosis-followup-releases/releases/latest/download/update.json"
```

Başarılı sonuç: `KABUL DENETİMİ BAŞARILI: Dağıtım göndermeye hazır.`

## Başka bilgisayarda kısa kabul testi

Yayın öncesinde Windows Sandbox, sanal makine veya ayrı bir Windows kullanıcı
hesabında aşağıdakileri bir kez doğrulayın:

1. Kurulum dosyası açılır, uygulama başlar ve lisans durumu anlaşılır görünür.
2. Örnek bir DICOM yüklenir; görüntüleme, yakınlaştırma ve pencere ayarı çalışır.
3. JPEG Lossless bir DICOM açılır; görüntü piksel verisi okunur.
4. Cobb ölçümü, rapor dışa aktarımı ve şifreli yedek işlemi tamamlanır.
5. Uygulama kapatılıp yeniden açıldığında yerel kayıtlar korunur.
6. `Help → Güncellemeleri Denetle` alanı GitHub'daki `latest/download/update.json`
   adresini okuyabilir.

Bu kontrol klinik geçerlilik veya tıbbi cihaz mevzuatı onayı değildir.

Yeni başlayanlar için tüm paketleme, GitHub güncelleme ve geri dönüş adımları:
`docs\ACEMI_KULLANICI_REHBERI.md`.
