@echo off
setlocal
cd /d "%~dp0"
title Quest HUD

echo ==========================================
echo    Quest HUD  -  setup and launch
echo ==========================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo [!] Python was not found on this PC.
  echo.
  echo     1^) Download it from https://www.python.org/downloads/
  echo     2^) During install, TICK the box "Add python.exe to PATH"
  echo     3^) Then run this file again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Setting up for the first time...
  %PY% -m venv .venv
  if errorlevel 1 ( echo [!] Could not create the environment. & pause & exit /b 1 )
)

call ".venv\Scripts\activate.bat"

python -c "import PySide6; assert PySide6.__version__ == '6.11.1'" 1>nul 2>nul
if errorlevel 1 (
  echo Installing components ^(first run only, about 1-2 minutes^)...
  python -m pip install --upgrade pip >nul 2>nul
  python -m pip install -r requirements.txt
  if errorlevel 1 ( echo [!] Install failed. Copy the text above and send it to me. & pause & exit /b 1 )
)

echo.
echo Starting Quest HUD...
echo ^(This window can stay minimized. Closing it stops the HUD.^)
echo For silent daily use, double-click start-hud.vbs instead.
echo.
python hud.py
if errorlevel 1 (
  echo.
  echo [!] Something went wrong above. Copy the error text and send it to me.
  pause
)
endlocal
