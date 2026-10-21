@echo off
chcp 65001 > nul
title Run YouTube Booster UI via Docker
echo ==========================================================
echo   🐳 ĐANG KHỞI CHẠY GIAO DIỆN WEB UI QUA DOCKER CONTAINER...
echo   Địa chỉ truy cập: http://localhost:8501
echo ==========================================================
echo.

docker compose up booster-ui
pause
