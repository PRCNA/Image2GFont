@echo off
cd /d "%~dp0"
python ocr_review.py
if errorlevel 1 pause
