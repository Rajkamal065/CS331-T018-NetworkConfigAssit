@echo off
title NetOps MCP Assistant — Desktop App (Docker Backend)
cd /d "%~dp0"
echo ============================================================
echo   Starting NetOps Desktop App connected to Docker Backend
echo   (Backend: Linux Kernel + iptables + FastMCP stdio)
echo ============================================================
echo.
python app.py --connect http://localhost:5000
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Launching web browser mode fallback...
    start http://localhost:5000
)
pause
