@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo   Environment check (read-only)
echo ==========================================
echo.
".venv\Scripts\python.exe" check_env.py
echo.
pause
