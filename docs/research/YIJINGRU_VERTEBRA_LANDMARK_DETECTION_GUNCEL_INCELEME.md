# yijingru/Vertebra-Landmark-Detection — Güncel Kaynak İncelemesi

**İnceleme tarihi:** 20 Ağustos 2026  
**Amaç:** 68-landmark tabanlı Cobb taslak hattı için ana uygulamadan ayrık bir teknik deneme uygunluğunu belirlemek.

## Birincil kaynak bulguları

| Alan | Doğrulanan bilgi | Teknik sonuç |
|---|---|---|
| Depo | `yijingru/Vertebra-Landmark-Detection`, varsayılan dal `master`, son görünen commit `b9fc05c` | Kaynak karantinası bu commit’e sabitlenmelidir. |
| Kod lisansı | Depoda MIT lisansı vardır. | Kaynak kodunun incelenmesi ve uyarlanması, lisans metni/kopya bildirimi korunarak mümkündür. |
| Çalışma ortamı | README; Ubuntu 14.04, Python 3.6.4, PyTorch 1.1.0 ve OpenCV 4.1.0.25 belirtir. | Bu ortam Windows/Python 3.13 uygulamasına doğrudan gömülmeye uygun değildir; ayrık ve sabitlenmiş bir deneme ortamı gerekir. |
| Veri | README, SpineWeb dataset16 kaynaklı JPEG ve `.mat` etiket düzenini belirtir. | Depo lisansı, kaynak veri seti veya hasta verisinin yeniden kullanım iznini tek başına vermez. Veri şartları ayrıca doğrulanmalıdır. |
| Ağırlık | Önceden eğitilmiş ağırlıklar GitHub sürüm varlığı yerine harici bir Google Drive bağlantısıyla gösterilir. | Ağırlık için ayrı lisans, sürüm/commit bağı ve SHA-256 bütünlük kaydı olmadan indirme/çalıştırma yapılmamalıdır. |
| Çıktı hedefi | Projenin amacı skolyoz değerlendirmesi için vertebra landmark tespitidir; önceki teknik plan 17 vertebrada 68 nokta varsayar. | Çıktı tensörü/koordinat sırası bağımsız testte kaynak kodundan doğrulanmadan uygulama adaptörü yazılmamalıdır. |
| Yayın | README, ISBI 2020 kabulünü ve arXiv ön baskısını belirtir. | Yayın, teknik açıklama için referanstır; üretim veya klinik kullanım izni/garantisi değildir. |

## Güvenli karar

> Kaynak kodu MIT lisanslı görünse de, **ağırlıklar ve kaynak görüntü veri seti için açık bir yeniden dağıtım/klinik kullanım lisansı bu depoda gösterilmemektedir**. Bu nedenle ilk denemede sadece kod metadatası ve çıktı sözleşmesi incelenecek; harici ağırlık veya eğitim verisi otomatik indirilip çalıştırılmayacaktır.

## Karantinada doğrulanan çıktı sözleşmesi

Sabitlenen `b9fc05c` kaynak kodu **çalıştırılmadan** incelendi. Bu incelemede 68-landmark varsayımı doğrulandı.

| Aşama | Kaynak davranışı | Bağımsız adaptör için sözleşme |
|---|---|---|
| Ağ başlıkları | `hm: 1`, `reg: 2`, `wh: 8` | Tek vertebra merkezi, iki merkez ofseti ve dört köşe için sekiz bileşen üretilir. |
| Decoder | `K = 17` değerini sabitler. | En çok 17 vertebra adayını çıkarır. |
| Decoder satırı | Her satır `cen_x, cen_y, tl_x, tl_y, tr_x, tr_y, bl_x, bl_y, br_x, br_y, score` olmak üzere `17 × 11` biçimindedir. | Landmark adaptörü yalnızca sütun `2:10` değerlerini kullanır; merkez ve skor ayrı metadata olarak tutulur. |
| Ölçekleme | İlk 10 koordinat ağın `down_ratio` değeriyle, sonra giriş/orijinal görüntü boyutlarıyla yeniden ölçeklenir. | Girdi dönüşümü, ölçekler ve orijinal piksel koordinatlarına geri dönüş açıkça kaydedilmelidir. |
| Sıralama | Satırlar merkez `y` değerine göre üstten alta sıralanır. | 68 nokta, vertebra sırası üstten alta olacak şekilde üretilir. |
| Landmark açılımı | Her satırın köşeleri `tl, tr, bl, br` olarak alınır. | Çıktı sırası `17 × 4 = 68` noktadır: her vertebra için `tl, tr, bl, br`. |

