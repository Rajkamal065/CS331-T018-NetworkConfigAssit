@echo off
title NetOps MCP Assistant — Web Browser Mode
cd /d "%~dp0"
echo ============================================================
echo   Starting NetOps Assistant in Web Browser Mode
echo   URL: http://127.0.0.1:8000
echo ============================================================
echo.
python app.py --web
pause
