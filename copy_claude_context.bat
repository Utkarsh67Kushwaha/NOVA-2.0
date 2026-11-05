@echo off
cd /d "%~dp0"
echo ========================================================
echo  Copying NOVA 2.0 Claude Context to Clipboard...
echo ========================================================
".venv\Scripts\python.exe" "scripts\dump_claude_context.py" --copy
echo.
pause
