param()
$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "Secret key Windows kullanici ortamina kaydedilecek."
Write-Host "Proje dosyalarina yazilmayacak."
Write-Host ""
$secure = Read-Host "sb_secret_... anahtarini girin" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if ([string]::IsNullOrWhiteSpace($plain) -or -not $plain.StartsWith("sb_secret_")) {
        throw "Gecerli sb_secret_... anahtari girilmedi."
    }
    [Environment]::SetEnvironmentVariable("SUPABASE_SECRET_KEY", $plain, "User")
    $env:SUPABASE_SECRET_KEY = $plain
    Write-Host ""
    Write-Host "[OK] Secret key Windows kullanici ortamina kaydedildi."
}
finally {
    if ($ptr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
    $plain = $null
}
