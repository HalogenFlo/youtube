@echo off
chcp 65001 >nul
title YouTube View & Shorts Booster Launcher
cd /d "%~dp0"

:menu
cls
echo =====================================================================
echo           YOUTUBE VIEW ^& SHORTS BOOSTER - CONTROLLER MENU
echo =====================================================================
echo.
echo   [1] Khoi chay Web UI Dashboard (Streamlit - Port 8501)
echo   [2] Khoi chay CLI Chay Ngam 24/7 (booster_config.json)
echo   [3] Chay Unit Tests kiem tra he thong
echo   [4] Don dep du lieu tam va profiles
echo   [0] Thoat
echo.
echo =====================================================================
set /p choice="Nhap lua chon cua ban (0-4): "

if "%choice%"=="1" goto ui
if "%choice%"=="2" goto cli
if "%choice%"=="3" goto test
if "%choice%"=="4" goto clean
if "%choice%"=="0" exit /b
goto menu

:ui
echo [*] Dang khoi chay Streamlit Web UI...
call scripts\run_view_booster_ui.bat
goto menu

:cli
echo [*] Dang khoi chay CLI Booster 24/7...
call scripts\run_view_booster_headless.bat
goto menu

:test
echo [*] Dang chay pytest...
pytest tests\test_booster.py
pause
goto menu

:clean
echo [*] Dang don dep temp profiles va log cu...
if exist temp\profiles rmdir /s /q temp\profiles
if exist output\booster.log.1 del /f /q output\booster.log.1
echo [OK] Don dep hoan tat!
pause
goto menu
