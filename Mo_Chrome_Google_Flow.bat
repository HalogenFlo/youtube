@echo off
title Mo Chrome Google Flow (Tu dong hoa)
cd /d "%~dp0"

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

echo [*] Dang khoi dong Chrome voi che do dieu khien tu dong tren cong 9222...
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%~dp0flow_chrome_profile" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://flow.google.com/project/4763b8d1-5c45-4532-85b9-960a80cefcb4/tool/a1dc8db6-3417-4d6b-a00a-50832cb508e1?mode=APP" "http://localhost:8502"

echo [*] Dang khoi chay Giao dien Web tren cong 8502...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run src\app.py --server.port 8502
) else (
    python -m streamlit run src\app.py --server.port 8502
)

pause
