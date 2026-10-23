@echo off
title YouTube View Booster - CLI 24/7
cd /d "%~dp0\.."

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"

echo [*] Dang khoi chay View Booster che do CLI chay ngam...
"%PYTHON_EXE%" cli_booster.py
pause
