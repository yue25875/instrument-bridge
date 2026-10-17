@echo off
cd /d "%~dp0"
echo Pitch detection only (no game output). Ctrl+C to quit.
echo.
".venv\Scripts\python.exe" live_pitch.py
echo.
pause