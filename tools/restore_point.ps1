param(
    [switch]$List,
    [string]$Tag = "",
    [switch]$Force,
    [switch]$Portable
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Show-PortableRestorePoints {
    param([string]$Root)
    $directory = Join-Path $Root '.restore_points'
    if (-not (Test-Path -LiteralPath $directory)) {
        Write-Host "Henüz taşınabilir geri dönüş noktası oluşturulmadı."
        return
    }
    Get-ChildItem -LiteralPath $directory -Filter 'restore-*.zip' -File |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object { $_.BaseName }
}

function Restore-PortableRestorePoint {
    param([string]$Root, [string]$RestoreTag, [bool]$SkipConfirmation)

    $archive = Join-Path (Join-Path $Root '.restore_points') "$RestoreTag.zip"
    if (-not (Test-Path -LiteralPath $archive)) {
        throw "Taşınabilir geri dönüş noktası bulunamadı: $RestoreTag"
    }
    if (-not $SkipConfirmation) {
        $answer = Read-Host "Kod dosyaları $RestoreTag sürümüne geri alınacak. Devam etmek için EVET yazın"
        if ($answer -cne 'EVET') {
            Write-Host "Geri alma iptal edildi."
            return
        }
    }

    $temporary = Join-Path (Join-Path $Root '.restore_points') ".restore-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $temporary -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $archive -DestinationPath $temporary -Force
        Get-ChildItem -LiteralPath $temporary -Recurse -File -Force | ForEach-Object {
            if ($_.Name -eq 'CHECKPOINT.txt') {
                return
            }
            $relative = $_.FullName.Substring($temporary.Length).TrimStart('\')
            $destination = Join-Path $Root $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
    }
    Write-Host "Kod $RestoreTag sürümüne geri alındı. Hasta verileri, DICOM'lar ve yerel veritabanı korunmuştur."
}

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git -and (Test-Path (Join-Path $root '.git')) -and -not $Portable) {
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
    & git restore --source=$Tag --staged --worktree -- .
    if ($LASTEXITCODE -ne 0) {
        throw "Kod dosyaları geri alınamadı."
    }
    Write-Host "Kod $Tag sürümüne geri alındı. Hasta verileri ve DICOM'lar korunmuştur."
}
else {
    if ($List) {
        Show-PortableRestorePoints -Root $root
        exit 0
    }
    if (-not $Tag) {
        Write-Host "Önce kullanılabilir geri dönüş noktalarını listeleyin:"
        Show-PortableRestorePoints -Root $root
        Write-Host "`nKullanım: .\tools\restore_point.ps1 -Tag restore-YYYYMMDD_HHMMSS"
        exit 1
    }
    Restore-PortableRestorePoint -Root $root -RestoreTag $Tag -SkipConfirmation $Force
}
