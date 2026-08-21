@echo off
setlocal
cd /d "%~dp0\..\.."
title Scoliosis Follow-Up - Lisans Yonetimi

for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v SUPABASE_SECRET_KEY 2^>nul ^| find "SUPABASE_SECRET_KEY"') do set "SUPABASE_SECRET_KEY=%%B"

if "%SUPABASE_SECRET_KEY%"=="" (
    echo.
    echo Secret key bulunamadi.
    echo Once Lisans_Yonetimi_Anahtar_Kaydet.ps1 dosyasini calistirin.
    echo.
    pause
    exit /b 1
)

python ".\tools\license_admin.py"
if errorlevel 1 pause
