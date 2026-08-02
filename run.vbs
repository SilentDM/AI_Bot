Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Obtém a pasta exata onde este arquivo run.vbs está salvo
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Define o diretório de trabalho como a raiz do projeto
objShell.CurrentDirectory = strPath

' Executa o script main.py usando pythonw (sem janela de terminal)
' O parâmetro 0 oculta qualquer janela e False não bloqueia a execução
objShell.Run "pythonw main.py", 0, False