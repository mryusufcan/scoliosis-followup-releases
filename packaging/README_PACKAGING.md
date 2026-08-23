# Windows EXE paketleme

Bu proje, Python veya ek kütüphane gerektirmeyen Windows paketi olarak
hazırlanır. Paket giriş noktası `main.py`'dır; Görüntüleyici, DICOM Omurga
Birleştirme, Skolyoz Takip, PACS, lisans ve tüm modüler özellikler dahildir.

## Bir defalık gereksinim

Paketleme yapılacak bilgisayarda **Python 3.10+ (64-bit)** kurulu olmalı ve
kurulumda **Add Python to PATH** seçili olmalıdır. Hedef kullanıcı bilgisayarında
Python kurulması gerekmez.

## Paket oluşturma

Uygulama kök klasöründe PowerShell açın ve çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Clean
```

Betik, `.venv-build` adlı ayrı bir paketleme ortamı oluşturur; gerekli tüm
kütüphaneleri `requirements-dev.txt` üzerinden yükler, testleri çalıştırır ve EXE'yi
oluşturur.

## Çıktı ve dağıtım

Oluşan dosya:

```text
dist\ScoliosisFollowUp\ScoliosisFollowUp.exe
```

`dist\ScoliosisFollowUp` klasörünün **tamamını** hedef bilgisayara kopyalayın.
`ScoliosisFollowUp.exe` çalıştırılır. Bu `onedir` biçimi, PySide6, DICOM/PACS
ve kriptografi bağımlılıkları için tek EXE biçiminden daha güvenilirdir.

Kullanıcı verileri (tetkik geçmişi, ayarlar, lisans süresi ve hata günlüğü)
EXE'nin yanında değil, şu klasörde tutulur:

```text
%LOCALAPPDATA%\ScoliosisFollowUp
```

Bu nedenle yeni sürüm kurarken `dist` klasörünü değiştirmek hasta kayıtlarını
silmez. Yedekleme için uygulamadaki şifreli veritabanı yedeği özelliğini kullanın.

## Dağıtım güvenliği

Paketleme betiği her EXE üretiminde `%LOCALAPPDATA%\ScoliosisFollowUp\security_keys\integrity_private.pem`
özel anahtarını oluşturur veya yeniden kullanır. Bu anahtar **yalnızca paketleme
bilgisayarında** kalır; başka bilgisayara, Git deposuna veya müşteriye asla
kopyalanmamalıdır. Kaybolmaması için güvenli bir parola kasasına ya da şifreli
harici ortama yedekleyin.

Paketin içine imzalı `runtime_integrity.json` dosyası eklenir. Uygulama
açılırken EXE ve dağıtımdaki dosyalar doğrulanır; dosya değiştirilmişse
uygulama açılmaz. Kurulum varsayılan olarak yönetici izniyle `Program Files`
altına yapılır; normal kullanıcılar kod dosyalarını değiştiremez.

Bu koruma, uygulama kodunun kopyalanmasını zorlaştırır ve kurcalamayı tespit
eder; fiziksel olarak bilgisayarın yönetici yetkisine sahip saldırgana karşı
mutlak koruma sağlamaz. Kurumsal dağıtımda ayrıca Authenticode kod imzalama
sertifikası kullanın. Sertifika yoksa paket teknik olarak oluşturulabilir,
ancak bu paket public release olarak yayımlanamaz.

## Kurulum sihirbazı (isteğe bağlı)

Dağıtımı tek bir kurulum dosyasıyla yapmak için önce yukarıdaki EXE paketini
oluşturun, sonra **Inno Setup 7 (veya 6)** kurun ve şunu çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1
```

Çıktı: `installer\ScoliosisFollowUp_Setup.exe`. Kurulum kaldırıldığında da
yerel hasta kayıtları ve lisans durumu silinmez.

## Kod imzalama (public release için zorunlu)

Kod imzalama sertifikası Windows sertifika deposunda kuruluysa, sertifika
parmak izini kullanarak önce EXE'yi, sonra kurulum dosyasını imzalayabilirsiniz:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Clean -CertificateThumbprint "SERTIFIKA_PARMAK_IZI"
powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1 -CertificateThumbprint "SERTIFIKA_PARMAK_IZI"
```

Bu seçenek için Windows SDK içindeki `signtool.exe` ve geçerli bir Code Signing
sertifikası gerekir. Mevcut bilgisayarda yapılan salt-okunur kontrolünde geçerli
Code Signing sertifikası bulunmadı ve mevcut QA EXE’si `NotSigned` durumundadır.
Bu yüzden 1.7.8 public release’i Authenticode sertifikası kurulana kadar
bilinçli olarak yayımlanmayacaktır. Self-signed sertifika son kullanıcı güveni
sağlamadığı için public release çözümü değildir.

`.github/workflows/windows-release.yml` etikete push edildiğinde yalnızca build
ve test çalıştırır. Public GitHub Release için workflow_dispatch ekranında
`publish=true` açıkça seçilmeli, sertifika kurulmuş güvenilir bir signing runner
kullanılmalı ve `WINDOWS_CERTIFICATE_THUMBPRINT` tanımlı olmalıdır. Private
signing key veya PFX dosyası kaynak koduna ya da GitHub artifact’ına konulmaz.

## İmzalı güncelleme bildirimi

Uygulama güncellemeyi kendisi indirmez veya kurmaz; yalnızca HTTPS üzerinde
yayınlanan imzalı bir bildirimi doğrular ve kullanıcıya indirme adresini gösterir.
Yeni kurulum dosyasını yayınladıktan sonra, özel bütünlük anahtarını kullanarak
bildirimi oluşturun:

```powershell
.\.venv-build\Scripts\python.exe .\packaging\generate_update_feed.py `
  --version "1.4.0" `
  --url "https://ornek-alanadiniz.com/ScoliosisFollowUp_Setup.exe" `
  --installer .\installer\ScoliosisFollowUp_Setup.exe `
  --private-key "$env:LOCALAPPDATA\ScoliosisFollowUp\security_keys\integrity_private.pem" `
  --output .\update.json
```

`update.json` dosyasını HTTPS ile erişilebilen bir adreste yayınlayın ve bu
adresi uygulamadaki **Help → Güncellemeleri Denetle** alanına girin. Özel anahtar
veya kurulum dosyası dışında hiçbir hasta verisi bu işleme dahil edilmez.

## Sorun giderme

- `Python bulunamadı`: Python 3.10+ 64-bit yükleyin ve PowerShell'i yeniden açın.
- Antivirüs uyarısı: Yerel olarak oluşturulmuş imzasız EXE'lerde görülebilir.
  Kurumsal dağıtım öncesinde kod imzalama sertifikasıyla imzalama önerilir.
- İlk paketlemenin ağ bağlantısı gerektirmesi normaldir; kütüphaneler indirilir.
