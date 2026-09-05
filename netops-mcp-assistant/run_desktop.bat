@echo off
title NetOps MCP Assistant — AI Network Operations
cd /d "%~dp0"
echo ============================================================
echo   Starting NetOps MCP AI Network Operations Assistant
echo   (FastMCP Server + LLM Client + Desktop GUI)
echo ============================================================
echo.
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Launching web browser mode fallback...
    python app.py --web
)
pause
