param(
    [string]$FeedUrl = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Paketleme ortamı bulunamadı. Önce .\packaging\build_windows.ps1 -Clean komutunu çalıştırın."
}

$commandArguments = @(
    (Join-Path $root 'packaging\verify_release.py'),
    '--root', $root
)
if ($FeedUrl.Trim()) {
    $commandArguments += @('--feed-url', $FeedUrl.Trim())
}

& $python @commandArguments
if ($LASTEXITCODE -ne 0) {
    throw "Dağıtım kabul denetimi başarısız oldu. EXE veya GitHub sürüm dosyalarını göndermeden önce yukarıdaki nedeni düzeltin."
}
