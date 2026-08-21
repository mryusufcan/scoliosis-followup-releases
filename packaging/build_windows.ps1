param(
    [switch]$Clean,
    [switch]$SkipTests,
    [string]$CertificateThumbprint = "",
    [string]$IntegrityPrivateKey = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$releaseVersion = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
if ($releaseVersion -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION dosyasında geçerli bir sürüm bulunamadı. Örnek: 1.3.0"
}

function Find-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return [PSCustomObject]@{ Path = $python.Source; Arguments = @() }
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        return [PSCustomObject]@{ Path = $launcher.Source; Arguments = @('-3') }
    }
    throw "Python 3.10 veya üzeri bulunamadı. Python'u yükleyip PATH'e ekleyin."
}

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $kits = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($kits) { return $kits[0].FullName }
    throw "Kod imzalama için SignTool bulunamadı. Windows SDK kurulumunu ve PATH ayarını kontrol edin."
}

function Sign-ApplicationFile([string]$Path) {
    if (-not $CertificateThumbprint) { return }
    $signTool = Find-SignTool
    & $signTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { throw "Kod imzalama başarısız oldu: $Path" }
}

# Ayrı ortam kullanmak, paketleme için gereken kütüphanelerin sistemdeki
# başka projelerle çakışmasını önler. İlk çalıştırmada otomatik oluşturulur.
$hostPython = Find-Python
$venvPython = Join-Path $root '.venv-build\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    & $hostPython.Path @($hostPython.Arguments) -m venv "$root\.venv-build"
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r "$root\requirements.txt"

# Her dağıtım kendi Ed25519 bütünlük anahtarını kullanır. Özel anahtar sadece
# paketleme bilgisayarında kalır; EXE'ye veya kurulum dosyasına eklenmez.
$securityKeyDirectory = Join-Path $root 'security_keys'
$integrityKey = if ($IntegrityPrivateKey) { $IntegrityPrivateKey } else { Join-Path $securityKeyDirectory 'integrity_private.pem' }
$integrityPublicKey = Join-Path $root 'resources\security\integrity_public_key.pem'
$integrityIdentity = Join-Path $root 'modular_app\security\integrity_identity.py'
& $venvPython "$root\packaging\generate_integrity_key.py" `
  --private "$integrityKey" `
  --public "$integrityPublicKey" `
  --identity "$integrityIdentity"
if ($LASTEXITCODE -ne 0) { throw "Dağıtım bütünlük anahtarı oluşturulamadı." }

if (-not $SkipTests) {
  $testLogDirectory = Join-Path $root 'build'
  New-Item -ItemType Directory -Force -Path $testLogDirectory | Out-Null
  $testLog = Join-Path $testLogDirectory 'test-results.txt'
  Remove-Item -LiteralPath $testLog -Force -ErrorAction SilentlyContinue

  function Invoke-LoggedPython([string]$label, [string[]]$arguments) {
    # Python'ın stderr çıktısı (örneğin üçüncü taraf uyarıları), PowerShell 7'de
    # NativeCommandError olarak yorumlanabiliyor. Süreci doğrudan başlatıp iki
    # akışı dosyaya yönlendirmek, yalnızca gerçek çıkış koduyla karar vermemizi
    # sağlar; hata/uyarı metni de test-results.txt içinde korunur.
    $stdout = Join-Path $testLogDirectory "$label.stdout.txt"
    $stderr = Join-Path $testLogDirectory "$label.stderr.txt"
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    $process = Start-Process -FilePath $venvPython -ArgumentList $arguments -WorkingDirectory $root `
      -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    foreach ($stream in @($stdout, $stderr)) {
      if (Test-Path -LiteralPath $stream) {
        Get-Content -LiteralPath $stream | Tee-Object -FilePath $testLog -Append | Out-Host
      }
    }
    return [int]$process.ExitCode
  }

  $environmentExitCode = Invoke-LoggedPython 'environment' @('.\tests\verify_environment.py')
  if ($environmentExitCode -ne 0) { throw "Paketleme ortamı doğrulaması başarısız oldu. Ayrıntılar: $testLog" }
  $testExitCode = Invoke-LoggedPython 'tests' @('.\tests\run_modular_tests.py')
  if ($testExitCode -ne 0) { throw "Otomatik testler başarısız olduğu için EXE oluşturulmadı. Ayrıntılar: $testLog" }
}

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$root\build", "$root\dist"
}

# --onedir, PySide6/DICOM/PACS gibi yerel DLL kullanan bu uygulama için en
# güvenilir dağıtım biçimidir. EXE ile birlikte oluşan klasör tek parça olarak
# teslim edilmelidir; hedef bilgisayarda Python kurulumu gerekmez.
# PyInstaller'in PySide6/pydicom/Qt hook'lari yalnizca gercek importlari
# toplar. Bu paketlerde --collect-all kullanmak Qt WebEngine, 3D, QML,
# gelistirme araclari ve test verilerini gereksiz yere dagitima ekler.
$specDirectory = Join-Path $root 'build\spec'
New-Item -ItemType Directory -Force -Path $specDirectory | Out-Null
& $venvPython -m PyInstaller --noconfirm --clean --windowed --onedir `
  --name "ScoliosisFollowUp" `
  --specpath "$specDirectory" `
  --icon "$root\resources\branding\ScoliosisFollowUp.ico" `
  --paths "$root" `
  --add-data "$root\VERSION;." `
  --add-data "$root\resources\branding\logo.png;." `
  --add-data "$root\resources;resources" `
  --hidden-import license_app `
  --hidden-import cv2 `
  --collect-submodules modular_app `
  --collect-submodules pacs `
  --collect-submodules dicom `
  --collect-submodules anonymization `
  --collect-submodules ai `
  --collect-all pylibjpeg `
  --collect-all libjpeg `
  --collect-all openjpeg `
  --collect-all rle `
  --collect-all jpeg_ls `
  "$root\main.py"
if ($LASTEXITCODE -ne 0) { throw "EXE paketleme başarısız oldu." }

Sign-ApplicationFile "$root\dist\ScoliosisFollowUp\ScoliosisFollowUp.exe"

# Manifest, EXE imzalandıktan sonra üretilir; böylece imzalı EXE dahil tüm
# dağıtım dosyalarının özeti uygulama açılışında doğrulanır.
& $venvPython "$root\packaging\generate_integrity_manifest.py" `
  --root "$root\dist\ScoliosisFollowUp" `
  --private-key "$integrityKey" `
  --version "$releaseVersion"
if ($LASTEXITCODE -ne 0) { throw "Dağıtım bütünlük manifest'i oluşturulamadı." }

Write-Host "Hazır: $root\dist\ScoliosisFollowUp\ScoliosisFollowUp.exe"
Write-Host "Dağıtım: dist\ScoliosisFollowUp klasörünün tamamını kopyalayın."
Write-Host "Kullanıcı verileri: %LOCALAPPDATA%\ScoliosisFollowUp"
Write-Host "Bütünlük: İmzalı runtime_integrity.json oluşturuldu."
if ($CertificateThumbprint) {
    Write-Host "EXE, belirtilen sertifikayla imzalandı."
}

