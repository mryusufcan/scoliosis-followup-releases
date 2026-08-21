@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"
title Scoliosis Follow-Up - Otomatik Testler

if not exist ".venv-build\Scripts\python.exe" (
    echo Paketleme ortami bulunamadi.
    echo Once Tam_Surum_Olustur.bat dosyasini bir kez calistirin.
    echo.
    pause
    exit /b 1
)

echo Bagimliliklar kontrol ediliyor...
".venv-build\Scripts\python.exe" ".\tests\verify_environment.py"
if errorlevel 1 goto failed

echo.
echo Otomatik testler calistiriliyor...
".venv-build\Scripts\python.exe" ".\tests\run_modular_tests.py"
if errorlevel 1 goto failed

echo.
echo TUM TESTLER BASARILI.
pause
exit /b 0

:failed
echo.
echo TESTLER BASARISIZ. Yukaridaki ilk hata mesajini kontrol edin.
pause
exit /b 1

