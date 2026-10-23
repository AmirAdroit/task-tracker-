@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once to install QuestHUD first.
  pause
  exit /b 1
)
if "%~1"=="" (
  ".venv\Scripts\python.exe" -B recovery.py --help
  pause
  exit /b 0
)
".venv\Scripts\python.exe" -B recovery.py %*
if errorlevel 1 ( pause & exit /b 1 )
endlocal
