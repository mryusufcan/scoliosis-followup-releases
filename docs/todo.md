# Yapay Zekâ Güçlendirme Görevleri

- [x] Mevcut AI/Cobb öneri modülünün giriş-çıkış sözleşmelerini ve güvenlik sınırlarını belgelemek.
- [x] GitHub'daki açık kaynak skolyoz AI projelerini lisans, bakım durumu ve yeniden kullanılabilirlik açısından taramak.
- [x] Aday projeleri DICOM uyumu, Cobb ölçüm doğruluğu, veri gereksinimi ve PySide6 entegrasyonu açısından karşılaştırmak.
- [x] Manuel doğrulama, provenance, hata görünürlüğü ve test veri seti gereksinimlerini tanımlamak.
- [x] En uygun aday için güvenli proof-of-concept entegrasyon planını hazırlamak.
- [x] V2 model paketi ve model kartı sözleşmesini uygulamak.
- [x] DICOM/görüntü uygunluk ve landmark geometri kapılarını kodlamak.
- [ ] Yetkili ONNX model paketi için hasta bazlı ayrılmış doğrulama protokolünü yürütmek.
- [x] V2 manifest ve model kartı parserını geriye dönük V1 uyumluluğuyla eklemek.
- [x] DICOM uygunluk karar nesnelerini ve teknik engel kodlarını uygulamak.
- [x] Dört noktalı landmark geometri denetimini ve taslak engel nedenlerini uygulamak.
- [x] AI taslağı kabul/ret provenance sözleşmesini ve testlerini tamamlamak.
- [x] AI Cobb taslağını uzman onayına sunan dialogu eklemek.
- [x] Onaylanan AI taslağını kilitli Cobb ölçümü olarak kaydetmek.
- [x] Reddedilen AI taslağı için audit kaydı oluşturmak.
- [x] Onay ekranı için kullanıcı yetkisi, unit test ve offscreen smoke testleri eklemek.
- [x] V1/V2 model paket durumunu ve model kartını gösteren denetim dialogunu eklemek.
- [x] Model denetim eylemini Gelişmiş menüsüne bağlamak.
- [x] Model denetim ekranı için durum, izin ve menü testlerini eklemek.
- [x] V2 ONNX model paketi için güvenli örnek manifest ve model kartı şablonunu eklemek.
- [x] Model dosyasını çalıştırmadan önce denetleyen kabul ön kontrol komutunu eklemek.
- [x] Model doğrulama raporu şeması ve kullanıcıya açık özet görünümünü eklemek.
- [x] AI kabul testi, bozuk paket ve rapor eksikliği senaryoları için test kapsamını genişletmek.
- [x] AI hazırlıklarıyla Windows paketini ve toplu regression setini doğrulamak.

## Son doğrulama kaydı — 2026-08-20

- Model kabul ön kontrolü: `ai/model_acceptance.py` ve `tools/validate_ai_model_package.py`
- Denetim görünümü: V2 paketlerde kabul sonucu ve doğrulama metrikleri gösteriliyor.
- Regresyon: `tests/run_modular_tests.py` ile **123 test başarılı**.
- Windows paketi: `dist/ScoliosisFollowUp/ScoliosisFollowUp.exe`, 20 saniyelik duman testi başarılı.

## Sonraki güvenli AI adımı

- [x] Yerel klasördeki aday V2 ONNX paketini etkinleştirmeden sadece doğrulayan inceleme dialogunu eklemek.
- [x] Aday paket inceleme eylemini Gelişmiş menüsüne bağlamak ve otomatik testlerini toplu regresyona katmak.

## GitHub kaynaklı AI varlığı değerlendirmesi

- [ ] GitHub’daki aday skolyoz model/ağırlık/veri varlıklarını güncel lisans, erişim ve yeniden kullanım koşullarıyla yeniden incelemek.
- [ ] Adayların mevcut V2 ONNX paket sözleşmesi, model kartı ve hasta bazlı doğrulama gereksinimleriyle uyumunu değerlendirmek.
- [ ] Uygun bir aday varsa çalıştırmadan karantinaya almak, kabul ön kontrolünü çalıştırmak ve uzman incelemesi için kayda geçirmek.

## Bağımsız 68-landmark denemesi

- [x] `yijingru/Vertebra-Landmark-Detection` deposunun güncel kaynak, lisans, ağırlık ve çıktı sözleşmesini önceki planla karşılaştırmak.
- [x] Ana uygulamadan ayrık, karantinaya alınmış Windows deneme klasörünü hazırlamak; kaynak kodu veya ağırlığı çalıştırmadan incelemek.
- [x] 68-landmark çıkışını doğrulayacak teknik smoke testi ve sonraki landmark → Cobb adaptör sözleşmesini tasarlamak.

## Landmark checkpoint → V2 ONNX aday paketi

