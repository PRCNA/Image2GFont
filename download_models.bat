@echo off
cd /d "%~dp0"
".venv-vision\Scripts\python.exe" download_qwen_model.py
if errorlevel 1 goto failed
echo Qwen downloaded and verified. RapidOCR downloads its models on first use.
pause
exit /b 0
:failed
echo Model download failed. Check network access and available disk space.
pause
exit /b 1
