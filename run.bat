@echo off
chcp 65001 >nul
title YouTube Automation Suite - Master Launcher
cd /d "%~dp0"

:menu
cls
echo =====================================================================
echo                YOUTUBE AUTOMATION - MASTER LAUNCHER
echo =====================================================================
echo.
echo   [1] Vao du an: AI Video Studio (San xuat video tu dong)
echo   [2] Vao du an: YouTube View Booster (Cay view ^& Shorts da luong)
echo.
echo   [3] Chay toan bo Unit Tests (Kiem tra ca 2 he thong)
echo   [0] Thoat
echo.
echo =====================================================================
set /p choice="Nhap lua chon cua ban (0-3): "

if "%choice%"=="1" goto video
if "%choice%"=="2" goto booster
if "%choice%"=="3" goto test_all
if "%choice%"=="0" exit /b
goto menu

:video
cd video_studio
call run.bat
cd ..
goto menu

:booster
cd view_booster
call run.bat
cd ..
goto menu

:test_all
echo [*] Dang chay kiem tra Video Studio...
cd video_studio
pytest tests/test_defensive_data_types.py tests/test_flow_engine.py
cd ..
echo.
echo [*] Dang chay kiem tra View Booster...
cd view_booster
pytest tests/test_booster.py
cd ..
echo.
echo [OK] Kiem tra hoan tat!
pause
goto menu
