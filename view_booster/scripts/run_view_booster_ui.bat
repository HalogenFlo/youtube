@echo off
title YouTube View Booster - Web UI
cd /d "%~dp0\.."

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"

echo [*] Dang khoi chay View Booster Web UI tren cong 8501...
start http://localhost:8501
"%PYTHON_EXE%" -m streamlit run src/app_view_booster.py --server.port 8501
pause
