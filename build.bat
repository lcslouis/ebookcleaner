@echo off
echo ============================================
echo  EbookCleaner - Windows Build Script
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Building executable...
pyinstaller ebookcleaner.spec --clean --noconfirm

echo.
echo [3/3] Done!
if exist "dist\EbookCleaner\EbookCleaner.exe" (
    echo SUCCESS: Executable created at dist\EbookCleaner\EbookCleaner.exe
    echo.
    echo To distribute: zip the entire dist\EbookCleaner\ folder
) else (
    echo ERROR: Build may have failed. Check output above.
)

pause
