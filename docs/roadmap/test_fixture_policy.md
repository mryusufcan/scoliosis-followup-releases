# Yol Haritası Test Fixture Politikası

## Amaç

`tests/roadmap_fixtures.py`, domain sözleşmelerini ve uygulama akışlarını deterministik biçimde test etmek için küçük, sentetik ve klinik olmayan kayıtlar sağlar. Bu fixture’lar model doğruluğu, klinik uyum, interobserver veya intraobserver analizi için kullanılmaz.

## Fixture sınıfları

| Fixture | Kullanım |
|---|---|
| `source_context()` | Hasta/tetkik/seri/SOP, boyut, PixelSpacing ve koordinat sistemi sözleşmeleri |
| `manual_cobb_record()` | Dört nokta, curve key, provenance ve longitudinal adapter testleri |
| `proposed_registration()` | ROI, translation, score, proposed status ve otomatik provenance testleri |
| Gerçek anonim DICOM seti | Decode, VOI, PixelSpacing, transfer syntax, registration/stitching ve performans benchmark’ları |

## Test verisi sınırları

Sentetik fixture sonuçları ürün UI’sında klinik vaka gibi gösterilmemeli, raporlara dahil edilmemeli ve AI model performans ölçümünde kullanılmamalıdır. Gerçek DICOM benchmark’ları anonimleştirilmiş olmalı; hasta etiketi içeren export’lar test sonuçlarına yazılmamalıdır.

## Genişleme kuralı

Her yeni ölçüm tipi için önce domain fixture, geometri unit testi, invalid state testi ve JSON round-trip testi eklenmelidir. Registration için düşük skor, uyumsuz PixelSpacing, eksik ROI, manual override ve deterministic tekrar testi bulunmalıdır. Quality gate için MONOCHROME1/2, multiframe, eksik PixelSpacing, compressed transfer syntax ve invalid metadata örnekleri gerçek veya anonim fixture setine eklenmelidir.

## Klinik doğrulama ayrımı

Klinik doğrulama modu ayrı bir veri akışı olmalıdır. Aynı vakanın farklı kullanıcılar tarafından ölçülmesi, gözlemci kimliği, zaman, uygulama/model sürümü ve manuel düzeltme kayıtlarıyla saklanır. Bland–Altman veya benzeri analizler yalnızca yeterli protokol, anonim veri ve yetkili değerlendirme süreci oluşturulduktan sonra yapılır.
