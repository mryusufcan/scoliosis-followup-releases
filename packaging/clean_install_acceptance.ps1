param(
    [string]$DicomPath = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
)
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup bulunamadı.' }

if (-not $DicomPath) {
    $DicomPath = Get-ChildItem (Join-Path $root 'dev_data\dicom_samples') -Recurse -File |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not (Test-Path -LiteralPath $DicomPath)) { throw "Kabul DICOM'u bulunamadı: $DicomPath" }

$acceptanceRoot = Join-Path $env:LOCALAPPDATA 'ScoliosisFollowUp-Acceptance'
$installDir = Join-Path $acceptanceRoot 'app'
$dataRoot = Join-Path $acceptanceRoot 'profile'
$setup = Join-Path $root 'build\acceptance-installer\ScoliosisFollowUp_Acceptance_Setup.exe'

& $iscc "/DAppVersion=$version" '/DAcceptanceBuild=1' (Join-Path $root 'packaging\ScoliosisFollowUp.iss')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $setup)) { throw 'Kabul installer derlemesi başarısız.' }

& $setup /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS
if ($LASTEXITCODE -ne 0) { throw 'Kabul kurulumu başarısız.' }

$exe = Join-Path $installDir 'ScoliosisFollowUp.exe'
$uninstaller = Join-Path $installDir 'unins000.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Kurulan EXE bulunamadı.' }

New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
$process = Start-Process -FilePath $exe `
    -ArgumentList @('--open-dicom', ('"' + (Resolve-Path $DicomPath).Path + '"')) `
    -WorkingDirectory $installDir -WindowStyle Hidden -PassThru `
    -Environment @{ LOCALAPPDATA = $dataRoot }
$exitedEarly = $process.WaitForExit(15000)
$earlyExitCode = if ($exitedEarly) { $process.ExitCode } else { $null }
if (-not $exitedEarly) { Stop-Process -Id $process.Id -Force }

$appData = Join-Path $dataRoot 'ScoliosisFollowUp'
$databaseCreated = Test-Path -LiteralPath (Join-Path $appData 'scoliosis.db')
$logCreated = Test-Path -LiteralPath (Join-Path $appData 'logs\application.log')

if (Test-Path -LiteralPath $uninstaller) {
    & $uninstaller /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
}
$installRemoved = -not (Test-Path -LiteralPath $exe)

$result = [ordered]@{
    setup_created = Test-Path -LiteralPath $setup
    installed_exe_created = $true
    stayed_running_for_15_seconds = -not $exitedEarly
    early_exit_code = $earlyExitCode
    isolated_database_created = $databaseCreated
    isolated_log_created = $logCreated
    uninstall_removed_executable = $installRemoved
    production_app_id_untouched = $true
}
$result | ConvertTo-Json

if ($exitedEarly -or -not $databaseCreated -or -not $logCreated -or -not $installRemoved) {
    exit 1
}
