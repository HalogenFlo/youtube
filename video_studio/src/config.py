# Chức năng: Lưu trữ toàn bộ các hằng số, cấu hình đường dẫn và các model AI của hệ thống.
# Lý do tạo: Tách biệt cấu hình khỏi logic nghiệp vụ để dễ bảo trì và mở rộng.
# Trích dẫn: Dựa trên sơ đồ kiến trúc và cấu trúc thư mục trong PLAN.md.

import os

try:
    import torch
except (ImportError, OSError):
    # Các luồng web/batch không cần PyTorch. Không để bản
    # CUDA/DLL lỗi chặn toàn bộ ứng dụng ngay từ lúc import config.
    torch = None

# --- ĐƯỜNG DẪN THƯ MỤC ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMP_DIR = os.path.join(BASE_DIR, "temp")
DOWNLOAD_DIR = os.path.join(TEMP_DIR, "downloads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONT_DIR = os.path.join(ASSETS_DIR, "fonts")

# Đường dẫn font mặc định cho phụ đề
FONT_PATH = os.path.join(FONT_DIR, "Montserrat-Bold.ttf")

# --- NẠP BIẾN MÔI TRƯỜNG (.ENV) ---
ENV_FILE = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

GMAIL_YTB = os.getenv("gmailytb", "").strip()
PASS_YTB = os.getenv("passytb", "").strip()

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
OLLAMA_MODEL_DEFAULT = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# TTS Configuration (edge-tts)
TTS_VOICES_VI = {
    "🌟 Nữ miền Nam — Hoài My (Kể chuyện truyền cảm, ấm áp)": "vi-VN-HoaiMyNeural|story_warm",
    "🔥 Nam miền Bắc — Nam Minh (Thuyết minh cuốn hút, nhịp nhanh Shorts)": "vi-VN-NamMinhNeural|narrator_dynamic",
    "🔬 Nữ miền Nam — Hoài My (Giải thích khoa học, rõ chữ, năng lượng cao)": "vi-VN-HoaiMyNeural|science_bright",
    "🌙 Nam miền Bắc — Nam Minh (Kể chuyện đêm khuya / Bí ẩn trầm sâu)": "vi-VN-NamMinhNeural|mystery_deep",
    "Nữ (vi-VN-HoaiMyNeural)": "vi-VN-HoaiMyNeural",
    "Nam (vi-VN-NamMinhNeural)": "vi-VN-NamMinhNeural",
}

STORYTELLING_VOICE_PRESETS = {
    "story_warm": {
        "base_voice": "vi-VN-HoaiMyNeural",
        "rate": "+5%",
        "pitch": "-1Hz",
        "eq_filter": "highpass=f=80,equalizer=f=190:width_type=o:width=1.2:g=2.6,equalizer=f=3300:width_type=o:width=1.4:g=2.0,acompressor=threshold=-18dB:ratio=2.4:attack=15:release=180:makeup=1.8",
    },
    "narrator_dynamic": {
        "base_voice": "vi-VN-NamMinhNeural",
        "rate": "+8%",
        "pitch": "-2Hz",
        "eq_filter": "highpass=f=75,equalizer=f=165:width_type=o:width=1.1:g=3.0,equalizer=f=3200:width_type=o:width=1.4:g=2.4,acompressor=threshold=-18dB:ratio=2.6:attack=12:release=160:makeup=2.0",
    },
    "science_bright": {
        "base_voice": "vi-VN-HoaiMyNeural",
        "rate": "+9%",
        "pitch": "+0Hz",
        "eq_filter": "highpass=f=85,equalizer=f=200:width_type=o:width=1.2:g=1.8,equalizer=f=3600:width_type=o:width=1.5:g=2.5,acompressor=threshold=-18dB:ratio=2.4:attack=12:release=150:makeup=1.8",
    },
    "mystery_deep": {
        "base_voice": "vi-VN-NamMinhNeural",
        "rate": "-2%",
        "pitch": "-4Hz",
        "eq_filter": "highpass=f=70,equalizer=f=150:width_type=o:width=1.2:g=3.5,equalizer=f=2900:width_type=o:width=1.3:g=1.6,acompressor=threshold=-19dB:ratio=2.5:attack=18:release=210:makeup=2.0",
    },
    "char_boy_bright": {
        "base_voice": "vi-VN-NamMinhNeural",
        "rate": "+11%",
        "pitch": "+9Hz",
        "eq_filter": "highpass=f=95,equalizer=f=240:width_type=o:width=1.2:g=1.5,equalizer=f=3600:width_type=o:width=1.4:g=2.8,acompressor=threshold=-18dB:ratio=2.5:attack=10:release=140:makeup=2.0",
    },
    "char_elder_deep": {
        "base_voice": "vi-VN-NamMinhNeural",
        "rate": "-6%",
        "pitch": "-9Hz",
        "eq_filter": "highpass=f=65,equalizer=f=135:width_type=o:width=1.2:g=4.0,equalizer=f=2800:width_type=o:width=1.3:g=1.8,acompressor=threshold=-19dB:ratio=2.6:attack=18:release=220:makeup=2.2",
    },
    "char_female_bright": {
        "base_voice": "vi-VN-HoaiMyNeural",
        "rate": "+12%",
        "pitch": "+10Hz",
        "eq_filter": "highpass=f=100,equalizer=f=260:width_type=o:width=1.2:g=1.4,equalizer=f=3800:width_type=o:width=1.4:g=2.6,acompressor=threshold=-18dB:ratio=2.4:attack=10:release=140:makeup=1.9",
    },
}
TTS_VOICES_EN = {
    "Nữ Mỹ (en-US-EmmaNeural)": "en-US-EmmaNeural",
    "Nam Mỹ (en-US-BrianNeural)": "en-US-BrianNeural",
    "Nữ Anh (en-GB-SoniaNeural)": "en-GB-SoniaNeural",
    "Nam Anh (en-GB-RyanNeural)": "en-GB-RyanNeural"
}
TTS_VOICES_ZH = {
    "Nữ Trung Quốc (zh-CN-XiaoxiaoNeural)": "zh-CN-XiaoxiaoNeural",
    "Nam Trung Quốc (zh-CN-YunxiNeural)": "zh-CN-YunxiNeural",
}
TTS_VOICE_DEFAULT = "vi-VN-HoaiMyNeural"
TTS_VOICE_ZH_DEFAULT = "zh-CN-XiaoxiaoNeural"

# Whisper Configuration
WHISPER_MODEL_DEFAULT = "small"
CUDA_AVAILABLE = bool(torch is not None and torch.cuda.is_available())
WHISPER_DEVICE = "cuda" if CUDA_AVAILABLE else "cpu"
WHISPER_COMPUTE_TYPE = "float16" if CUDA_AVAILABLE else "int8"

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
    if not CUDA_AVAILABLE:
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
DEFAULT_IMAGE_STYLE = "2d animation, flat 2d cartoon, colorful cel-shaded vector art"
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

# --- CẤU HÌNH TURBO BATCH PIPELINE (ĐA LUỒNG TĂNG TỐC) ---
TURBO_BATCH_ENABLED = True
TURBO_FLOW_QUEUE_SIZE_DEFAULT = 4
TURBO_TTS_WORKERS_DEFAULT = 4

