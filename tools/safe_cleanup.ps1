$ErrorActionPreference = 'Stop'

$appRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$requiredFiles = @('main.py', 'VERSION', 'packaging\build_windows.ps1')
foreach ($required in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $appRoot $required))) {
        throw "Uygulama kok klasoru dogrulanamadi: $appRoot"
    }
}

$relativeTargets = @(
    'build',
    'work',
    'tests\golden_preview',
    'database',
    'imaging',
    'measurements',
    'models',
    'registration',
    'reporting',
    'timeline',
    'ui',
    'utils',
    'packaging\ScoliosisFollowUp.spec',
    'test_scoliosis.db',
    'data'
)

function Assert-SafeTarget([string]$path) {
    $fullPath = [System.IO.Path]::GetFullPath($path)
    if (-not $fullPath.StartsWith($appRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Temizlik hedefi uygulama klasoru disinda: $fullPath"
    }
    return $fullPath
}

function Item-Size([string]$path) {
    $item = Get-Item -LiteralPath $path
    if (-not $item.PSIsContainer) { return [long]$item.Length }
    return [long](
        (Get-ChildItem -LiteralPath $path -File -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum
    )
}

$existingTargets = @()
$estimatedBytes = 0L
foreach ($relative in $relativeTargets) {
    $candidate = Assert-SafeTarget (Join-Path $appRoot $relative)
    if (Test-Path -LiteralPath $candidate) {
        $existingTargets += $candidate
        $estimatedBytes += Item-Size $candidate
    }
}

$excludedRoots = '\\(\.venv-build|\.git|\.restore_points|dist|installer)\\'
$cacheTargets = @(
    Get-ChildItem -LiteralPath $appRoot -Directory -Recurse -Force -Filter '__pycache__' |
        Where-Object { $_.FullName -notmatch $excludedRoots } |
        Sort-Object { $_.FullName.Length } -Descending
)
foreach ($cache in $cacheTargets) {
    if (-not ($existingTargets | Where-Object { $cache.FullName.StartsWith($_ + '\', [System.StringComparison]::OrdinalIgnoreCase) })) {
        $estimatedBytes += Item-Size $cache.FullName
    }
}

Write-Host 'Guvenli temizlik hedefleri:' -ForegroundColor Cyan
foreach ($target in $existingTargets) {
    Write-Host ('  - ' + $target.Substring($appRoot.Length + 1))
}
Write-Host '  - Kaynak kod klasorlerindeki __pycache__ ve gevsek .pyc/.pyo dosyalari'
Write-Host ''
Write-Host ('Yaklasik bosalacak alan: {0:N2} MB' -f ($estimatedBytes / 1MB)) -ForegroundColor Yellow
Write-Host ''
Write-Host 'KORUNACAK: .venv-build, dist, installer, .restore_points, security_keys,'
Write-Host 'modular_app\data ve ___Skolyoz deneme hastalari.'
Write-Host ''
$answer = Read-Host 'Devam etmek icin TEMIZLE yazin'
if ($answer -cne 'TEMIZLE') {
    Write-Host 'Islem iptal edildi; hicbir dosya silinmedi.' -ForegroundColor Yellow
    exit 0
}

$removedBytes = 0L
$removedCount = 0
foreach ($target in $existingTargets) {
    if (-not (Test-Path -LiteralPath $target)) { continue }
    $removedBytes += Item-Size $target
    Remove-Item -LiteralPath $target -Recurse -Force
    $removedCount++
}

$cacheTargets = @(
    Get-ChildItem -LiteralPath $appRoot -Directory -Recurse -Force -Filter '__pycache__' |
        Where-Object { $_.FullName -notmatch $excludedRoots } |
        Sort-Object { $_.FullName.Length } -Descending
)
foreach ($cache in $cacheTargets) {
    $safeCache = Assert-SafeTarget $cache.FullName
    if (-not (Test-Path -LiteralPath $safeCache)) { continue }
    $removedBytes += Item-Size $safeCache
    Remove-Item -LiteralPath $safeCache -Recurse -Force
    $removedCount++
}

$looseBytecode = @(
    Get-ChildItem -LiteralPath $appRoot -File -Recurse -Force |
        Where-Object {
            $_.Extension -in '.pyc', '.pyo' -and
            $_.FullName -notmatch $excludedRoots
        }
)
foreach ($file in $looseBytecode) {
    $safeFile = Assert-SafeTarget $file.FullName
    $removedBytes += $file.Length
    Remove-Item -LiteralPath $safeFile -Force
    $removedCount++
}

Write-Host ''
Write-Host ('Temizlik tamamlandi. {0} hedef kaldirildi, {1:N2} MB alan bosaltildi.' -f $removedCount, ($removedBytes / 1MB)) -ForegroundColor Green

