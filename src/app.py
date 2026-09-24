# Chức năng: Giao diện người dùng Streamlit chính, quản lý state và điều phối toàn bộ pipeline.
# Lý do tạo: Cung cấp trải nghiệm tương tác trực quan (human-in-the-loop) để kiểm soát từng bước sản xuất video.
# Trích dẫn: Sử dụng thư viện Streamlit và tích hợp các module dịch vụ trong src/.

import os
import sys

# Ép console và Streamlit logger luôn dùng UTF-8 với chế độ thay thế lỗi, chống hoàn toàn UnicodeEncodeError
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

import time
import streamlit as st
import pandas as pd

# Tự động thêm thư mục gốc của dự án vào sys.path để tránh lỗi ModuleNotFoundError
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

from src.config import (
    TTS_VOICES_VI, TTS_VOICES_EN, TTS_VOICE_DEFAULT, SD_MODEL_DEFAULT, WAN_MODEL_DEFAULT,
    DEFAULT_MAX_DURATION, DEFAULT_IMAGE_STYLE, TEMP_DIR, OUTPUT_DIR, WAN_DEFAULT_STEPS,
    get_gpu_benchmark_sec_per_step
)
from src.llm_service import generate_script, remake_script
from src.tts_service import generate_tts
from src.video_downloader import download_and_extract
from src.whisper_service import transcribe_audio_to_text, get_word_timestamps
from src.image_service import generate_single_image, generate_batch_images
from src.flow_image_service import generate_flow_image, generate_flow_batch
from src.video_gen_service import generate_single_video, generate_batch_videos
from src.video_compiler import compile_video_pipeline

