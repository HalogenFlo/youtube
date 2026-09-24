@echo off
title AI Video Producer - Google Flow Auto Batch
cd /d "%~dp0"

echo ============================================================
echo   AI VIDEO PRODUCER - GOOGLE FLOW AUTO PIPELINE
echo ============================================================
echo.

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

echo [*] Dang khoi dong Chrome voi tai khoan Google np368057@gmail.com tren cong 9222...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --remote-allow-origins=* --restore-last-session "https://flow.google.com"

echo.
echo [*] Dang khoi chay Giao dien Web tren cong 8502...
echo     Trinh duyet se tu dong mo http://localhost:8502
echo.

start http://localhost:8502
streamlit run src\app.py --server.port 8502

pause
