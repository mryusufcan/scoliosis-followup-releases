param(
    [string]$Message = "Çalışan sürüm"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path (Join-Path $root '.git'))) {
    throw "Bu klasörde sürüm kontrolü başlatılmamış."
}

# .gitignore sayesinde hasta verileri, DICOM'lar ve derleme çıktıları eklenmez.
& git add --all
& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Kaydedilecek kod değişikliği yok."
    exit 0
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$tag = "restore-$stamp"
& git commit -m "Checkpoint: $Message"
if ($LASTEXITCODE -ne 0) {
    throw "Geri dönüş noktası oluşturulamadı."
}
& git tag -a $tag -m "Geri dönüş noktası: $Message"
if ($LASTEXITCODE -ne 0) {
    throw "Geri dönüş etiketi oluşturulamadı."
}

Write-Host "Geri dönüş noktası hazır: $tag"
Write-Host "Listelemek için: .\tools\restore_point.ps1 -List"
