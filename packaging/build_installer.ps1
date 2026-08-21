param(
    [string]$CertificateThumbprint = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$releaseVersion = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
if ($releaseVersion -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION dosyasında geçerli bir sürüm bulunamadı. Örnek: 1.3.0"
}

function Find-InnoCompiler {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $paths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )

    $registryRoots = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    )
    foreach ($registryRoot in $registryRoots) {
        Get-ChildItem $registryRoot -ErrorAction SilentlyContinue | ForEach-Object {
            $entry = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            if ($entry.DisplayName -like 'Inno Setup*' -and $entry.InstallLocation) {
                $paths += (Join-Path $entry.InstallLocation 'ISCC.exe')
            }
        }
    }

    return $paths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

$dist = Join-Path $root 'dist\ScoliosisFollowUp\ScoliosisFollowUp.exe'
if (-not (Test-Path $dist)) {
    throw "Önce EXE paketini oluşturun: .\packaging\build_windows.ps1 -Clean"
}

$innoCompiler = Find-InnoCompiler
if (-not $innoCompiler) {
    throw "Inno Setup 7 veya 6 bulunamadı. Kurduktan sonra bu betiği yeniden çalıştırın."
}

& $innoCompiler "/DAppVersion=$releaseVersion" (Join-Path $PSScriptRoot 'ScoliosisFollowUp.iss')
if ($LASTEXITCODE -ne 0) {
    throw "Kurulum paketi derlenemedi. Yukarıdaki Inno Setup hata iletisini kontrol edin."
}
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
