# Landmark venv Yeniden Kurulum ve Restore Point Temizliği

## Bulgular

Projenin genel `requirements.txt` dosyası uygulama runtime'ını kapsar; deneysel landmark ortamını tek başına yeniden oluşturmaz. Deneysel ortam Python **3.8.10** kullanıyor ve `torch`, `scipy`, `matplotlib` ile `onnx` gibi uygulama requirements dosyasında bulunmayan paketlere sahip.

Mevcut deneysel ortamın gerçek `pip freeze` çıktısı şu dosyaya kaydedildi:

```text
docs\landmark_experimental_requirements_20260820.txt
```

Bu kilit dosyasıyla proje dışındaki geçici Python 3.8 ortamı yeniden oluşturuldu ve aynı CPU smoke testi başarıyla tamamlandı. Sonuçlar:

- `torch==2.1.2` yüklendi.
- Checkpoint `weights_only=True` ile açıldı.
- Girdi şekli: `[1, 3, 1024, 512]`.
- Decoder çıktısı: `17 x 11`.
- Landmark çıktısı: `68 x 2`.
- `clinical_result_generated: false`.
- DICOM açılmadı ve model uygulamaya entegre edilmedi.

Bu nedenle deneysel `.venv` klasörü, kilit dosyası ve Python 3.8 kurulumu mevcut olduğu sürece yeniden kurulabilir kabul edildi. Genel `requirements.txt` ile değil, deneysel lock dosyasıyla yeniden kurulmalıdır.

## Yeniden kurulum testi için PowerShell

```powershell
$root = 'C:\Users\yusuf\Desktop\Scoliosis Follow Up'
$testVenv = Join-Path $env:TEMP 'ScoliosisFollowUp_landmark_rebuild_test'
$python38 = 'C:\Users\yusuf\AppData\Local\Programs\Python\Python38\python.exe'

if (Test-Path $testVenv) {
    Remove-Item -LiteralPath $testVenv -Recurse -Force
}

& $python38 -m venv $testVenv
& (Join-Path $testVenv 'Scripts\python.exe') -m pip install `
    --disable-pip-version-check `
    -r (Join-Path $root 'docs\landmark_experimental_requirements_20260820.txt')

& (Join-Path $testVenv 'Scripts\python.exe') `
    (Join-Path $root '.quarantine\landmark_lab\landmark_cpu_smoke.py') `
    --checkpoint (Join-Path $root '.quarantine\landmark_lab\weights_quarantine\model_last.pth') `
    --report (Join-Path $root 'docs\landmark_rebuilt_venv_smoke_manual.json')

if ($LASTEXITCODE -ne 0) {
    throw 'Landmark yeniden kurulum smoke testi başarısız.'
}

Remove-Item -LiteralPath $testVenv -Recurse -Force
Write-Host 'LANDMARK_REBUILD_TEST_OK'
```

## Büyük restore point için güvenli silme komutu

SHA-256 karşılaştırmasıyla aşağıdaki restore point’in `.quarantine\landmark_lab` içeriğinin **1.604,82 MiB / 23.976 dosyalık birebir kopyasını** tuttuğu doğrulandı:

```text
.restore_points\landmark_lab_adapter_20260820_114227
```

Silme işlemi öncesinde klasörün beklenen boyutunu kontrol eden ve insan onayı isteyen PowerShell komutu:

```powershell
$root = 'C:\Users\yusuf\Desktop\Scoliosis Follow Up'
$target = Join-Path $root '.restore_points\landmark_lab_adapter_20260820_114227'
$expectedBytes = [int64]1682796025

if (-not (Test-Path -LiteralPath $target)) {
    throw "Restore point bulunamadı: $target"
}

$files = @(Get-ChildItem -LiteralPath $target -File -Recurse -Force)
$actualBytes = [int64](($files | Measure-Object -Property Length -Sum).Sum)
if ($actualBytes -ne $expectedBytes) {
    throw "Boyut beklenenden farklı. Beklenen=$expectedBytes Gerçek=$actualBytes. Silme durduruldu."
}

Write-Host "Silinecek klasör: $target"
Write-Host ("Boyut: {0:N2} MiB / Dosya: {1}" -f ($actualBytes / 1MB), $files.Count)
$confirmation = Read-Host "Silmek için SIL yazın"
if ($confirmation -cne 'SIL') {
    throw 'Onay verilmedi; hiçbir dosya silinmedi.'
}

Remove-Item -LiteralPath $target -Recurse -Force
Write-Host 'DUPLICATE_RESTORE_POINT_REMOVED'
```

Bu komut yalnızca yol ve beklenen byte boyutunu kontrol eder; SHA-256 tekrar karşılaştırmasını daha önceki `docs\quarantine_restore_analysis_20260820.json` raporu sağlar. En güvenli seçenek, silmeden önce bu restore point’i proje dışındaki harici diske veya arşive kopyalamaktır. Bu çalışma sırasında restore point silinmedi.
