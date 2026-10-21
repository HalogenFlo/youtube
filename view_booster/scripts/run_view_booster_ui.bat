@echo off
title YouTube View Booster - Web UI
cd /d "%~dp0\.."
echo [*] Dang khoi chay View Booster Web UI tren cong 8501...
streamlit run src/app_view_booster.py --server.port 8501
pause
