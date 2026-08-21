# UI Sadeleştirme Envanteri

## Amaç

Kullanıcının uygulamayı açtığında ne yapacağını hızlıca anlaması, aktif bağlamı kaybetmemesi ve görüntüyü açmadan ölçüm/rapor sonucuna giden yolu mümkün olan en az tıklamayla tamamlaması.

## Mevcut ana yüzeyler

| Yüzey | Mevcut yapı | Ana sürtünme noktası | Sadeleştirme hedefi |
|---|---|---|---|
| Ana pencere | Modüler başlatıcı menüleri + üç sekme | Menü adlarında Türkçe/İngilizce karışımı ve aynı işlemin farklı yerlerde bulunması | Tek bir anlaşılır iş akışı menüsü ve tutarlı eylem adları |
| Görüntüleyici | Dosya, Görünüm, Ölçüm, Düzenle ribbon’ı; ikinci satırda W/L, araçlar, işaretleme, oturum ve dışa aktarma | Çok sayıda kontrol aynı görsel ağırlıkta; “Liste”, “DICOM”, “Araçlar” gibi kısa adlar bağlamsız | Birincil eylemi belirginleştirmek, gelişmiş işlemleri gruplamak ve aktif görüntü bilgisini sürekli göstermek |
| Skolyoz Takip | Yükleme, karşılaştırma, Cobb, hizalama ve yoğun Overlay slider’ları | Kullanıcı hangi sırayla ilerleyeceğini ve hangi tetkikin aktif olduğunu her an göremiyor; X/Y/Z/R kısaltmaları belirsiz | “Yükle → seç → karşılaştır → ölç → raporla” akış çubuğu ve tam adlandırılmış kontroller |
| DICOM omurga birleştirme | Sağ panelde parça yükleme, manuel nokta, otomatik hizalama, kalite, hassas kaydırma ve kaydetme | Aşama görünür olsa da hazır/aktif/sonraki durumları farklı kontrollerde dağınık; “Hizala/Birleştir” ve “Onayla/Bitir” ayrımı zayıf | Aşama tabanlı tek bir ana eylem, durum kartı ve güvenli son kaydetme adımı |
| Takip dialogları | Birbirinden farklı başlık, buton ve alt bilgi stilleri | Modal pencerelerde kullanıcı bağlamı ve bir sonraki adım her zaman açık değil | Ortak dialog başlığı, aktif hasta/tetkik satırı, birincil/ikincil buton hiyerarşisi |
| Menü sistemi | “Hasta”, “Takip”, “Görünüm”, “Veri”, “Raporlar”, “Deneysel”, “Yardım” | Menü sayısı ve action yoğunluğu yüksek; deneysel/klinik işlemler aynı seviyede görünebiliyor | Klinik günlük akışını öne almak, gelişmiş ve deneysel işlemleri ikincil seviyeye indirmek |

## Hedef hızlı akışlar

### Görüntü açma ve ölçüm

`Görüntüleyici → Aç → DICOM seç → Sığdır → Cobb Ölç → ölçümü tamamla → rapor veya takip görünümüne geç`.

### İki tetkiki karşılaştırma

`Skolyoz Takip → Yükle → iki tetkiki seç → Yan Yana veya Overlay → Otomatik Hizala → gerekirse manuel düzelt → ölç veya raporla`.

### Omurga birleştirme

`Parçaları seç → üç bölümün hazır durumunu gör → Hizala/Birleştir → kaliteyi kontrol et → Onayla ve Bitir → PNG + DICOM kaydet`.

### Longitudinal takip

`Takip Merkezi → hasta → eğri → ilk/son/delta/yıllık değişim → son tetkiki Overlay’e gönder`.

## Tasarım kararları

Bir ekranda yalnızca bir **birincil eylem** bulunmalı; ikincil eylemler nötr, geri dönüşü olmayan eylemler kırmızı ve gelişmiş işlemler açılır menü içinde gösterilmeli. Buton metni fiil ile başlamalı ve sonucu belirtmeli: “Aç”, “Sığdır”, “Cobb Ölç”, “Hizala ve Birleştir”, “Onayla ve Bitir”, “Raporu Dışa Aktar”.

Kısaltmalar, aynı satırda açıklayıcı metinle birlikte kullanılmalı. Örneğin `X` yerine `Yatay kaydırma`, `Z` yerine `Ölçek`, `R` yerine `Döndürme` görünmelidir. Tooltip yardımcı bilgi olarak kalmalı; temel işlem tooltip’e bağımlı olmamalıdır.

Aktif hasta, aktif tetkik, seçili görüntü sayısı, işlem aşaması ve bir sonraki önerilen adım görünür bir bağlam satırında tutulmalı. Kullanıcı yalnızca renk ile yönlendirilmemeli; aktif durum metin ve değerle de ifade edilmelidir.

## Uygulama sırası

İlk değişikliklerde ortak UI yardımcıları ve bağlam satırları oluşturulacak. Ardından ana menü ve sekme başlıkları sadeleştirilecek; sonrasında görüntüleyici, takip ve stitching kontrolleri aynı birincil/ikincil eylem hiyerarşisine geçirilecek. Her aşamada SQLite, DICOM, ölçüm, export ve cache davranışı korunacak; yalnızca UI yerleşimi, metinleri ve kullanıcı akışı iyileştirilecek.
