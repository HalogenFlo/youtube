# Chức năng: Tự động kiểm tra và khởi động Google Chrome với cổng CDP 9222 hoàn toàn tự động.

import os
import sys
import time
import subprocess
import urllib.request
import json
from pathlib import Path

# UTF-8 cho Windows console
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PORT = 9222

def is_port_ready() -> bool:
    try:
        url = f"http://127.0.0.1:{PORT}/json/version"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

def find_chrome_path() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""

def main():
    print("[*] Kiểm tra kết nối Chrome Google Flow (Cổng CDP 9222)...")
    if is_port_ready():
        print("[OK] Chrome Google Flow (Port 9222) đã sẵn sàng hoạt động!")
        return 0

    chrome_bin = find_chrome_path()
    if not chrome_bin:
        print("[!] Không tìm thấy Google Chrome trong hệ thống.")
        return 1

    user_data = str(Path(__file__).resolve().parent.parent / "flow_chrome_profile")
    profile = "Default"

    # Kiểm tra xem Chrome có đang chạy không
    try:
        chk = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True)
        if "chrome.exe" in chk.stdout.lower():
            print("[*] Đang đóng Chrome cũ để mở lại với cổng 9222...")
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
    except Exception:
        pass

    print("[*] Đang khởi chạy Chrome với cổng 9222...")
    cmd = [
        chrome_bin,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={user_data}",
        f"--profile-directory={profile}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "https://flow.google.com"
    ]

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for i in range(15):
            time.sleep(0.5)
            if is_port_ready():
                print(f"[OK] Google Chrome đã kích hoạt thành công trên cổng {PORT}!")
                return 0
    except Exception as e:
        print(f"[ERROR] Lỗi khởi động Chrome: {e}")
        return 1

    print("[!] Chrome đã được mở nhưng chưa kịp phản hồi cổng 9222. Vẫn tiếp tục quy trình.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