- [x] Karantinadaki landmark checkpointini CPU üzerinde ONNX aday modeline dönüştürmek ve dosya bütünlüğünü kaydetmek.
- [x] PyTorch ve ONNX çıktılarında ağ başlıkları, 17×11 decoder satırı ve 68 landmark sözleşmesi eşdeğerliğini test etmek.
- [x] Landmark test ortamı için örnek Python betiğini, V2 manifest/model kartını ve teknik doğrulama kaydını hazırlamak.
- [x] Aktif uygulama modeline geçiş için hasta bazlı doğrulama raporu ve uzman onayı eksiklerini açıkça kapı olarak korumak.

## DICOM ön işleme laboratuvarı ve V2 kabul kanıtı

- [x] Yerel DICOM’u değiştirmeden okuyup mevcut kalite kapılarından geçiren ve ONNX giriş tensörünü bellek içinde hazırlayan örnek pipeline’ı kurmak.
- [ ] İzinli/de-identifiye gerçek DICOM örneklerinde yalnızca teknik 68-landmark taslağı ve kalite kapısı duman testini çalıştırmak; çıktıların otomatik kayda dönüşmesini engellemek.
- [x] V2 kabulü için klinik metrikler, hasta bazlı veri ayrımı, ağırlık/veri lisans kanıtları ve bağımsız inceleme gereksinimlerini matriste belgelemek.

## Deneysel 68-landmark ONNX uygulama entegrasyonu

- [x] Yerel 68-landmark ONNX paketini DICOM’a tahribatsız erişen, düşük güven ve geometri hatalarında taslağı engelleyen modüler runtime’a eklemek.
- [x] Landmark taslağını görüntü üzerinde inceleme için açan; uzman düzeltmesi ve açık onay olmadan ölçüm kaydı oluşturmayan UI akışını bağlamak.
- [x] Aday paketin deneysel durumunu, kabul eksiklerini ve kullanım sınırlarını uygulama içinde görünür kılmak.
- [x] Entegrasyon testleri, offscreen smoke, toplu regresyon ve Windows EXE paket doğrulamasını tamamlamak.

## Deneysel landmark kullanım kılavuzu

- [x] Deneysel 68-landmark taslağının yerel çalışma, kayıt dışı overlay ve kalite engelleme adımlarını uygulama içi kullanıcı rehberine eklemek.
- [x] Landmark dialogu ve rehber akışının offscreen önizlemesini alarak örnek ekran görüntüsünü doğrulamak.

## Landmark → deneysel Cobb taslağı

- [ ] 68 landmarktan vertebra eğimlerini çıkaran, end-vertebra adaylarını öneren ve geçersiz geometrileri engelleyen ayrı post-processing modülünü eklemek.
- [ ] Deneysel Cobb önerisini açık kullanıcı eylemiyle görüntü üstünde gösteren; kaydetme/onay akışına otomatik bağlanmayan arayüzü eklemek.
- [ ] Yerel analiz düğmesinin DICOM/model uygunluğuna göre durum mesajını ve etkinlik koşullarını görünür kılmak.
- [ ] Post-processing geometri, dialog, menü ve regresyon testleri ile Windows paket doğrulamasını tamamlamak.

## Landmark hizalama hatası düzeltmesi

- [ ] Gerçek görüntüdeki yanlış hizalamanın model ön işleme, koordinat ölçeği ve checkpoint sözleşmesi kök nedenini izole etmek.
- [ ] Sırasız, sınır dışı, düşük güvenli veya anatomik olarak tutarsız 68-landmark taslaklarını overlay öncesinde engellemek.
- [ ] Landmarklar doğrulanmadan deneysel Cobb önerisi düğmesini kapalı tutmak; engel nedenini kullanıcıya açıklamak.

## Manuel Cobb küçük açı düzeltmesi

- [x] Görüntüleyici manuel Cobb hesabında `min(θ, 180°−θ)` küçük açı kuralını uygulamak.
- [x] 161,9° supplementer örneğinin 18,1° olarak gösterildiğini otomatik testle güvence altına almak.

## Kompakt görüntü ağacı ve yeni DICOM EXE smoke testi

- [x] Açılan Görüntüler ağaç bölümünü içerik odaklı sabit/üst sınırlı yükseklikle kompaktlaştırmak.
- [x] Güncellenmiş EXE’yi daha önce kullanılmamış yerel bir DICOM örneğiyle salt okunur açılış ve görüntüleme testinden geçirmek.

## Ağaç satırı yoğunluğu düzeltmesi

- [x] Önizlemesiz hasta/tetkik/seri grup satırlarının yüksekliğini küçültüp gerçek görüntü önizleme satırlarını korumak.
- [x] Tek hasta/kısa seri yapısında gereksiz dikey kaydırmanın kalktığını offscreen doğrulamak.

## Açılan Görüntüler kutusunu sol panele geri yayma

- [x] Açılan Görüntüler ağacındaki üst yükseklik sınırını kaldırıp kalan sol panel alanını kullanmasını sağlamak.
- [x] Kompakt grup satırlarını korurken tam yükseklikli sol panel davranışını offscreen doğrulamak.

## Paketleme tercihi

- [x] Windows EXE paketini yalnızca kullanıcının açık talebi olduğunda üretmek; ara arayüz değişikliklerini `main.py` üzerinden doğrulamak.
