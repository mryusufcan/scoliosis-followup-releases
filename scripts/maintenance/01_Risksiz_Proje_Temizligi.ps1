# app devam v2 - Aşama 1: Risksiz proje temizliği
# Python kaynak dosyaları, import yolları ve BAT/SPEC dosyaları değiştirilmez.

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
Set-Location $root

Write-Host ""
Write-Host "=== Scoliosis Follow-Up | Aşama 1 Proje Düzenleme ===" -ForegroundColor Cyan
Write-Host "Proje: $root"
Write-Host ""

# Hedef klasörler
$folders = @(
    "releases",
    "artifacts",
    "artifacts\old_build",
    "artifacts\old_dist"
)

foreach ($folder in $folders) {
    $full = Join-Path $root $folder
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full | Out-Null
        Write-Host "[OLUSTURULDU] $folder" -ForegroundColor Green
    }
}

# Eski build çıktısını arşivle
$build = Join-Path $root "build"
if (Test-Path $build) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $target = Join-Path $root "artifacts\old_build\build_$stamp"
    Move-Item $build $target
    Write-Host "[TASINDI] build -> artifacts\old_build\build_$stamp" -ForegroundColor Yellow
}

# Eski dist çıktısını arşivle
$dist = Join-Path $root "dist"
if (Test-Path $dist) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $target = Join-Path $root "artifacts\old_dist\dist_$stamp"
    Move-Item $dist $target
    Write-Host "[TASINDI] dist -> artifacts\old_dist\dist_$stamp" -ForegroundColor Yellow
}

# Kök dizindeki zip paketlerini releases altına taşı
Get-ChildItem -Path $root -File -Filter "*.zip" | ForEach-Object {
    $destination = Join-Path $root ("releases\" + $_.Name)

    # Aynı isim varsa tarih ekle
    if (Test-Path $destination) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
        $destination = Join-Path $root ("releases\" + $name + "_" + $stamp + ".zip")
    }

    Move-Item $_.FullName $destination
    Write-Host "[TASINDI] $($_.Name) -> releases" -ForegroundColor Yellow
}

# Python cache klasörlerini temizle - kaynak koda dokunmaz
Get-ChildItem -Path $root -Directory -Recurse -Force -ErrorAction SilentlyContinue |
Where-Object { $_.Name -eq "__pycache__" } |
ForEach-Object {
    try {
        Remove-Item $_.FullName -Recurse -Force
        Write-Host "[TEMIZLENDI] $($_.FullName)" -ForegroundColor DarkGray
    } catch {
        Write-Host "[ATLANDI] $($_.FullName)" -ForegroundColor DarkYellow
    }
}

# .pyc dosyalarını temizle
Get-ChildItem -Path $root -File -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue |
ForEach-Object {
    try {
        Remove-Item $_.FullName -Force
    } catch {}
}

Write-Host ""
Write-Host "Aşama 1 tamamlandı." -ForegroundColor Green
Write-Host ""
Write-Host "DOKUNULMAYAN KRITIK DOSYA/KLASORLER:" -ForegroundColor Cyan
Write-Host "  - modular_app"
Write-Host "  - dicom"
Write-Host "  - pacs"
Write-Host "  - resources"
Write-Host "  - security_keys"
Write-Host "  - *.py"
Write-Host "  - *.bat"
Write-Host "  - *.spec"
Write-Host "  - requirements.txt"
Write-Host ""
Write-Host "Devam etmek icin bir tusa basin..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

