@echo off
setlocal
title FreeLanSync Desktop Server
echo ========================================================
echo        Starting FreeLanSync Local Desktop Server
echo ========================================================
echo.

cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Run Server using uvicorn
echo Starting server on http://0.0.0.0:8080 ...
echo Press Ctrl+C to stop the server.
echo.

python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload

pause
