@echo off
setlocal EnableDelayedExpansion
title YouTube Automation and AI Video Suite
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo   YOUTUBE AUTOMATION AND AI VIDEO PRODUCTION SUITE
echo ============================================================
echo.
echo   [1] Khoi chay AI Video Producer (Streamlit Web UI - Port 8502)
echo   [2] Khoi chay YouTube View Booster (Streamlit Web UI - Port 8501)
echo   [3] Khoi chay YouTube View Booster (CLI Chay ngam 24/7)
echo   [4] Mo Chrome Debugging CDP cho Google Flow (Port 9222)
echo   [5] Chay kiem tra chan doan he thong (Tests)
echo   [6] Don dep file rac & cache he thong (Clean Temp & Logs)
echo   [7] Thoat
echo.
echo ============================================================
set /p opt="Nhap lua chon cua ban (1-7): "

if "%opt%"=="1" goto opt1
if "%opt%"=="2" goto opt2
if "%opt%"=="3" goto opt3
if "%opt%"=="4" goto opt4
if "%opt%"=="5" goto opt5
if "%opt%"=="6" goto opt6
if "%opt%"=="7" goto opt7
goto menu

:opt1
echo.
echo [*] Dang khoi chay AI Video Producer tren cong 8502...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run src\app.py --server.port 8502
) else (
    streamlit run src/app.py --server.port 8502
)
pause
goto menu

:opt2
echo.
echo [*] Dang khoi chay YouTube View Booster UI tren cong 8501...
call scripts\run_view_booster_ui.bat
goto menu

:opt3
echo.
echo [*] Dang khoi chay YouTube View Booster CLI...
call scripts\run_view_booster_headless.bat
goto menu

:opt4
echo.
echo [*] Dang mo Chrome Debugging cho Google Flow...
call scripts\launch_flow_chrome.bat
goto menu

:opt5
echo.
echo [*] Dang chay kiem tra he thong...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m unittest discover -s tests -v
) else (
    python -m unittest discover -s tests -v
)
pause
goto menu

:opt6
echo.
echo [*] Dang don dep file rac, log va cache...
powershell -Command "Remove-Item -Path 'chrome_test.log' -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path 'scratch' -Recurse | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue; Remove-Item -Path 'output\booster.log.1', 'output\booster.log.2' -Force -ErrorAction SilentlyContinue; Remove-Item -Path 'temp\*.png', 'temp\*.mp3', 'temp\*.mp4', 'temp\*.ass', 'temp\*.log' -Force -ErrorAction SilentlyContinue; Remove-Item -Path 'temp\test_audio_verify', 'temp\test_no_fallback', 'temp\flow_attempts' -Recurse -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path . -Include '__pycache__', '.pytest_cache' -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
echo [OK] Da don dep xong file rac va cache!
pause
goto menu

:opt7
exit /b 0
