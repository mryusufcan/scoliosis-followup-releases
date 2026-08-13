param(
    [string]$CertificateThumbprint = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'dist\ScoliosisFollowUp\ScoliosisFollowUp.exe'
if (-not (Test-Path $dist)) {
    throw "Önce EXE paketini oluşturun: .\packaging\build_windows.ps1 -Clean"
}

$candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $candidates) {
    throw "Inno Setup 6 bulunamadı. Kurduktan sonra bu betiği yeniden çalıştırın."
}

& $candidates[0] (Join-Path $PSScriptRoot 'ScoliosisFollowUp.iss')
if ($CertificateThumbprint) {
    $signToolCommand = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($signToolCommand) {
        $signToolPath = $signToolCommand.Source
    } else {
        $signToolCandidate = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1
        if (-not $signToolCandidate) { throw "Kod imzalama için SignTool bulunamadı. Windows SDK kurulumunu kontrol edin." }
        $signToolPath = $signToolCandidate.FullName
    }
    & $signToolPath sign /sha1 $CertificateThumbprint /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 "$root\installer\ScoliosisFollowUp_Setup.exe"
    if ($LASTEXITCODE -ne 0) { throw "Kurulum dosyası imzalanamadı." }
}
Write-Host "Hazır: $root\installer\ScoliosisFollowUp_Setup.exe"
