' Explicit stable-renderer launch. Quit the running app from its tray first.
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = here & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then
  MsgBox "Run run.bat once to install QuestHUD first.", vbExclamation, "Quest HUD"
  WScript.Quit
End If
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = here
sh.Run """" & pyw & """ """ & here & "\hud.py" & """ --renderer software", 0, False
