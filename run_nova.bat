@echo off
title NOVA Desktop Assistant
cd /d "%~dp0"
echo ========================================
echo  Launching NOVA Desktop Assistant...
echo ========================================
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_desktop.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] NOVA encountered an issue while running.
    pause
)
