@echo off
cd /d "%~dp0"
python -m stroke_editor.app
if errorlevel 1 pause
