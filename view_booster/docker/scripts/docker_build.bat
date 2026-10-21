@echo off
chcp 65001 > nul
title Build YouTube Booster Docker Image
echo ==========================================================
echo   🐳 ĐANG TIẾN HÀNH BUILD DOCKER IMAGE CHO YOUTUBE BOOSTER...
echo ==========================================================
echo.

docker compose build

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==========================================================
    echo   ✅ BUILD DOCKER IMAGE THÀNH CÔNG!
    echo   Bạn có thể xuất image ra file .tar bằng lệnh:
    echo   docker save -o yt-booster-image.tar yt-booster-ui:latest
    echo ==========================================================
) else (
    echo.
    echo ❌ Lỗi trong quá trình build Docker. Hãy đảm bảo Docker Desktop đang chạy.
)

pause
