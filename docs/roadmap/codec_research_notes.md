# Codec araştırma notları

## Gerçek veri envanteri

`dev_data/dicom_samples` altında 16 dosya bulundu. Tamamı `1.2.840.10008.1.2.4.70` — JPEG Lossless, Non-Hierarchical, First-Order Prediction (Process 14, Selection Value 1); tamamı compressed, tek frameli ve 16-bit. Bu fixture setinde JPEG 2000 veya JPEG-LS örneği yok.

## Resmî pydicom dokümantasyonu

Kaynak: https://pydicom.github.io/pydicom/stable/guides/user/image_data_handlers.html (pydicom 3.0.2 dokümantasyonu, erişim 2026-08-22).

- Sıkıştırılmış Pixel Data için pydicom; `pylibjpeg` ve `pylibjpeg-libjpeg`, `pylibjpeg-openjpeg`, `pylibjpeg-rle` eklentilerini; `jpeg_ls`/pyjpegls; GDCM; ve Pillow seçeneklerini listeliyor.
- JPEG-LS için pydicom tablosu NumPy + GDCM ve Pillow yollarını gösteriyor; JPEG 2000 Lossless/Lossy için Pillow ve NumPy + pylibjpeg yollarını gösteriyor; JPEG Lossless Process 14 SV1 (`1.2.840.10008.1.2.4.70`) için tabloda Pillow yolu var, pylibjpeg yolu bu satırda gösterilmiyor.
- pydicom, Pillow'u önerilen birincil yol olarak sunmuyor; decoded image üzerinde her zaman geri döndürülemeyebilecek istenmeyen işlemler yaptığı uyarısını veriyor.
- Dokümantasyon, verinin data-handler kapasitesine güvenildiğini ve üretilen uncompressed Pixel Data'nın doğruluğunun ayrıca kontrol edilmesi gerektiğini belirtiyor.
- Dosya yoluyla `pydicom.pixels.pixel_array()` veya `iter_pixels()` kullanımının bellek tüketimini azaltmaya yardımcı olabileceği belirtiliyor; bu, full frame decode maliyetini yok etmez ancak dataset yaşam döngüsünü azaltabilir.

## Resmî pylibjpeg-openjpeg deposu

Kaynak: https://github.com/pydicom/pylibjpeg-openjpeg (erişim 2026-08-22).

- Proje açıklaması: pylibjpeg için J2K, JP2 ve HTJ2K plugin'i.
- README/repository metadata'sında Linux, macOS ve Windows desteği belirtiliyor.
- Depodaki son değişiklik açıklamalarında OpenJPEG v2.5.3 güncellemesi ve büyük dosyanın küçük bir bölgesini çekmede bazı marker'ların decode performansını artırabileceği notu görülüyor; bu, mevcut kayıplı/kayıpsız DICOM dosyalarında otomatik ROI decode garantisi anlamına gelmez.

## Yerel ortam

`pydicom==3.0.2`. `pydicom.pixels.get_decoder()` çıktısında:

- JPEG Lossless SV1: `pylibjpeg` mevcut; GDCM eksik (`gdcm>=3.0.10` gerekir).
- JPEG 2000 Lossless/Lossy: `pillow`, `pylibjpeg` mevcut; GDCM eksik.
- JPEG-LS Lossless/Near-lossless: `pyjpegls`, `pylibjpeg` mevcut; GDCM eksik.
- `config.pixel_data_handlers` listesinde Numpy, GDCM, Pillow, JPEG-LS, pylibjpeg ve RLE Lossless handler kayıtları görülüyor; kayıtlı olmak ile tüm bağımlılığın gerçekten kullanılabilir olması aynı şey değil.

Bu notlar mimari/codec raporunda kaynak ve ölçüm temeli olarak kullanılacaktır.

## Plugin tablosu ve pyjpegls ayrıntıları

Kaynak: https://pydicom.github.io/pydicom/stable/guides/plugin_table.html (pydicom 3.0.2 dokümantasyonu, erişim 2026-08-22).

