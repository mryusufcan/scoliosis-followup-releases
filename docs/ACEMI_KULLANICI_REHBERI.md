# Scoliosis Follow-Up — Acemi Kullanıcı Rehberi

Bu rehber, uygulamayı günlük kullanmak, yeni sürüm hazırlamak, GitHub üzerinden
yayınlamak ve bir sorun olduğunda geri dönmek için hazırlanmıştır. Komutları
tek tek kopyalayıp PowerShell penceresine yapıştırabilirsiniz.

> **Önemli:** Bu rehberdeki tüm komutlar `app` klasöründe çalıştırılır.
> Aşağıdaki satırla doğru klasöre geçin:

```powershell
cd "C:\Users\yusuf\Documents\Codex\2026-08-13\referenced-chatgpt-conversation-this-is-an\app"
```

## 1. Günlük kullanım: hangi dosyayı açacağım?

### Kurulmuş uygulama

Kurulum yaptıysanız Başlat Menüsü veya masaüstündeki **Scoliosis Follow-Up**
kısayolunu açın. Günlük kullanım için en kolay yöntem budur.

### Taşınabilir paket

Kurulum yapmadan kullanmak isterseniz aşağıdaki dosyayı açın:

```text
app\dist\ScoliosisFollowUp\ScoliosisFollowUp.exe
```

`dist\ScoliosisFollowUp` klasörünün tamamı birlikte kalmalıdır. Sadece EXE
dosyasını başka yere taşımayın.

### Geliştirme sırasında

Kaynak koddan uygulamayı açmak için:

```powershell
python .\main.py
```

Bu yöntem geliştirici içindir; dağıtım için EXE veya kurulum dosyasını kullanın.

## 2. Kodda değişiklik yapmadan önce yedek alma

Çalışan bir sürüm varken önce geri dönüş noktası oluşturun:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\create_restore_point.ps1 `
  -Portable -Message "degisiklik-oncesi"
```

Bu yedek kodu ve ayar dosyalarını saklar. Hasta verileri, DICOM görüntüleri,
yerel veritabanı ve gizli anahtar bu arşive bilinçli olarak eklenmez.

Kullanılabilir yedekleri listelemek için:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\restore_point.ps1 -List
```

Bir geri dönüş noktası gerekirse önce uygulamayı kapatın. Ardından:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\restore_point.ps1 `
  -Portable -Tag "LISTEDE_GORUNEN_YEDEK_ADI"
```

Komut sizden onay ister; yalnızca `EVET` yazdığınızda geri yükler.

## 3. Yeni sürüm hazırlama

Örnek: mevcut sürüm `1.4.0`, yeni sürüm `1.4.1` olacak.

1. Önce `VERSION` dosyasını açın:

```powershell
notepad .\VERSION
```

2. İçindeki sürümü `1.4.1` yapın, kaydedin ve Not Defteri'ni kapatın.

3. EXE paketini oluşturun. Bu işlem gerekli kütüphaneleri kurar ve otomatik
   testleri çalıştırır:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Clean
```

Başarılı sonuçta bu klasör oluşur:

```text
app\dist\ScoliosisFollowUp
```

4. Tek dosyalık Windows kurulumunu oluşturun:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1
```

Başarılı sonuç:

```text
app\installer\ScoliosisFollowUp_Setup.exe
```

### Test hata verirse

Derleme test hatasında durursa bu doğrudur; `-SkipTests` kullanmayın. Ayrıntıyı
şurada açın:

```powershell
notepad .\build\test-results.txt
```

Hata metnini paylaşın; çözmeden EXE'yi yayınlamayın.

## 4. Yayın öncesi kabul denetimi

Kurulum paketini kullanıcıya göndermeden önce aşağıdaki denetimi çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\release_acceptance.ps1
```

Bu işlem şunları kontrol eder:

- EXE klasörünün imzalı bütünlüğü,
- kurulum dosyasının SHA-256 özeti,
- yerel `update.json` dosyasının imzası ve sürümü.

Beklenen son satır:

```text
KABUL DENETİMİ BAŞARILI: Dağıtım göndermeye hazır.
```

## 5. GitHub Releases ile güncelleme yayınlama

GitHub deposu yalnızca kurulum dosyasını ve `update.json` dosyasını içermelidir.
Kaynak kodunuzu, `app` klasörünü veya gizli anahtarınızı GitHub'a yüklemeyin.

Kullanılan depo:

```text
https://github.com/mryusufcan/scoliosis-followup-releases
```

### 5.1. İmzalı güncelleme dosyasını oluşturma

Önce yukarıdaki 3. bölümde EXE ve kurulum paketini oluşturmuş olun. Sonra,
sürüm numarasını yeni sürümünüze göre değiştirerek aşağıdaki komutu çalıştırın.
Bu örnek `1.4.1` içindir:

