@echo off
setlocal
cd /d "%~dp0"
echo Image2GFont - install dependencies (network required)
py -3.9 -m venv .venv-ocr
if errorlevel 1 goto failed
py -3.12 -m venv .venv-vision
if errorlevel 1 goto failed
".venv-ocr\Scripts\python.exe" -m pip install -r requirements-ocr-lock.txt
if errorlevel 1 goto failed
".venv-vision\Scripts\python.exe" -m pip install --extra-index-url https://download.pytorch.org/whl/cu128 -r requirements-vision-lock.txt
if errorlevel 1 goto failed
".venv-vision\Scripts\python.exe" -m pip install -r requirements-desktop-lock.txt
if errorlevel 1 goto failed
echo Dependencies installed. Run download_models.bat for Qwen, then start_frontend.bat.
pause
exit /b 0
:failed
echo Installation failed. See the message above. Python 3.9 and 3.12 with the Windows py launcher are required.
pause
exit /b 1