Kaynak test kodu ağırlıkları `torch.load()` ile yüklemekte ve görüntü tensörünü sabit olarak `cuda` cihazına göndermektedir. Bu nedenle kaynak depo, mevcut Windows/Python 3.13 uygulamasında **doğrudan yürütülmeyecek**; yükleme güvenliği, CPU yolu ve modern PyTorch uyumu ayrı deneme adaptöründe ele alınmalıdır.

## Bağımsız Windows deneme ortamı

| Alan | Durum |
|---|---|
| Kaynak karantinası | `.quarantine\Vertebra-Landmark-Detection_b9fc05c` altında, sabit commit kaynak arşivinden açıldı. Kaynak kod çalıştırılmadı. |
| Kaynak arşivi SHA-256 | `B380729E6892D2B8959A2041439EC6E2DC238292B8ABAE6471BF70E5613F218` |
| Laboratuvar kökü | `.quarantine\landmark_lab` |
| Python | Ana uygulamadan ayrı Python 3.8.10 sanal ortamı oluşturuldu. |
| GPU | `nvidia-smi` NVML başlatılamadığı için GPU yoluna güvenilmemelidir; ilk deneme CPU yolu için hazırlanacaktır. |
| Ağırlık / DICOM erişimi | İndirilmedi, açılmadı veya işlenmedi. |

Google Drive klasörü salt okunur incelendiğinde, `weights.zip` adlı **85,7 MB** paylaşımlı bir arşiv görünmektedir. Klasörde ağırlıklara ait ayrı bir lisans metni, sürüm etiketi veya checksum görünmedi. Kullanıcı talebi doğrultusunda bu arşiv yalnızca karantinaya indirilebilir; indirildikten sonra SHA-256 kaydı alınmalı, arşiv listesi okunmalı ve PyTorch serileştirme dosyası güvenli yükleme denetimi tamamlanmadan ağırlıklar çalıştırılmamalıdır.

### Ağırlık karantina denetimi

| Kontrol | Sonuç |
|---|---|
| İndirilen arşiv | `weights.zip`, 89.819.955 bayt, SHA-256: `1B088004614C09AD6605F444C39B160144B07704B58BAE13F21DD19665D7A1D2` |
| Arşiv yapısı | Yalnızca `model_last.pth` içeriyor; 96.958.693 bayt açılmış toplam boyut ve yol doğrulaması geçti. |
| Model dosyası | SHA-256: `6A779E01B9A41601334E0A9541278FC557A95BD650C6C8DE311204821509D19B` |
| Serileştirme | Dosya Python pickle başlığı taşıyor. Varsayılan `torch.load()` çağrısı yapılmadı. |
| Güvenli yükleme | Ayrık PyTorch 2.1.2 CPU ortamında `torch.load(..., map_location="cpu", weights_only=True)` başarılı oldu. |
| İçerik | Üst seviye anahtarlar `epoch`, `state_dict`; epoch `25`; `state_dict` 270 tensör girdisi içeriyor. |
| Yan etki | Kaynak repo import edilmedi, ağ kurulmadı, `forward()` çağrılmadı, DICOM erişimi yapılmadı. |

