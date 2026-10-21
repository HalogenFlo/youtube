# Chức năng: Cấu hình thư mục cơ sở và đường dẫn cho dự án YouTube View Booster.
# Lý do tạo: Tách biệt độc lập cấu hình môi trường giữa View Booster và Video Studio.

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = str(BASE_DIR / "temp")
OUTPUT_DIR = str(BASE_DIR / "output")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
