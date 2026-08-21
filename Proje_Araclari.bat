@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".\.venv-build\Scripts\python.exe" set "PYTHON_EXE=.\.venv-build\Scripts\python.exe"
if exist ".\.venv\Scripts\python.exe" set "PYTHON_EXE=.\.venv\Scripts\python.exe"

set "CONTROL_CENTER="

if exist ".\tools\project_control_center.py" (
    set "CONTROL_CENTER=.\tools\project_control_center.py"
)

if not defined CONTROL_CENTER if exist ".\project_control_center.py" (
    set "CONTROL_CENTER=.\project_control_center.py"
)

if not defined CONTROL_CENTER (
    echo.
    echo [HATA] project_control_center.py bulunamadi.
    echo.
    echo Dosyayi su iki konumdan birine koyun:
    echo   %CD%\tools\project_control_center.py
    echo veya
    echo   %CD%\project_control_center.py
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%CONTROL_CENTER%" %*
exit /b %ERRORLEVEL%
