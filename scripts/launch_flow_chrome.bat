@echo off
title Khoi chay Chrome cho Google Flow
cd /d "%~dp0\.."
echo ============================================================
echo   KHỞI CHẠY GOOGLE CHROME DEBUGGING (PORT 9222)
echo   Profile: Default (np368057@gmail.com)
echo ============================================================
echo.

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_EXE%" (
    echo [ERROR] Khong tim thay Chrome tren may!
    pause
    exit /b 1
)

echo [*] Dang khoi chay Chrome voi cong CDP 9222...
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://flow.google.com"

echo.
echo [OK] Chrome da duoc kich hoat! Hay kiem tra trang Google Flow tren Chrome.
echo.
pause
