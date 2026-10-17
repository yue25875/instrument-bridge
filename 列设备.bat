@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" list_devices.py
echo.
pause