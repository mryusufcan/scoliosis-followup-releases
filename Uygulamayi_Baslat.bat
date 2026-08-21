@echo off
setlocal
title Scoliosis Follow-Up - Calisma Konsolu
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo HATA: Proje Python ortami bulunamadi.
    echo Beklenen: %CD%\.venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

echo Scoliosis Follow-Up baslatiliyor...
echo Bu pencere uygulama acik oldugu surece acik kalacaktir.
echo.
".venv\Scripts\python.exe" -u main.py

set "SFU_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%SFU_EXIT_CODE%"=="0" (
    echo Uygulama hata koduyla kapandi: %SFU_EXIT_CODE%
) else (
    echo Uygulama kapatildi.
)
echo Bu pencereyi kapatmak icin bir tusa basin.
pause >nul
exit /b %SFU_EXIT_CODE%
