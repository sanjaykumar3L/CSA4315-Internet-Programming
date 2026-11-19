@echo off
setlocal
title Capstone - Web Service Contract Studio
echo ================================================
echo   Web Service Interoperability Capstone
echo   Starting local Flask application
echo ================================================
echo.
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH. Install Python 3.10 or newer.
  pause
  exit /b 1
)
echo Installing dependencies if needed: python -m pip install -r requirements.txt
echo Launching the local server at http://127.0.0.1:5000
echo Press Ctrl+C to stop.
start "" http://127.0.0.1:5000
python run.py
if errorlevel 1 (
  echo.
  echo Startup failed. Check installation and requirements.txt.
  pause
  exit /b 1
)
endlocal
