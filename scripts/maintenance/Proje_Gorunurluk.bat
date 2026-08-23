@echo off
setlocal
cd /d "%~dp0\..\.."

if exist .venv\Scripts\python.exe (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if /I "%~1"=="show" goto show

%PYTHON% scripts\maintenance\project_root_visibility.py --hide
if errorlevel 1 exit /b 1

echo Proje teknik ve yerel klasorleri gizlendi.
echo Geri gostermek icin: scripts\maintenance\Proje_Gorunurluk.bat show
goto done

:show
%PYTHON% scripts\maintenance\project_root_visibility.py --show
if errorlevel 1 exit /b 1

echo Tum teknik ve yerel klasorler yeniden gorunur.

:done
endlocal
