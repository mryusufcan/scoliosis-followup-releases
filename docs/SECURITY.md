# Scoliosis Follow-Up Güvenlik ve Fikrî Mülkiyet Koruma Politikası

## Kapsam

Bu belge Scoliosis Follow-Up Windows dağıtım paketinin, kaynak kodunun, release artifact’lerinin ve lisans doğrulama yüzeyinin korunması için uygulanacak teknik kuralları tanımlar. Amaç, yazılımın izinsiz kopyalanmasını ve değiştirilmiş paketlerin resmi sürüm gibi sunulmasını zorlaştırmaktır. Hiçbir istemci tarafı koruma mekanizması, çalıştırılabilir bir programın reverse engineering veya patch edilmesini mutlak olarak engelleyemez.

## Dağıtım güvenliği ilkeleri

Kaynak DICOM dosyaları ve hasta verileri EXE içine gömülmez. Uygulama, klinik görüntü verisini yerelde ve tahribatsız biçimde işler. API anahtarları, lisans private key’i, update-signing private key’i ve kod imzalama sertifikası/şifresi dağıtım klasörüne veya GitHub Release artifact’ine konulmaz.

Frozen dağıtımda yalnızca doğrulama için gereken public key bulunabilir. `security_keys` klasörü ve private key’ler release archive’larına dahil edilmez. Release öncesinde dağıtım security audit’i private-key marker’larını, uygulama kaynak dosya adlarını ve codec test/example/benchmark yollarını blocking finding olarak kontrol eder.

## Bütünlük ve imza

Windows release’leri Authenticode ile imzalanmalıdır. İmza akışında SHA-256 digest ve RFC 3161 timestamp kullanılmalıdır. İmzalı EXE ve installer’ın SHA-256 özeti release feed’de yer alır. `runtime_integrity.json` ve `runtime_integrity.sig`, frozen dağıtımın içerik bütünlüğünü uygulama başlangıcında kontrol eder.

İmzasız installer test veya dahili QA için üretilebilir; ancak yayınlama pipeline’ı `-PublishGitHubRelease` kullanıldığında sertifika thumbprint’i olmadan fail-closed davranır ve GitHub’a imzasız release göndermeyi reddeder.

## Python/PyInstaller sınırı

PyInstaller dağıtımı kaynak `.py` dosyalarını doğrudan bırakmamaya yardımcı olur; ancak Python modülleri frozen archive içinde derlenmiş bytecode olarak bulunabilir. Bu nedenle PyInstaller kod gizleme sistemi olarak değerlendirilmez. Paketleme akışında codec runtime binary’leri açıkça toplanır; test, benchmark ve example modülleri EXE’ye alınmaz.

Kritik algoritmaların daha güçlü korunması için sonraki iterasyonda düşük riskli bir native-module spike yapılmalıdır. Adaylar Nuitka, Cython veya C++/Rust extension’dır. Bu geçiş; PySide6, pydicom, NumPy, native codec DLL’leri, multi-frame decode, DICOM acceptance testleri ve Windows installer davranışı birlikte doğrulanmadan ana release yoluna alınmamalıdır.

## Lisans koruması

Lisans doğrulaması yalnızca yerel boolean veya kolay değiştirilebilir sabitlere dayanmamalıdır. Önerilen model, private key ile imzalanmış lisans payload’ının uygulamada public key ile doğrulanmasıdır. Offline kullanım gerekiyorsa lisans; cihaz kimliği, özellik kapsamı ve son geçerlilik tarihi içeren, süreli ve imzalı bir payload olmalıdır. Private signing key yalnızca lisans üretim servisi veya erişimi sınırlı yönetici makinesinde tutulmalıdır.

Uygulamadaki offline lisans akışında cihazdan yalnızca **uygulama kapsamlı tek yönlü cihaz digest’i** alınır. MachineGuid veya volume serial gibi ham sinyaller sunucuya gönderilmez ve saklanmaz. Lisans JSON’u Ed25519 public key ile yerelde doğrulanır; imza, ürün, süre, sürüm, özellikler ve cihaz eşleşmesi başarısızsa dosya geçersiz sayılır. Geçersiz offline dosya, çevrimiçi lisans/trial akışını bastıramaz.

