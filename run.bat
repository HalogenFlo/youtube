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
echo   [5] Tu Dong Tao Hang Loat Video tu Prompt (CLI Auto Batch Loop)
echo   [6] Chay kiem tra chan doan he thong (Tests)
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
streamlit run src/app.py --server.port 8502
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
echo [*] Dang khoi chay Auto Batch Video Producer tu Prompt...
python scripts\batch_video_producer.py
pause
goto menu

:opt6
echo.
echo [*] Dang chay kiem tra he thong...
python -m unittest discover -s tests -v
python tests\test_flow_connection.py
pause
goto menu

:opt7
exit /b 0
