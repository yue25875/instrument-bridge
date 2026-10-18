@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo   instrument-bridge  -  installer
echo ==========================================
echo.

rem ---- ???????? Python 3.10+ ----
rem Windows ??? python.exe ????????????
rem where python ???????????????????????????
set "PY="
call :try_python python
if not defined PY call :try_python py -3
if not defined PY call :try_python python3

if not defined PY goto :no_python

echo Using Python launcher: !PY!
for /f "delims=" %%v in ('!PY! --version 2^>^&1') do echo   %%v
echo.

rem ---- ????? ----
echo [1/2] Creating virtual environment ...
!PY! -m venv .venv
if errorlevel 1 goto :venv_failed
if not exist ".venv\Scripts\python.exe" goto :venv_failed

rem ---- ??? ----
echo.
echo [2/2] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :pip_failed

echo.
echo ==========================================
echo   Done.
echo.
echo   Next: double-click the piano launcher .bat
echo         (or the mic test .bat to check your microphone first)
echo ==========================================
echo.
pause
exit /b 0

:try_python
rem ???????? Python 3??? >= 3.10
%* -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "PY=%*"
exit /b 0

:no_python
echo [ERROR] No working Python 3.10+ found.
echo.
echo   "python" exists but does not actually run --
echo   this is usually the Microsoft Store stub.
echo.
echo   How to fix:
echo     1. Install Python 3.10+ from https://www.python.org/downloads/
echo     2. During install, CHECK "Add Python to PATH"
echo     3. If you previously installed Python from Microsoft Store,
echo        uninstall it first (Settings - Apps)
echo     4. Close this window, open a NEW one, and run this again
echo.
pause
exit /b 1

:venv_failed
echo.
echo [ERROR] Failed to create the virtual environment.
echo.
echo   This usually means the Python installation is broken or incomplete.
echo   Try:
echo     1. Reinstall Python from https://www.python.org/downloads/
echo     2. Or run in a normal cmd window:
echo          cd /d "%~dp0"
echo          python -m venv .venv
echo   and send us the exact error message.
echo.
pause
exit /b 1

:pip_failed
echo.
echo [ERROR] pip install failed. If PyPI is slow, try a mirror:
echo.
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
pause
exit /b 1
