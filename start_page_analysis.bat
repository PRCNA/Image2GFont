@echo off
cd /d "%~dp0"
".venv-vision\Scripts\python.exe" launch_page_analysis.py
if errorlevel 1 pause
