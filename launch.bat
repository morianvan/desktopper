@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
