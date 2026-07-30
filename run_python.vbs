Option Explicit

Dim shell, pythonwPath
pythonwPath = "C:\Python314\pythonw.exe" ' troque se necessário

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

shell.Run """" & pythonwPath & """ main.py", 0, False
