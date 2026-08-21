# Yerel DICOM → ONNX Landmark Laboratuvarı — Duman Testi

**Tarih:** 20 Ağustos 2026  
**Kapsam:** Yerel, tahribatsız DICOM ön işleme hattının ONNX landmark adayına bağlanmasının teknik olarak doğrulanması.

> Bu duman testi **hasta verisi içermeyen sentetik DX fixture** ile yapılmıştır. Proje klasöründe izinli/de-identifiye gerçek DICOM örneği bulunmadığı için gerçek hasta görüntüsü üzerinde model çalıştırılmamıştır.

## Uygulanan hat

```text
Yerel DICOM dosyası (salt okunur)
→ teknik metadata kapısı
→ bellek içi Rescale / Window veya percentile normalizasyonu / MONOCHROME inversion
→ [1,3,1024,512] float32 tensörü
→ ONNX Runtime (CPU)
→ 17×11 decoder
→ 68×2 landmark taslağı
→ sınır ve güven kalite kapısı
→ yalnızca JSON teknik raporu
```

Ham DICOM dosyası değiştirilmez, ağ üzerinden gönderilmez, Cobb açısı hesaplanmaz ve ölçüm kaydı oluşturulmaz.

## Sentetik DX duman testi

| Kontrol | Sonuç |
|---|---|
| Fixture | Hasta verisi içermeyen, tek kareli `DX / AP / MONOCHROME2` sentetik DICOM |
| Dosya bütünlüğü | Kaynak SHA-256 işlem öncesi/sonrası değişmedi |
| DICOM metadata kapısı | Geçti: geometri, tek kare, tek kanal, modalite, photometric ve ViewPosition |
| Ön işleme | DICOM Window/Level uygulanarak `float32 [1,3,1024,512]` tensörü üretildi |
| ONNX çalıştırma | Teknik olarak tamamlandı; `17×11` decoder ve `68×2` landmark biçimi üretildi |
| Landmark kalite kapısı | **Engellendi**: sentetik görüntüde landmarklar kaynak sınırları dışındaydı; güven aralığı `%6,3–%9,9` düzeyindeydi |
| Yan etkiler | DICOM değişikliği yok, ağ aktarımı yok, kalıcı ölçüm yok, Cobb/klinik sonuç yok |

Bu engelleme beklenen bir güvenlik sonucudur. Sentetik gradient görüntüde anatomik landmark bulunmaması gerekir; pipeline koordinatları kırpmamış veya uydurmamış, taslağı doğru biçimde engellemiştir.

## Gerçek izinli DICOM ile teknik test komutu

Sadece kullanım izni ve uygun veri yönetişimi bulunan, tercihen de-identifiye tek kareli AP/PA DX veya CR görüntü için:

```powershell
$lab = '.quarantine\landmark_lab'
& "$lab\.venv\Scripts\python.exe" "$lab\dicom_onnx_landmark_pipeline.py" `
  --dicom 'C:\izinli_veri\deidentified_ap_or_pa.dcm' `
  --onnx "$lab\onnx_candidate\vertebra_landmarks_68.onnx" `
  --report "$lab\onnx_candidate\local_dicom_landmark_report.json"
```

Bu komut yalnızca yerel rapor üretir. `--include-landmarks` parametresi kullanılmadıkça rapora koordinatlar yazılmaz. "eligible" veya "review_required" sonucu bile klinik doğruluk anlamına gelmez; ölçüm kaydı ve Cobb hesabı ayrı uzman onay akışına bağlıdır.
