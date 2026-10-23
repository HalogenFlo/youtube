@echo off
chcp 65001 >nul
title AI Video Studio Launcher
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"

:menu
cls
echo =====================================================================
echo                AI VIDEO STUDIO - CONTROLLER MENU
echo =====================================================================
echo.
echo   [1] Khoi chay AI Video Producer (Streamlit Web UI - Port 8502)
echo   [2] Khoi chay Google Chrome CDP 9222 (Ket noi Google Flow)
echo   [3] Chay Batch Producer (Che do tao video hang loat)
echo   [4] Chay Autonomous Factory (Tu dong hoa 24/7)
echo   [5] Chay Unit Tests kiem tra he thong
echo   [6] Don dep du lieu tam (temp files)
echo   [0] Thoat
echo.
echo =====================================================================
set "choice="
set /p choice="Nhap lua chon cua ban (0-6): "

if "%choice%"=="1" goto web
if "%choice%"=="2" goto chrome
if "%choice%"=="3" goto batch
if "%choice%"=="4" goto factory
if "%choice%"=="5" goto test
if "%choice%"=="6" goto clean
if "%choice%"=="0" exit /b
if "%choice%"=="" exit /b
goto menu

:web
echo [*] Dang khoi chay Video Producer Web UI...
call run_web.bat
goto menu

:chrome
echo [*] Dang mo Chrome CDP tren cong 9222...
call scripts\launch_flow_chrome.bat
goto menu

:batch
echo [*] Dang khoi chay Batch Producer Dashboard tren port 8503...
start http://localhost:8503
"%PYTHON_EXE%" -m streamlit run src\app_batch.py --server.port 8503
goto menu

:factory
echo [*] Dang chay Autonomous Factory...
"%PYTHON_EXE%" src\autonomous_factory.py
pause
goto menu

:test
echo [*] Dang chay pytest...
"%PYTHON_EXE%" -m pytest tests/test_defensive_data_types.py tests/test_flow_engine.py
pause
goto menu

:clean
echo [*] Dang don dep cache va cac file tam...
powershell -Command "Remove-Item -Path 'temp\*.png', 'temp\*.mp3', 'temp\*.mp4', 'temp\*.ass', 'temp\*.log' -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path . -Include '__pycache__', '.pytest_cache' -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
echo [OK] Don dep hoan tat!
pause
goto menu
