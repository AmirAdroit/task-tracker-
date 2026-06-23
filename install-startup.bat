@echo off
setlocal
cd /d "%~dp0"
title Quest HUD - add to startup

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut('%STARTUP%\Quest HUD.lnk'); $s.TargetPath='%~dp0start-hud.vbs'; $s.WorkingDirectory='%~dp0'; $s.Save()"
if errorlevel 1 ( echo [!] Could not create the startup shortcut. & pause & exit /b 1 )

echo Done. Quest HUD will now start automatically when you log in to Windows.
echo.
echo To undo later: press Win+R, type   shell:startup   and delete "Quest HUD".
echo.
pause
endlocal
