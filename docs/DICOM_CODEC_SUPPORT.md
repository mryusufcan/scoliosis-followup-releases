# DICOM sıkıştırma desteği

Uygulama pydicom çözücü eklentileriyle aşağıdaki DICOM piksel aktarım türlerini
destekler. Teknik kalite denetiminde her dosyanın aktarım türü ve çözücü durumu
gösterilir; ayrıntılı CSV raporu da bu bilgiyi içerir.

| Aktarım türü | Durum |
| --- | --- |
| Sıkıştırılmamış DICOM | Desteklenir |
| RLE Lossless | Desteklenir |
| JPEG Baseline / Extended | Desteklenir |
| JPEG Lossless Process 14 / SV1 | Desteklenir |
| JPEG-LS Lossless / Near Lossless | Desteklenir |
| JPEG 2000 Lossless / JPEG 2000 | Desteklenir |
| HTJ2K | Desteklenir |

JPEG Baseline, JPEG Extended, JPEG-LS Near Lossless, JPEG 2000 ve HTJ2K'nin
kayıplı biçimlerinde uygulama teknik uyarı gösterir. Bu uyarı dosyanın bozuk
olduğu anlamına gelmez; çekimin zaten kayıplı sıkıştırılmış olabileceğini
belirtir.

Desteklenmeyen veya bozuk bir aktarım türünde uygulama görüntü açmadan önce
açık bir çözümleyici uyarısı verir. Bu bilgi teknik denetim içindir; klinik
görüntü kalitesi veya tanı doğrulaması değildir.

Pydicom'un güncel çözücü tablosu: https://pydicom.github.io/pydicom/stable/guides/plugin_table.html
