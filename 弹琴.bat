@echo off
cd /d "%~dp0"
echo ==========================================
echo   Instrument  -^>  Game Piano
echo.
echo   1. Open the piano in game
echo   2. Run this, then CLICK the game window once
echo   3. Play. Do NOT touch the mouse.
echo   Ctrl+C to quit
echo ==========================================
echo.
".venv\Scripts\python.exe" live_to_game.py --low-latency --gate-db -45
echo.
echo [exited]
pause