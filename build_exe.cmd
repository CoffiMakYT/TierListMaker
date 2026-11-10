@echo off
setlocal
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Building TierListMaker.exe...
python -m PyInstaller --noconfirm --clean --windowed --onefile --name TierListMaker --icon assets\tierlist-icon.ico --add-data "assets\tierlist-icon.png;." --collect-all PySide6 --collect-all shiboken6 main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete:
echo %~dp0dist\TierListMaker.exe
pause