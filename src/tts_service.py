# Chức năng: Gọi CLI edge-tts qua subprocess để sinh giọng đọc tiếng Việt chất lượng cao.
# Lý do tạo: Tránh các lỗi encoding websocket và xung đột asyncio event loop trong môi trường Streamlit.
# Trích dẫn: Sử dụng CLI chính thức của thư viện edge-tts với file tạm UTF-8 và cơ chế voice fallback.

import os
import re
import sys
import tempfile
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

# Bản đồ giọng đọc dự phòng khi giọng chính gặp lỗi NoAudioReceived hoặc nghẽn mạng
VOICE_FALLBACK_MAP = {
    "vi-VN-HoaiMyNeural": "vi-VN-NamMinhNeural",
    "vi-VN-NamMinhNeural": "vi-VN-HoaiMyNeural",
    "en-US-EmmaNeural": "en-US-JennyNeural",
    "en-US-JennyNeural": "en-US-GuyNeural",
    "en-US-GuyNeural": "en-US-JennyNeural",
}


def sanitize_tts_text(text: str) -> str:
    """
    Làm sạch văn bản kịch bản trước khi đưa vào TTS:
    - Loại bỏ các thẻ chỉ dẫn đạo diễn trong ngoặc: [nhạc nền...], (tiếng thở dài...)
    - Loại bỏ các ký hiệu markdown: **, *, #, __, `
    - Chuẩn hóa khoảng trắng và dấu câu
    """
    if not text:
        return ""
    
    clean = str(text)
    
    # 1. Loại bỏ các chỉ dẫn kịch bản trong ngoặc vuông [âm thanh], [nhạc nền], [SFX]
    clean = re.sub(r'\[.*?\]', ' ', clean)
    
    # 2. Loại bỏ các chỉ dẫn trong ngoặc đơn nếu có dạng gợi ý đạo diễn (ví dụ: (cười), (thì thầm), (giọng trầm))
    clean = re.sub(r'\((?:cười|khóc|thì thầm|giọng trầm|tiếng cười|tiếng nói|nhạc|thở dài|ngạc nhiên|pause|dừng|im lặng).*?\)', ' ', clean, flags=re.IGNORECASE)
    
    # 3. Loại bỏ ký tự markdown
    clean = re.sub(r'[*#_`~]', '', clean)
    
    # 4. Loại bỏ các URL nếu có
    clean = re.sub(r'https?://\S+', '', clean)
    
    # 5. Chuẩn hóa khoảng trắng
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Nếu sau khi lọc mà văn bản bị rỗng hoặc không còn chữ nào, giữ lại văn bản gốc đã gọt bỏ ký tự đặc biệt
    if not clean or not re.search(r'[\w\d]', clean, flags=re.UNICODE):
        clean = re.sub(r'[[\](){}*#_`~]', '', str(text)).strip()
        
    return clean


def _run_edge_tts_cli(text: str, output_path: str, voice: str, rate: str) -> Tuple[bool, str]:
    """
    Thực thi edge-tts qua subprocess sử dụng file text tạm UTF-8 (--file).
    Cách này chống 100% lỗi escape ký tự đặc biệt và command-line limits trên Windows.
    """
    # Đảm bảo thư mục cha tồn tại
    parent_dir = os.path.dirname(output_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    # Định dạng tốc độ đọc phù hợp với tham số --rate của CLI edge-tts (+0%, +10%, -5%)
    formatted_rate = rate
    if not (rate.startswith('+') or rate.startswith('-')):
        formatted_rate = f"+{rate}"

    # Tạo file text tạm lưu nội dung UTF-8 an toàn tuyệt đối
    tmp_txt_fd, tmp_txt_path = tempfile.mkstemp(prefix="tts_input_", suffix=".txt", dir=parent_dir)
    try:
        with open(tmp_txt_fd, "w", encoding="utf-8") as f:
            f.write(text)

        # Cấu trúc câu lệnh CLI sử dụng chính Python interpreter của môi trường ảo
        cmd = [
            sys.executable,
            "-m", "edge_tts",
            "--voice", voice,
            "--file", tmp_txt_path,
            "--rate", formatted_rate,
            "--write-media", output_path
        ]

        # Cấu hình ẩn cửa sổ console đen khi chạy subprocess trên Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            timeout=40  # Timeout 40s cho mỗi lần gọi
        )

        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path
        else:
            err = result.stderr or result.stdout or "Không nhận được phản hồi âm thanh từ edge-tts."
            # Dọn dẹp file 0-byte nếu có
            if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            return False, err.strip()

    except Exception as e:
        if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False, str(e)
    finally:
        # Xóa file text tạm
        if os.path.exists(tmp_txt_path):
            try:
                os.remove(tmp_txt_path)
            except Exception:
                pass


def generate_tts(
    text: str, 
    output_path: str, 
    voice: str = TTS_VOICE_DEFAULT, 
    rate: str = "+0%"
) -> Tuple[bool, str]:
    """
    Sinh file audio giọng đọc từ văn bản sử dụng CLI edge-tts với cơ chế:
    1. Làm sạch văn bản kịch bản (loại bỏ markdown, thẻ đạo diễn).
    2. Ghi file UTF-8 tạm và gọi sys.executable -m edge_tts --file.
    3. Thử lại tối đa 3 lần với giọng chính.
    4. Tự động chuyển sang giọng phụ (fallback voice) nếu giọng chính bị NoAudioReceived hoặc lỗi mạng.
    Trả về: (True, output_path) nếu thành công, (False, error_message) nếu thất bại.
    """
    clean_text = sanitize_tts_text(text)
    if not clean_text or not clean_text.strip():
        return False, "Văn bản trống hoặc chỉ chứa ký hiệu, không thể sinh giọng đọc."

    voices_to_try = [voice]
    # Xác định giọng dự phòng nếu có
    alt_voice = VOICE_FALLBACK_MAP.get(voice)
    if not alt_voice:
        if "vi-VN" in voice:
            alt_voice = "vi-VN-NamMinhNeural" if "HoaiMy" in voice else "vi-VN-HoaiMyNeural"
        elif "en-US" in voice:
            alt_voice = "en-US-JennyNeural" if "Emma" in voice else "en-US-GuyNeural"
    if alt_voice and alt_voice not in voices_to_try:
        voices_to_try.append(alt_voice)

    last_err = ""
    for v_idx, current_voice in enumerate(voices_to_try):
        max_attempts = 2 if len(voices_to_try) > 1 else 3
        for attempt in range(max_attempts):
            success, result_or_err = _run_edge_tts_cli(
                text=clean_text,
                output_path=output_path,
                voice=current_voice,
                rate=rate
            )
            if success:
                if v_idx > 0:
                    try:
                        print(f"[TTS] Đã tự động phục hồi thành công bằng giọng dự phòng: {current_voice}")
                    except Exception:
                        pass
                return True, output_path
            
            last_err = result_or_err
            try:
                print(f"[TTS] Lần thử {attempt + 1}/{max_attempts} với giọng '{current_voice}' thất bại: {last_err}")
            except Exception:
                pass
            time.sleep(1.0)

        if v_idx < len(voices_to_try) - 1:
            try:
                print(f"[TTS] Giọng '{current_voice}' không phản hồi, tự động chuyển sang giọng dự phòng '{voices_to_try[v_idx + 1]}'...")
            except Exception:
                pass

    return False, f"Lỗi sinh giọng đọc edge-tts CLI: {last_err}"
