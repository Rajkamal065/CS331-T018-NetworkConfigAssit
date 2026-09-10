@echo off
title NetOps MCP Assistant — AI Network Operations
cd /d "%~dp0"
echo ============================================================
echo   Starting NetOps MCP AI Network Operations Assistant
echo ============================================================
echo.

:: Check if Docker backend is running on port 5000
curl -s -m 1 http://localhost:5000/api/status >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Detected active Docker backend at http://localhost:5000
    echo [INFO] Connecting native desktop window to Docker Linux backend...
    echo.
    python app.py --connect http://localhost:5000
    goto end
)

:: Otherwise run local standalone mode
echo [INFO] No Docker backend detected on port 5000. Running local mode...
echo.
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Launching web browser mode fallback...
    python app.py --web
)

:end
pause

