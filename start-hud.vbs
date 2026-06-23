' Launches Quest HUD silently (no console window) using the local environment.
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = here & "\.venv\Scripts\pythonw.exe"
script = here & "\hud.py"

If Not fso.FileExists(pyw) Then
  MsgBox "Please run run.bat once first to finish setup.", vbExclamation, "Quest HUD"
  WScript.Quit
End If

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = here
sh.Run """" & pyw & """ """ & script & """", 0, False
