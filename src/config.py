# Chức năng: Lưu trữ toàn bộ các hằng số, cấu hình đường dẫn và các model AI của hệ thống.
# Lý do tạo: Tách biệt cấu hình khỏi logic nghiệp vụ để dễ bảo trì và mở rộng.
# Trích dẫn: Dựa trên sơ đồ kiến trúc và cấu trúc thư mục trong PLAN.md.

import os
import torch

# --- ĐƯỜNG DẪN THƯ MỤC ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMP_DIR = os.path.join(BASE_DIR, "temp")
DOWNLOAD_DIR = os.path.join(TEMP_DIR, "downloads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONT_DIR = os.path.join(ASSETS_DIR, "fonts")

# Đường dẫn font mặc định cho phụ đề
FONT_PATH = os.path.join(FONT_DIR, "Montserrat-Bold.ttf")

# Tự động tạo các thư mục nếu chưa tồn tại
for directory in [TEMP_DIR, DOWNLOAD_DIR, OUTPUT_DIR, ASSETS_DIR, FONT_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# --- CẤU HÌNH DUBBING (LỒNG TIẾNG) ---
DUBBING_DIR = os.path.join(TEMP_DIR, "dubbing")
DUBBING_UPLOAD_DIR = os.path.join(DUBBING_DIR, "uploads")
for directory in [DUBBING_DIR, DUBBING_UPLOAD_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

DUBBING_BG_VOLUME_LOW = 0.12


# --- CẤU HÌNH CÁC MODEL AI ---
# Ollama Configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL_DEFAULT = "qwen2.5:14b"

# TTS Configuration (edge-tts)
TTS_VOICES_VI = {
    "Nữ (vi-VN-HoaiMyNeural)": "vi-VN-HoaiMyNeural",
    "Nam (vi-VN-NamMinhNeural)": "vi-VN-NamMinhNeural"
}
TTS_VOICES_EN = {
    "Nữ Mỹ (en-US-EmmaNeural)": "en-US-EmmaNeural",
    "Nam Mỹ (en-US-BrianNeural)": "en-US-BrianNeural",
    "Nữ Anh (en-GB-SoniaNeural)": "en-GB-SoniaNeural",
    "Nam Anh (en-GB-RyanNeural)": "en-GB-RyanNeural"
}
TTS_VOICE_DEFAULT = "vi-VN-HoaiMyNeural"

# Whisper Configuration
WHISPER_MODEL_DEFAULT = "small"
WHISPER_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

# Image Generation (Stable Diffusion 1.5)
SD_MODEL_DEFAULT = "Lykon/dreamshaper-8"
SD_RESOLUTIONS = {
    "vertical": (512, 768),   # width, height
    "horizontal": (768, 512)
}

# Video Generation (Wan 2.1 1.3B)
WAN_MODEL_DEFAULT = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
WAN_RESOLUTIONS = {
    "vertical": (480, 848),   # width, height
    "horizontal": (848, 480)
}
WAN_DEFAULT_FRAMES = 81       # 81 frames tương đương ~5 giây ở 16fps
WAN_DEFAULT_STEPS = 50        # Số bước lập mặc định để sinh video

def get_gpu_benchmark_sec_per_step() -> float:
    """
    Xác định hiệu năng GPU hiện tại để ước lượng thời gian sinh video bằng Wan 2.1.
    Trả về số giây trên mỗi inference step (sec/step).
    """
    if not torch.cuda.is_available():
        return 100.0
    
    try:
        gpu_name = torch.cuda.get_device_name(0).upper()
        
        # RTX 4090, A100, H100
        if any(x in gpu_name for x in ["4090", "A100", "H100", "A800", "H800"]):
            return 1.5
        # RTX 3090, 4080
        if any(x in gpu_name for x in ["3090", "4080"]):
            return 3.0
        # RTX 3080, 4070
        if any(x in gpu_name for x in ["3080", "4070"]):
            return 5.0
        # RTX 3060, 4060, A10, A30, A40
        if any(x in gpu_name for x in ["3060", "4060", "A10", "A30"]):
            return 9.5
        # RTX 1660, 2060, T4, P100
        if any(x in gpu_name for x in ["1660", "2060", "2070", "2080", "T4"]):
            return 14.0
            
        # Các GPU khác mặc định
        return 10.0
    except Exception:
        return 10.0


# --- CẤU HÌNH VIDEO & BIÊN TẬP ---
DEFAULT_MAX_DURATION = 60      # Thời lượng tối đa 1 video phần (giây)
DEFAULT_IMAGE_STYLE = "cinematic, detailed, 4k"
DEFAULT_FPS = 30               # FPS chuẩn hóa khi render video cuối cùng
WAN_FPS = 16                   # FPS mặc định khi sinh clip Wan 2.1

# --- CẤU HÌNH SELF-HEAL ---
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
if not os.path.exists(MUSIC_DIR):
    os.makedirs(MUSIC_DIR)

BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
if not os.path.exists(BACKGROUNDS_DIR):
    os.makedirs(BACKGROUNDS_DIR)


DEFAULT_READING_WPM = 130
DEFAULT_MUSIC_VOLUME = 1.0
DEFAULT_MUSIC_VOLUME_WITH_VOICE = 0.25
DEFAULT_MUSIC_VOLUME_SILENT_SPEAKER = 0.6
DEFAULT_SELFHEAL_STYLE = "peaceful nature landscape, serene forest river, soft morning light, cinematic, 4k"
DEFAULT_SELFHEAL_RATE = "-15%"
DEFAULT_PAUSE_BEFORE_SILENT = 1.0  # Khoảng dừng (giây) trước lượt speaker không có giọng

# Liên từ tiếng Việt để tách câu dịch
VI_SPLIT_CONJUNCTIONS = ["và", "nhưng", "để", "rồi", "mà", "khi", "nếu", "vì", "nên", "hay"]

# Bảng màu cho các speaker (ASS color format BGR)
SPEAKER_COLORS = [
    "&H0000FFFF",  # Vàng neon
    "&H0000FF00",  # Xanh lá
    "&H00FF9933",  # Xanh dương nhạt
    "&H005050FF",  # Đỏ cam
    "&H00FF00FF",  # Hồng
    "&H0033CCFF",  # Cam
]

# --- CẤU HÌNH EDUCATIONAL (BÀI DẠY AI SLIDESHOW) ---
DEFAULT_EDUCATIONAL_STYLE = "modern tech illustration, flat design, clean UI, soft gradient background, 4k"
DEFAULT_EDUCATIONAL_SCENES = 8


