@echo off
cd /d "%~dp0"
python -m coordinate_editor.app
if errorlevel 1 pause
