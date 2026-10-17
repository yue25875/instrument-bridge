@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo   instrument-bridge  -  installer
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo.
    echo   Install Python 3.10 or newer from:
    echo     https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo Found Python %%v

echo.
echo [1/2] Creating virtual environment (.venv) ...
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] venv creation failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing dependencies (numpy, sounddevice) ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed. If GitHub/PyPI is slow, try a mirror:
    echo.
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Done.
echo.
echo   Next: double-click  弹琴.bat
echo     (or 麦克风测试.bat to check your mic first)
echo ==========================================
echo.
pause
