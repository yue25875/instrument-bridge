@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   Key Mapping Wizard
echo   Build a key map for YOUR game.
echo ==========================================
echo.
if not exist "instrument-bridge.exe" (
    echo [ERROR] instrument-bridge.exe not found in this folder.
    pause
    exit /b 1
)
"instrument-bridge.exe" --wizard
echo.
pause