Pydicom'un resmî plugin tablosu, JPEG Lossless SV1 için `pylibjpeg-libjpeg`, JPEG 2000 Lossless/Lossy ve HTJ2K için `pylibjpeg-openjpeg`, JPEG-LS için `pyjpegls`, RLE için `pylibjpeg-rle` eşleşmelerini açıkça gösteriyor. `pylibjpeg` ailesinde JPEG 2000/HTJ2K için Bits Stored üst sınırı 24 olarak belirtiliyor. GDCM için python-gdcm gerektiği ve Bits Stored üst sınırının 16 olduğu yazıyor. Pillow tarafında JPEG 2000 desteğinin Jpeg2KImagePlugin/OpenJPEG'e bağlı olduğu ve bazı sınırlamalar bulunduğu belirtiliyor. Pydicom'un saf kendi decoder yolunun diğer pluginlerden yaklaşık 3–4 kat yavaş olduğu not edilmiş.

Kaynak: https://github.com/pydicom/pyjpegls (erişim 2026-08-22).

pyjpegls, JPEG-LS için CharLS C++ Library üzerinden Python arayüzü sunuyor. Depo Windows ve Ubuntu x64 üzerinde test edildiğini README içinde belirtiyor; görünen son release v1.5.1 (2024-10-28) ve CharLS v2.4.2 güncellemesi repository geçmişinde yer alıyor. Bu nedenle JPEG-LS için pydicom plugin tablosundaki `pyjpegls` yolu, Python seviyesinde saf decoder yazmaktan daha uygun bir native-backend seçeneği.

## JPEG Lossless ve GDCM alternatifleri

Kaynak: https://github.com/pydicom/pylibjpeg-libjpeg (erişim 2026-08-22).

`pylibjpeg-libjpeg`, pylibjpeg için native libjpeg tabanlı plugin olarak JPEG Baseline, Extended, Lossless Process 14, Lossless SV1 ve JPEG-LS Lossless/Near-Lossless UID'lerini desteklediğini listeliyor. README'de Linux, macOS ve Windows desteği belirtiliyor. Bu, mevcut fixture setindeki `1.2.840.10008.1.2.4.70` için doğrudan adaydır; yerel benchmarkta `pylibjpeg` plugininin başarıyla seçilebilmesi bu kurulumun etkin olduğunu gösterdi.

Kaynak: https://pydicom.github.io/pydicom/stable/tutorials/installation.html (pydicom 3.0.2 dokümantasyonu, erişim 2026-08-22).

Pydicom, GDCM'yi JPEG, JPEG-LS ve JPEG 2000 çözebilen C++ kütüphanesi olarak tanımlıyor. PyPI `python-gdcm` wheel'lerinin Windows, macOS ve Linux için güncel Python sürümleriyle üretildiğini ve `pip install python-gdcm` ile kurulabildiğini belirtiyor. Buna rağmen bu çalışma ortamında `python-gdcm` kurulu değil ve pydicom bunu `gdcm>=3.0.10` eksikliği olarak raporluyor; GDCM kurulumu mevcut benchmark sonucu yerine varsayımsal hız kazancı olarak sunulmamalıdır.

## Gerçek veri codec benchmarkı

`tools/benchmark_dicom_codecs.py` ile gerçek `dev_data/dicom_samples` dosyalarında Pixel Data değiştirilmeden `shape`, `dtype`, SHA-256 array digest, min/max/mean ve decode süresi karşılaştırıldı. 16 dosyanın tamamı JPEG Lossless SV1 ve 12 Bits Stored, tek frame.

Dört gerçek örnekte iki ölçüm tekrarında `pylibjpeg` 4/4 başarılı, digest mismatch 0 ve dosya başına median ortanca yaklaşık 1155 ms oldu. `default` yol 4/4 başarılı ve yaklaşık 1207 ms oldu; ilk başarılı plugin ile çıktıların digest'i eşleşti. `pillow` ve `pyjpegls`, JPEG Lossless SV1 decoder'ına plugin olarak eklenmediği için 0/4; `gdcm` native bağımlılığı eksik olduğu için 0/4.

On altı dosyanın tamamında tek tekrar ile `pylibjpeg` 16/16, mismatch 0; dosya başına median sürelerin ortalaması yaklaşık 1409.8 ms, tüm dosyaların medyanı yaklaşık 1209.6 ms oldu. `default` 16/16, mismatch 0; ortalama median yaklaşık 1397.1 ms, tüm dosyaların medyanı yaklaşık 1174.7 ms oldu. Tekrarsız bu all-file ölçüm, dört dosyalık çoklu tekrar benchmarkından daha az stabil olmakla birlikte kapsamı doğrular. Sonuç: mevcut ortamda native `pylibjpeg` zaten aktif; JPEG 2000/JPEG-LS için gerçek fixture olmadan yeni entegrasyonun hız kazancı iddia edilmemelidir.
