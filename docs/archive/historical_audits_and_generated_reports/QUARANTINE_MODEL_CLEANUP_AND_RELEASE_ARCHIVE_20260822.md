# Karantina Model Temizliği ve Release Arşivleme Raporu

**Tarih:** 22 Ağustos 2026  
**Kapsam:** `.quarantine` içindeki model ağırlıkları/venv kopyaları ve `releases` altındaki eski sürümler  
**Durum:** Betikler hazırlandı; bu çalışma sırasında hiçbir model, venv veya release dosyası silinmedi ve taşınmadı.

## Karantina model dry-run sonucu

Aktif model dosyaları `resources\ai` ile SHA-256 karşılaştırıldı. Aktif resources dosyaları hiçbir koşulda hedeflenmiyor. Aynı hash’e sahip quarantine kopyaları ve quarantine içindeki birebir tekrarlar ayrı aday olarak işaretleniyor.

| Sonuç | Sayı / boyut |
|---|---:|
| Model/weight girdisi | 14 |
| Birebir duplicate silme adayı | **6 dosya / 1.022,92 MiB** |
| Korunan benzersiz model/weight girdisi | 8 |
| Karantina venv’i | **2 / 6.116,57 MiB** |
| Varsayılan silme davranışı | **Dry-run; silme yok** |

Silme adayı olanlar şunlardır: Mazurowski `epoch_24.pth`–`latest.pth` çiftindeki `latest.pth`; aktif resources modeliyle aynı hash’e sahip iki Mazurowski ONNX kopyası; quarantine içindeki aynı hash’e sahip bir Mazurowski ONNX kopyası; aktif resources landmark modeliyle aynı hash’e sahip iki 68-landmark ONNX kopyası.

Korunan dosyalar arasında benzersiz Mazurowski dynamic/standard adayları, tekil ONNX model adayları, landmark `model_last.pth`, `weights.zip` ve bir canonical `epoch_24.pth` bulunuyor. Bu nedenle betik yalnızca kanıtlanmış birebir kopyaları hedefliyor; benzersiz model adaylarını silmiyor.

### Oluşturulan betik

```text
scripts\maintenance\cleanup_quarantine_models.py
scripts\maintenance\Temizle_Karantina_Modelleri.bat
```

Batch betiği varsayılan olarak dry-run çalışır. Model duplicate’lerini silmek için açık onay gerekir:

```powershell
scripts\maintenance\Temizle_Karantina_Modelleri.bat --apply-model-duplicates --confirm QUARANTINE_MODEL_SIL
```

Karantina venv’lerini silmek için model duplicate onayına ek olarak yeniden kurulum smoke testinin yapıldığını belirten ikinci bir kapı gerekir:

```powershell
scripts\maintenance\Temizle_Karantina_Modelleri.bat --apply-venvs --venv-tested --confirm QUARANTINE_MODEL_SIL
```

İki venv için de bu onay verilmeden silme yapılmaz. Mazurowski ortamının Python sürümü 3.8.10’dur ve kurulu paket listesi şu lock dosyasına kaydedilmiştir:

```text
docs\mazurowski_experimental_requirements_20260822.txt
```

Bu ortamın lock dosyası kaydedildi; tam izolasyonlu yeniden kurulum testi bu çalışmada yapılmadı. Bu nedenle venv silme kapısı özellikle `--venv-tested` gerektirir.

## Release arşivleme hesabı

Mevcut `releases` alanında 1.7.0, 1.7.2, 1.7.3, 1.7.4 ve 1.7.5 bulunuyor. Her sürümde installer, release ZIP’i, `update.json` ve `VERSION` yer alıyor.

| Yerelde tutulacak sürüm | Harici arşive alınabilecek sürümler | Kazanılabilecek alan |
|---|---|---:|
| Yalnızca 1.7.5 | 1.7.0, 1.7.2, 1.7.3, 1.7.4 | **2.419 GiB** |
| 1.7.4 + 1.7.5 | 1.7.0, 1.7.2, 1.7.3 | **1.730 GiB** |
| 1.7.3 + 1.7.4 + 1.7.5 | 1.7.0, 1.7.2 | **1.041 GiB** |

Kök `installer\ScoliosisFollowUp_Setup.exe`, `releases\1.7.5\ScoliosisFollowUp_Setup_1.7.5.exe` ile SHA-256 olarak aynıdır. Kök installer kopyası ayrıca kaldırılırsa yaklaşık **353,03 MiB** daha açılabilir; ancak bu işlem release verify sonrasında yapılmalıdır. `installer\ScoliosisFollowUp_Setup_1.7.1.exe` farklı bir dosyadır ve eski sürüm olarak ayrıca değerlendirilmelidir.

Arşivleme hesabı şu JSON dosyasına kaydedildi:

```text
docs\release_archive_savings_20260822.json
```

Bu rapor yalnızca hesaplama yapar. Harici arşiv yolu, arşivin checksum’ı ve geri yükleme testi tamamlanmadan release klasörleri taşınmamalıdır.

## Doğrulama

Yeni cleanup ve hesaplama araçları `.venv` ile derlendi. Uygulama smoke ve regresyon kapıları da yeniden çalıştırıldı:

```text
py_compile: başarılı
UI_THEME_SMOKE_OK
182 passed, 5 warnings
```

Uyarılar pydicom/openjpeg tarafındaki Python 3.15 deprecation bildirimleridir; test başarısını etkilemedi.

## Önerilen güvenli sıra

İlk olarak yalnızca SHA-256 ile doğrulanmış model duplicate’leri silinebilir. Sonra Mazurowski ve landmark venv’leri için geçici Python ortamlarında rebuild/smoke kanıtı alınmalıdır. Son olarak en az son iki release yerelde tutularak eski sürümler harici checksum’lı arşive taşınabilir. Kullanıcı onayı ve arşiv doğrulaması olmadan hiçbir yıkıcı komut çalıştırılmamalıdır.
