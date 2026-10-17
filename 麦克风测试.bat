@echo off
cd /d "%~dp0"
echo Mic level meter. Talk, clap or play. Ctrl+C to quit.
echo.
".venv\Scripts\python.exe" mic_meter.py
echo.
pause