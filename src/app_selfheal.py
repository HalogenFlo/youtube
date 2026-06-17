# Chức năng: Giao diện người dùng Streamlit cho tính năng học tiếng Anh Self-heal.
# Lý do tạo: Tách biệt UI Self-heal ra file riêng để tránh sửa đổi làm hỏng code gốc của app.py.
# Trích dẫn: Sử dụng thiết kế CSS premium tương tự app.py và tích hợp dịch vụ selfheal_compiler.

import os
import streamlit as st
import pandas as pd
from src.config import (
    TTS_VOICES_EN, TEMP_DIR, OUTPUT_DIR, SPEAKER_COLORS,
    DEFAULT_READING_WPM, DEFAULT_PAUSE_BEFORE_SILENT, DEFAULT_SELFHEAL_STYLE,
    BACKGROUNDS_DIR
)
from src.llm_service import generate_selfheal_script, feedback_selfheal_script
from src.tts_service import generate_tts
from src.image_service import generate_batch_images, generate_single_image
from src.video_gen_service import generate_batch_videos, generate_single_video
from src.music_service import (
    list_available_music, download_music_from_url, get_audio_duration,
    list_available_backgrounds, download_background_from_url,
    download_background_asset
)
from src.selfheal_compiler import compile_selfheal_video

# Định nghĩa các màu chữ hiển thị thân thiện
COLOR_MAP = {
    "🟡 Vàng neon": "&H0000FFFF",
    "🟢 Xanh lá": "&H0000FF00",
    "🔵 Xanh dương": "&H00FF9933",
    "🔴 Đỏ cam": "&H005050FF",
    "🌸 Hồng": "&H00FF00FF",
    "🟠 Cam": "&H0033CCFF"
}

# Định nghĩa ý tưởng mặc định theo thể loại kịch bản
DEFAULT_IDEAS = {
    "meditation": "Một buổi thiền ngắn hướng dẫn hít thở sâu, thư giãn đầu óc và cảm nhận sự bình yên của thiên nhiên thanh bình.",
    "interview": "Một cuộc phỏng vấn tiếng Anh giao tiếp ngắn giữa Interviewer (Người phỏng vấn) và Candidate (Ứng viên) về chủ đề giới thiệu bản thân và kinh nghiệm làm việc.",
    "conversation": "Cuộc trò chuyện tiếng Anh hàng ngày giữa hai người bạn thân (Tom và Anna) đang lên kế hoạch đi dã ngoại vào cuối tuần.",
    "custom": "You are an AI-powered self-health assistant designed to help users monitor and improve their daily well-being.\n\nContext:\nThe user is a 32-year-old office worker who spends most of the day sitting in front of a computer. They often experience mild back pain, eye strain, irregular sleep patterns, and occasional stress.\n\nYour responsibilities include:\n- Suggesting healthy habits, eye break exercises, and stress management.\n- Focus on actionable steps that the user can realistically follow."
}