Mevcut çevrimiçi aktivasyon geriye dönük uyumluluk için eski HWID RPC’lerini kullanmaya devam eder. İmzalı offline entitlement istemcisi yeni anonim device binding ile yalnızca opsiyonel `get_signed_offline_entitlement` RPC’sini çağırır; RPC henüz kurulmamışsa aktivasyon başarısız sayılmaz. Migration `supabase/migrations/20260823_signed_offline_entitlements.sql` dosyasındadır ve kullanıcı onayıyla Production’da uygulanmıştır. Uygulanan migration yalnızca yeni entitlement tablosunu ve RPC’yi oluşturur; `licenses` ve `device_trials` tablolarını değiştirmez. Daha sonraki salt-okunur Production denetiminde her iki mevcut tabloda da `rowsecurity = true`, anon/authenticated için doğrudan tablo SELECT/INSERT/UPDATE/DELETE izinlerinin kapalı olduğu ve legacy RPC’lerin `SECURITY DEFINER`, sabit `search_path = public` ve şema nitelikli tablo referansları kullandığı doğrulanmıştır. Bu nedenle bu iki tablo için ek RLS migration’ı şu anda gerekli değildir; gelecekteki değişiklikler aynı uyumluluk testleri korunarak yapılmalıdır.

İnternet bağlantısı bulunan ortamlarda entitlement ve aktivasyon durumu sunucu tarafında da kontrol edilebilir. DICOM PatientID, hasta adı, piksel verisi, dosya yolu veya rapor içeriği lisans kontrolü için sunucuya gönderilmemelidir. Lisans kontrolü, görüntüleme iş akışının ve yerel klinik verinin gizliliğinden ayrı tutulmalıdır.

Server-side issuer `issue-offline-entitlement` Supabase Edge Function olarak Production’a deploy edilmiştir. Function yalnızca `OFFLINE_ISSUER_TOKEN` ile yetkili yönetici çağrısını kabul eder; private Ed25519 key `OFFLINE_LICENSE_PRIVATE_KEY_PEM` adıyla yalnızca Function Secret’ta tutulur. Masaüstü uygulaması ve müşteri JSON’u issuer token’ını veya private key’i içermez. Yanlış token testi HTTP 401, doğru token ile dummy/nonexistent license testi HTTP 409 döndürerek authentication ve lisans önkoşulu katmanlarını doğrulamıştır. Yönetici çağrı aracı `tools/request_offline_entitlement.py` yalnızca opaque lisans/cihaz alanlarını gönderir ve dönen belgeyi public key ile yerelde doğrular.

## Release kontrol listesi

| Kontrol | Beklenen durum |
|---|---|
| Sürüm | `VERSION`, runtime `APP_VERSION`, installer ve release tag aynı sürümü gösterir. |
| Secret scan | Private key, API key, token veya secret marker bulunmaz. |
| Distribution audit | Uygulama source dosyası ve codec test/example/benchmark içeriği bulunmaz. |
| Bütünlük | `runtime_integrity.json` ve imza doğrulaması başarılıdır. |
| Authenticode | EXE ve installer SHA-256 ile imzalı ve timestamp’li olur. |
| Update feed | Feed sürümü, HTTPS URL’si ve installer SHA-256 değeri ile eşleşir. |
| DICOM güvenliği | Kaynak DICOM dosyaları release sürecinde değiştirilmez ve artifact’e dahil edilmez. |
| Offline entitlement | İmzalı dosya yalnızca uygulama public key’i ve anonim device digest ile doğrulanır; private key pakete girmez. Production issuer Edge Function’dır. |
| Supabase migration | Entitlement migration kullanıcı onayıyla uygulandı; mevcut lisans satırları değiştirilmedi. |
| Server-side issuer | Edge Function deploy edildi; secret değerleri yalnızca Supabase Function Secrets’ta tutulur; yanlış token 401, dummy lisans 409 ile test edildi. |
| QA | Full pytest, compileall, offscreen smoke ve gerçek DICOM acceptance geçer. |

## Mevcut 1.7.7 koruma çalışması

1.7.7 sonrası güvenlik sertleştirmesinde timestamp’li restore point oluşturuldu. PyInstaller codec paketlemesindeki geniş `--collect-all` kullanımı kaldırılarak gerekli native binary’ler `--collect-binaries` ile toplandı ve codec test/example/benchmark modülleri dışlandı. Frozen dağıtımda application source leak veya private-key marker bulunmadığı read-only audit ile doğrulandı.

Bu aday paket 1.7.7 release’inin yerine otomatik olarak geçirilmemiştir. Mevcut yayımlanmış 1.7.7 artifact’i değişmeden korunur; sertleştirilmiş paket ayrı bir QA adayıdır ve testleri tamamlandıktan sonra yeni bir sürüm, örneğin 1.7.8, olarak yayımlanmalıdır.

## Restore point

Güvenlik sertleştirmesi öncesi kaynak archive ve metadata şu konumdadır:

`.restore_points/pre_security_hardening_1.7.7_20260823_134035/`

Archive içinde private signing key kasıtlı olarak bulunmaz. Artifact hash’leri ve yayımlanmış release bağlantıları `restore_metadata.json` dosyasında kayıtlıdır.
