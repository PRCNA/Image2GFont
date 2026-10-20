$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv-vision\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Run setup_windows.bat before creating the shortcut.'
}
$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath 'Image2GFont.lnk'
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonPath
$shortcut.Arguments = '"' + (Join-Path $projectRoot 'desktop_app.py') + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = (Join-Path $projectRoot 'frontend\logo.ico') + ',0'
$shortcut.Description = 'Image2GFont'
$shortcut.Save()
Write-Output $shortcutPath
