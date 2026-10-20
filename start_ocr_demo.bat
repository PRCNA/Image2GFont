@echo off
cd /d "%~dp0"
.venv-ocr\Scripts\python.exe ocr_demo.py
if errorlevel 1 pause
