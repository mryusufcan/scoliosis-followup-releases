# Scoliosis Follow-Up Gelecek Optimizasyon ve Özellik Yol Haritası

**Tarih:** 20 Ağustos 2026  
**Mevcut sürüm:** 1.6.0  
**Kapsam:** Gelecekteki teknik optimizasyonlar, klinik güvenlik iyileştirmeleri, yeni özellikler ve kabul ölçütleri

## 1. Planlama ilkeleri

Gelecek çalışmalar mevcut SQLite tablolarını, eski export akışlarını ve DICOM verisini kırmadan ilerlemelidir. DICOM piksel matrisi ve metadata hiçbir zaman değiştirilmemeli; görüntü işleme yalnızca görüntüleme amacıyla oluşturulan çalışma kopyalarında yapılmalıdır. Otomatik veya AI sonuçları kesin klinik sonuç gibi gösterilmemeli, manuel doğrulama durumu ve model provenance bilgisi her zaman korunmalıdır.

Her değişiklikten önce restore point oluşturulmalı; değişiklikten sonra `py_compile`, UI smoke, ilgili modül testleri ve tam regresyon kapısı çalıştırılmalıdır. Qt widget, QImage ve QPixmap işlemleri GUI thread’inde tutulmalı; decode ve ağır NumPy işlemleri worker veya kontrollü throttling üzerinden yürütülmelidir.

## 2. Öncelik özeti

| Öncelik | Çalışma alanı | Hedef | Beklenen etki | Önerilen sıra |
|---|---|---|---|---:|
| P0 | Son Windows doğrulama ve gözlemlenebilirlik | Release sonrası güvenilirlik | Hata ayıklama süresini azaltır | 1 |
| P0 | DICOM kalite ve Cobb güvenliği | Ölçüm hatalarını görünür kılmak | Klinik risk azaltma | 2 |
| P1 | Render pipeline v2 | Büyük görüntü ve slider akıcılığı | Açılış/render gecikmesini azaltır | 3 |
| P1 | Restore/backup ve veri yaşam döngüsü | Veri kaybı riskini azaltmak | Operasyonel güvenlik | 4 |
| P1 | Longitudinal takip v2 ve raporlama | Takip kararlarını hızlandırmak | Kullanıcı verimliliği | 5 |
| P2 | Kontrollü landmark/AI katmanı | Yardımcı otomatik ölçüm | Manuel iş yükünü azaltır | 6 |
| P2 | PACS/DICOMweb ve anonimleştirme | Kurumsal entegrasyon | Veri akışını genişletir | 7 |
| P2 | Dağıtım ve güncelleme otomasyonu | Kurulum/bakım yükünü azaltmak | Sürüm yönetimini kolaylaştırır | 8 |

## 3. P0 — Güvenilirlik ve klinik güvenlik

### 3.1. Windows son doğrulama kapısı

Kontrol merkezine retention dry-run düğmesi eklendikten sonra Windows üzerinde son `py_compile`, UI smoke ve tam regresyon koşusu tamamlanmalıdır. Bu kapı, kodun işlevinden bağımsız olarak bağlı Windows terminalinin tekrar kullanılabilir olmasını da doğrulamalıdır.

Kabul ölçütleri şunlardır: `py_compile` hatasız tamamlanır; `UI_THEME_SMOKE_OK` alınır; tam test paketi sıfır hata ile tamamlanır; kontrol merkezindeki retention düğmesi görünür; düğme dry-run modunda rapor üretir ve dosya silmez.

### 3.2. DICOM kalite uyarıları

Viewer açılışında veya ölçüm başlatılmadan önce aşağıdaki kalite durumları görünür uyarıya dönüştürülmelidir: PixelSpacing yokluğu, PatientID uyuşmazlığı, seri/projeksiyon uyumsuzluğu, multi-frame beklenmeyen durumlar, eksik veya şüpheli yön bilgisi ve görüntü boyutunun ölçüm için uygunsuz olması.