## Bağımsız CPU landmark duman testi

Karantina laboratuvarındaki `landmark_cpu_smoke.py` betiği, kaynak deponun ana/test/eval modüllerini çağırmadan yalnızca ağ katmanlarını kurdu. ResNet ön eğitimli ağırlık indirme seçeneği kapatıldı; indirilen checkpoint yalnızca `weights_only=True` ile CPU’da yüklendi. Test girdisi DICOM değil, `1 × 3 × 1024 × 512` boyutunda sıfır değerli sentetik tensördü.

| Denetim | Sonuç |
|---|---|
| Ağ başlıkları | `hm: 1×1×256×128`, `reg: 1×2×256×128`, `wh: 1×8×256×128` |
| Decoder | `17×11` satır üretti. |
| Landmark açılımı | `68×2` nokta üretti. |
| Sıra | Üstten alta; her vertebra için `tl, tr, bl, br`. |
| Cihaz | CPU; GPU kullanılmadı. |
| DICOM erişimi | Yapılmadı. |
| Ana uygulama entegrasyonu | Yapılmadı. |
| Klinik sonuç / Cobb önerisi | Üretilmedi. |

Bu test, gerçek hasta görüntüsündeki doğruluğu kanıtlamaz. Yalnızca kaynak checkpoint ve ağ sözleşmesinin bağımsız ortamda 17 vertebra adayı ile 68 landmark biçimini teknik olarak oluşturabildiğini doğrular.

## Landmark adaptör sözleşmesi

`landmark_lab/landmark_contract.py`, modelden gelen `17×11` değerini uygulama entegrasyonundan bağımsız bir `LandmarkDraft` nesnesine dönüştürür. Bu modül model yüklemez, görüntü/DICOM açmaz, Cobb hesabı yapmaz ve klinik sonuç üretmez.

| Koruma | Davranış |
|---|---|
| Şekil kontrolü | Yalnızca tam `17×11` decoder satırı kabul edilir. |
| Sayısal kontrol | `NaN`/sonsuz koordinat reddedilir. |
| Güven kontrolü | Her skorun 0–1 aralığında olması gerekir. |
| Sıralama | Merkez `y` koordinatına göre üstten alta stabil sıralama uygulanır. |
| Açılım | Her satırdan `tl, tr, bl, br` köşeleri alınarak `68×2` piksel-koordinat landmark dizisi üretilir. |
| Test | Şekil, sıralama, 68 nokta, güven aralığı ve sonlu sayı durumları için 4 test başarılıdır. |

Bu adaptör, sonraki aşamada yalnızca **uzman düzeltmesine açık landmark taslağı** üretmek için kullanılabilir. Cobb açı seçimi ve kaydı ayrı bir sözleşme, kalite kapısı ve açık uzman onayı gerektirir.

## Bağımsız deneme için geçiş koşulları

1. Kullanılacak ağırlığın dosya adı, kaynağı, sürümü ve lisans/izin belgesi kaydedilir.
2. Dosyanın SHA-256 özeti alınır ve karantina manifestine yazılır.
3. Kaynak kod, sabit commit’te ve ana uygulama klasörünün dışında incelenir.
4. Sadece sentetik/izinli bir test girdisi ile 68 landmark çıktı sayısı, koordinat sırası ve güven alanları doğrulanır.
5. Çıktı ancak sonrasında uygulama içi AI taslağına dönüştürülebilir; Cobb önerisi hiçbir aşamada otomatik kaydedilmez.

## Kaynaklar

[1] [GitHub deposu](https://github.com/yijingru/Vertebra-Landmark-Detection)  
[2] [Depo README’si](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/README.md)  
[3] [MIT lisans metni](https://raw.githubusercontent.com/yijingru/Vertebra-Landmark-Detection/master/LICENSE)  
[4] [ISBI 2020 / arXiv ön baskısı](https://arxiv.org/pdf/2001.03187.pdf)
