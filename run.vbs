Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strPath
' Usa o pythonw de dentro da build_env para garantir que todas as bibliotecas existam
objShell.Run "build_env\Scripts\pythonw.exe main.py", 0, False