Uyarılar görüntüyü değiştirmemeli; yalnızca ölçüm birimini, güven seviyesini ve kullanıcıya sunulan açıklamayı etkilemelidir. PixelSpacing yoksa ölçüm açıkça `px` olarak gösterilmeli, mm gibi sunulmamalıdır.

### 3.3. Cobb ölçüm güvenlik katmanı

Cobb aracı için dört noktalı işlem akışı daha görünür hale getirilebilir. Her nokta numaralandırılmalı, yanlış sırada seçim yapıldığında ölçüm engellenmeli veya kullanıcıya açık bir düzeltme önerilmelidir. Son nokta seçilmeden önce geri alma, yeniden başlatma ve ölçümü temizleme düğmeleri kullanılabilir olmalıdır.

Ölçüm kaydında şu alanlar zorunlu hale getirilebilir: kaynak görüntü, seri/çalışma bilgisi, PixelSpacing durumu, ölçüm birimi, taraf, vertebra, eğri yönü, ölçüm yöntemi, manuel doğrulama durumu ve görünüm ayarları.

## 4. P1 — DICOM render pipeline v2

### 4.1. Kontrollü slider throttling

Window/Level, parlaklık ve kontrast slider’larında her mouse hareketinde tam decode/render yapmak yerine 16–33 ms aralığında throttle uygulanabilir. Slider hareket ederken düşük maliyetli önizleme, bırakıldığında tam kalite render kullanılabilir.

Kabul ölçütü: slider sürüklenirken GUI heartbeat kaybı oluşmamalı; stale pixmap uygulanmamalı; slider bırakıldığında son değer kesin olarak render edilmelidir. Ortalama render hedefi 300 ms altında, cache hit hedefi 1 ms altında korunmalıdır.

### 4.2. Thumbnail ve full-resolution ayrımı

Dosya ağacı ve seri listesi için thumbnail üretimi full-size pixmap cache’inden tamamen ayrılabilir. Thumbnail worker kuyruğu düşük öncelikli çalışmalı, aktif görüntü render’ını engellememelidir. Aynı seri içinde tekrar eden thumbnail üretimi için küçük ve ayrı bir byte bütçeli cache kullanılabilir.

### 4.3. Prefetch ring ve kuyruk adaleti

Kullanıcının aktif görüntüsünün önceki/sonraki bir veya iki frame’i düşük öncelikle preload edilebilir. Büyük görüntü, multi-frame ve küçük görüntü kuyrukları için adil planlama yapılmalı; tek büyük DICOM tüm kuyruğu bloke etmemelidir.

Kabul ölçütleri: aktif görüntü hiçbir zaman düşük öncelikli prefetch tarafından geciktirilmemeli; worker iptali ve stale token kontrolü çalışmalı; uzun seri taramasında bellek bütçesi aşılmamalıdır.

### 4.4. Decode profilleme ve codec politikası

Codec başına decode süresi, hata oranı, tepe bellek ve fallback kullanımı ayrı ölçülmelidir. Paket içinde kullanılmayan codec bağımlılıkları opsiyonel profile taşınabilir; ancak gerçek hasta veya kabul fixture’larında kullanılan codec’ler release paketinden çıkarılmamalıdır.

## 5. P1 — Bellek, cache ve veri yaşam döngüsü

Mevcut byte-ağırlıklı cache yaklaşımı genişletilerek seri bazlı bütçe, kullanıcı tercihi ve aktif görüntü önceliği eklenebilir. Cache temizleme yalnızca görünüm değiştiğinde tümden yapılmamalı; LRU, aktif dosya koruması ve seri değişiminde kontrollü eviction birlikte kullanılmalıdır.

