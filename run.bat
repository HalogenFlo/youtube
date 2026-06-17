:: Chức năng: Tự động cài đặt thư viện phụ thuộc và khởi chạy ứng dụng Streamlit Web UI.
:: Lý do tạo: Tiện ích khởi chạy nhanh cho người dùng trên hệ điều hành Windows.
:: Trích dẫn: Tuân thủ quy định khởi chạy trong PLAN.md.

@echo off
title AI Video Producer Launcher
echo ============================================================
echo   KHOI CHAY HE THONG AUTOMATED AI VIDEO PRODUCTION PIPELINE
echo ============================================================

:: Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python chua duoc cai dat hoac chua duoc them vao PATH.
    echo Vui long tai va cai dat Python 3.10+ tu python.org truoc.
    pause
    exit /b 1
)

:: Kiem tra FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg chua duoc cai dat hoac chua duoc them vao PATH.
    echo He thong van se khoi chay, nhung khau tach audio va burn phu de se gap loi.
    echo Vui long tai FFmpeg va them vao bien moi truong PATH.
    echo ------------------------------------------------------------
)

echo [1/2] Dang kiem tra va cai dat cac thu vien phu thuoc (requirements.txt)...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Co loi xay ra khi cai dat thu vien. Vui long kiem tra ket noi mang.
)

echo [2/2] Dang khoi chay giao dien Streamlit Web UI...
streamlit run src/app.py

pause
