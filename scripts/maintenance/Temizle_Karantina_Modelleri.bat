@echo off
setlocal
cd /d "%~dp0\..\.."
if exist .venv\Scripts\python.exe (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% scripts\maintenance\cleanup_quarantine_models.py %*
if errorlevel 1 (
    echo Karantina model bakimi basarisiz oldu.
    exit /b 1
)

echo.
echo Varsayilan mod dry-run'dir. Silme icin betik yardimindaki iki acik onay kosulunu kullanin.
pause
endlocal
