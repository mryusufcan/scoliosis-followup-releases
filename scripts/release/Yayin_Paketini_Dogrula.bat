@echo off
setlocal EnableExtensions
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Yerel Yayin Dogrulama

echo.
echo ============================================================
echo              YEREL YAYIN PAKETI DOGRULAMA
echo ============================================================
echo.

if not exist ".\tools\release_acceptance.ps1" (
    echo [HATA] tools\release_acceptance.ps1 bulunamadi.
    exit /b 1
)

rem FeedUrl verilmez: sadece yerel EXE / installer / update.json dogrulanir.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\release_acceptance.ps1"
set "CHECK_RESULT=%ERRORLEVEL%"

echo.
if not "%CHECK_RESULT%"=="0" (
    echo YEREL YAYIN DENETIMI BASARISIZ.
    exit /b %CHECK_RESULT%
)

echo YEREL YAYIN DENETIMI BASARILI.
echo Paket yerel olarak dagitima hazir.
exit /b 0
