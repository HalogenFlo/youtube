# Chức năng: Gọi CLI edge-tts qua subprocess để sinh giọng đọc tiếng Việt chất lượng cao.
# Lý do tạo: Tránh các lỗi encoding websocket và xung đột asyncio event loop trong môi trường Streamlit.
# Trích dẫn: Sử dụng CLI chính thức của thư viện edge-tts.

import os
import sys
import subprocess
import time
from typing import Tuple
from src.config import TTS_VOICE_DEFAULT

# Đảm bảo in log trên Windows không bị UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def generate_tts(
    text: str, 
    output_path: str, 
    voice: str = TTS_VOICE_DEFAULT, 
    rate: str = "+0%"
) -> Tuple[bool, str]:
    """
    Sinh file audio giọng đọc từ văn bản sử dụng CLI edge-tts qua subprocess.
    Trả về: (True, output_path) nếu thành công, (False, error_message) nếu thất bại.
    """
    if not text or not str(text).strip():
        return False, "Văn bản trống, không thể sinh giọng đọc."
    text = str(text)

        
    # Đảm bảo thư mục cha tồn tại
    parent_dir = os.path.dirname(output_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    # Định dạng tốc độ đọc phù hợp với tham số --rate của CLI edge-tts (+0%, +10%, -5%)
    formatted_rate = rate
    if not (rate.startswith('+') or rate.startswith('-')):
        formatted_rate = f"+{rate}"

    # Cấu trúc câu lệnh CLI
    cmd = [
        "edge-tts",
        "--voice", voice,
        "--text", text,
        "--rate", formatted_rate,
        "--write-media", output_path
    ]

    # Cấu hình ẩn cửa sổ console đen khi chạy subprocess trên Windows
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    max_retries = 3
    last_err = ""
    
    for attempt in range(max_retries):
        try:
            # Chạy câu lệnh CLI edge-tts
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8", # Ép mã hóa UTF-8 để hỗ trợ tiếng Việt có dấu
                startupinfo=startupinfo,
                timeout=30 # Tránh treo tiến trình nếu mạng bị nghẽn
            )
            
            # Kiểm tra kết quả thực thi lệnh và sự tồn tại của file đầu ra
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True, output_path
            else:
                last_err = result.stderr or "Khong nhan duoc phan hoi am thanh tu API."
                try:
                    print(f"[TTS] Lan thu {attempt + 1}/{max_retries} that bai: {last_err.strip()}")
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    time.sleep(1.5)
                    
        except Exception as e:
            last_err = str(e)
            try:
                print(f"[TTS] Lan thu {attempt + 1}/{max_retries} gap loi: {last_err}")
            except Exception:
                pass
            if attempt < max_retries - 1:
                time.sleep(1.5)

    return False, f"Lỗi sinh giọng đọc edge-tts CLI: {last_err.strip()}"
