@echo off
setlocal EnableDelayedExpansion
title AI Video Producer - Google Flow Auto Batch Loop
cd /d "%~dp0"

echo ============================================================
echo   AI VIDEO PRODUCER - GOOGLE FLOW AUTO BATCH PIPELINE
echo ============================================================
echo.

:: 1. TU DONG KICH HOAT CHROME PORT 9222 CHO GOOGLE FLOW (OPT 4 CU)
echo [*] Dang tu dong kiem tra va khoi dong Chrome Google Flow (Cong CDP 9222)...

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=1)" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [OK] Chrome Google Flow (Port 9222) da san sang!
) else (
    echo [*] Cong 9222 chua bat. Dang tu dong khoi dong Chrome voi profile Default...
    tasklist /FI "IMAGENAME eq chrome.exe" 2>NUL | find /I /N "chrome.exe">NUL
    if "%ERRORLEVEL%"=="0" (
        echo [*] Dang giai phong Chrome cu de mo cong 9222...
        taskkill /F /IM chrome.exe >nul 2>&1
        timeout /t 1 >nul
    )
    start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://flow.google.com"
    timeout /t 2 >nul
    echo [OK] Chrome da tu dong kich hoat tai cong 9222!
)

echo.
echo ============================================================
echo   CHON CHE DO KHOI CHAY
echo ============================================================
echo   [1] Giao dien Web (Streamlit UI - Nhap Prompt va Tao Video) [MAC DINH]
echo   [2] Chay truc tiep tren Command Line (CLI Auto Batch)
echo   [3] Thoat
echo ============================================================
set "opt=1"
set /p opt="Nhap lua chon (1-3, mac dinh 1 sau 5 giay): "

if "%opt%"=="2" goto run_cli
if "%opt%"=="3" exit /b 0

:run_ui
echo.
echo [*] Dang khoi chay AI Video Producer tren cong 8502...
start http://localhost:8502
streamlit run src/app.py --server.port 8502
pause
exit /b 0

:run_cli
echo.
echo [*] Dang chay Auto Batch Video Producer CLI...
python scripts\batch_video_producer.py
pause
exit /b 0
