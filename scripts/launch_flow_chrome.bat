@echo off
title Khoi chay Chrome cho Google Flow
cd /d "%~dp0\.."
echo ============================================================
echo   KHOI CHAY GOOGLE CHROME DEBUGGING (PORT 9222)
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

:: Kiem tra xem Chrome co dang chay khong
tasklist /FI "IMAGENAME eq chrome.exe" 2>NUL | find /I /N "chrome.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [CANH BAO] Google Chrome hien dang mo.
    echo Chromium chi mo cong 9222 khi khoi dong sach tu dau.
    echo.
    set /p restart="Ban co muon dong toan bo Chrome cu de mo lai voi cong 9222 khong? (Y/N, mac dinh Y): "
    if /i "!restart!"=="N" (
        echo Giu nguyen Chrome hien tai...
    ) else (
        echo Dang tat Chrome cu...
        taskkill /F /IM chrome.exe >nul 2>&1
        timeout /t 2 >nul
    )
)

echo [*] Dang khoi chay Chrome voi cong CDP 9222...
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://flow.google.com"

echo.
echo [OK] Chrome da duoc kich hoat! Hay dang nhap tai khoan va mo flow.google.com tren Chrome.
echo.
pause
