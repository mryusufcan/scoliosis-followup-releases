@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Guvenli Temizlik

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\safe_cleanup.ps1"
set "CLEAN_RESULT=%ERRORLEVEL%"

echo.
if not "%CLEAN_RESULT%"=="0" (
    echo TEMIZLIK BASARISIZ. Yukaridaki hata mesajini kontrol edin.
)
pause
exit /b %CLEAN_RESULT%