Uzun süreli 50/100 dosya taraması için bellek trend testi eklenmelidir. Test; RSS, tracemalloc tepe değeri, dataset cache, pixmap cache ve worker kuyruğu uzunluğunu zaman serisi olarak kaydetmelidir. Hedef, seri taraması sonunda belleğin sürekli artmaması ve bütçelerin sabit kalmasıdır.

Restore/backup tarafında retention politikasının yanında şu özellikler eklenebilir: restore point içeriği manifesti, checksum, bozuk yedek tespiti, tek tıklamayla rapor üretimi, harici arşiv doğrulaması ve son başarılı backup zamanının kontrol merkezinde gösterilmesi.

## 6. P1 — Longitudinal takip ve raporlama v2

Longitudinal merkezinde hasta, seri, projeksiyon, tarih ve eğri türü filtreleri eklenebilir. Trend grafiğinde ölçüm noktası seçildiğinde kaynak görüntüye ve ölçüm overlay’ine dönülebilmelidir.

Rapor çıktısı aşağıdaki bilgileri standartlaştırmalıdır: ölçüm tarihi, kaynak DICOM, görüntü/seri bilgisi, ölçüm birimi, PixelSpacing durumu, Cobb değeri, önceki ölçüme göre fark, kullanılan görünüm ayarları ve “otomatik sonuç manuel doğrulama gerektirir” notu.

İhracat akışında mevcut eski formatlar korunmalı; yeni alanlar geriye uyumlu ek alan olarak yazılmalıdır. PDF/HTML rapor şablonları aynı ölçüm kaynağını kullanmalı, ekranda görülen değer ile dışa aktarılan değer arasında fark oluşmamalıdır.

## 7. P2 — Kontrollü AI ve landmark özellikleri

Landmark/AI katmanı doğrudan klinik sonuç üretmek yerine yardımcı ölçüm önerisi olarak konumlandırılmalıdır. Model registry içinde model adı, sürüm, kaynak commit, checksum, eğitim/validasyon notu, input boyutu, cihaz ve kullanılan decoder bilgisi tutulabilir.

Her AI önerisi şu durumlarla birlikte gösterilmelidir: öneri üretildi, manuel doğrulama bekliyor, kullanıcı tarafından düzeltildi, reddedildi veya ölçüm için kullanılamaz. Model başarısız olduğunda uygulama kapanmamalı; manuel Cobb akışı çalışmaya devam etmelidir.

AI inference ayrı bir worker veya subprocess içinde çalıştırılabilir. Model dosyası proje dışından veya güvenilmeyen yoldan yüklenmemeli; path traversal, checksum ve `weights_only` güvenlik kontrolleri korunmalıdır. AI sonucu hiçbir zaman kendiliğinden longitudinal klinik trend içine kesin ölçüm olarak yazılmamalıdır.

Kabul ölçütü: gerçek DICOM’a zarar verilmez; model yolu sınırlandırılır; eksik/bozuk model kullanıcıya anlaşılır bildirilir; manuel ölçüm ve kayıt akışı AI olmadan çalışır; rapor otomatik öneriyi manuel doğrulanmış ölçümden ayırır.

## 8. P2 — PACS, DICOMweb ve veri güvenliği

Kurumsal kullanım hedeflenirse PACS veya DICOMweb bağlantısı eklenebilir. Bu çalışma mevcut yerel dosya akışını bozmayacak bir adapter katmanında yapılmalıdır. Önce yalnızca sorgulama ve indirme, daha sonra açık kullanıcı onaylı gönderim desteği eklenmesi daha güvenlidir.

Gelecek özellikler arasında anonimleştirme profilleri, gönderim öncesi metadata önizlemesi, audit log, bağlantı testi, timeout/retry politikası ve kullanıcı onayı bulunabilir. Token, sertifika ve private key kaynak koda yazılmamalıdır.

PACS/DICOMweb özelliği uygulanmadan önce tehdit modeli, kimlik doğrulama yöntemi, TLS sertifika politikası, başarısız gönderim davranışı ve yerel audit kayıt formatı belirlenmelidir.

