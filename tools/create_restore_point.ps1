param(
    [string]$Message = "Çalışan sürüm",
    [switch]$Portable
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function ConvertTo-RestoreFileLabel {
    param([string]$Text)

    # Açıklama Windows dosya adına güvenle eklenir. Türkçe karakterler ve
    # boşluklar sadeleştirilir; böylece her bilgisayarda aynı şekilde açılır.
    $source = ($Text -replace 'ı', 'i' -replace 'İ', 'I')
    $decomposed = $source.Normalize([System.Text.NormalizationForm]::FormD)
    $plain = New-Object System.Text.StringBuilder
    foreach ($character in $decomposed.ToCharArray()) {
        if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($character) -ne [Globalization.UnicodeCategory]::NonSpacingMark) {
            [void]$plain.Append($character)
        }
    }
    $label = [regex]::Replace($plain.ToString(), '[^A-Za-z0-9]+', '-').Trim('-').ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($label)) {
        $label = 'calisan-surum'
    }
    return $label.Substring(0, [Math]::Min(48, $label.Length))
}

function New-PortableRestorePoint {
    param([string]$Root, [string]$CheckpointMessage)

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $label = ConvertTo-RestoreFileLabel $CheckpointMessage
    $tag = "restore-$stamp-$label"
    $restoreDirectory = Join-Path $Root '.restore_points'
    $stage = Join-Path $restoreDirectory ".stage-$stamp"
    $archive = Join-Path $restoreDirectory "$tag.zip"
    $excludedRoots = @(
        '.git', '.restore_points', '.venv-build', '__pycache__', 'build', 'dist',
        'installer', 'data', 'logs', 'work', '___Skolyoz deneme hastaları'
    )
    $excludedExtensions = @('.dcm', '.dicom', '.db', '.sqlite', '.sqlite3', '.sfbak', '.zip')

    New-Item -ItemType Directory -Path $restoreDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    try {
        Get-ChildItem -LiteralPath $Root -Recurse -File -Force | ForEach-Object {
            $relative = $_.FullName.Substring($Root.Length).TrimStart('\')
            $parts = $relative -split '\\'
            $isModuleLocalData = $parts.Count -ge 2 -and $parts[0] -eq 'modular_app' -and $parts[1] -eq 'data'
            if ($parts[0] -in $excludedRoots -or $isModuleLocalData -or $_.Extension.ToLowerInvariant() -in $excludedExtensions) {
                return
            }
            if ($parts -contains '__pycache__') {
                return
            }
            $destination = Join-Path $stage $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }
        @(
            "Scoliosis Follow-Up geri dönüş noktası",
            "Etiket: $tag",
            "Tarih: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
            "Açıklama: $CheckpointMessage",
            "Hasta verileri, DICOM'lar ve yerel veritabanı dahil edilmemiştir."
        ) | Set-Content -LiteralPath (Join-Path $stage 'CHECKPOINT.txt') -Encoding UTF8
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $archive -CompressionLevel Optimal -Force
    }
    finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item -LiteralPath $stage -Recurse -Force
        }
    }

    Write-Host "Taşınabilir geri dönüş noktası hazır: $tag"
    Write-Host "Dosya: $archive"
    Write-Host "Listelemek için: .\tools\restore_point.ps1 -List"
}

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git -and (Test-Path (Join-Path $root '.git')) -and -not $Portable) {
    # .gitignore sayesinde hasta verileri, DICOM'lar ve derleme çıktıları eklenmez.
    & git add --all
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Kaydedilecek kod değişikliği yok."
        exit 0
    }

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $tag = "restore-$stamp-$(ConvertTo-RestoreFileLabel $Message)"
    & git commit -m "Checkpoint: $Message"
    if ($LASTEXITCODE -ne 0) {
        throw "Geri dönüş noktası oluşturulamadı."
    }
    & git tag -a $tag -m "Geri dönüş noktası: $Message"
    if ($LASTEXITCODE -ne 0) {
        throw "Geri dönüş etiketi oluşturulamadı."
    }

    Write-Host "Git geri dönüş noktası hazır: $tag"
    Write-Host "Listelemek için: .\tools\restore_point.ps1 -List"
}
else {
    # Git kurulmamış bilgisayarlarda aynı korumayı ZIP anlık görüntüsü sağlar.
    New-PortableRestorePoint -Root $root -CheckpointMessage $Message
}
