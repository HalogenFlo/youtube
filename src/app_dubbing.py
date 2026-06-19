# Chức năng: Giao diện người dùng Streamlit cho tính năng Dịch & Lồng tiếng Video Douyin.
# Lý do tạo: Tách biệt UI Dịch & Lồng tiếng ra file riêng để tránh sửa đổi làm hỏng code gốc của app.py.
# Trích dẫn: Sử dụng thiết kế tương thích với app.py, gọi các dịch vụ trong dubbing_service.py.

import os
import streamlit as st
import pandas as pd
import time
from PIL import Image
from src.config import (
    TEMP_DIR, DUBBING_DIR, DUBBING_UPLOAD_DIR,
    TTS_VOICES_VI, TTS_VOICES_EN, OUTPUT_DIR
)
from src.video_downloader import download_douyin_video, download_and_extract, extract_audio
from src.whisper_service import transcribe_with_segments
from src.llm_service import translate_segments_batch
from src.tts_service import generate_tts
from src.dubbing_service import (
    get_video_info, get_video_frame, crop_and_trim_video, save_uploaded_video,
    adjust_tts_speed, mix_dubbed_audio, compile_dubbed_video, build_dubbing_ass_subtitle
)

def run_dubbing_ui():
    st.title("🎙️ Dịch & Lồng tiếng Video Douyin (AI Local)")
    st.markdown("Tính năng giúp tự động tải hoặc upload video, cắt xén, dịch lời thoại và lồng tiếng nói khớp thời lượng hoàn toàn local.")

    # --- KHỞI TẠO STATE ---
    if "dub_step" not in st.session_state:
        st.session_state.dub_step = 1
    if "dub_source_type" not in st.session_state:
        st.session_state.dub_source_type = "Dán link video"
    if "dub_video_url" not in st.session_state:
        st.session_state.dub_video_url = ""
    if "dub_source_video_path" not in st.session_state:
        st.session_state.dub_source_video_path = ""
    if "dub_source_audio_path" not in st.session_state:
        st.session_state.dub_source_audio_path = ""
    if "dub_video_info" not in st.session_state:
        st.session_state.dub_video_info = {}
    if "dub_trim_range" not in st.session_state:
        st.session_state.dub_trim_range = (0.0, 10.0)
    if "dub_crop_x" not in st.session_state:
        st.session_state.dub_crop_x = 0
    if "dub_crop_y" not in st.session_state:
        st.session_state.dub_crop_y = 0
    if "dub_crop_w" not in st.session_state:
        st.session_state.dub_crop_w = 0
    if "dub_crop_h" not in st.session_state:
        st.session_state.dub_crop_h = 0
    if "dub_aspect_preset" not in st.session_state:
        st.session_state.dub_aspect_preset = "Giữ nguyên"
    if "dub_target_lang" not in st.session_state:
        st.session_state.dub_target_lang = "Tiếng Việt"
    if "dub_voice" not in st.session_state:
        st.session_state.dub_voice = ""
    if "dub_tts_rate" not in st.session_state:
        st.session_state.dub_tts_rate = "+0%"
    if "dub_bg_volume_mode" not in st.session_state:
        st.session_state.dub_bg_volume_mode = "Giữ nhỏ (10-15%)"
    if "dub_sub_mode" not in st.session_state:
        st.session_state.dub_sub_mode = "Song ngữ gốc-dịch"
    if "dub_segments" not in st.session_state:
        st.session_state.dub_segments = None
    if "dub_detected_lang" not in st.session_state:
        st.session_state.dub_detected_lang = ""
    if "dub_trimmed_video_path" not in st.session_state:
        st.session_state.dub_trimmed_video_path = ""
    if "dub_trimmed_audio_path" not in st.session_state:
        st.session_state.dub_trimmed_audio_path = ""
    if "dub_output_video_path" not in st.session_state:
        st.session_state.dub_output_video_path = ""

    # --- SIDEBAR CẤU HÌNH ---
    st.sidebar.markdown("### 🎙️ Cấu hình Lồng tiếng")
    
    if st.sidebar.button("🔄 Reset quy trình"):
        st.session_state.dub_step = 1
        st.session_state.dub_source_video_path = ""
        st.session_state.dub_source_audio_path = ""
        st.session_state.dub_video_info = {}
        st.session_state.dub_segments = None
        st.session_state.dub_detected_lang = ""
        st.session_state.dub_trimmed_video_path = ""
        st.session_state.dub_trimmed_audio_path = ""
        st.session_state.dub_output_video_path = ""
        st.rerun()

    # Chọn ngôn ngữ đích
    target_lang = st.sidebar.selectbox(
        "Dịch sang ngôn ngữ",
        ["Tiếng Việt", "Tiếng Anh (English)"],
        index=0 if st.session_state.dub_target_lang == "Tiếng Việt" else 1
    )
    st.session_state.dub_target_lang = target_lang

    # Chọn giọng đọc TTS tương ứng
    if target_lang == "Tiếng Việt":
        voice_opts = TTS_VOICES_VI
        lang_code = "vi"
    else:
        voice_opts = TTS_VOICES_EN
        lang_code = "en"
        
    voice_label = st.sidebar.selectbox(
        "Giọng đọc lồng tiếng",
        list(voice_opts.keys()),
        index=0
    )
    st.session_state.dub_voice = voice_opts[voice_label]

    # Cấu hình rate (tốc độ đọc)
    rate_val = st.sidebar.slider(
        "Tốc độ đọc (rate)",
        min_value=-30,
        max_value=30,
        value=0,
        step=5,
        format="%d%%"
    )
    # Format thành dạng edge-tts rate (+10%, -5%)
    st.session_state.dub_tts_rate = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"

    # Chế độ âm thanh nền
    bg_vol = st.sidebar.radio(
        "Âm thanh nền gốc",
        ["Giữ nhỏ (10-15%)", "Tắt hoàn toàn"],
        index=0 if st.session_state.dub_bg_volume_mode == "Giữ nhỏ (10-15%)" else 1
    )
    st.session_state.dub_bg_volume_mode = bg_vol

    # Chế độ phụ đề
    sub_mode = st.sidebar.radio(
        "Chế độ phụ đề hiển thị",
        ["Song ngữ gốc-dịch", "Chỉ ngôn ngữ dịch", "Không phụ đề"],
        index=["Song ngữ gốc-dịch", "Chỉ ngôn ngữ dịch", "Không phụ đề"].index(st.session_state.dub_sub_mode)
    )
    st.session_state.dub_sub_mode = sub_mode

    # --- TIẾN TRÌNH CÁC BƯỚC ---
    # Vẽ các tabs giả lập bước
    cols_step = st.columns(3)
    steps_title = ["1. Tải & Cắt xén", "2. Transcribe & Dịch", "3. Lồng tiếng & Render"]
    for i, title in enumerate(steps_title):
        step_num = i + 1
        with cols_step[i]:
            if st.session_state.dub_step == step_num:
                st.markdown(f"**👉 {title}**")
                st.markdown("---")
            else:
                st.markdown(f"*{title}*")

    # ==================== BƯỚC 1: TẢI & CẮT XÉN ====================
    if st.session_state.dub_step == 1:
        st.subheader("Bước 1: Chọn nguồn video & Cấu hình cắt xén")
        
        source_type = st.radio(
            "Nguồn video đầu vào",
            ["Dán link video", "Upload file từ máy tính"],
            index=0 if st.session_state.dub_source_type == "Dán link video" else 1
        )
        st.session_state.dub_source_type = source_type
        
        # Nhập nguồn
        has_video = False
        
        if source_type == "Dán link video":
            url_input = st.text_input("Nhập link video (Douyin, TikTok, YouTube...)", value=st.session_state.dub_video_url)
            st.session_state.dub_video_url = url_input
            
            if st.button("⬇️ Tải video"):
                if not url_input.strip():
                    st.warning("Vui lòng nhập đường dẫn URL.")
                else:
                    with st.spinner("Đang kết nối và tải video... (Quá trình này chạy offline với local headers)"):
                        # Nếu là Douyin, TikTok
                        if "douyin.com" in url_input or "tiktok.com" in url_input:
                            success, v_path, a_path, err_msg = download_douyin_video(url_input)
                        else:
                            success, v_path, a_path, err_msg = download_and_extract(url_input)
                            
                        if success:
                            st.session_state.dub_source_video_path = v_path
                            st.session_state.dub_source_audio_path = a_path
                            st.success(f"Tải video thành công! Lưu tại: {os.path.basename(v_path)}")
                            # Lấy thông tin video
                            info_success, info = get_video_info(v_path)
                            if info_success:
                                st.session_state.dub_video_info = info
                                st.session_state.dub_trim_range = (0.0, info["duration"])
                            st.rerun()
                        else:
                            st.error(err_msg)
        else:
            uploaded_file = st.file_uploader("Chọn file video từ máy tính của bạn", type=["mp4", "mkv", "webm", "avi", "mov"])
            if uploaded_file is not None:
                # Tạo tên file độc nhất để lưu
                temp_filename = f"upload_{int(time.time())}_{uploaded_file.name}"
                upload_dest = os.path.join(DUBBING_UPLOAD_DIR, temp_filename)
                
                # Tránh lưu lại nhiều lần cùng một file
                if not st.session_state.dub_source_video_path or os.path.basename(st.session_state.dub_source_video_path) != temp_filename:
                    with st.spinner("Đang lưu file upload..."):
                        success, path = save_uploaded_video(uploaded_file, upload_dest)
                        if success:
                            st.session_state.dub_source_video_path = path
                            
                            # Tách audio
                            video_dir, video_file = os.path.split(path)
                            video_name, _ = os.path.splitext(video_file)
                            audio_path = os.path.join(video_dir, f"{video_name}.wav")
                            
                            success_audio, audio_err = extract_audio(path, audio_path)
                            if success_audio:
                                st.session_state.dub_source_audio_path = audio_path
                                # Lấy thông tin video
                                info_success, info = get_video_info(path)
                                if info_success:
                                    st.session_state.dub_video_info = info
                                    st.session_state.dub_trim_range = (0.0, info["duration"])
                                st.success("Upload và trích xuất audio thành công!")
                                st.rerun()
                            else:
                                st.error(f"Upload thành công nhưng tách audio thất bại: {audio_err}")

        # Hiển thị cấu hình trim / crop nếu đã có video nguồn
        if st.session_state.dub_source_video_path and os.path.exists(st.session_state.dub_source_video_path):
            st.markdown("---")
            st.markdown("### ✂️ Thiết lập Trim & Crop vùng")
            
            info = st.session_state.dub_video_info
            st.info(f"Thông số video gốc: Độ phân giải: **{info.get('width')}x{info.get('height')}** | Thời lượng: **{info.get('duration')}s** | FPS: **{info.get('fps')}**")
            
            # Trim slider
            duration = info.get("duration", 10.0)
            trim_range = st.slider(
                "Phạm vi thời gian cắt (Trim) - Giây",
                min_value=0.0,
                max_value=float(duration),
                value=st.session_state.dub_trim_range,
                step=0.5
            )
            st.session_state.dub_trim_range = trim_range
            
            # Crop preset và Sliders
            col1, col2 = st.columns(2)
            with col1:
                aspect_preset = st.selectbox(
                    "Tỷ lệ khung hình mẫu (Aspect Ratio Preset)",
                    ["Giữ nguyên", "9:16 (Dọc)", "16:9 (Ngang)", "1:1 (Vuông)"],
                    index=["Giữ nguyên", "9:16 (Dọc)", "16:9 (Ngang)", "1:1 (Vuông)"].index(st.session_state.dub_aspect_preset)
                )
                st.session_state.dub_aspect_preset = aspect_preset
                
                # Tự động tính toán crop mặc định dựa trên preset
                orig_w, orig_h = info.get("width", 1080), info.get("height", 1920)
                
                if aspect_preset == "9:16 (Dọc)":
                    # Cắt dọc ở giữa
                    target_w = int(orig_h * (9/16))
                    if target_w > orig_w:
                        target_w = orig_w
                        target_h = int(orig_w * (16/9))
                    else:
                        target_h = orig_h
                    default_w = target_w
                    default_h = target_h
                    default_x = (orig_w - target_w) // 2
                    default_y = (orig_h - target_h) // 2
                elif aspect_preset == "16:9 (Ngang)":
                    target_h = int(orig_w * (9/16))
                    if target_h > orig_h:
                        target_h = orig_h
                        target_w = int(orig_h * (16/9))
                    else:
                        target_w = orig_w
                    default_w = target_w
                    default_h = target_h
                    default_x = (orig_w - target_w) // 2
                    default_y = (orig_h - target_h) // 2
                elif aspect_preset == "1:1 (Vuông)":
                    size = min(orig_w, orig_h)
                    default_w = size
                    default_h = size
                    default_x = (orig_w - size) // 2
                    default_y = (orig_h - size) // 2
                else:
                    # Giữ nguyên
                    default_w = orig_w
                    default_h = orig_h
                    default_x = 0
                    default_y = 0
                    
            with col2:
                # Chỉ số sliders
                crop_w = st.number_input("Chiều rộng (Width)", min_value=10, max_value=orig_w, value=default_w)
                crop_h = st.number_input("Chiều cao (Height)", min_value=10, max_value=orig_h, value=default_h)
                crop_x = st.number_input("Tọa độ X (Left)", min_value=0, max_value=orig_w - crop_w, value=default_x)
                crop_y = st.number_input("Tọa độ Y (Top)", min_value=0, max_value=orig_h - crop_h, value=default_y)
                
                st.session_state.dub_crop_w = crop_w
                st.session_state.dub_crop_h = crop_h
                st.session_state.dub_crop_x = crop_x
                st.session_state.dub_crop_y = crop_y

            # Nút Xem trước vùng crop và Xác nhận
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("👁️ Xem trước vùng crop", use_container_width=True):
                    preview_img = os.path.join(DUBBING_DIR, "preview.jpg")
                    success_frame, p_path = get_video_frame(
                        st.session_state.dub_source_video_path,
                        st.session_state.dub_trim_range[0],
                        preview_img
                    )
                    if success_frame:
                        try:
                            img = Image.open(p_path)
                            if st.session_state.dub_crop_w > 0 and st.session_state.dub_crop_h > 0:
                                # Pillow crop: (left, upper, right, lower)
                                cropped_img = img.crop((
                                    st.session_state.dub_crop_x,
                                    st.session_state.dub_crop_y,
                                    st.session_state.dub_crop_x + st.session_state.dub_crop_w,
                                    st.session_state.dub_crop_y + st.session_state.dub_crop_h
                                ))
                                st.image(cropped_img, caption=f"Vùng Crop đã chọn ({st.session_state.dub_crop_w}x{st.session_state.dub_crop_h})", use_container_width=True)
                            else:
                                st.image(img, caption="Khung hình gốc", use_container_width=True)
                        except Exception as e:
                            st.error(f"Lỗi load ảnh xem trước: {e}")
                    else:
                        st.error("Không lấy được frame hình để preview. Có thể FFmpeg bị lỗi.")

            with col_btn2:
                if st.button("✅ Cắt xén video & Chuyển sang Bước 2", type="primary", use_container_width=True):
                    with st.spinner("Đang cắt xén video (Trim & Crop)..."):
                        trimmed_v_file = os.path.join(DUBBING_DIR, f"trimmed_{int(time.time())}.mp4")
                        success_crop, crop_path = crop_and_trim_video(
                            st.session_state.dub_source_video_path,
                            trimmed_v_file,
                            st.session_state.dub_trim_range[0],
                            st.session_state.dub_trim_range[1],
                            st.session_state.dub_crop_x,
                            st.session_state.dub_crop_y,
                            st.session_state.dub_crop_w,
                            st.session_state.dub_crop_h
                        )
                        if success_crop:
                            st.session_state.dub_trimmed_video_path = crop_path
                            
                            # Tách âm thanh của video đã cắt xén để transcribe
                            trimmed_a_file = os.path.join(DUBBING_DIR, f"trimmed_{int(time.time())}.wav")
                            success_audio, audio_path = extract_audio(crop_path, trimmed_a_file)
                            if success_audio:
                                st.session_state.dub_trimmed_audio_path = audio_path
                                # Reset segments cũ
                                st.session_state.dub_segments = None
                                st.session_state.dub_step = 2
                                st.success("Cắt xén video thành công!")
                                st.rerun()
                            else:
                                st.error(f"Không thể trích xuất âm thanh từ video đã cắt: {audio_path}")
                        else:
                            st.error(f"Cắt xén video thất bại: {crop_path}")

    # ==================== BƯỚC 2: TRANSCRIBE & DỊCH ====================
    elif st.session_state.dub_step == 2:
        st.subheader("Bước 2: Phân tích giọng nói & Biên dịch phụ đề")
        
        # Nếu chưa chạy Whisper & LLM dịch thuật
        if st.session_state.dub_segments is None:
            with st.spinner("Đang chạy Whisper tự động nhận diện giọng nói và mốc thời gian..."):
                success_whisp, segments, detected_lang = transcribe_with_segments(st.session_state.dub_trimmed_audio_path)
                if success_whisp:
                    st.session_state.dub_detected_lang = detected_lang
                    
                    if not segments:
                        st.warning("Whisper không nhận diện được bất kỳ đoạn hội thoại nào trong video này. Bạn có thể tự thêm dòng thoại ở bảng bên dưới.")
                        st.session_state.dub_segments = []
                    else:
                        with st.spinner(f"Đã nhận diện ngôn ngữ: '{detected_lang}'. Đang gọi local LLM dịch thuật sang {st.session_state.dub_target_lang}..."):
                            # Chuyển mã ngôn ngữ đích
                            tgt_code = "vi" if st.session_state.dub_target_lang == "Tiếng Việt" else "en"
                            translated_segs = translate_segments_batch(segments, detected_lang, tgt_code)
                            st.session_state.dub_segments = translated_segs
                            st.rerun()
                else:
                    st.error(f"Whisper gặp lỗi khi phân tích âm thanh: {detected_lang}")
                    
        # Giao diện sửa bảng thoại
        if st.session_state.dub_segments is not None:
            st.markdown(f"Ngôn ngữ nguồn phát hiện: **{st.session_state.dub_detected_lang.upper()}** | Ngôn ngữ dịch đích: **{st.session_state.dub_target_lang}**")
            
            st.markdown("Hãy chỉnh sửa nội dung bản dịch hoặc mốc thời gian dưới đây nếu cần thiết:")
            
            # Tạo DataFrame hiển thị
            data = []
            for idx, seg in enumerate(st.session_state.dub_segments):
                data.append({
                    "STT": idx + 1,
                    "Bắt đầu (s)": seg["start"],
                    "Kết thúc (s)": seg["end"],
                    "Thoại gốc": seg["text"],
                    "Thoại dịch": seg.get("translated_text", "")
                })
            df = pd.DataFrame(data)
            
            # Sử dụng data_editor cho người dùng chỉnh sửa trực tiếp
            edited_df = st.data_editor(
                df,
                column_config={
                    "STT": st.column_config.NumberColumn("STT", disabled=True),
                    "Bắt đầu (s)": st.column_config.NumberColumn("Bắt đầu (s)", format="%.2f"),
                    "Kết thúc (s)": st.column_config.NumberColumn("Kết thúc (s)", format="%.2f"),
                    "Thoại gốc": st.column_config.TextColumn("Thoại gốc"),
                    "Thoại dịch": st.column_config.TextColumn("Thoại dịch"),
                },
                use_container_width=True,
                num_rows="dynamic"
            )
            
            # Nút dịch lại và duyệt
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button("🔄 Dịch lại toàn bộ (LLM)", use_container_width=True):
                    # Lưu tạm các thay đổi của cột Thoại gốc trước khi dịch lại
                    temp_segs = []
                    for _, row in edited_df.iterrows():
                        temp_segs.append({
                            "text": row["Thoại gốc"],
                            "start": row["Bắt đầu (s)"],
                            "end": row["Kết thúc (s)"]
                        })
                    with st.spinner("Đang gọi local LLM dịch lại bảng..."):
                        tgt_code = "vi" if st.session_state.dub_target_lang == "Tiếng Việt" else "en"
                        translated_segs = translate_segments_batch(temp_segs, st.session_state.dub_detected_lang, tgt_code)
                        st.session_state.dub_segments = translated_segs
                        st.success("Đã cập nhật bản dịch mới từ LLM!")
                        st.rerun()
            
            with col_b2:
                # Nút cập nhật chay (chỉ lưu chỉnh sửa thủ công của người dùng)
                if st.button("💾 Lưu thay đổi", use_container_width=True):
                    new_segments = []
                    for _, row in edited_df.iterrows():
                        new_segments.append({
                            "text": row["Thoại gốc"],
                            "start": float(row["Bắt đầu (s)"]),
                            "end": float(row["Kết thúc (s)"]),
                            "translated_text": row["Thoại dịch"]
                        })
                    st.session_state.dub_segments = new_segments
                    st.success("Đã lưu chỉnh sửa thủ công!")
                    
            with col_b3:
                if st.button("✅ Duyệt bản dịch → Bước 3", type="primary", use_container_width=True):
                    new_segments = []
                    for _, row in edited_df.iterrows():
                        new_segments.append({
                            "text": row["Thoại gốc"],
                            "start": float(row["Bắt đầu (s)"]),
                            "end": float(row["Kết thúc (s)"]),
                            "translated_text": row["Thoại dịch"]
                        })
                    st.session_state.dub_segments = new_segments
                    st.session_state.dub_step = 3
                    st.rerun()

    # ==================== BƯỚC 3: LỒNG TIẾNG & RENDER ====================
    elif st.session_state.dub_step == 3:
        st.subheader("Bước 3: Lồng tiếng & Xuất video thành phẩm")
        
        # Nếu chưa render xong video thành phẩm
        if not st.session_state.dub_output_video_path:
            st.info("Nhấp vào nút dưới đây để bắt đầu sinh giọng nói local, khớp mốc thời gian và burn phụ đề.")
            
            if st.button("▶️ Bắt đầu Render Video", type="primary", use_container_width=True):
                if not st.session_state.dub_segments:
                    st.error("Không có đoạn thoại nào để lồng tiếng. Quay lại Bước 2 và thêm ít nhất 1 dòng thoại.")
                else:
                    # Chạy quy trình render
                    tts_dir = os.path.join(DUBBING_DIR, "tts_segs")
                    if not os.path.exists(tts_dir):
                        os.makedirs(tts_dir)
                    
                    p_text = st.empty()
                    p_bar = st.progress(0.0)
                    
                    num_segs = len(st.session_state.dub_segments)
                    tts_seg_files = []
                    
                    # 3.1 Sinh TTS & 3.2 Adjust speed
                    for idx, seg in enumerate(st.session_state.dub_segments):
                        p_text.text(f"🕒 [1/3] Đang sinh giọng đọc cho câu {idx+1}/{num_segs}...")
                        
                        raw_tts_path = os.path.join(tts_dir, f"seg_{idx:03d}.mp3")
                        # Sinh file TTS
                        success_tts, err_tts = generate_tts(
                            text=seg["translated_text"],
                            output_path=raw_tts_path,
                            voice=st.session_state.dub_voice,
                            rate=st.session_state.dub_tts_rate
                        )
                        if not success_tts:
                            st.error(f"Lỗi khi sinh giọng đọc tại câu {idx+1}: {err_tts}")
                            return
                            
                        p_text.text(f"🕒 [1/3] Đang co giãn tốc độ giọng đọc câu {idx+1}/{num_segs}...")
                        adjusted_tts_path = os.path.join(tts_dir, f"seg_{idx:03d}_adjusted.wav")
                        target_dur = seg["end"] - seg["start"]
                        
                        # Co giãn tốc độ khớp với timeline
                        success_speed, err_speed = adjust_tts_speed(raw_tts_path, target_dur, adjusted_tts_path)
                        if not success_speed:
                            st.warning(f"Lỗi điều chỉnh tốc độ tại câu {idx+1}. Fallback dùng file gốc: {err_speed}")
                            adjusted_tts_path = raw_tts_path
                            
                        tts_seg_files.append({
                            "adjusted_tts_path": adjusted_tts_path,
                            "start": seg["start"],
                            "end": seg["end"]
                        })

                        
                        # Cập nhật progress bar (sinh TTS chiếm tối đa 50% tiến trình)
                        p_bar.progress(float((idx + 1) / num_segs) * 0.5)
                        
                    # 3.3 Mix Audio
                    p_text.text("🕒 [2/3] Đang mix giọng đọc mới với âm thanh nền video...")
                    mixed_audio_file = os.path.join(DUBBING_DIR, "mixed_dubbed_audio.wav")
                    success_mix, err_mix = mix_dubbed_audio(
                        original_audio_path=st.session_state.dub_trimmed_audio_path,
                        tts_segments=tts_seg_files,
                        output_audio_path=mixed_audio_file,
                        bg_volume_mode=st.session_state.dub_bg_volume_mode
                    )
                    if not success_mix:
                        st.error(f"Lỗi mix âm thanh: {err_mix}")
                        return
                    p_bar.progress(0.7)
                    
                    # 3.4 Tạo phụ đề ASS
                    p_text.text("🕒 [3/3] Đang khởi tạo phụ đề ASS...")
                    sub_file = os.path.join(DUBBING_DIR, "dubbing_sub.ass")
                    width_v = st.session_state.dub_video_info.get("width", 1080)
                    height_v = st.session_state.dub_video_info.get("height", 1920)
                    orientation = "vertical" if width_v < height_v else "horizontal"
                    
                    success_sub, err_sub = build_dubbing_ass_subtitle(
                        segments=st.session_state.dub_segments,
                        output_path=sub_file,
                        mode=st.session_state.dub_sub_mode,
                        orientation=orientation
                    )
                    if not success_sub:
                        st.warning(f"Lỗi tạo phụ đề: {err_sub}. Sẽ xuất video không phụ đề.")
                        sub_file = ""
                    p_bar.progress(0.85)
                    
                    # 3.5 Render
                    p_text.text("🎬 Đang render video cuối cùng (Burn phụ đề & Ghép âm thanh)...")
                    final_video_file = os.path.join(OUTPUT_DIR, f"dubbed_video_{int(time.time())}.mp4")
                    
                    success_comp, err_comp = compile_dubbed_video(
                        video_path=st.session_state.dub_trimmed_video_path,
                        dubbed_audio_path=mixed_audio_file,
                        subtitle_path=sub_file if st.session_state.dub_sub_mode != "Không phụ đề" else "",
                        output_path=final_video_file,
                        subtitle_mode=st.session_state.dub_sub_mode
                    )
                    
                    if success_comp:
                        st.session_state.dub_output_video_path = final_video_file
                        p_bar.progress(1.0)
                        p_text.text("Đã xuất bản video thành công! 🎉")
                        st.success("Quá trình Dịch & Lồng tiếng Video đã hoàn tất.")
                        st.rerun()
                    else:
                        st.error(f"Lỗi ghép nối video: {err_comp}")
        else:
            # Hiển thị video thành phẩm
            st.subheader("🎉 Video thành phẩm dịch & lồng tiếng")
            st.video(st.session_state.dub_output_video_path)
            
            # Nút download
            with open(st.session_state.dub_output_video_path, "rb") as f:
                video_bytes = f.read()
                
            st.download_button(
                label="⬇️ Tải video thành phẩm về máy",
                data=video_bytes,
                file_name=os.path.basename(st.session_state.dub_output_video_path),
                mime="video/mp4",
                use_container_width=True
            )
            
            # Nút làm lại
            if st.button("🔄 Tạo video khác", use_container_width=True):
                st.session_state.dub_output_video_path = ""
                st.session_state.dub_step = 1
                st.session_state.dub_segments = None
                st.rerun()
