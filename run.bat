@echo off
title AI Video Producer - Google Flow Auto Batch
cd /d "%~dp0"

echo ============================================================
echo   AI VIDEO PRODUCER - GOOGLE FLOW AUTO BATCH
echo ============================================================
echo.

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

echo [*] Dang tu dong mo Chrome Google Flow tren cong 9222...
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://flow.google.com"

echo.
echo [*] Dang khoi dong Web UI tao video tu dong tren cong 8502...
echo     Trinh duyet se tu dong mo http://localhost:8502
echo.

start http://localhost:8502
streamlit run src\app.py --server.port 8502

pause
