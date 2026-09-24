@echo off
title AI Video Producer - Web UI
cd /d "%~dp0"

echo ============================================================
echo   AI VIDEO PRODUCER - WEB UI (PORT 8502)
echo ============================================================
echo.

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://flow.google.com"

start http://localhost:8502
streamlit run src\app.py --server.port 8502

pause