```powershell
.\.venv-build\Scripts\python.exe .\packaging\generate_update_feed.py `
  --version "1.4.1" `
  --url "https://github.com/mryusufcan/scoliosis-followup-releases/releases/download/v1.4.1/ScoliosisFollowUp_Setup.exe" `
  --installer .\installer\ScoliosisFollowUp_Setup.exe `
  --private-key .\security_keys\integrity_private.pem `
  --output .\update.json
```

Bu işlem `app\update.json` dosyasını üretir. Bu dosya kurulum dosyasının
özetini ve imzasını taşır.

> **Asla paylaşmayın:** `security_keys\integrity_private.pem` sizin gizli
> imzalama anahtarınızdır. GitHub'a, Drive'a, kullanıcıya veya e-postaya
> yüklenmez.

### 5.2. GitHub'da yeni Release oluşturma

1. Tarayıcıda deponuzu açın.
2. **Releases** → **Draft a new release** seçin.
3. **Choose a tag** alanına `v1.4.1` yazın ve yeni etiketi oluşturun.
4. Başlık alanına `Scoliosis Follow-Up 1.4.1` yazın.
5. Dosya alanına aşağıdaki iki dosyayı sürükleyip bırakın:

```text
app\installer\ScoliosisFollowUp_Setup.exe
app\update.json
```

6. **Publish release** düğmesine basın.

GitHub EXE yüklemesinde sorun çıkarırsa önce hatalı dosya satırındaki `×`
işaretine basın; sayfayı yenileyip tekrar deneyin. Devam ederse EXE'yi ZIP'e
sıkıştırın, ZIP'i yükleyin ve 5.1 adımını ZIP dosya adı/yolu ile yeniden yapın.

### 5.3. GitHub yayını gerçekten doğru mu?

Release yayınlandıktan sonra aşağıdaki komutu çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\release_acceptance.ps1 `
  -FeedUrl "https://github.com/mryusufcan/scoliosis-followup-releases/releases/latest/download/update.json"
```

Bu komut GitHub'daki dosyanın yerelde hazırladığınız imzalı bilgiyle aynı
olduğunu doğrular. Başarılı olmadan duyuru veya dağıtım yapmayın.

## 6. Uygulama içindeki güncelleme bağlantısı

Uygulamada **Help → Güncellemeleri Denetle** bölümüne bir kez aşağıdaki adresi
girin:

```text
https://github.com/mryusufcan/scoliosis-followup-releases/releases/latest/download/update.json
```

Bu adres kaydedilir. Sonraki sürümlerde yeni sürümün Release'ine yine aynı isimli
`update.json` dosyasını yüklemeniz yeterlidir; `latest` otomatik olarak en yeni
yayımlanmış sürümü bulur.

## 7. Başka bilgisayarda son kullanıcı testi

Mümkünse yeni bir Windows hesabında, Windows Sandbox'ta veya başka bilgisayarda
şunları deneyin:

1. `ScoliosisFollowUp_Setup.exe` ile kurulum yapılır ve uygulama açılır.
2. Lisans ekranı anlaşılır görünür.
3. Örnek DICOM açılır; yakınlaştırma, pencere ayarı ve anotasyonlar çalışır.
4. JPEG Lossless bir DICOM açılır.
5. Cobb ölçümü, rapor dışa aktarımı ve şifreli yedek çalışır.
6. Uygulama kapatılıp açıldığında hasta takibi kayıtları korunur.
7. **Help → Güncellemeleri Denetle** GitHub adresini okuyabilir.

Sıkıştırılmış DICOM desteğinin teknik özeti:
`docs\DICOM_CODEC_SUPPORT.md`.

Bu kontrol uygulamanın teknik kabul testidir; klinik geçerlilik veya tıbbi cihaz
mevzuatı onayı değildir.

## 8. Sık görülen durumlar

| Durum | Ne yapmalıyım? |
| --- | --- |
| `packaging\build_windows.ps1 bulunamadı` | PowerShell'de önce `app` klasörüne geçin. |
| `Otomatik testler başarısız` | `build\test-results.txt` dosyasını açın; testleri atlamayın. |
| EXE açılırken bütünlük hatası | `dist\ScoliosisFollowUp` klasörünün tamamını birlikte kopyalayın. |
| GitHub'a EXE yüklenmiyor | Hatalı satırı silip tekrar deneyin; gerekirse ZIP yükleyip update.json'u yeniden üretin. |
| Güncelleme bulunamıyor | Release'in yayımlandığını, `update.json` dosyasının eklendiğini ve `latest` bağlantısının doğru olduğunu kontrol edin. |
