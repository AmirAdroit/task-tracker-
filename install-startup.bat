@echo off
setlocal
cd /d "%~dp0"
title Quest HUD - add to startup

if not exist ".venv\Scripts\python.exe" (
  echo [!] Run run.bat once to finish setup first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -B -c "from state_service import configure_startup; configure_startup(True)"
if errorlevel 1 ( echo [!] Could not create the startup shortcut. & pause & exit /b 1 )

echo Done. Quest HUD will now start automatically when you log in to Windows.
echo.
echo To undo later: press Win+R, type   shell:startup   and delete "Quest HUD".
echo.
pause
endlocal
