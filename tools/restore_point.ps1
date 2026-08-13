param(
    [switch]$List,
    [string]$Tag = "",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path (Join-Path $root '.git'))) {
    throw "Bu klasörde sürüm kontrolü başlatılmamış."
}

if ($List) {
    & git tag --list 'restore-*' --sort=-creatordate
    exit $LASTEXITCODE
}

if (-not $Tag) {
    Write-Host "Önce kullanılabilir geri dönüş noktalarını listeleyin:"
    & git tag --list 'restore-*' --sort=-creatordate
    Write-Host "`nKullanım: .\tools\restore_point.ps1 -Tag restore-YYYYMMDD_HHMMSS"
    exit 1
}

& git rev-parse -q --verify "refs/tags/$Tag^{commit}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Geri dönüş noktası bulunamadı: $Tag"
}

$changes = & git status --porcelain
if ($changes -and -not $Force) {
    throw "Kaydedilmemiş kod değişiklikleri var. Önce geri dönüş noktası oluşturun veya işlemi -Force ile yeniden çalıştırın."
}

# Sadece Git tarafından izlenen kod dosyaları geri alınır. .gitignore kapsamındaki
# hasta verileri, DICOM'lar ve yerel veritabanı kesinlikle değiştirilmez.
& git restore --source=$Tag --staged --worktree -- .
if ($LASTEXITCODE -ne 0) {
    throw "Kod dosyaları geri alınamadı."
}

Write-Host "Kod $Tag sürümüne geri alındı. Hasta verileri ve DICOM'lar korunmuştur."
