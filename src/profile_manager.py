# Chức năng: Quản lý thư mục Profile Chrome độc lập cho từng Proxy/Worker.
# Lý do tạo: Giữ session, cookie và bộ nhớ cache riêng biệt giúp YouTube coi mỗi worker là 1 người dùng quay lại thay vì thiết bị lạ mới tinh.
# Trích dẫn: Lưu trữ profile trong thư mục temp/profiles.

import os
import hashlib
import shutil
from typing import Optional
from src.config import TEMP_DIR

PROFILES_DIR = os.path.join(TEMP_DIR, "profiles")
if not os.path.exists(PROFILES_DIR):
    os.makedirs(PROFILES_DIR, exist_ok=True)


def get_profile_dir_for_proxy(proxy_str: Optional[str], worker_id: int = 0) -> str:
    """
    Tạo hoặc trả về đường dẫn User Data Dir độc lập cho từng worker_id,
    kết hợp với băm địa chỉ proxy (nếu có) để đảm bảo 100% không bị xung đột khóa (profile lock).
    """
    if proxy_str and proxy_str.strip():
        h = hashlib.md5(proxy_str.strip().encode("utf-8")).hexdigest()[:8]
        folder_name = f"profile_w{worker_id}_p{h}"
    else:
        folder_name = f"profile_w{worker_id}"

    profile_path = os.path.join(PROFILES_DIR, folder_name)
    if not os.path.exists(profile_path):
        os.makedirs(profile_path, exist_ok=True)
    return profile_path


def cleanup_all_profiles() -> int:
    """Xóa tất cả các profile tạm thời khi người dùng muốn reset hoàn toàn."""
    count = 0
    if os.path.exists(PROFILES_DIR):
        for item in os.listdir(PROFILES_DIR):
            item_path = os.path.join(PROFILES_DIR, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                    count += 1
            except Exception:
                pass
    return count
