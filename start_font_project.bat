@echo off
cd /d "%~dp0"
python launch_font_project.py
if errorlevel 1 pause
