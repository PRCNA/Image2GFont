Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = root & "\.venv-vision\Scripts\pythonw.exe"
If Not fs.FileExists(python) Then
    MsgBox "Please run setup_windows.bat first.", 16, "Image2GFont"
Else
    shell.CurrentDirectory = root
    shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\desktop_app.py" & Chr(34), 0, False
End If
