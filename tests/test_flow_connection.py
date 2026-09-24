# Chức năng: Chẩn đoán và kiểm tra toàn diện kết nối Google Flow, Chrome CDP, Profile và Mascot.
# Lý do tạo: Giúp người dùng xác minh nhanh chóng hệ thống Google Flow trước khi chạy sản xuất video thật.
# Trích dẫn: Tuân thủ quy tắc verification của dự án.

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_diagnostics():
    print("=" * 60)
    print("  🔍 KIỂM TRA CHẨN ĐOÁN KẾT NỐI GOOGLE FLOW (G-FLOW)")
    print("=" * 60)

    # 1. Kiểm tra cấu hình
    cfg_file = ROOT / "flow_config.json"
    if not cfg_file.exists():
        print("❌ [FAIL] Không tìm thấy flow_config.json")
        return False
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    print(f"✅ [PASS] flow_config.json hợp lệ.")
    print(f"   - Tool URL: {cfg.get('tool_url')[:60]}...")
    print(f"   - Profile: {cfg.get('profile_directory')} ({cfg.get('user_email')})")
    print(f"   - Cổng CDP: {cfg.get('cdp_port')}")

    # 2. Kiểm tra Mascot Reference
    mascot_rel = cfg.get("mascot_reference_path", "assets/characters/channel-mascot/reference-v1.png")
    mascot_file = ROOT / mascot_rel
    if not mascot_file.exists():
        print(f"❌ [FAIL] Không tìm thấy ảnh mascot tại: {mascot_file}")
        return False
    print(f"✅ [PASS] Ảnh mascot Stickman sẵn sàng ({mascot_file.stat().st_size} bytes).")

    # 3. Kiểm tra Chrome Profile Default
    user_data = Path(cfg.get("chrome_user_data_dir", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")))
    profile_dir = user_data / cfg.get("profile_directory", "Default")
    if not profile_dir.exists():
        print(f"⚠️ [WARNING] Không tìm thấy thư mục profile Chrome: {profile_dir}")
    else:
        print(f"✅ [PASS] Thư mục Chrome Profile Default tồn tại.")

    # 4. Kiểm tra Playwright Python
    try:
        import playwright
        print(f"✅ [PASS] Thư viện Playwright đã được cài đặt.")
    except ImportError:
        print("❌ [FAIL] Chưa cài đặt thư viện playwright. Hãy chạy: pip install playwright")
        return False

    # 5. Kiểm tra kết nối cổng CDP 9222
    from src.flow_browser_service import is_cdp_available
    cdp_port = cfg.get("cdp_port", 9222)
    if is_cdp_available(cdp_port):
        print(f"✅ [PASS] Cổng Chrome CDP {cdp_port} ĐANG HOẠT ĐỘNG.")
    else:
        print(f"ℹ️ [INFO] Cổng Chrome CDP {cdp_port} hiện chưa mở.")
        print(f"   👉 Bạn có thể click đúp file 'launch_flow_chrome.bat' để mở Chrome kết nối Google Flow.")

    print("\n" + "=" * 60)
    print("  🎉 CHẨN ĐOÁN HOÀN TẤT: Cấu trúc hệ thống Google Flow đã sẵn sàng!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    run_diagnostics()
