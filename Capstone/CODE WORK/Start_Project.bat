@echo off
title Web Service Interoperability & Contract Validation Platform
color 0A

echo =======================================================================
echo   Starting: Web Service Interoperability and Data Contract Validation
echo   Course: CSA4315 - Internet Programming
echo =======================================================================
echo.

cd /d "C:\Users\lsk87\OneDrive\Desktop\inventory\IP\Capstone"

echo [1/2] Launching Web Browser at http://127.0.0.1:5000 ...
start "" http://127.0.0.1:5000

echo [2/2] Starting Python Flask Full-Stack Server...
echo.
python run.py

if errorlevel 1 (
    echo.
    echo [ERROR] An error occurred while starting the server.
    pause
)
