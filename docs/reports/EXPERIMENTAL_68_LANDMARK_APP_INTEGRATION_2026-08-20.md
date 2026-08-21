# Deneysel 68-Landmark ONNX Uygulama Entegrasyonu — Teslim Raporu

**Tarih:** 20 Ağustos 2026  
**Kapsam:** `yijingru/Vertebra-Landmark-Detection` kaynaklı checkpointten dönüştürülen ONNX adayının Scoliosis Follow-Up uygulamasına yalnızca yerel, tahribatsız ve deneysel landmark taslağı olarak eklenmesi.

> Bu özellik **tanı koymaz**, Cobb açısı üretmez, end-vertebra seçmez ve otomatik ölçüm kaydı oluşturmaz. Çıktı, yalnızca görüntü üstünde incelenebilen 68 noktalı bir taslaktır.

## Uygulanan bileşenler

| Bileşen | Dosya / konum | Davranış |
|---|---|---|
| Deneysel ONNX paket | `resources/ai/vertebra_landmarks_experimental/` | ONNX, manifest, teknik dönüşüm raporu ve deneysel durum metni içerir. |
| Yerel runtime | `ai/landmark_runtime.py` | SHA-256 denetimi, DICOM uygunluk kapısı, bellek içi ön işleme, CPU ONNX çıkarımı ve 68 nokta kalite kontrolü yapar. |
| Taslak dialogu | `modular_app/ui/ai_landmark_assistant_dialog.py` | Açık kullanıcı eylemi olmadan çalışmaz; taslağı yalnızca görüntüye aktarır. |
| Menü eylemi | `Gelişmiş → Deneysel AI 68-Landmark Taslağı` | Mevcut tek kareli DICOM bağlamını kullanır. |
| Görüntü üstü overlay | `modular_app/run_modular.py` | 68 turkuaz nokta, 17 üstten alta aday etiketi ve “ölçüm kaydedilmedi” banner’ı çizer. |

## Güvenlik ve veri sınırları

| Koruma | Uygulanan davranış |
|---|---|
| Yerellik | ONNX çıkarımı yalnızca `CPUExecutionProvider` ile yerelde yürür; ağ isteği yapılmaz. |
| DICOM bütünlüğü | DICOM dosyası salt okunur açılır; ham piksel ve metadata değiştirilmez. |
| Teknik uygunluk | Tek kare, tek kanal, DX/CR, AP/PA ve MONOCHROME1/2 kontrolleri uygulanır. |
| Sayısal bütünlük | Model dosyası manifestteki SHA-256 ile eşleşmezse çalıştırılmaz. |
| Landmark güvenliği | Sınır dışı, sonlu olmayan veya düşük güvenli landmark çıktısı gösterilmez; koordinatlar kırpılmaz/uydurulmaz. |
| Kayıt sınırı | Landmark overlay’i hiçbir SQLite ölçüm kaydı oluşturmaz; Cobb taslağına veya onay dialoguna otomatik aktarılmaz. |
| Kabul görünürlüğü | V2 kabul eksikleri runtime açıklamasında görünür; paket “deneysel” olarak işaretlenir. |

## Kullanım akışı

1. Tek kareli, AP/PA yönü metadata’da belirtilmiş DX veya CR DICOM görüntüyü açın.
2. **Gelişmiş → Deneysel AI 68-Landmark Taslağı** menüsünü seçin.
3. Dialogdaki deneysel ve kayıt dışı uyarıyı okuyun; **Yerel Landmark Taslağını Çalıştır** düğmesine bilinçli olarak basın.
4. Teknik kalite kapıları geçerse **Taslağı Görüntüye Aktar (Kaydetmez)** seçeneği ile 68 noktayı görüntü üstünde inceleyin.
5. Taslak, mevcut Cobb kaydını değiştirmez. Manuel Cobb ölçümü gerekiyorsa uygulamanın ayrı manuel ölçüm aracını kullanın.

## Kabul durumu

Paket teknik olarak bütünlük denetiminden geçse de V2 **uzman incelemeli POC kabulünden geçmemiştir**. Aşağıdaki kanıtlar eksik olduğu sürece bu durum bilinçli olarak değişmeyecektir:

- ağırlık dosyası için açık kullanım/dağıtım lisansı veya yazılı izin;
- eğitim/doğrulama verisi için kullanım ve değerlendirme hakkı;
- hasta bazlı ayrılmış değerlendirme seti;
- medyan landmark hatası ve Cobb MAE raporu;
- veri yönetişimi ve sorumlu uzman inceleme kaydı.

Bu maddeler tamamlandığında kabul ön kontrolü yeniden çalıştırılmalıdır. Kabul geçse dahi bu, otomatik klinik karar veya otomatik kayıt yetkisi anlamına gelmez.

## Doğrulama sonuçları

| Doğrulama | Sonuç |
|---|---|
| Runtime birim ve bütünlük testleri | Başarılı: 4 test |
| Landmark dialog offscreen testleri | Başarılı: 2 test |
| Gelişmiş menü entegrasyonu | Başarılı: 2 test |
| Toplu modüler regresyon | **139 test başarılı** |
| Windows paket | ONNX Runtime ve deneysel kaynak paketi dağıtıma dahil edildi |
| Paketlenmiş EXE duman testi | 20 saniye kararlı açılış başarılı |

## Geri yükleme noktası

`.restore_points\experimental_landmark_app_20260820_122524`

## Bilinen sınırlar

Sentetik DX duman testi, anatomik landmark içermediği için çıkışı doğru biçimde engellenmiştir. Uygulama gerçek izinli/de-identifiye DICOM ile çalıştırılabilir; ancak gerçek görüntü üzerindeki teknik taslak çıktısı klinik doğruluk kanıtı değildir. Landmark → end-vertebra → Cobb akışı, klinik doğrulama kanıtı tamamlanmadan bu entegrasyona eklenmemiştir.
