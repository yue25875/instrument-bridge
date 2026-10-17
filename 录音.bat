@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" record_sample.py --seconds 12
echo.
pause