@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Scoliosis Follow-Up - PixelSpacing Ölçüm Testi
echo ============================================================
echo.
python pixel_spacing_test_uret.py
echo.
echo Test DICOM olusturulduysa uygulamada acip:
echo   1) Yatay iki arti merkezi: 16.00 cm
echo   2) Dikey iki arti merkezi: 10.00 cm
echo   3) 90 derece dondurup tekrar olc: ayni fiziksel sonuc
echo.
pause
