@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Scoliosis Follow-Up - Registration Testleri
echo ============================================================
echo.

if not exist "tests\test_registration_math.py" (
    echo [HATA] tests\test_registration_math.py bulunamadi.
    echo.
    echo Bu BAT dosyasini proje kokune koyun.
    echo Proje yapisi soyle olmali:
    echo.
    echo   Scoliosis Follow Up\
    echo     run_registration_tests.bat
    echo     tests\
    echo       __init__.py
    echo       test_registration_math.py
    echo.
    pause
    exit /b 1
)

python -m unittest discover -s tests -p "test_registration_math.py" -v

echo.
if errorlevel 1 (
    echo [HATA] Registration testlerinden en az biri basarisiz.
) else (
    echo [OK] Translation + Zoom + Rotation testleri basarili.
)

echo.
pause
