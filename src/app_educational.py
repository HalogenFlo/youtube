# Chức năng: Giao diện người dùng Streamlit cho tính năng Bài dạy AI Slideshow Video.
# Lý do tạo: Tách biệt giao diện và logic của tính năng bài giảng để dễ dàng phát triển và bảo trì.
# Trích dẫn: Tái sử dụng các module sinh ảnh, video AI, TTS và compile video hiện có từ hệ thống.

import os
import streamlit as st
import pandas as pd
from src.config import (
    TEMP_DIR, OUTPUT_DIR, DEFAULT_EDUCATIONAL_STYLE, DEFAULT_EDUCATIONAL_SCENES,
    TTS_VOICES_VI, TTS_VOICE_DEFAULT, WAN_DEFAULT_STEPS, get_gpu_benchmark_sec_per_step
)
from src.llm_service import (
    generate_educational_script, generate_script_from_doc, feedback_educational_script
)
from src.tts_service import generate_tts
from src.image_service import generate_batch_images, generate_single_image
from src.video_gen_service import generate_batch_videos, generate_single_video
from src.whisper_service import get_word_timestamps
from src.video_compiler import compile_video_pipeline

def get_audio_duration(file_path: str) -> float:
    """Trả về thời lượng file audio sử dụng MoviePy AudioFileClip."""
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(file_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return 5.0

def run_educational_ui():
    # --- KHỞI TẠO STATE CHO EDUCATIONAL SLIDESHOW ---
    if "edu_step" not in st.session_state:
        st.session_state.edu_step = 1
    if "edu_scenes" not in st.session_state:
        st.session_state.edu_scenes = []
    if "edu_topic" not in st.session_state:
        st.session_state.edu_topic = ""
    if "edu_doc_content" not in st.session_state:
        st.session_state.edu_doc_content = ""
    if "edu_feedback_input" not in st.session_state:
        st.session_state.edu_feedback_input = ""
    if "edu_style_preset" not in st.session_state:
        st.session_state.edu_style_preset = DEFAULT_EDUCATIONAL_STYLE
    if "edu_target_scenes" not in st.session_state:
        st.session_state.edu_target_scenes = DEFAULT_EDUCATIONAL_SCENES
    if "edu_orientation" not in st.session_state:
        st.session_state.edu_orientation = "vertical"
    if "edu_image_mode" not in st.session_state:
        st.session_state.edu_image_mode = "Nhanh (Ảnh AI)"
    if "edu_tts_voice" not in st.session_state:
        st.session_state.edu_tts_voice = TTS_VOICE_DEFAULT
    if "edu_tts_rate" not in st.session_state:
        st.session_state.edu_tts_rate = "+0%"
    if "edu_max_duration" not in st.session_state:
        st.session_state.edu_max_duration = 60.0
    if "edu_wan_steps" not in st.session_state:
        st.session_state.edu_wan_steps = WAN_DEFAULT_STEPS
    if "edu_wan_measured_sec_per_step" not in st.session_state:
        st.session_state.edu_wan_measured_sec_per_step = get_gpu_benchmark_sec_per_step()
    if "edu_final_videos" not in st.session_state:
        st.session_state.edu_final_videos = []

    # --- SIDEBAR CẤU HÌNH ---
    st.sidebar.markdown("### 📚 Cấu hình Bài dạy AI")
    
    if st.sidebar.button("🔄 Reset toàn bộ (Tạo lại từ đầu)"):
        st.session_state.edu_step = 1
        st.session_state.edu_scenes = []
        st.session_state.edu_topic = ""
        st.session_state.edu_doc_content = ""
        st.session_state.edu_feedback_input = ""
        st.session_state.edu_final_videos = []
        st.rerun()

    # Cấu hình video
    st.sidebar.markdown("#### 🎬 Định dạng Đầu ra")
    st.session_state.edu_orientation = st.sidebar.radio(
        "Hướng video",
        ["Dọc (9:16 — Shorts/TikTok)", "Ngang (16:9 — YouTube)"],
        index=0 if st.session_state.edu_orientation == "vertical" else 1
    )
    st.session_state.edu_orientation = "vertical" if "Dọc" in st.session_state.edu_orientation else "horizontal"

    st.session_state.edu_image_mode = st.sidebar.radio(
        "Chế độ hình ảnh",
        ["Nhanh (Ảnh AI)", "Video AI (Wan 2.1)"],
        index=0 if st.session_state.edu_image_mode == "Nhanh (Ảnh AI)" else 1
    )

    # Cấu hình giọng đọc
    st.sidebar.markdown("#### 🎙️ Giọng đọc & Tốc độ")
    voice_labels = list(TTS_VOICES_VI.keys())
    voice_values = list(TTS_VOICES_VI.values())
    default_voice_idx = voice_values.index(st.session_state.edu_tts_voice) if st.session_state.edu_tts_voice in voice_values else 0
    selected_voice_label = st.sidebar.selectbox(
        "Chọn giọng đọc",
        voice_labels,
        index=default_voice_idx
    )
    st.session_state.edu_tts_voice = TTS_VOICES_VI[selected_voice_label]

    st.session_state.edu_tts_rate = st.sidebar.slider(
        "Tốc độ đọc",
        min_value=-30,
        max_value=30,
        value=int(st.session_state.edu_tts_rate.replace("%", "").replace("+", "")),
        step=5,
        format="%d%%"
    )
    st.session_state.edu_tts_rate = f"{st.session_state.edu_tts_rate:+.0f}%"

    # Phong cách hình ảnh
    st.sidebar.markdown("#### 🎨 Phong cách Visual")
    st.session_state.edu_style_preset = st.sidebar.text_input(
        "Phong cách hình ảnh mặc định",
        value=st.session_state.edu_style_preset
    )

    # Thời lượng & Số phân cảnh
    st.sidebar.markdown("#### ⏱️ Thời lượng & Phân cảnh")
    st.session_state.edu_max_duration = st.sidebar.number_input(
        "Thời lượng tối đa 1 video phần (giây)",
        min_value=15.0,
        max_value=300.0,
        value=st.session_state.edu_max_duration,
        step=5.0
    )

    st.session_state.edu_target_scenes = st.sidebar.slider(
        "Số phân cảnh mong muốn",
        min_value=4,
        max_value=20,
        value=st.session_state.edu_target_scenes,
        step=1
    )

    # Cấu hình Wan 2.1
    if st.session_state.edu_image_mode == "Video AI (Wan 2.1)":
        st.sidebar.markdown("#### 🎥 Cấu hình Video AI (Wan 2.1)")
        
        # Inference Steps (Inference Quality Presets)
        steps_mode = st.sidebar.selectbox(
            "Chất lượng sinh Video AI",
            ["Tốc độ (20 steps)", "Cân bằng (35 steps)", "Chất lượng (50 steps)", "Tùy chỉnh"],
            index=2 # Mặc định là chất lượng
        )
        
        if steps_mode == "Tốc độ (20 steps)":
            st.session_state.edu_wan_steps = 20
        elif steps_mode == "Cân bằng (35 steps)":
            st.session_state.edu_wan_steps = 35
        elif steps_mode == "Chất lượng (50 steps)":
            st.session_state.edu_wan_steps = 50
        else:
            st.session_state.edu_wan_steps = st.sidebar.slider(
                "Số bước lập (Steps)",
                min_value=10,
                max_value=100,
                value=st.session_state.edu_wan_steps,
                step=5
            )

        # Hiển thị ước tính thời gian sinh cho mỗi phân cảnh
        sec_per_step = st.session_state.edu_wan_measured_sec_per_step
        est_sec_per_video = sec_per_step * st.session_state.edu_wan_steps
        est_min_per_video = est_sec_per_video / 60.0
        
        st.sidebar.info(
            f"⏱️ **Ước tính sinh video:**\n"
            f"- Tốc độ máy: **{sec_per_step:.2f}** giây/step\n"
            f"- Sinh 1 clip ~5s: **{est_min_per_video:.1f}** phút\n"
            f"- Tổng {st.session_state.edu_target_scenes} phân cảnh: **{(est_min_per_video * st.session_state.edu_target_scenes / 60.0):.1f}** giờ"
        )

    # --- MAIN UI AREA ---
    st.title("📚 Bài dạy AI Slideshow")
    st.write("Tạo video hướng dẫn học tập, chia sẻ kiến thức công nghệ từ từ khóa hoặc tài liệu.")

    # Thanh tiến trình 3 bước
    step_cols = st.columns(3)
    steps_titles = ["📝 1. Kịch bản", "🎨 2. Tài nguyên", "🎬 3. Render"]
    for i, title in enumerate(steps_titles):
        with step_cols[i]:
            if st.session_state.edu_step == i + 1:
                st.markdown(f"**[ {title} ]**")
            else:
                st.markdown(f"<span style='color: gray'>{title}</span>", unsafe_allow_html=True)
    st.markdown("---")

    # --- BƯỚC 1: BIÊN SOẠN KỊCH BẢN ---
    if st.session_state.edu_step == 1:
        st.markdown("### 📝 Bước 1: Soạn thảo kịch bản bài dạy")
        
        input_mode = st.radio(
            "Chọn phương thức đầu vào",
            ["Nhập từ khóa/chủ đề", "Dán tài liệu văn bản"],
            horizontal=True
        )

        if input_mode == "Nhập từ khóa/chủ đề":
            # Gợi ý nhanh
            st.write("💡 Gợi ý nhanh chủ đề:")
            sug_cols = st.columns(6)
            suggestions = [
                ("🐳 Docker", "Docker cho người mới bắt đầu"),
                ("🤖 ChatGPT", "Cách viết prompt ChatGPT hiệu quả"),
                ("🔀 Git", "Quy trình làm việc với Git cơ bản"),
                ("🐍 Python", "Học lập trình Python trong 5 phút"),
                ("⚛️ React", "React Hooks là gì và cách dùng"),
                ("🔥 Firebase", "Firebase là gì và các dịch vụ cốt lõi")
            ]
            for idx, (label, suggestion_topic) in enumerate(suggestions):
                with sug_cols[idx]:
                    if st.button(label, key=f"edu_sug_{idx}"):
                        st.session_state.edu_topic = suggestion_topic
                        st.session_state.edu_trigger_gen = True

            topic_input = st.text_input(
                "Nhập từ khóa hoặc chủ đề bài dạy:",
                value=st.session_state.edu_topic,
                placeholder="Ví dụ: Giới thiệu về Docker và Container"
            )
            st.session_state.edu_topic = topic_input

            trigger_script_gen = st.button("✨ Sinh kịch bản bài dạy") or st.session_state.get("edu_trigger_gen", False)
            if trigger_script_gen:
                st.session_state.edu_trigger_gen = False
                if not st.session_state.edu_topic.strip():
                    st.warning("Vui lòng nhập chủ đề bài giảng.")
                else:
                    with st.spinner("Ollama đang soạn thảo kịch bản bài dạy..."):
                        success, data = generate_educational_script(
                            topic=st.session_state.edu_topic,
                            style_preset=st.session_state.edu_style_preset,
                            language="vi",
                            target_scenes=st.session_state.edu_target_scenes
                        )
                        if success:
                            st.session_state.edu_scenes = data.get("scenes", [])
                            st.success("Đã sinh kịch bản thành công!")
                        else:
                            st.error(f"Lỗi sinh kịch bản: {data}")

        else:  # Dán tài liệu văn bản
            doc_input = st.text_area(
                "Dán tài liệu học tập hoặc bài viết của bạn tại đây:",
                value=st.session_state.edu_doc_content,
                placeholder="Dán nội dung tài liệu, bài giảng hoặc hướng dẫn kỹ thuật dài...",
                height=250
            )
            st.session_state.edu_doc_content = doc_input

            if st.button("✨ Chuyển tài liệu thành kịch bản"):
                if not st.session_state.edu_doc_content.strip():
                    st.warning("Vui lòng dán tài liệu nội dung.")
                else:
                    with st.spinner("Ollama đang phân tích tài liệu và soạn kịch bản..."):
                        success, data = generate_script_from_doc(
                            doc_content=st.session_state.edu_doc_content,
                            style_preset=st.session_state.edu_style_preset,
                            language="vi",
                            target_scenes=st.session_state.edu_target_scenes
                        )
                        if success:
                            st.session_state.edu_scenes = data.get("scenes", [])
                            st.success("Đã chuyển đổi kịch bản thành công từ tài liệu!")
                        else:
                            st.error(f"Lỗi chuyển kịch bản: {data}")

        # Hiển thị kịch bản để chỉnh sửa và duyệt
        if st.session_state.edu_scenes:
            st.markdown("#### Kịch bản phân cảnh:")
            df = pd.DataFrame(st.session_state.edu_scenes)
            
            edited_df = st.data_editor(
                df,
                column_config={
                    "scene_num": st.column_config.NumberColumn("STT", disabled=True, width="small"),
                    "narration": st.column_config.TextColumn("Lời thoại (Tiếng Việt giảng dạy)", width="large"),
                    "video_prompt": st.column_config.TextColumn("Prompt hình ảnh/video (Tiếng Anh)", width="large")
                },
                num_rows="dynamic",
                use_container_width=True
            )

            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("💾 Lưu kịch bản"):
                    st.session_state.edu_scenes = edited_df.to_dict(orient="records")
                    st.success("Đã lưu thay đổi!")
            with col_btn2:
                if st.button("✅ Duyệt kịch bản — Chuyển sang Bước 2"):
                    st.session_state.edu_scenes = edited_df.to_dict(orient="records")
                    # Khởi tạo đường dẫn lưu tài nguyên
                    for i, scene in enumerate(st.session_state.edu_scenes):
                        scene["audio_path"] = os.path.join(TEMP_DIR, f"edu_scene_{i+1:03d}.mp3")
                        scene["image_path"] = os.path.join(TEMP_DIR, f"edu_scene_{i+1:03d}.png")
                        scene["video_path"] = os.path.join(TEMP_DIR, f"edu_scene_{i+1:03d}.mp4")
                        scene["use_video_ai"] = (st.session_state.edu_image_mode == "Video AI (Wan 2.1)")
                    
                    st.session_state.edu_step = 2
                    st.rerun()

            # Góp ý chỉnh sửa kịch bản
            st.markdown("---")
            st.markdown("#### 💬 Góp ý bổ sung cho kịch bản")
            feedback_text = st.text_area(
                "Nhập yêu cầu chỉnh sửa (Ví dụ: 'Thêm ví dụ mã nguồn ở scene 3', 'Đổi prompt visual sang tone màu sáng hơn')",
                value=st.session_state.edu_feedback_input
            )
            st.session_state.edu_feedback_input = feedback_text

            if st.button("💬 Gửi góp ý bổ sung"):
                if not st.session_state.edu_feedback_input.strip():
                    st.warning("Vui lòng nhập nội dung góp ý.")
                else:
                    with st.spinner("Ollama đang chỉnh sửa kịch bản theo yêu cầu..."):
                        success, data = feedback_educational_script(
                            current_script=st.session_state.edu_scenes,
                            feedback=st.session_state.edu_feedback_input,
                            style_preset=st.session_state.edu_style_preset,
                            language="vi"
                        )
                        if success:
                            st.session_state.edu_scenes = data.get("scenes", [])
                            st.success("Đã cập nhật kịch bản theo góp ý!")
                            st.rerun()
                        else:
                            st.error(f"Lỗi khi sửa kịch bản: {data}")

    # --- BƯỚC 2: SINH TÀI NGUYÊN ---
    elif st.session_state.edu_step == 2:
        st.markdown("### 🎨 Bước 2: Sinh tài nguyên cho từng phân cảnh")
        
        if st.button("⬅️ Quay lại Bước 1 (Sửa kịch bản)"):
            st.session_state.edu_step = 1
            st.rerun()

        st.markdown("---")

        # Nút sinh toàn bộ tài nguyên
        if st.button("⚡ Bắt đầu sinh toàn bộ tài nguyên tự động"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 1. Sinh Audio TTS
            status_text.text("Đang sinh giọng đọc giảng dạy TTS cho các phân cảnh...")
            total = len(st.session_state.edu_scenes)
            for i, scene in enumerate(st.session_state.edu_scenes):
                progress_bar.progress(int((i / total) * 30))
                generate_tts(
                    text=scene["narration"],
                    output_path=scene["audio_path"],
                    voice=st.session_state.edu_tts_voice,
                    rate=st.session_state.edu_tts_rate
                )
                scene["audio_duration"] = get_audio_duration(scene["audio_path"])

            # 2. Sinh Visual
            sd_scenes = []
            wan_scenes = []
            for i, scene in enumerate(st.session_state.edu_scenes):
                if scene.get("use_video_ai", False):
                    wan_scenes.append((i, scene))
                else:
                    sd_scenes.append((i, scene))

            # Sinh loạt ảnh SD
            if sd_scenes:
                status_text.text("Đang sinh ảnh AI bằng Stable Diffusion...")
                sd_raw_scenes = [s[1] for s in sd_scenes]
                success, paths = generate_batch_images(
                    scenes=sd_raw_scenes,
                    temp_dir=TEMP_DIR,
                    orientation=st.session_state.edu_orientation,
                    style_preset=st.session_state.edu_style_preset
                )
                if success:
                    for idx, (original_idx, scene) in enumerate(sd_scenes):
                        scene["image_path"] = paths[idx]
                        progress_bar.progress(30 + int((idx / len(sd_scenes)) * 30))
                else:
                    st.error(f"Lỗi sinh ảnh loạt: {paths}")

            # Sinh loạt video Wan 2.1
            if wan_scenes:
                status_text.text("Đang sinh video AI bằng Wan 2.1 (Quá trình này tốn nhiều thời gian)...")
                wan_raw_scenes = [s[1] for s in wan_scenes]
                success, paths, elapsed = generate_batch_videos(
                    scenes=wan_raw_scenes,
                    temp_dir=TEMP_DIR,
                    orientation=st.session_state.edu_orientation,
                    num_inference_steps=st.session_state.edu_wan_steps
                )
                if success and paths and elapsed > 0:
                    total_steps = len(wan_raw_scenes) * st.session_state.edu_wan_steps
                    st.session_state.edu_wan_measured_sec_per_step = elapsed / total_steps
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

        for i, scene in enumerate(st.session_state.edu_scenes):
            st.markdown("<div style='border: 1px solid #444; border-radius: 5px; padding: 15px; margin-bottom: 15px;'>", unsafe_allow_html=True)
            col_info, col_asset = st.columns([3, 2])

            with col_info:
                st.markdown(f"#### 🎬 Phân cảnh {i+1}")
                new_narration = st.text_area(
                    f"Lời thoại phân cảnh {i+1}",
                    value=scene["narration"],
                    key=f"edu_narr_{i}",
                    height=70
                )
                scene["narration"] = new_narration

                use_video = st.checkbox(
                    "Sử dụng Video AI (Wan 2.1) thay vì Ảnh AI",
                    value=scene.get("use_video_ai", False),
                    key=f"edu_use_video_{i}"
                )
                scene["use_video_ai"] = use_video

                # TTS Audio
                audio_file = scene["audio_path"]
                if os.path.exists(audio_file):
                    st.audio(audio_file, format="audio/mp3")
                    scene["audio_duration"] = get_audio_duration(audio_file)
                    st.caption(f"Thời lượng: {scene['audio_duration']:.2f} giây")
                else:
                    st.warning("Chưa sinh giọng đọc cho cảnh này.")

                if st.button("🔊 Sinh lại giọng đọc", key=f"edu_btn_tts_{i}"):
                    with st.spinner("Đang sinh giọng đọc..."):
                        success, path = generate_tts(
                            text=scene["narration"],
                            output_path=scene["audio_path"],
                            voice=st.session_state.edu_tts_voice,
                            rate=st.session_state.edu_tts_rate
                        )
                        if success:
                            scene["audio_duration"] = get_audio_duration(path)
                            st.success("Đã cập nhật giọng đọc!")
                            st.rerun()
                        else:
                            st.error(path)

            with col_asset:
                new_prompt = st.text_input(
                    f"Prompt visual phân cảnh {i+1}",
                    value=scene["video_prompt"],
                    key=f"edu_prompt_{i}"
                )
                scene["video_prompt"] = new_prompt

                if use_video:
                    v_path = scene["video_path"]
                    if os.path.exists(v_path):
                        st.video(v_path)
                    else:
                        st.warning("Chưa sinh clip video cho cảnh này.")

                    if st.button("🎥 Tạo lại clip Video AI", key=f"edu_btn_vid_{i}"):
                        with st.spinner("Đang chạy Wan 2.1 sinh video (~15 phút)..."):
                            success, path, elapsed = generate_single_video(
                                prompt=scene["video_prompt"],
                                output_path=scene["video_path"],
                                orientation=st.session_state.edu_orientation,
                                num_inference_steps=st.session_state.edu_wan_steps
                            )
                            if success and elapsed > 0:
                                st.session_state.edu_wan_measured_sec_per_step = elapsed / st.session_state.edu_wan_steps
                            if success:
                                st.success("Sinh video thành công!")
                                st.rerun()
                            else:
                                st.error(path)
                else:
                    img_path = scene["image_path"]
                    if os.path.exists(img_path):
                        st.image(img_path, use_column_width=True)
                    else:
                        st.warning("Chưa sinh ảnh cho cảnh này.")

                    if st.button("🖼️ Tạo lại ảnh AI", key=f"edu_btn_img_{i}"):
                        with st.spinner("Đang chạy SD sinh ảnh..."):
                            success, path = generate_single_image(
                                prompt=scene["video_prompt"],
                                output_path=scene["image_path"],
                                orientation=st.session_state.edu_orientation,
                                style_preset=st.session_state.edu_style_preset
                            )
                            if success:
                                st.success("Sinh ảnh thành công!")
                                st.rerun()
                            else:
                                st.error(path)

            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")

        all_ready = True
        for scene in st.session_state.edu_scenes:
            if not os.path.exists(scene["audio_path"]):
                all_ready = False
            if scene["use_video_ai"] and not os.path.exists(scene["video_path"]):
                all_ready = False
            if not scene["use_video_ai"] and not os.path.exists(scene["image_path"]):
                all_ready = False

        if not all_ready:
            st.info("💡 Mẹo: Hãy sinh toàn bộ tài nguyên tự động trước để dễ dàng kiểm tra và duyệt.")

        if st.button("✅ Duyệt tài nguyên — Chuyển sang Bước 3 (Render)", disabled=not all_ready):
            st.session_state.edu_step = 3
            st.rerun()

    # --- BƯỚC 3: RENDER & XUẤT BẢN ---
    elif st.session_state.edu_step == 3:
        st.markdown("### 🎬 Bước 3: Tiến hành Render Video & Xuất bản")

        if st.button("⬅️ Quay lại Bước 2 (Chỉnh sửa tài nguyên)"):
            st.session_state.edu_step = 2
            st.rerun()

        st.markdown("---")

        if st.button("▶️ Bắt đầu Render Video hoàn chỉnh"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.text("Đang phân tích giọng nói để lấy timestamps từ Faster-Whisper...")
            progress_bar.progress(25)

            all_words = []
            cumulative_time = 0.0
            total_scenes = len(st.session_state.edu_scenes)
            whisper_success = True

            for idx, scene in enumerate(st.session_state.edu_scenes):
                status_text.text(f"Đang phân tích timestamps cho Phân cảnh {idx+1}/{total_scenes}...")
                success, words = get_word_timestamps(
                    scene["audio_path"],
                    language="vi"
                )
                if success:
                    for w in words:
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
                status_text.text("Đang xử lý ghép nối clip và burn phụ đề bằng MoviePy & FFmpeg...")
                progress_bar.progress(60)

                success, videos, err_msg = compile_video_pipeline(
                    scenes=st.session_state.edu_scenes,
                    words_timestamps=all_words,
                    max_duration=st.session_state.edu_max_duration,
                    orientation=st.session_state.edu_orientation
                )

                progress_bar.progress(100)
                if success:
                    st.session_state.edu_final_videos = videos
                    status_text.text("Biên tập video hoàn thành xuất sắc!")
                    st.success("Tất cả các phần video đã được render thành công!")
                else:
                    status_text.text("Có lỗi xảy ra khi render.")
                    st.error(f"Chi tiết lỗi render: {err_msg}")

        # Hiển thị kết quả
        if st.session_state.edu_final_videos:
            st.markdown("### 📥 Video Thành Phẩm")

            if len(st.session_state.edu_final_videos) == 1:
                video_path = st.session_state.edu_final_videos[0]
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
                st.info(f"Video vượt quá {st.session_state.edu_max_duration} giây và được chia làm {len(st.session_state.edu_final_videos)} phần.")
                tab_names = [f"Phần {i+1}" for i in range(len(st.session_state.edu_final_videos))]
                tabs = st.tabs(tab_names)

                for idx, tab in enumerate(tabs):
                    with tab:
                        video_path = st.session_state.edu_final_videos[idx]
                        if os.path.exists(video_path):
                            st.video(video_path)
                            with open(video_path, "rb") as file:
                                st.download_button(
                                    label=f"💾 Tải video Phần {idx+1}",
                                    data=file,
                                    file_name=os.path.basename(video_path),
                                    mime="video/mp4",
                                    key=f"edu_dl_part_{idx}"
                                )
