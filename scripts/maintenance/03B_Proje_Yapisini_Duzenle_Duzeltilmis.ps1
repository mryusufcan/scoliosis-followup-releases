# Scoliosis Follow-Up - Aşama 3 (DÜZELTİLMİŞ)
# .gitignore düzeltmesi + test DICOM klasörü düzenleme + maintenance script temizliği

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "=== Aşama 3 | Proje Yapısı Düzenleme ===" -ForegroundColor Cyan
Write-Host "Proje: $root"
Write-Host ""

# 1) Yedek
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $root ".restore_points\stage3_$stamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

foreach ($item in @(".gitignore", "tests\test_real_dicom_samples.py")) {
    $src = Join-Path $root $item
    if (Test-Path $src) {
        $dest = Join-Path $backupDir $item
        New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
        Copy-Item $src $dest -Force
    }
}
Write-Host "[YEDEK] $backupDir" -ForegroundColor Green

# 2) .gitignore UTF-8
$gitignore = @'
# Yerel Python ve derleme çıktıları
__pycache__/
*.py[cod]
.venv-build/
build/
dist/
installer/
.restore_points/
security_keys/

# Hasta verileri ve yerel çalışma dosyaları
data/
logs/
modular_app/data/
work/
dev_data/
___Skolyoz deneme hastaları/
*.dcm
*.dicom
*.db
*.sqlite
*.sqlite3
*.sfbak

# Yerel dışa aktarımlar ve oturum kayıtları
*.zip
*oturum*.json

# İşletim sistemi / düzenleyici dosyaları
.DS_Store
Thumbs.db
.idea/
.vscode/
'@

Set-Content -Path (Join-Path $root ".gitignore") -Value $gitignore -Encoding UTF8
Write-Host "[DUZELTILDI] .gitignore UTF-8 olarak yenilendi." -ForegroundColor Green

# 3) Test DICOM klasörü
$oldSamples = Join-Path $root "___Skolyoz deneme hastaları"
$devData = Join-Path $root "dev_data"
$newSamples = Join-Path $devData "dicom_samples"

New-Item -ItemType Directory -Path $devData -Force | Out-Null

if (Test-Path $oldSamples) {
    if (Test-Path $newSamples) {
        throw "Hedef zaten mevcut: $newSamples"
    }
    Move-Item $oldSamples $newSamples
    Write-Host "[TASINDI] ___Skolyoz deneme hastaları -> dev_data\dicom_samples" -ForegroundColor Yellow
}
elseif (Test-Path $newSamples) {
    Write-Host "[OK] dev_data\dicom_samples zaten mevcut." -ForegroundColor Green
}
else {
    Write-Host "[UYARI] Test DICOM klasörü bulunamadı." -ForegroundColor DarkYellow
}

# 4) Test dosyasındaki yolu güncelle
$testFile = Join-Path $root "tests\test_real_dicom_samples.py"
if (Test-Path $testFile) {
    $text = Get-Content $testFile -Raw -Encoding UTF8

    $old1 = 'ROOT / "___Skolyoz deneme hastaları"'
    $new1 = 'ROOT / "dev_data" / "dicom_samples"'
    $old2 = "ROOT / '___Skolyoz deneme hastaları'"
    $new2 = "ROOT / 'dev_data' / 'dicom_samples'"

    $original = $text
    $text = $text.Replace($old1, $new1)
    $text = $text.Replace($old2, $new2)

    if ($text -ne $original) {
        Set-Content -Path $testFile -Value $text -Encoding UTF8
        Write-Host "[DUZELTILDI] tests\test_real_dicom_samples.py" -ForegroundColor Green
    }
    else {
        Write-Host "[UYARI] Test dosyasında eski örnek klasör yolu bulunamadı." -ForegroundColor DarkYellow
    }
}

# 5) Önceki scriptleri maintenance altına taşı
foreach ($name in @(
    "02B_Asama2_Devam_Duzeltme.ps1",
    "03_Proje_Yapisini_Duzenle.ps1"
)) {
    $src = Join-Path $root $name
    if (Test-Path $src) {
        $dst = Join-Path $root ("scripts\maintenance\" + $name)
        Move-Item $src $dst -Force
        Write-Host "[TASINDI] $name -> scripts\maintenance" -ForegroundColor Yellow
    }
}

# 6) Kök cache temizliği
$rootCache = Join-Path $root "__pycache__"
if (Test-Path $rootCache) {
    Remove-Item $rootCache -Recurse -Force
    Write-Host "[TEMIZLENDI] kök __pycache__" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Aşama 3 tamamlandı." -ForegroundColor Green
Write-Host "Yeni test veri yolu: dev_data\dicom_samples"
Write-Host "Private key yerinde: security_keys\integrity_private.pem"
Write-Host ""
Write-Host "Devam etmek icin bir tusa basin..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
