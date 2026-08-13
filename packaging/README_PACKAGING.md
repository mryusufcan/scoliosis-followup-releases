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
kütüphaneleri `requirements.txt` üzerinden yükler, testleri çalıştırır ve EXE'yi
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

## Kurulum sihirbazı (isteğe bağlı)

Dağıtımı tek bir kurulum dosyasıyla yapmak için önce yukarıdaki EXE paketini
oluşturun, sonra **Inno Setup 6** kurun ve şunu çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1
```

Çıktı: `installer\ScoliosisFollowUp_Setup.exe`. Kurulum kaldırıldığında da
yerel hasta kayıtları ve lisans durumu silinmez.

## Kod imzalama (isteğe bağlı, kurumsal dağıtım için önerilir)

Kod imzalama sertifikası Windows sertifika deposunda kuruluysa, sertifika
parmak izini kullanarak önce EXE'yi, sonra kurulum dosyasını imzalayabilirsiniz:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1 -Clean -CertificateThumbprint "SERTIFIKA_PARMAK_IZI"
powershell -ExecutionPolicy Bypass -File .\packaging\build_installer.ps1 -CertificateThumbprint "SERTIFIKA_PARMAK_IZI"
```

Bu seçenek için Windows SDK içindeki `signtool.exe` gerekir. Sertifika veya
Windows SDK yoksa parametreyi vermeyin; imzasız paket normal şekilde oluşur.

## Sorun giderme

- `Python bulunamadı`: Python 3.10+ 64-bit yükleyin ve PowerShell'i yeniden açın.
- Antivirüs uyarısı: Yerel olarak oluşturulmuş imzasız EXE'lerde görülebilir.
  Kurumsal dağıtım öncesinde kod imzalama sertifikasıyla imzalama önerilir.
- İlk paketlemenin ağ bağlantısı gerektirmesi normaldir; kütüphaneler indirilir.