# --- THIẾT LẬP TRANG STREAMLIT ---
st.set_page_config(
    page_title="AI Video Producer - Antigravity",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- CUSTOM CSS CHO PREMIUM LOOK & FEEL ---
st.markdown("""
<style>
    /* Dark mode background và Typography */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0e1117 0%, #161b22 100%);
        color: #c9d1d9;
    }
    
    /* Thiết kế Header */
    .main-header {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #ff7e5f, #feb47b, #86e3ce, #d6e4f0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #8b949e;
        text-align: center;
        margin-bottom: 2.5rem;
    }
    
    /* Thiết kế thẻ trạng thái các bước (Stepper) */
    .stepper-container {
        display: flex;
        justify-content: space-around;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    .step-item {
        text-align: center;
        opacity: 0.5;
        transition: all 0.3s ease;
    }
    .step-item.active {
        opacity: 1;
        font-weight: 600;
        transform: scale(1.05);
    }
    .step-number {
        display: inline-block;
        width: 30px;
        height: 30px;
        line-height: 30px;
        border-radius: 50%;
        background: #feb47b;
        color: #0e1117;
        margin-bottom: 5px;
        font-weight: 800;
    }
    .step-item.active .step-number {
        background: linear-gradient(45deg, #ff7e5f, #feb47b);
        box-shadow: 0 0 15px rgba(254, 180, 123, 0.5);
    }
    
    /* Button Custom */
    .stButton>button {
        background: linear-gradient(90deg, #ff7e5f 0%, #feb47b 100%);
        color: #0e1117;
        border: none;
        padding: 0.6rem 2rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(255, 126, 95, 0.2);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 126, 95, 0.4);
        color: #0e1117;
    }
    
    /* Data Editor và Text Input */
    .stTextArea textarea, .stTextInput input {
        background-color: #1f242c !important;
        border: 1px solid #30363d !important;
        color: #c9d1d9 !important;
        border-radius: 8px !important;
    }
    
    /* Scene Card */
    .scene-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- KHỞI TẠO STATE ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "script_scenes" not in st.session_state:
    st.session_state.script_scenes = []
if "orientation" not in st.session_state:
    st.session_state.orientation = "vertical"
if "image_mode" not in st.session_state:
    st.session_state.image_mode = "Nhanh (Ảnh AI)"
if "language" not in st.session_state:
    st.session_state.language = "vi"
if "voice" not in st.session_state:
    st.session_state.voice = TTS_VOICE_DEFAULT
if "rate" not in st.session_state:
    st.session_state.rate = "+0%"
if "max_duration" not in st.session_state:
    st.session_state.max_duration = DEFAULT_MAX_DURATION
if "style_preset" not in st.session_state:
    st.session_state.style_preset = DEFAULT_IMAGE_STYLE
if "final_videos" not in st.session_state:
    st.session_state.final_videos = []
if "wan_steps" not in st.session_state:
    st.session_state.wan_steps = WAN_DEFAULT_STEPS
if "wan_measured_sec_per_step" not in st.session_state:
    st.session_state.wan_measured_sec_per_step = get_gpu_benchmark_sec_per_step()

feature_mode = st.sidebar.selectbox(
    "🎯 Chọn tính năng chính",
    ["🎬 Sản xuất Video Ngắn", "🧘 Học Tiếng Anh Self-heal", "🎙️ Dịch & Lồng tiếng Video", "📚 Bài dạy AI Slideshow"],
    key="feature_mode"
)

if feature_mode == "🧘 Học Tiếng Anh Self-heal":
    from src.app_selfheal import run_selfheal_ui
    run_selfheal_ui()
    st.stop()

if feature_mode == "🎙️ Dịch & Lồng tiếng Video":
    from src.app_dubbing import run_dubbing_ui
    run_dubbing_ui()
    st.stop()

if feature_mode == "📚 Bài dạy AI Slideshow":
    from src.app_educational import run_educational_ui
    run_educational_ui()
    st.stop()


# --- SIDEBAR CẤU HÌNH ---
st.sidebar.markdown("### ⚙️ Cấu hình Hệ thống")

# Chọn Ngôn ngữ video
language_display = st.sidebar.selectbox(
    "Ngôn ngữ video (Language)",
    ["Tiếng Việt", "English (Tiếng Anh)"],
    index=0 if st.session_state.language == "vi" else 1
)
new_lang = "vi" if "Tiếng Việt" in language_display else "en"

# Nếu thay đổi ngôn ngữ, cập nhật state và đặt giọng đọc mặc định tương ứng
if new_lang != st.session_state.language:
    st.session_state.language = new_lang
    st.session_state.voice = "vi-VN-HoaiMyNeural" if new_lang == "vi" else "en-US-EmmaNeural"

# Chọn từ điển giọng đọc tương ứng
voices_dict = TTS_VOICES_VI if st.session_state.language == "vi" else TTS_VOICES_EN

# Đảm bảo giọng đọc hiện tại có trong từ điển
if st.session_state.voice not in voices_dict.values():
    st.session_state.voice = list(voices_dict.values())[0]

# Hướng video
orientation_display = st.sidebar.radio(
    "Hướng video (Orientation)",
    ["Dọc (9:16 — Shorts/TikTok)", "Ngang (16:9 — YouTube)"],
    index=0 if st.session_state.orientation == "vertical" else 1
)
st.session_state.orientation = "vertical" if "Dọc" in orientation_display else "horizontal"

# Chế độ hình ảnh mặc định
st.session_state.image_mode = st.sidebar.radio(
    "Chế độ hình ảnh mặc định",
    ["Nhanh (Ảnh AI)", "Video AI (Wan 2.1)"],
    index=0 if st.session_state.image_mode == "Nhanh (Ảnh AI)" else 1
)

# Cấu hình chất lượng sinh video (chỉ hiện khi chọn Video AI)
if st.session_state.image_mode == "Video AI (Wan 2.1)":
    st.sidebar.markdown("---")
    st.sidebar.markdown("🎬 **Cấu hình Sinh Video (Wan 2.1)**")
    
    # Xác định index mặc định cho preset
    default_preset_idx = 2
    if st.session_state.wan_steps == 20:
        default_preset_idx = 0
    elif st.session_state.wan_steps == 35:
        default_preset_idx = 1
    elif st.session_state.wan_steps == 50:
        default_preset_idx = 2
    else:
        default_preset_idx = 3

    preset_opt = st.sidebar.selectbox(
        "Lựa chọn Chất lượng/Tốc độ",
        ["Tốc độ (20 steps)", "Cân bằng (35 steps)", "Chất lượng (50 steps)", "Tùy chỉnh"],
        index=default_preset_idx
    )
    
    if preset_opt == "Tốc độ (20 steps)":
        st.session_state.wan_steps = 20
    elif preset_opt == "Cân bằng (35 steps)":
        st.session_state.wan_steps = 35
    elif preset_opt == "Chất lượng (50 steps)":
        st.session_state.wan_steps = 50
    else:
        st.session_state.wan_steps = st.sidebar.slider(
            "Số bước lập (Inference Steps)",
            min_value=10,
            max_value=100,
            value=int(st.session_state.wan_steps),
            step=5
        )
        
    sec_per_step = st.session_state.wan_measured_sec_per_step
    estimated_sec = sec_per_step * st.session_state.wan_steps
    
    st.sidebar.info(
        f"⏱️ **Ước tính thời gian:**\n"
        f"- Mỗi clip (~5s): ~{estimated_sec:.1f} giây ({estimated_sec/60:.1f} phút)\n"
        f"- Tốc độ hiện tại: {sec_per_step:.2f} s/step\n"
        f"*(Dự tính dựa trên phần cứng thực tế)*"
    )

# Giọng đọc TTS
voice_display = st.sidebar.selectbox(
    "Giọng đọc TTS (Voice)",
    list(voices_dict.keys()),
    index=list(voices_dict.values()).index(st.session_state.voice)
)
st.session_state.voice = voices_dict[voice_display]

# Tốc độ đọc
rate_slider = st.sidebar.slider(
    "Tốc độ đọc (Rate)",
    min_value=-30,
    max_value=30,
    value=0,
    step=5,
    format="%+d%%"
)
st.session_state.rate = f"{rate_slider}%"

# Thời lượng tối đa mỗi phần
st.session_state.max_duration = st.sidebar.number_input(
    "Thời lượng tối đa mỗi phần (giây)",
    min_value=15,
    max_value=180,
    value=st.session_state.max_duration,
    step=5
)

# Phong cách hình ảnh
st.session_state.style_preset = st.sidebar.text_input(
    "Phong cách hình ảnh mặc định",
    value=st.session_state.style_preset
)

# Nguồn sinh ảnh & Kỹ thuật chuyển động
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎨 Nguồn sinh hình ảnh")
image_engine = st.sidebar.radio(
    "Mô hình tạo ảnh:",
    ["🍌 Google Flow (Nano Banana Pro / CDP)", "💻 Stable Diffusion 1.5 (Local GPU/CPU)"],
    index=0,
    help="Google Flow sử dụng Nano Banana Pro trên cloud, khóa nhân vật Stickman và không tốn VRAM card rời."
)
st.session_state.image_engine = image_engine

# --- HEADER CHÍNH ---
st.markdown("<div class='main-header'>AI VIDEO PRODUCER</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Hệ thống tự động hóa sản xuất video ngắn local sử dụng AI</div>", unsafe_allow_html=True)

# --- STEPPER DISPLAY ---
step_1_active = "active" if st.session_state.step == 1 else ""
step_2_active = "active" if st.session_state.step == 2 else ""
step_3_active = "active" if st.session_state.step == 3 else ""

st.markdown(f"""
<div class='stepper-container'>
    <div class='step-item {step_1_active}'>
        <div class='step-number'>1</div>
        <div>Biên soạn Kịch bản</div>
    </div>
    <div class='step-item {step_2_active}'>
        <div class='step-number'>2</div>
        <div>Duyệt & Sinh Tài nguyên</div>
    </div>
    <div class='step-item {step_3_active}'>
        <div class='step-number'>3</div>
        <div>Render & Thành phẩm</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- HÀM HELPER LẤY THỜI LƯỢNG AUDIO ---
def get_audio_duration(file_path: str) -> float:
    """Đọc chính xác thời lượng file âm thanh bằng mutagen hoặc moviepy."""
    if HAS_MUTAGEN:
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception:
            pass
    try:
        from moviepy.editor import AudioFileClip
        audio_clip = AudioFileClip(file_path)
        duration = audio_clip.duration
        audio_clip.close()
        return duration
    except Exception:
        return 5.0

# --- BƯỚC 1: BIÊN SOẠN KỊCH BẢN ---
if st.session_state.step == 1:
    st.markdown("### 📝 Bước 1: Thiết lập nội dung & Tạo kịch bản")
    
    input_mode = st.radio(
        "Chọn phương thức đầu vào",
        ["Tạo mới từ ý tưởng bằng văn bản", "Remake kịch bản từ link video"]
    )
    
    if input_mode == "Tạo mới từ ý tưởng bằng văn bản":
        idea_text = st.text_area(
            "Nhập ý tưởng/chủ đề chi tiết cho video của bạn",
            placeholder="Ví dụ: Kể câu chuyện ngụ ngôn con quạ khát nước bằng giọng điệu hài hước, bài học sâu sắc ở cuối.",
            height=150
        )
        
        if st.button("✨ Sinh kịch bản phân cảnh"):
            if not idea_text.strip():
                st.warning("Vui lòng nhập ý tưởng trước.")
            else:
                with st.spinner("Ollama đang động não viết kịch bản..."):
                    success, data = generate_script(
                        idea_text, 
                        st.session_state.style_preset, 
                        language=st.session_state.language
                    )
                    if success and "scenes" in data:
                        st.session_state.script_scenes = data["scenes"]
                        st.success("Đã sinh kịch bản thành công! Bạn có thể chỉnh sửa ở bảng dưới.")
                    else:
                        st.error(f"Lỗi sinh kịch bản: {data}")
                        
    else:  # Luồng B: Remake
        video_url = st.text_input(
            "Dán link video nguồn (YouTube Shorts, TikTok, Reels...)",
            placeholder="https://www.youtube.com/shorts/..."
        )
        edit_prompt = st.text_area(
            "Nhập hướng dẫn chỉnh sửa kịch bản",
            placeholder="Ví dụ: Viết lại kịch bản trên theo phong cách giật gân, hình ảnh anime lung linh.",
            height=100
        )
        
        if st.button("🚀 Phân tích & Remake video"):
            if not video_url.strip() or not edit_prompt.strip():
                st.warning("Vui lòng nhập đầy đủ link video và hướng dẫn chỉnh sửa.")
            else:
                # Tạo tiến trình
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 1. Tải video
                status_text.text("Đang tải video nguồn bằng yt-dlp...")
                progress_bar.progress(20)
                dl_success, v_path, a_path, dl_err = download_and_extract(video_url)
                
                if not dl_success:
                    st.error(f"Thất bại khi xử lý video: {dl_err}")
                else:
                    # 2. Transcribe
                    status_text.text("Đang trích xuất lời thoại bằng Faster-Whisper...")
                    progress_bar.progress(50)
                    tx_success, transcript = transcribe_audio_to_text(
                        a_path, 
                        language=st.session_state.language
                    )
                    
                    if not tx_success:
                        st.error(f"Lỗi trích xuất lời thoại: {transcript}")
                    else:
                        st.info(f"Lời thoại gốc nhận diện được:\n\"{transcript}\"")
                        
                        # 3. Viết lại bằng LLM
                        status_text.text("Ollama đang viết lại kịch bản mới...")
                        progress_bar.progress(80)
                        success, data = remake_script(
                            transcript, 
                            edit_prompt, 
                            st.session_state.style_preset, 
                            language=st.session_state.language
                        )
                        
                        progress_bar.progress(100)
                        status_text.text("Hoàn thành!")
                        
                        if success and "scenes" in data:
                            st.session_state.script_scenes = data["scenes"]
                            st.success("Đã remake kịch bản thành công! Bạn có thể chỉnh sửa ở bảng dưới.")
                        else:
                            st.error(f"Lỗi sinh kịch bản remake: {data}")
                            
    # Hiển thị kịch bản và cho phép chỉnh sửa nếu có
    if st.session_state.script_scenes:
        st.markdown("#### Bảng phân cảnh kịch bản (Cho phép chỉnh sửa trực tiếp)")
        
        # Chuyển đổi list of dict thành DataFrame để dùng st.data_editor
        df = pd.DataFrame(st.session_state.script_scenes)
        
        # Hiển thị bảng biên tập
        edited_df = st.data_editor(
            df,
            column_config={
                "scene_num": st.column_config.NumberColumn("STT", disabled=True, width="small"),
                "narration": st.column_config.TextColumn(
                    "Lời thoại (Tiếng Việt)" if st.session_state.language == "vi" else "Narration (English)", 
                    width="large"
                ),
                "video_prompt": st.column_config.TextColumn("Prompt hình ảnh/video (Tiếng Anh)", width="large")
            },
            num_rows="dynamic",
            use_container_width=True
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 Lưu chỉnh sửa kịch bản"):
                st.session_state.script_scenes = edited_df.to_dict(orient="records")
                st.success("Đã lưu chỉnh sửa!")
                
        with col2:
            if st.button("✅ Duyệt kịch bản — Chuyển sang Bước 2"):
                # Lưu lại kịch bản trước khi chuyển bước
                st.session_state.script_scenes = edited_df.to_dict(orient="records")
                
                # Khởi tạo các trường tài nguyên cho mỗi phân cảnh nếu chưa có
                for i, scene in enumerate(st.session_state.script_scenes):
                    scene["audio_path"] = os.path.join(TEMP_DIR, f"scene_{i+1:03d}.mp3")
                    scene["image_path"] = os.path.join(TEMP_DIR, f"scene_{i+1:03d}.png")
                    scene["video_path"] = os.path.join(TEMP_DIR, f"scene_{i+1:03d}.mp4")
                    scene["use_video_ai"] = (st.session_state.image_mode == "Video AI (Wan 2.1)")
                    
                st.session_state.step = 2
                st.rerun()

# --- BƯỚC 2: DUYỆT & SINH TÀI NGUYÊN ---
elif st.session_state.step == 2:
    st.markdown("### 🎨 Bước 2: Sinh tài nguyên cho từng phân cảnh")
    
    # Nút chuyển về bước 1
    if st.button("⬅️ Quay lại Bước 1 (Sửa kịch bản)"):
        st.session_state.step = 1
        st.rerun()
        
    st.markdown("---")
    
    # Nút sinh toàn bộ tài nguyên
    if st.button("⚡ Bắt đầu sinh toàn bộ tài nguyên tự động"):
        # Sinh giọng đọc loạt
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. Sinh Audio
        status_text.text("Đang sinh giọng đọc TTS cho các phân cảnh...")
        total = len(st.session_state.script_scenes)
        for i, scene in enumerate(st.session_state.script_scenes):
            progress_bar.progress(int((i / total) * 30))
            generate_tts(
                text=scene["narration"],
                output_path=scene["audio_path"],
                voice=st.session_state.voice,
                rate=st.session_state.rate
            )
            # Cập nhật thời lượng audio thực tế
            scene["audio_duration"] = get_audio_duration(scene["audio_path"])
            
        # 2. Sinh Hình ảnh hoặc Video AI
        # Gom nhóm các phân cảnh theo loại sinh
        sd_scenes = []
        wan_scenes = []
        for i, scene in enumerate(st.session_state.script_scenes):
            if scene.get("use_video_ai", False):
                wan_scenes.append((i, scene))
            else:
                sd_scenes.append((i, scene))
                
        # Sinh loạt ảnh (Google Flow hoặc Stable Diffusion)
        if sd_scenes:
            use_flow = getattr(st.session_state, "image_engine", "").startswith("🍌 Google Flow")
            engine_name = "Google Flow (Nano Banana Pro)" if use_flow else "Stable Diffusion 1.5"
            status_text.text(f"Đang sinh ảnh AI bằng {engine_name}...")
            
            # Tạo list scene dict thô để truyền cho batch
            sd_raw_scenes = [s[1] for s in sd_scenes]
            if use_flow:
                success, paths = generate_flow_batch(
                    scenes=sd_raw_scenes,
                    temp_dir=TEMP_DIR,
                    orientation=st.session_state.orientation,
                    style_preset=st.session_state.style_preset
                )
            else:
                success, paths = generate_batch_images(
                    scenes=sd_raw_scenes,
                    temp_dir=TEMP_DIR,
                    orientation=st.session_state.orientation,
                    style_preset=st.session_state.style_preset
                )
            if success:
                for idx, (original_idx, scene) in enumerate(sd_scenes):
                    scene["image_path"] = paths[idx]
                    progress_bar.progress(30 + int((idx / len(sd_scenes)) * 30))
            else:
                err_msg = paths[0] if (isinstance(paths, list) and paths) else str(paths)
                st.error(f"❌ {err_msg}")
                if use_flow:
                    st.warning("👉 Hãy mở Chrome kết nối Google Flow: chạy file scripts/launch_flow_chrome.bat (hoặc phím [4] trong run.bat).")
                
        # Sinh loạt video Wan 2.1
        if wan_scenes:
            status_text.text("Đang sinh video AI bằng Wan 2.1 (Quá trình này tốn nhiều thời gian)...")
            # Unload Ollama trước khi chạy Wan để giải phóng VRAM
            wan_raw_scenes = [s[1] for s in wan_scenes]
            success, paths, elapsed = generate_batch_videos(
                scenes=wan_raw_scenes,
                temp_dir=TEMP_DIR,
                orientation=st.session_state.orientation,
                num_inference_steps=st.session_state.wan_steps
            )
            if success and paths and elapsed > 0:
                total_steps = len(wan_raw_scenes) * st.session_state.wan_steps
                st.session_state.wan_measured_sec_per_step = elapsed / total_steps
            if success:
                for idx, (original_idx, scene) in enumerate(wan_scenes):
                    scene["video_path"] = paths[idx]
                    progress_bar.progress(60 + int((idx / len(wan_scenes)) * 40))
            else:
                st.error(f"Lỗi sinh video loạt: {paths}")
                
        progress_bar.progress(100)
        status_text.text("Đã hoàn thành sinh toàn bộ tài nguyên!")
        st.success("Tất cả tài nguyên đã được khởi tạo. Hãy xem danh sách phân cảnh bên dưới.")
        st.rerun()

    st.markdown("### Danh sách phân cảnh:")
    
    # Hiển thị và cho phép chỉnh sửa từng phân cảnh độc lập
    for i, scene in enumerate(st.session_state.script_scenes):
        st.markdown(f"<div class='scene-card'>", unsafe_allow_html=True)
        col_info, col_asset = st.columns([3, 2])
        
        with col_info:
            st.markdown(f"#### 🎬 Phân cảnh {i+1}")
            
            # Sửa lời thoại trực tiếp
            new_narration = st.text_area(
                f"Lời thoại phân cảnh {i+1}", 
                value=scene["narration"], 
                key=f"narr_{i}",
                height=70
            )
            scene["narration"] = new_narration
            
            # Chọn loại tài nguyên
            use_video = st.checkbox(
                "Sử dụng Video AI (Wan 2.1) thay vì Ảnh AI", 
                value=scene.get("use_video_ai", False),
                key=f"use_video_{i}"
            )
            scene["use_video_ai"] = use_video
            
            # Nút nghe thử audio và sinh lại audio riêng lẻ
            audio_file = scene["audio_path"]
            if os.path.exists(audio_file):
                st.audio(audio_file, format="audio/mp3")
                scene["audio_duration"] = get_audio_duration(audio_file)
                st.caption(f"Thời lượng: {scene['audio_duration']:.2f} giây")
            else:
                st.warning("Chưa sinh giọng đọc cho cảnh này.")
                
            if st.button("🔊 Sinh lại giọng đọc", key=f"btn_tts_{i}"):
                with st.spinner("Đang sinh giọng đọc..."):
                    success, path = generate_tts(
                        text=scene["narration"],
                        output_path=scene["audio_path"],
                        voice=st.session_state.voice,
                        rate=st.session_state.rate
                    )
                    if success:
                        scene["audio_duration"] = get_audio_duration(path)
                        st.success("Đã cập nhật giọng đọc!")
                        st.rerun()
                    else:
                        st.error(path)
                        
        with col_asset:
            # Sửa prompt visual trực tiếp
            new_prompt = st.text_input(
                f"Prompt hình ảnh/video phân cảnh {i+1}", 
                value=scene["video_prompt"], 
                key=f"prompt_{i}"
            )
            scene["video_prompt"] = new_prompt
            
            # Hiển thị asset hiện tại
            if use_video:
                # Hiển thị video preview
                v_path = scene["video_path"]
                if os.path.exists(v_path):
                    st.video(v_path)
                else:
                    st.warning("Chưa sinh clip video cho cảnh này.")
                    
                if st.button("🎥 Tạo lại clip Video AI", key=f"btn_vid_{i}"):
                    with st.spinner("Đang chạy Wan 2.1 sinh video (~15 phút)..."):
                        success, path, elapsed = generate_single_video(
                            prompt=scene["video_prompt"],
                            output_path=scene["video_path"],
                            orientation=st.session_state.orientation,
                            num_inference_steps=st.session_state.wan_steps
                        )
                        if success and elapsed > 0:
                            st.session_state.wan_measured_sec_per_step = elapsed / st.session_state.wan_steps
                        if success:
                            st.success("Sinh video thành công!")
                            st.rerun()
                        else:
                            st.error(path)
            else:
                # Hiển thị ảnh preview
                img_path = scene["image_path"]
                if os.path.exists(img_path):
                    st.image(img_path, use_column_width=True)
                else:
                    st.warning("Chưa sinh ảnh cho cảnh này.")
                    
                if st.button("🖼️ Tạo lại ảnh AI", key=f"btn_img_{i}"):
                    use_flow = getattr(st.session_state, "image_engine", "").startswith("🍌 Google Flow")
                    spinner_msg = "Đang chạy Google Flow sinh ảnh..." if use_flow else "Đang chạy SD sinh ảnh..."
                    with st.spinner(spinner_msg):
                        if use_flow:
                            success, path = generate_flow_image(
                                prompt=scene["video_prompt"],
                                output_path=scene["image_path"],
                                orientation=st.session_state.orientation,
                                style_preset=st.session_state.style_preset
                            )
                        else:
                            success, path = generate_single_image(
                                prompt=scene["video_prompt"],
                                output_path=scene["image_path"],
                                orientation=st.session_state.orientation,
                                style_preset=st.session_state.style_preset
                            )
                        if success:
                            st.success("Sinh ảnh thành công!")
                            st.rerun()
                        else:
                            st.error(path)
                            
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")
        
    # Nút duyệt để chuyển sang Bước 3
    # Đảm bảo toàn bộ tài nguyên đã được sinh đầy đủ trước khi cho duyệt
    all_ready = True
    for scene in st.session_state.script_scenes:
        if not os.path.exists(scene["audio_path"]):
            all_ready = False
        if scene["use_video_ai"] and not os.path.exists(scene["video_path"]):
            all_ready = False
        if not scene["use_video_ai"] and not os.path.exists(scene["image_path"]):
            all_ready = False
            
    if not all_ready:
        st.info("💡 Mẹo: Hãy sinh toàn bộ tài nguyên tự động trước để dễ dàng kiểm tra và duyệt.")
        
    if st.button("✅ Duyệt tài nguyên — Chuyển sang Bước 3 (Render)", disabled=not all_ready):
        st.session_state.step = 3
        st.rerun()

# --- BƯỚC 3: RENDER & XUẤT BẢN ---
elif st.session_state.step == 3:
    st.markdown("### 🎬 Bước 3: Tiến hành Render Video & Xuất bản")
    
    # Nút quay lại bước 2
    if st.button("⬅️ Quay lại Bước 2 (Chỉnh sửa tài nguyên)"):
        st.session_state.step = 2
        st.rerun()
        
    st.markdown("---")
    
    if st.button("▶️ Bắt đầu Render Video hoàn chỉnh"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. Trích xuất word-level timestamps của từng audio phân cảnh
        status_text.text("Đang phân tích giọng nói để lấy timestamps từ Faster-Whisper...")
        progress_bar.progress(25)
        
        all_words = []
        cumulative_time = 0.0
        
        total_scenes = len(st.session_state.script_scenes)
        whisper_success = True
        
        for idx, scene in enumerate(st.session_state.script_scenes):
            status_text.text(f"Đang phân tích timestamps cho Phân cảnh {idx+1}/{total_scenes}...")
            # Lấy timestamps cho file audio của cảnh này
            success, words = get_word_timestamps(
                scene["audio_path"], 
                language=st.session_state.language
            )
            if success:
                for w in words:
                    # Dịch chuyển mốc thời gian dựa theo thời gian tích lũy của các cảnh trước
                    shifted_word = {
                        "word": w["word"],
                        "start": w["start"] + cumulative_time,
                        "end": w["end"] + cumulative_time
                    }
                    all_words.append(shifted_word)
            else:
                whisper_success = False
                st.error(f"Lỗi phân tích giọng nói ở phân cảnh {idx+1}: {words}")
                break
                
            cumulative_time += scene.get("audio_duration", 5.0)
            progress_bar.progress(25 + int((idx / total_scenes) * 25))
            
        if whisper_success:
            # 2. Thực hiện ghép video, chia phần và burn phụ đề
            status_text.text("Đang xử lý ghép nối clip và burn phụ đề bằng MoviePy & FFmpeg...")
            progress_bar.progress(60)
            
            success, videos, err_msg = compile_video_pipeline(
                scenes=st.session_state.script_scenes,
                words_timestamps=all_words,
                max_duration=st.session_state.max_duration,
                orientation=st.session_state.orientation
            )
            
            progress_bar.progress(100)
            if success:
                st.session_state.final_videos = videos
                status_text.text("Biên tập video hoàn thành xuất sắc!")
                st.success("Tất cả các phần video đã được render thành công!")
            else:
                status_text.text("Có lỗi xảy ra khi render.")
                st.error(f"Chi tiết lỗi render: {err_msg}")
                
    # Hiển thị kết quả video sau khi render
    if st.session_state.final_videos:
        st.markdown("### 📥 Video Thành Phẩm")
        
        if len(st.session_state.final_videos) == 1:
            # Chỉ có 1 video duy nhất
            video_path = st.session_state.final_videos[0]
            if os.path.exists(video_path):
                st.video(video_path)
                with open(video_path, "rb") as file:
                    st.download_button(
                        label="💾 Tải video về máy",
                        data=file,
                        file_name=os.path.basename(video_path),
                        mime="video/mp4"
                    )
        else:
            # Có nhiều phần (Part 1, Part 2...)
            st.info(f"Video vượt quá {st.session_state.max_duration} giây và đã được tự động chia thành {len(st.session_state.final_videos)} phần.")
            
            # Hiển thị từng phần dưới dạng tabs
            tab_names = [f"Phần {i+1}" for i in range(len(st.session_state.final_videos))]
            tabs = st.tabs(tab_names)
            
            for idx, tab in enumerate(tabs):
                with tab:
                    video_path = st.session_state.final_videos[idx]
                    if os.path.exists(video_path):
                        st.video(video_path)
                        with open(video_path, "rb") as file:
                            st.download_button(
                                label=f"💾 Tải video Phần {idx+1}",
                                data=file,
                                file_name=os.path.basename(video_path),
                                mime="video/mp4",
                                key=f"dl_part_{idx}"
                            )
