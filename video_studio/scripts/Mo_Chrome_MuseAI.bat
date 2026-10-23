@echo off
title Mo Chrome MuseAI + Google Flow (Hybrid 3D Pipeline)
cd /d "%~dp0\.."

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

echo ==============================================================================
echo [*] Khoi dong Chrome CDP cong 9222 de dieu khien MuseAI + Google Flow...
echo [*] Profile: flow_chrome_profile
echo [*] Tab 1: MuseAI (https://muse.ai/) - Viet kich ban cot truyen 3D
echo [*] Tab 2: Google Flow (https://flow.google.com/) - Sinh video 3D Veo
echo ==============================================================================
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%~dp0flow_chrome_profile" --profile-directory="Default" --remote-allow-origins=* --no-first-run --no-default-browser-check "https://muse.ai/" "https://flow.google.com/" "http://localhost:8502"

echo [*] Chrome da duoc mo. Ban hay dang nhap MuseAI va Google Flow (neu chua).
echo [*] Dang khoi chay Giao dien Web Video Studio tren cong 8502...
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" -m streamlit run src\app.py --server.port 8502
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run src\app.py --server.port 8502
) else (
    python -m streamlit run src\app.py --server.port 8502
)

pause