## 9. P2 — Dağıtım ve operasyon

CI/CD akışı genişletilerek nightly kalite koşusu, codec matrisi, uzun seri bellek benchmarkı ve temiz Windows sanal makine kurulum testi eklenebilir. Release artifact’leri için imza doğrulaması ve installer checksum kontrolü sürdürülebilir.

Kullanıcı tarafında otomatik güncelleme eklenirse güncelleme öncesi SQLite backup, sürüm uyumluluk kontrolü, başarısız güncellemede rollback ve kullanıcıya görünen değişiklik günlüğü zorunlu olmalıdır. Güncelleme sistemi çalışmadığında uygulama mevcut sürümle açılmaya devam etmelidir.

Tanı paketi özelliği; uygulama sürümü, işletim sistemi, codec listesi, son hata özeti, cache ölçümü ve anonimleştirilmiş teknik logları tek ZIP içinde toplayabilir. DICOM veya kişisel hasta verileri varsayılan olarak tanı paketine alınmamalıdır.

## 10. Aşamalandırılmış yol haritası

### Faz A — Stabilizasyon ve ölçülebilirlik

İlk fazda Windows son doğrulama kapısı, retention dry-run doğrulaması, DICOM kalite uyarıları, Cobb ölçüm state makinesi ve uzun seri bellek benchmarkı tamamlanmalıdır. Bu faz yeni klinik özelliklerden önce güvenilir bir taban oluşturur.

### Faz B — Render ve kullanıcı deneyimi

İkinci faz slider throttling, prefetch ring, thumbnail ayrıştırma, queue fairness, ölçüm geri alma ve longitudinal filtrelerini kapsamalıdır. Her iş kaleminin öncesi/sonrası ölçümü kaydedilmelidir.

### Faz C — Raporlama ve operasyon

Üçüncü fazda rapor şablonları, tanı paketi, backup doğrulama, release imzası, temiz Windows kurulumu ve kontrollü otomatik güncelleme ele alınmalıdır.

### Faz D — Kontrollü AI ve entegrasyon

Dördüncü fazda model registry, worker tabanlı AI inference, manuel doğrulama akışı ve daha sonra PACS/DICOMweb adapter’ı uygulanabilir. Bu faz klinik doğrulama ve veri güvenliği gereksinimleri netleşmeden başlatılmamalıdır.

## 11. Önerilen ilk uygulama paketi

En mantıklı ilk uygulama paketi şudur:

1. Windows bağlantısı kullanılabilir olduğunda retention düğmesinin son kabul testini tamamlamak.
2. DICOM kalite uyarılarını ve PixelSpacing/ölçüm birimi gösterimini eklemek.
3. Cobb ölçümünde geri alma, temizleme ve nokta sırası doğrulamasını tamamlamak.
4. Slider throttling için ölçüm tabanlı küçük bir prototip oluşturmak.
5. 50/100 dosyalık bellek trend benchmarkını CI kapısına eklemek.

Bu paket, yeni özelliklerin klinik güvenlik ve performans tabanını güçlendirir; mevcut SQLite, export, DICOM ve UI akışlarını kırmadan ilerlenebilir.

## 12. Başarı göstergeleri

| Gösterge | Hedef |
|---|---:|
| Ortalama DICOM render süresi | 300 ms altında |
| Cache hit süresi | 1 ms altında |
| Slider sırasında GUI heartbeat | Donma olmaması |
| Cache byte bütçesi | Dataset 32 MiB, pixmap 128 MiB sınırında |
| Uzun seri bellek trendi | Sürekli artış olmaması |
| Tam regresyon | Sıfır hata |
| DICOM metadata değişikliği | 0 |
| AI sonucu manuel doğrulama olmadan klinik kayda dönüşmesi | 0 |
| Backup/restore doğrulama | Checksum ve manifest başarılı |
| Release | Test + build + installer + verify kapıları zorunlu |
