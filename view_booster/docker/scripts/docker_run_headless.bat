@echo off
chcp 65001 > nul
title Run YouTube Booster Headless 24/7 via Docker
echo ==========================================================
echo   🐳 ĐANG CHẠY NỀN TOOL CÀY VIEW YOUTUBE 24/7 QUA DOCKER...
echo   Cấu hình: booster_config.json
echo   Xem log trực tiếp: docker compose logs -f booster-cli
echo ==========================================================
echo.

docker compose up -d booster-cli
echo Container dang chay ngam. De xem log hay go: docker compose logs -f booster-cli
pause
