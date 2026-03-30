Option Explicit

Dim shell, fso, scriptDir, psScript, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
psScript = scriptDir & "\launch_kai_panel.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & psScript & """"

' 0 = hidden window, False = return immediately
shell.Run cmd, 0, False