def run_selfheal_ui():
    # --- KHỞI TẠO STATE CHO SELF-HEAL ---
    if "sh_idea_input" not in st.session_state:
        st.session_state.sh_idea_input = DEFAULT_IDEAS["interview"]
    if "sh_feedback_input" not in st.session_state:
        st.session_state.sh_feedback_input = ""
    if "sh_prev_script_type" not in st.session_state:
        st.session_state.sh_prev_script_type = ""
    if "sh_step" not in st.session_state:
        st.session_state.sh_step = 1
    if "sh_scenes" not in st.session_state:
        st.session_state.sh_scenes = []
    if "sh_speakers" not in st.session_state:
        st.session_state.sh_speakers = []
    if "sh_speaker_config" not in st.session_state:
        st.session_state.sh_speaker_config = {}
    if "sh_final_videos" not in st.session_state:
        st.session_state.sh_final_videos = []
    if "sh_music_file" not in st.session_state:
        st.session_state.sh_music_file = ""
    if "sh_wpm" not in st.session_state:
        st.session_state.sh_wpm = DEFAULT_READING_WPM
    if "sh_pause" not in st.session_state:
        st.session_state.sh_pause = DEFAULT_PAUSE_BEFORE_SILENT
    if "sh_style_preset" not in st.session_state:
        st.session_state.sh_style_preset = DEFAULT_SELFHEAL_STYLE
    if "sh_orientation" not in st.session_state:
        st.session_state.sh_orientation = "vertical"
    if "sh_image_mode" not in st.session_state:
        st.session_state.sh_image_mode = "Nhanh (Ảnh AI)"
    if "sh_show_translation" not in st.session_state:
        st.session_state.sh_show_translation = True
    if "sh_script_type" not in st.session_state:
        st.session_state.sh_script_type = "interview"
    if "sh_use_single_bg" not in st.session_state:
        st.session_state.sh_use_single_bg = True
    if "sh_bg_video_file" not in st.session_state:
        st.session_state.sh_bg_video_file = ""
    if "sh_max_duration" not in st.session_state:
        st.session_state.sh_max_duration = 60.0
    if "sh_target_scenes" not in st.session_state:
        st.session_state.sh_target_scenes = 12

    # --- SIDEBAR CẤU HÌNH SELF-HEAL ---
    st.sidebar.markdown("### 🧘 Cấu hình Self-heal")
    
    if st.sidebar.button("🔄 Reset toàn bộ (Tạo lại từ đầu)"):
        st.session_state.sh_step = 1
        st.session_state.sh_scenes = []
        st.session_state.sh_speakers = []
        st.session_state.sh_speaker_config = {}
        st.session_state.sh_final_videos = []
        st.session_state.sh_bg_video_file = ""
        st.rerun()
        
    # Loại kịch bản
    selected_script_type = st.sidebar.selectbox(
        "Loại kịch bản",
        ["meditation", "interview", "conversation", "custom"],
        index=["meditation", "interview", "conversation", "custom"].index(st.session_state.sh_script_type)
    )
    st.session_state.sh_script_type = selected_script_type
    
    if st.session_state.sh_prev_script_type != selected_script_type:
        st.session_state.sh_prev_script_type = selected_script_type
        current_val = st.session_state.get("sh_idea_input", "").strip()
        if not current_val or current_val in DEFAULT_IDEAS.values() or current_val == "Ví dụ: Cuộc trò chuyện phỏng vấn xin việc bằng tiếng Anh giữa Interviewer và Candidate.":
            st.session_state.sh_idea_input = DEFAULT_IDEAS.get(selected_script_type, "")
    
    # Quản lý nhạc nền
    st.sidebar.markdown("#### 🎵 Nhạc nền")
    available_music = list_available_music()
    music_index = 0
    if st.session_state.sh_music_file in available_music:
        music_index = available_music.index(st.session_state.sh_music_file)
        
    if available_music:
        st.session_state.sh_music_file = st.sidebar.selectbox(
            "Chọn nhạc nền",
            available_music,
            index=music_index
        )
    else:
        st.sidebar.warning("Chưa có nhạc nền trong thư mục assets/music.")
        st.session_state.sh_music_file = ""
        
    # Tải nhạc mới
    music_url = st.sidebar.text_input("Nhập link tải nhạc (YouTube/SoundCloud...)", key="sh_music_url")
    music_name = st.sidebar.text_input("Tên nhạc lưu trữ", placeholder="chill_nature", key="sh_music_name")
    
    if st.sidebar.button("⬇️ Tải nhạc về"):
        if not music_url.strip():
            st.sidebar.warning("Vui lòng nhập link nhạc.")
        else:
            with st.sidebar.spinner("Đang tải nhạc..."):
                success, path = download_music_from_url(music_url, music_name)
                if success:
                    st.sidebar.success(f"Đã tải xong: {os.path.basename(path)}")
                    st.rerun()
                else:
                    st.sidebar.error(f"Lỗi tải nhạc: {path}")

    # Cấu hình video/ảnh nền chung
    st.sidebar.markdown("#### 📺 Nền Chung (Video/Ảnh)")
    st.session_state.sh_use_single_bg = st.sidebar.checkbox(
        "Sử dụng 1 video/ảnh nền duy nhất",
        value=st.session_state.sh_use_single_bg
    )

    if st.session_state.sh_use_single_bg:
        # Lựa chọn nguồn nền chung
        bg_source = st.sidebar.radio(
            "Nguồn nền chung",
            ["Chọn từ thư viện / Tải từ URL", "Sinh video bằng AI (Wan 2.1)", "Sinh ảnh bằng AI (Stable Diffusion)"],
            key="sh_bg_source"
        )
        
        available_bgs = list_available_backgrounds()
        bg_index = 0
        if st.session_state.sh_bg_video_file in available_bgs:
            bg_index = available_bgs.index(st.session_state.sh_bg_video_file)
            
        if available_bgs:
            st.session_state.sh_bg_video_file = st.sidebar.selectbox(
                "Chọn file nền",
                available_bgs,
                index=bg_index
            )
        else:
            st.sidebar.warning("Chưa có file nền trong backgrounds.")
            st.session_state.sh_bg_video_file = ""

        if bg_source == "Chọn từ thư viện / Tải từ URL":
            bg_url = st.sidebar.text_input("Nhập link tải video/ảnh nền (YouTube/Direct Link...)", key="sh_bg_url")
            bg_name = st.sidebar.text_input("Tên file nền lưu trữ", placeholder="nature_bg", key="sh_bg_name")
            
            if st.sidebar.button("⬇️ Tải nền"):
                if not bg_url.strip():
                    st.sidebar.warning("Vui lòng nhập link nền.")
                else:
                    with st.sidebar.spinner("Đang tải tài nguyên nền..."):
                        success, path = download_background_asset(bg_url, bg_name)
                        if success:
                            st.sidebar.success(f"Đã tải xong: {os.path.basename(path)}")
                            st.session_state.sh_bg_video_file = os.path.basename(path)
                            st.rerun()
                        else:
                            st.sidebar.error(f"Lỗi tải: {path}")
        elif bg_source == "Sinh video bằng AI (Wan 2.1)":
            ai_bg_prompt = st.sidebar.text_area(
                "Nhập Prompt sinh video nền bằng AI",
                value="A peaceful serene forest river with soft sunlight, slow motion, cinematic, 4k",
                key="sh_ai_bg_prompt"
            )
            if st.sidebar.button("🎥 Sinh video nền bằng AI"):
                if not ai_bg_prompt.strip():
                    st.sidebar.warning("Vui lòng nhập prompt.")
                else:
                    import time
                    bg_name = f"ai_bg_{int(time.time())}.mp4"
                    output_path = os.path.join(BACKGROUNDS_DIR, bg_name)
                    with st.sidebar.spinner("Đang khởi động Wan 2.1 và sinh video nền (~15 phút)..."):
                        success, path = generate_single_video(
                            prompt=ai_bg_prompt,
                            output_path=output_path,
                            orientation=st.session_state.sh_orientation
                        )
                        if success:
                            st.sidebar.success(f"Sinh thành công video nền AI: {os.path.basename(path)}")
                            st.session_state.sh_bg_video_file = os.path.basename(path)
                            st.rerun()
                        else:
                            st.sidebar.error(f"Lỗi sinh video nền AI: {path}")
        else:
            # Sinh ảnh bằng AI (Stable Diffusion)
            ai_bg_prompt_img = st.sidebar.text_area(
                "Nhập Prompt sinh ảnh nền bằng AI",
                value="A peaceful serene forest river with soft sunlight, cinematic, 4k",
                key="sh_ai_bg_prompt_img"
            )
            style_preset = st.sidebar.text_input(
                "Style preset sinh ảnh nền",
                value="peaceful nature landscape, serene forest river, soft morning light, cinematic, 4k",
                key="sh_ai_bg_style_preset"
            )
            if st.sidebar.button("🖼️ Sinh ảnh nền bằng AI"):
                if not ai_bg_prompt_img.strip():
                    st.sidebar.warning("Vui lòng nhập prompt.")
                else:
                    import time
                    bg_name = f"ai_bg_img_{int(time.time())}.png"
                    output_path = os.path.join(BACKGROUNDS_DIR, bg_name)
                    with st.sidebar.spinner("Đang khởi động Stable Diffusion và sinh ảnh nền (~10 giây)..."):
                        success, path = generate_single_image(
                            prompt=ai_bg_prompt_img,
                            output_path=output_path,
                            orientation=st.session_state.sh_orientation,
                            style_preset=style_preset
                        )
                        if success:
                            st.sidebar.success(f"Sinh thành công ảnh nền AI: {os.path.basename(path)}")
                            st.session_state.sh_bg_video_file = os.path.basename(path)
                            st.rerun()
                        else:
                            st.sidebar.error(f"Lỗi sinh ảnh nền AI: {path}")
    else:
        # Ẩn bớt để tránh rối mắt (Yêu cầu 2)
        st.session_state.sh_image_mode = st.sidebar.selectbox(
            "Chế độ hình ảnh mặc định",
            ["Nhanh (Ảnh AI)", "Video AI (Wan 2.1)"],
            index=0 if st.session_state.sh_image_mode == "Nhanh (Ảnh AI)" else 1
        )
        st.session_state.sh_style_preset = st.sidebar.text_input(
            "Prompt phong cách hình ảnh mặc định",
            value=st.session_state.sh_style_preset
        )

    # Các cấu hình khác
    st.sidebar.markdown("#### ⚙️ Cấu hình khác")
    st.session_state.sh_wpm = st.sidebar.slider(
        "Tốc độ đọc (WPM - Words Per Minute)",
        min_value=80,
        max_value=200,
        value=st.session_state.sh_wpm,
        step=10
    )
    
    st.session_state.sh_pause = st.sidebar.slider(
        "Khoảng dừng trước lượt im lặng (giây)",
        min_value=0.5,
        max_value=3.0,
        value=st.session_state.sh_pause,
        step=0.5
    )
    
    # Cho phép chọn thời lượng cho Self-heal (Yêu cầu 4)
    st.session_state.sh_max_duration = st.sidebar.number_input(
        "Thời lượng tối đa mỗi phần (giây)",
        min_value=15,
        max_value=180,
        value=int(st.session_state.sh_max_duration),
        step=5
    )
    
    st.session_state.sh_target_scenes = st.sidebar.slider(
        "Số phân cảnh mong muốn",
        min_value=4,
        max_value=30,
        value=int(st.session_state.sh_target_scenes),
        step=1,
        help="Số phân cảnh AI sẽ viết. Nhiều cảnh hơn sẽ tạo ra video dài hơn (12 cảnh tương đương khoảng 60 giây)."
    )
    
    sub_mode = st.sidebar.radio(
        "Chế độ phụ đề",
        ["Song ngữ Anh-Việt", "Chỉ tiếng Anh"],
        index=0 if st.session_state.sh_show_translation else 1
    )
    st.session_state.sh_show_translation = (sub_mode == "Song ngữ Anh-Việt")
    
    orientation_sel = st.sidebar.selectbox(
        "Hướng video (Ngang/Dọc)",
        ["Dọc (9:16 — Shorts/TikTok)", "Ngang (16:9 — YouTube)"],
        index=0 if st.session_state.sh_orientation == "vertical" else 1
    )
    st.session_state.sh_orientation = "vertical" if orientation_sel.startswith("Dọc") else "horizontal"

    # --- STEPPER DISPLAY ---
    step_1_active = "active" if st.session_state.sh_step == 1 else ""
    step_2_active = "active" if st.session_state.sh_step == 2 else ""
    step_3_active = "active" if st.session_state.sh_step == 3 else ""
    
    st.markdown(f"""
    <div class='stepper-container'>
        <div class='step-item {step_1_active}'>
            <div class='step-number'>1</div>
            <div>Biên soạn Kịch bản & Nhân vật</div>
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

    # --- BƯỚC 1: BIÊN SOẠN KỊCH BẢN ---
    if st.session_state.sh_step == 1:
        st.markdown("### 🧘 Bước 1: Tạo kịch bản học tiếng Anh Self-heal")
        
        idea_text = st.text_area(
            "Nhập ý tưởng/chủ đề cho video Self-heal của bạn",
            value=st.session_state.sh_idea_input,
            placeholder="Nhập ý tưởng của bạn hoặc chọn các gợi ý nhanh bên dưới...",
            height=150
        )
        st.session_state.sh_idea_input = idea_text
        
        # Gợi ý nhanh chủ đề
        st.markdown("💡 *Gợi ý nhanh chủ đề kịch bản:*")
        col_i1, col_i2, col_i3, col_i4 = st.columns(4)
        with col_i1:
            if st.button("🧘 Thiền thư giãn", key="btn_suggest_med"):
                st.session_state.sh_idea_input = DEFAULT_IDEAS["meditation"]
                st.rerun()
        with col_i2:
            if st.button("💼 Phỏng vấn", key="btn_suggest_int"):
                st.session_state.sh_idea_input = DEFAULT_IDEAS["interview"]
                st.rerun()
        with col_i3:
            if st.button("💬 Hội thoại", key="btn_suggest_conv"):
                st.session_state.sh_idea_input = DEFAULT_IDEAS["conversation"]
                st.rerun()
        with col_i4:
            if st.button("🩺 Trợ lý sức khỏe", key="btn_suggest_cust"):
                st.session_state.sh_idea_input = DEFAULT_IDEAS["custom"]
                st.rerun()
                
        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
        
        if st.button("✨ Sinh kịch bản Self-heal"):
            if not idea_text.strip():
                st.warning("Vui lòng nhập ý tưởng kịch bản.")
            else:
                with st.spinner("Ollama đang sinh kịch bản Self-heal..."):
                    success, data = generate_selfheal_script(
                        idea_text,
                        st.session_state.sh_script_type,
                        target_scenes=st.session_state.sh_target_scenes
                    )
                    if success and "scenes" in data:
                        st.session_state.sh_final_videos = []
                        st.session_state.sh_scenes = data["scenes"]
                        st.session_state.sh_speakers = data.get("speakers", list(set(s.get("speaker", "Narrator") for s in data["scenes"])))
                        
                        # Khởi tạo config speaker mặc định
                        st.session_state.sh_speaker_config = {}
                        for idx, spk in enumerate(st.session_state.sh_speakers):
                            color_key = list(COLOR_MAP.keys())[idx % len(COLOR_MAP)]
                            st.session_state.sh_speaker_config[spk] = {
                                "has_voice": True,
                                "voice": "en-US-EmmaNeural" if idx % 2 == 0 else "en-US-BrianNeural",
                                "color": COLOR_MAP[color_key],
                                "color_name": color_key
                            }
                        st.success("Đã tạo kịch bản thành công! Cấu hình nhân vật bên dưới.")
                    else:
                        st.error(f"Lỗi sinh kịch bản: {data}")
                        
        # Góp ý chỉnh sửa kịch bản (Yêu cầu 3)
        if st.session_state.sh_scenes:
            st.markdown("### ✍️ Góp ý chỉnh sửa kịch bản hiện tại")
            feedback_mode = st.radio(
                "Chế độ chỉnh sửa",
                ["Góp ý bổ sung (Chỉ cập nhật/chỉnh sửa phân cảnh dựa trên kịch bản hiện có)", 
                 "Viết lại kịch bản hoàn toàn mới từ đầu"],
                key="sh_feedback_mode"
            )
            feedback_text = st.text_area(
                "Nhập nội dung góp ý chỉnh sửa kịch bản",
                value=st.session_state.sh_feedback_input,
                placeholder="Ví dụ (Bổ sung): Thay đổi lời thoại ở Cảnh 2 thành 'Nice to meet you'.\nVí dụ (Viết lại): Hãy viết lại câu chuyện này theo bối cảnh vũ trụ."
            )
            st.session_state.sh_feedback_input = feedback_text
            
            # Gợi ý nhanh cho góp ý
            st.markdown("💡 *Gợi ý nhanh cho góp ý:*")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                if st.button("➕ Viết thêm cảnh mới", key="btn_f_add"):
                    st.session_state.sh_feedback_input = "Hãy viết tiếp thêm 4 phân cảnh nữa nối tiếp câu chuyện để kéo dài video."
                    st.rerun()
            with col_f2:
                if st.button("💬 Dễ hiểu hơn", key="btn_f_easy"):
                    st.session_state.sh_feedback_input = "Hãy điều chỉnh từ vựng trong lời thoại để dễ hiểu và thông dụng hơn cho người mới học."
                    st.rerun()
            with col_f3:
                if st.button("👋 Thêm lời chào", key="btn_f_bye"):
                    st.session_state.sh_feedback_input = "Thay đổi lời thoại của phân cảnh cuối cùng thành lời cảm ơn và chào tạm biệt người xem."
                    st.rerun()
                    
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            if st.button("✨ Cập nhật kịch bản"):
                if not feedback_text.strip():
                    st.warning("Vui lòng nhập nội dung góp ý.")
                else:
                    with st.spinner("AI đang cập nhật kịch bản theo góp ý của bạn..."):
                        if "Góp ý bổ sung" in feedback_mode:
                            success, data = feedback_selfheal_script(
                                st.session_state.sh_scenes,
                                feedback_text,
                                st.session_state.sh_script_type,
                                target_scenes=st.session_state.sh_target_scenes
                            )
                        else:
                            success, data = generate_selfheal_script(
                                feedback_text,
                                st.session_state.sh_script_type,
                                target_scenes=st.session_state.sh_target_scenes
                            )
                            
                        if success and "scenes" in data:
                            st.session_state.sh_final_videos = []
                            st.session_state.sh_scenes = data["scenes"]
                            st.session_state.sh_speakers = data.get("speakers", list(set(s.get("speaker", "Narrator") for s in data["scenes"])))
                            
                            # Cập nhật config speaker cũ
                            for idx, spk in enumerate(st.session_state.sh_speakers):
                                if spk not in st.session_state.sh_speaker_config:
                                    color_key = list(COLOR_MAP.keys())[idx % len(COLOR_MAP)]
                                    st.session_state.sh_speaker_config[spk] = {
                                        "has_voice": True,
                                        "voice": "en-US-EmmaNeural" if idx % 2 == 0 else "en-US-BrianNeural",
                                        "color": COLOR_MAP[color_key],
                                        "color_name": color_key
                                    }
                            st.success("Cập nhật kịch bản thành công!")
                            st.rerun()
                        else:
                            st.error(f"Lỗi cập nhật kịch bản: {data}")

        # Cấu hình Speaker
        if st.session_state.sh_scenes:
            st.markdown("### 👤 Cấu hình nhân vật (Speakers)")
            
            for spk in st.session_state.sh_speakers:
                cfg = st.session_state.sh_speaker_config.get(spk, {
                    "has_voice": True, "voice": "en-US-EmmaNeural", "color": "&H0000FFFF", "color_name": "🟡 Vàng neon"
                })
                
                with st.expander(f"Cấu hình cho speaker: {spk}", expanded=True):
                    col_voice, col_voice_name, col_color = st.columns(3)
                    
                    with col_voice:
                        cfg["has_voice"] = st.checkbox("Có giọng đọc TTS", value=cfg["has_voice"], key=f"voice_chk_{spk}")
                        
                    with col_voice_name:
                        if cfg["has_voice"]:
                            voice_name = st.selectbox(
                                "Chọn giọng đọc",
                                list(TTS_VOICES_EN.keys()),
                                index=list(TTS_VOICES_EN.values()).index(cfg["voice"]) if cfg["voice"] in TTS_VOICES_EN.values() else 0,
                                key=f"voice_sel_{spk}"
                            )
                            cfg["voice"] = TTS_VOICES_EN[voice_name]
                        else:
                            st.info("Speaker im lặng (người dùng đọc).")
                            
                    with col_color:
                        color_name = st.selectbox(
                            "Màu phụ đề Karaoke",
                            list(COLOR_MAP.keys()),
                            index=list(COLOR_MAP.keys()).index(cfg["color_name"]) if cfg.get("color_name") in COLOR_MAP else 0,
                            key=f"color_sel_{spk}"
                        )
                        cfg["color_name"] = color_name
                        cfg["color"] = COLOR_MAP[color_name]
                        
                st.session_state.sh_speaker_config[spk] = cfg

            # data editor cho kịch bản
            st.markdown("#### Bảng phân cảnh chi tiết (Cho phép sửa trực tiếp)")
            
            # Tính thời lượng ước lượng
            est_total_duration = 0.0
            for scene in st.session_state.sh_scenes:
                narration = scene.get("narration", "")
                words_count = len(str(narration).split())
                speaker = scene.get("speaker", "Narrator")
                spk_cfg = st.session_state.sh_speaker_config.get(speaker, {"has_voice": True})
                if spk_cfg.get("has_voice", True):
                    est_dur = (words_count / st.session_state.sh_wpm) * 60.0
                else:
                    est_dur = (words_count / st.session_state.sh_wpm) * 60.0 + st.session_state.sh_pause
                est_total_duration += est_dur
                
            st.info(
                f"📊 **Thống kê kịch bản:** {len(st.session_state.sh_scenes)} phân cảnh | "
                f"⏱️ **Tổng thời lượng ước tính:** ~{est_total_duration:.1f} giây "
                f"(Giới hạn mỗi phần: **{st.session_state.sh_max_duration} giây**)"
            )
            
            df = pd.DataFrame(st.session_state.sh_scenes)
            
            if "speaker" not in df.columns:
                df["speaker"] = "Narrator"
                
            edited_df = st.data_editor(
                df,
                column_config={
                    "scene_num": st.column_config.NumberColumn("STT", disabled=True, width="small"),
                    "speaker": st.column_config.SelectboxColumn("Nhân vật", options=st.session_state.sh_speakers, width="medium"),
                    "narration": st.column_config.TextColumn("Lời thoại tiếng Anh (EN)", width="large"),
                    "translation": st.column_config.TextColumn("Dịch tiếng Việt (VI)", width="large"),
                    "video_prompt": st.column_config.TextColumn("Prompt hình nền thiên nhiên (EN)", width="large")
                },
                num_rows="dynamic",
                use_container_width=True
            )
            
            col_save, col_next = st.columns([1, 4])
            with col_save:
                if st.button("💾 Lưu kịch bản"):
                    st.session_state.sh_scenes = edited_df.to_dict(orient="records")
                    st.session_state.sh_speakers = list(set(s.get("speaker", "Narrator") for s in st.session_state.sh_scenes))
                    st.success("Đã lưu chỉnh sửa!")
                    st.rerun()
                    
            with col_next:
                if st.button("✅ Duyệt kịch bản — Chuyển sang Bước 2"):
                    st.session_state.sh_scenes = edited_df.to_dict(orient="records")
                    
                    for i, scene in enumerate(st.session_state.sh_scenes):
                        scene["audio_path"] = os.path.join(TEMP_DIR, f"sh_scene_{i+1:03d}.mp3")
                        scene["image_path"] = os.path.join(TEMP_DIR, f"sh_scene_{i+1:03d}.png")
                        scene["video_path"] = os.path.join(TEMP_DIR, f"sh_scene_{i+1:03d}.mp4")
                        scene["use_video_ai"] = (st.session_state.sh_image_mode == "Video AI (Wan 2.1)")
                        
                    st.session_state.sh_step = 2
                    st.rerun()

    # --- BƯỚC 2: DUYỆT & SINH TÀI NGUYÊN ---
    elif st.session_state.sh_step == 2:
        st.markdown("### 🎨 Bước 2: Sinh tài nguyên cảnh nền & Giọng đọc")
        
        if st.button("⬅️ Quay lại Bước 1 (Sửa kịch bản)"):
            st.session_state.sh_step = 1
            st.rerun()
            
        st.markdown("---")
        
        # Nút sinh loạt
        if st.button("⚡ Bắt đầu sinh tài nguyên tự động"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 1. Sinh Audio
            status_text.text("Đang sinh giọng đọc TTS cho các phân cảnh được cấu hình...")
            total = len(st.session_state.sh_scenes)
            for i, scene in enumerate(st.session_state.sh_scenes):
                progress_bar.progress(int((i / total) * 35))
                speaker = scene.get("speaker", "Narrator")
                spk_cfg = st.session_state.sh_speaker_config.get(speaker, {"has_voice": True, "voice": "en-US-EmmaNeural"})
                
                if spk_cfg.get("has_voice", True):
                    generate_tts(
                        text=scene.get("narration") or "",
                        output_path=scene["audio_path"],
                        voice=spk_cfg["voice"]
                    )
                    scene["audio_duration"] = get_audio_duration(scene["audio_path"])
                else:
                    scene["audio_duration"] = 0.0
                    
            # 2. Sinh Visuals
            if not st.session_state.sh_use_single_bg:
                sd_scenes = []
                wan_scenes = []
                for i, scene in enumerate(st.session_state.sh_scenes):
                    if scene.get("use_video_ai", False):
                        wan_scenes.append((i, scene))
                    else:
                        sd_scenes.append((i, scene))
                        
                if sd_scenes:
                    status_text.text("Đang sinh ảnh nền thiên nhiên bằng Stable Diffusion...")
                    sd_raw = [s[1] for s in sd_scenes]
                    success, paths = generate_batch_images(
                        scenes=sd_raw,
                        temp_dir=TEMP_DIR,
                        orientation=st.session_state.sh_orientation,
                        style_preset=st.session_state.sh_style_preset
                    )
                    if success:
                        for idx, (orig_idx, scene) in enumerate(sd_scenes):
                            scene["image_path"] = paths[idx]
                            progress_bar.progress(35 + int((idx / len(sd_scenes)) * 30))
                    else:
                        st.error(f"Lỗi sinh ảnh loạt: {paths}")
                        
                if wan_scenes:
                    status_text.text("Đang sinh video nền thiên nhiên bằng Wan 2.1...")
                    wan_raw = [s[1] for s in wan_scenes]
                    success, paths = generate_batch_videos(
                        scenes=wan_raw,
                        temp_dir=TEMP_DIR,
                        orientation=st.session_state.sh_orientation
                    )
                    if success:
                        for idx, (orig_idx, scene) in enumerate(wan_scenes):
                            scene["video_path"] = paths[idx]
                            progress_bar.progress(65 + int((idx / len(wan_scenes)) * 35))
                    else:
                        st.error(f"Lỗi sinh video loạt: {paths}")
            else:
                # Nếu sử dụng 1 nền chung và nguồn là "Sinh video bằng AI (Wan 2.1)"
                if st.session_state.get("sh_bg_source") == "Sinh video bằng AI (Wan 2.1)":
                    bg_file = st.session_state.sh_bg_video_file
                    bg_exists = False
                    if bg_file:
                        bg_path = os.path.join(BACKGROUNDS_DIR, bg_file)
                        if os.path.exists(bg_path):
                            bg_exists = True
                            
                    if not bg_exists:
                        status_text.text("Đang sinh 1 video nền chung duy nhất bằng Wan 2.1 (~15 phút)...")
                        import time
                        bg_name = f"ai_bg_{int(time.time())}.mp4"
                        output_path = os.path.join(BACKGROUNDS_DIR, bg_name)
                        
                        prompt_to_use = st.session_state.get("sh_step2_ai_bg_prompt") or st.session_state.get("sh_ai_bg_prompt") or "A peaceful serene forest river with soft sunlight"
                        success, path = generate_single_video(
                            prompt=prompt_to_use,
                            output_path=output_path,
                            orientation=st.session_state.sh_orientation
                        )
                        if success:
                            st.session_state.sh_bg_video_file = bg_name
                            st.success(f"Đã sinh thành công video nền AI chung: {bg_name}")
                        else:
                            st.error(f"Lỗi sinh video nền AI chung: {path}")
                elif st.session_state.get("sh_bg_source") == "Sinh ảnh bằng AI (Stable Diffusion)":
                    bg_file = st.session_state.sh_bg_video_file
                    bg_exists = False
                    if bg_file:
                        bg_path = os.path.join(BACKGROUNDS_DIR, bg_file)
                        if os.path.exists(bg_path):
                            bg_exists = True
                            
                    if not bg_exists:
                        status_text.text("Đang sinh 1 ảnh nền chung duy nhất bằng Stable Diffusion (~10 giây)...")
                        import time
                        bg_name = f"ai_bg_img_{int(time.time())}.png"
                        output_path = os.path.join(BACKGROUNDS_DIR, bg_name)
                        
                        prompt_to_use = st.session_state.get("sh_step2_ai_bg_prompt_img") or st.session_state.get("sh_ai_bg_prompt_img") or "A peaceful serene forest river with soft sunlight"
                        style_to_use = st.session_state.get("sh_step2_ai_bg_style_preset") or st.session_state.get("sh_ai_bg_style_preset") or "peaceful nature landscape, serene forest river, soft morning light, cinematic, 4k"
                        success, path = generate_single_image(
                            prompt=prompt_to_use,
                            output_path=output_path,
                            orientation=st.session_state.sh_orientation,
                            style_preset=style_to_use
                        )
                        if success:
                            st.session_state.sh_bg_video_file = bg_name
                            st.success(f"Đã sinh thành công ảnh nền AI chung: {bg_name}")
                        else:
                            st.error(f"Lỗi sinh ảnh nền AI chung: {path}")
                progress_bar.progress(100)
                    
            progress_bar.progress(100)
            status_text.text("Đã hoàn thành sinh tài nguyên!")
            st.success("Tất cả tài nguyên đã được chuẩn bị xong.")
            st.rerun()

        # Hiển thị Nền Chung nếu đang chọn chế độ 1 nền
        if st.session_state.sh_use_single_bg:
            st.markdown("### 📺 Nền Chung Đã Chọn")
            bg_file = st.session_state.sh_bg_video_file
            bg_path = ""
            if bg_file:
                bg_path = os.path.join(BACKGROUNDS_DIR, bg_file)
                
            if bg_path and os.path.exists(bg_path):
                ext = os.path.splitext(bg_path)[1].lower()
                is_image = ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
                if is_image:
                    st.image(bg_path, use_column_width=True)
                else:
                    st.video(bg_path)
            else:
                st.warning("⚠️ Chưa có file nền chung. Hãy bấm 'Bắt đầu sinh tài nguyên tự động' hoặc sinh bằng AI bên dưới.")
                
            # Nếu nguồn sinh video bằng AI thì hiển thị thêm nút sinh nhanh tại đây
            if st.session_state.get("sh_bg_source") == "Sinh video bằng AI (Wan 2.1)":
                ai_prompt = st.text_area(
                    "Sửa prompt sinh video nền chung",
                    value=st.session_state.get("sh_ai_bg_prompt", "A peaceful serene forest river with soft sunlight, slow motion, cinematic, 4k"),
                    key="sh_step2_ai_bg_prompt"
                )
                
                if st.button("🎥 Sinh lại video nền chung bằng AI"):
                    with st.spinner("Đang sinh video nền chung bằng Wan 2.1 (~15 phút)..."):
                        import time
                        bg_name = f"ai_bg_{int(time.time())}.mp4"
                        output_path = os.path.join(BACKGROUNDS_DIR, bg_name)
                        success, path = generate_single_video(
                            prompt=ai_prompt,
                            output_path=output_path,
                            orientation=st.session_state.sh_orientation
                        )
                        if success:
                            st.session_state.sh_bg_video_file = bg_name
                            st.success(f"Sinh thành công video nền AI chung: {bg_name}")
                            st.rerun()
                        else:
                            st.error(f"Lỗi sinh video nền AI chung: {path}")
            elif st.session_state.get("sh_bg_source") == "Sinh ảnh bằng AI (Stable Diffusion)":
                ai_prompt_img = st.text_area(
                    "Sửa prompt sinh ảnh nền chung",
                    value=st.session_state.get("sh_ai_bg_prompt_img", "A peaceful serene forest river with soft sunlight, cinematic, 4k"),
                    key="sh_step2_ai_bg_prompt_img"
                )
                
                style_preset = st.text_input(
                    "Sửa style preset sinh ảnh nền chung",
                    value=st.session_state.get("sh_ai_bg_style_preset", "peaceful nature landscape, serene forest river, soft morning light, cinematic, 4k"),
                    key="sh_step2_ai_bg_style_preset"
                )
                
                if st.button("🖼️ Sinh lại ảnh nền chung bằng AI"):
                    with st.spinner("Đang sinh ảnh nền chung bằng Stable Diffusion (~10 giây)..."):
                        import time
                        bg_name = f"ai_bg_img_{int(time.time())}.png"
                        output_path = os.path.join(BACKGROUNDS_DIR, bg_name)
                        success, path = generate_single_image(
                            prompt=ai_prompt_img,
                            output_path=output_path,
                            orientation=st.session_state.sh_orientation,
                            style_preset=style_preset
                        )
                        if success:
                            st.session_state.sh_bg_video_file = bg_name
                            st.success(f"Sinh thành công ảnh nền AI chung: {bg_name}")
                            st.rerun()
                        else:
                            st.error(f"Lỗi sinh ảnh nền AI chung: {path}")
            st.markdown("---")

        # Hiển thị từng phân cảnh
        actual_total_duration = sum(s.get("audio_duration", 0.0) for s in st.session_state.sh_scenes)
        num_parts = max(1, int(actual_total_duration // st.session_state.sh_max_duration) + (1 if actual_total_duration % st.session_state.sh_max_duration > 0.05 else 0))
        
        st.info(
            f"📈 **Thông tin tài nguyên:** Đã chuẩn bị {len(st.session_state.sh_scenes)} phân cảnh.\n\n"
            f"⏱️ **Tổng thời lượng thực tế:** **{actual_total_duration:.1f} giây** | "
            f"📦 **Dự kiến xuất ra:** **{num_parts} phần** (Giới hạn mỗi phần: **{st.session_state.sh_max_duration:.0f} giây**)."
        )
        
        st.markdown("### Danh sách phân cảnh:")
        for i, scene in enumerate(st.session_state.sh_scenes):
            st.markdown("<div class='scene-card'>", unsafe_allow_html=True)
            
            speaker = scene.get("speaker", "Narrator")
            spk_cfg = st.session_state.sh_speaker_config.get(speaker, {"has_voice": True, "voice": "en-US-EmmaNeural"})
            
            # Giao diện gọn gàng hơn nếu dùng video nền chung (Yêu cầu 1 và 2)
            if st.session_state.sh_use_single_bg:
                st.markdown(f"#### 🎬 Phân cảnh {i+1} ({speaker})")
                st.write(f"**EN:** {scene['narration']}")
                st.write(f"**VI:** {scene['translation']}")
                
                if spk_cfg.get("has_voice", True):
                    audio_file = scene["audio_path"]
                    if os.path.exists(audio_file):
                        st.audio(audio_file, format="audio/mp3")
                        scene["audio_duration"] = get_audio_duration(audio_file)
                    else:
                        st.warning("Chưa sinh giọng đọc cho phân cảnh này.")
                        
                    if st.button("🔊 Sinh lại giọng đọc", key=f"sh_btn_tts_{i}"):
                        with st.spinner("Đang sinh giọng..."):
                            generate_tts(scene.get("narration") or "", scene["audio_path"], voice=spk_cfg["voice"])
                            st.rerun()
                else:
                    words_count = len(scene["narration"].split())
                    dur = (words_count / st.session_state.sh_wpm) * 60.0 + st.session_state.sh_pause
                    st.info(f"🔇 Nhân vật im lặng. Thời gian hiển thị dự kiến: {dur:.1f}s")
            else:
                # Luồng 2 cột hiển thị đầy đủ assets
                col_info, col_asset = st.columns([3, 2])
                with col_info:
                    st.markdown(f"#### 🎬 Phân cảnh {i+1} ({speaker})")
                    st.write(f"**EN:** {scene['narration']}")
                    st.write(f"**VI:** {scene['translation']}")
                    
                    use_video = st.checkbox("Dùng Video AI", value=scene.get("use_video_ai", False), key=f"sh_use_vid_{i}")
                    scene["use_video_ai"] = use_video
                    
                    if spk_cfg.get("has_voice", True):
                        audio_file = scene["audio_path"]
                        if os.path.exists(audio_file):
                            st.audio(audio_file, format="audio/mp3")
                            scene["audio_duration"] = get_audio_duration(audio_file)
                        else:
                            st.warning("Chưa sinh giọng đọc cho phân cảnh này.")
                            
                        if st.button("🔊 Sinh lại giọng đọc", key=f"sh_btn_tts_{i}"):
                            with st.spinner("Đang sinh giọng..."):
                                generate_tts(scene.get("narration") or "", scene["audio_path"], voice=spk_cfg["voice"])
                                st.rerun()
                    else:
                        words_count = len(scene["narration"].split())
                        dur = (words_count / st.session_state.sh_wpm) * 60.0 + st.session_state.sh_pause
                        st.info(f"🔇 Nhân vật im lặng. Thời gian hiển thị dự kiến: {dur:.1f}s")
                        
                with col_asset:
                    new_prompt = st.text_input("Prompt hình nền", value=scene["video_prompt"], key=f"sh_prompt_{i}")
                    scene["video_prompt"] = new_prompt
                    
                    if use_video:
                        v_path = scene["video_path"]
                        if os.path.exists(v_path):
                            st.video(v_path)
                        else:
                            st.warning("Chưa sinh video nền.")
                        if st.button("🎥 Tạo lại video nền", key=f"sh_btn_vid_{i}"):
                            with st.spinner("Đang sinh video Wan 2.1..."):
                                generate_single_video(scene["video_prompt"], scene["video_path"], st.session_state.sh_orientation)
                                st.rerun()
                    else:
                        img_path = scene["image_path"]
                        if os.path.exists(img_path):
                            st.image(img_path, use_column_width=True)
                        else:
                            st.warning("Chưa sinh ảnh nền.")
                        if st.button("🖼️ Tạo lại ảnh nền", key=f"sh_btn_img_{i}"):
                            with st.spinner("Đang sinh ảnh SD..."):
                                generate_single_image(scene["video_prompt"], scene["image_path"], st.session_state.sh_orientation, st.session_state.sh_style_preset)
                                st.rerun()
                                
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")
            
        # Kiểm tra đầy đủ tài nguyên
        all_ready = True
        
        # Kiểm tra video nền chung nếu sử dụng
        if st.session_state.sh_use_single_bg:
            bg_file = st.session_state.sh_bg_video_file
            if not bg_file:
                all_ready = False
            else:
                bg_path = os.path.join(BACKGROUNDS_DIR, bg_file)
                if not os.path.exists(bg_path):
                    all_ready = False
                    
        for scene in st.session_state.sh_scenes:
            speaker = scene.get("speaker", "Narrator")
            spk_cfg = st.session_state.sh_speaker_config.get(speaker, {"has_voice": True})
            
            # Chỉ check audio nếu bật video nền chung
            if spk_cfg.get("has_voice", True) and not os.path.exists(scene["audio_path"]):
                all_ready = False
            # Check visual nếu tắt video nền chung
            if not st.session_state.sh_use_single_bg:
                if scene["use_video_ai"] and not os.path.exists(scene["video_path"]):
                    all_ready = False
                if not scene["use_video_ai"] and not os.path.exists(scene["image_path"]):
                    all_ready = False
                    
        if st.button("✅ Duyệt tài nguyên — Chuyển sang Bước 3 (Render)", disabled=not all_ready):
            st.session_state.sh_step = 3
            st.rerun()

    # --- BƯỚC 3: RENDER VIDEO ---
    elif st.session_state.sh_step == 3:
        st.markdown("### 🎬 Bước 3: Render Video Self-heal song ngữ")
        
        if st.button("⬅️ Quay lại Bước 2 (Chỉnh sửa tài nguyên)"):
            st.session_state.sh_step = 2
            st.rerun()
            
        st.markdown("---")
        
        if not st.session_state.sh_music_file:
            st.error("⚠️ Vui lòng chọn một file nhạc nền ở Sidebar trước khi bắt đầu Render.")
        elif st.session_state.sh_use_single_bg and not st.session_state.sh_bg_video_file:
            st.error("⚠️ Bạn đang bật chế độ dùng video nền chung. Vui lòng chọn hoặc tải 1 video nền ở Sidebar.")
        else:
            music_path = os.path.join(TEMP_DIR, "downloads", st.session_state.sh_music_file)
            if not os.path.exists(music_path):
                from src.config import MUSIC_DIR
                music_path = os.path.join(MUSIC_DIR, st.session_state.sh_music_file)
                
            bg_video_path = None
            if st.session_state.sh_use_single_bg:
                bg_video_path = os.path.join(BACKGROUNDS_DIR, st.session_state.sh_bg_video_file)
                
            if st.button("▶️ Bắt đầu Render Video hoàn chỉnh"):
                with st.spinner("Đang biên tập video Self-heal song ngữ (trộn nhạc nền, tạo silence, burn sub ASS)..."):
                    success, videos, err = compile_selfheal_video(
                        scenes=st.session_state.sh_scenes,
                        speaker_config=st.session_state.sh_speaker_config,
                        music_path=music_path,
                        wpm=st.session_state.sh_wpm,
                        orientation=st.session_state.sh_orientation,
                        show_translation=st.session_state.sh_show_translation,
                        max_duration=st.session_state.sh_max_duration,
                        bg_video_path=bg_video_path
                    )
                    if success:
                        st.session_state.sh_final_videos = videos
                        st.success("Render video thành công!")
                    else:
                        st.error(f"Render video thất bại: {err}")
                        
        if st.session_state.sh_final_videos:
            st.markdown("### 📥 Video Thành Phẩm")
            
            if len(st.session_state.sh_final_videos) == 1:
                video_path = st.session_state.sh_final_videos[0]
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
                st.info(f"Video đã được chia thành {len(st.session_state.sh_final_videos)} phần.")
                tab_names = [f"Phần {i+1}" for i in range(len(st.session_state.sh_final_videos))]
                tabs = st.tabs(tab_names)
                for idx, tab in enumerate(tabs):
                    with tab:
                        video_path = st.session_state.sh_final_videos[idx]
                        if os.path.exists(video_path):
                            st.video(video_path)
                            with open(video_path, "rb") as file:
                                st.download_button(
                                    label=f"💾 Tải video Phần {idx+1}",
                                    data=file,
                                    file_name=os.path.basename(video_path),
                                    mime="video/mp4",
                                    key=f"dl_sh_part_{idx}"
                                )
