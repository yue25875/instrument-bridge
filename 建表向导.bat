@echo off
cd /d "%~dp0"
chcp 65001 >nul
echo ==========================================
echo   Key Mapping Wizard
echo.
echo   Build a profiles/games/*.json for YOUR game.
echo   The game must be running with the instrument open.
echo ==========================================
echo.
".venv\Scripts\python.exe" setup_wizard.py
echo.
pause