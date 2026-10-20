@echo off
cd /d "%~dp0"
python -m page_import
if errorlevel 1 pause
