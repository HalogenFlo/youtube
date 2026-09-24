# Chức năng: Giao diện Web Streamlit cho quy trình Nhập Prompt -> Sinh Kịch Bản -> Google Flow vẽ cảnh -> Render Video.
# Lý do tạo: Đáp ứng 100% mong muốn của người dùng: Trực quan, dễ dùng trên Web, hiển thị kịch bản và tự động chạy Google Flow.

import os
import sys
import time
import urllib.request
import streamlit as st
import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import OUTPUT_DIR, TEMP_DIR, TTS_VOICES_VI, TTS_VOICES_EN, DEFAULT_IMAGE_STYLE
from src.llm_service import generate_script
from src.tts_service import generate_tts
from src.flow_image_service import generate_flow_image
from src.whisper_service import get_word_timestamps
from src.video_compiler import compile_video_pipeline
from src.flow_browser_service import get_flow_controller


def check_chrome_flow_status() -> bool:
    """Kiểm tra nhanh trong 0.2s xem cổng CDP 9222 có phản hồi không."""
    try:
        req = urllib.request.Request("http://127.0.0.1:9222/json/version", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=0.2) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_audio_duration(file_path: str) -> float:
    try:
        from mutagen.mp3 import MP3
        return MP3(file_path).info.length
    except Exception:
        pass
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(file_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return 5.0


def run_batch_ui():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="font-size: 2.6rem; font-weight: 800; background: linear-gradient(90deg, #ff7e5f, #feb47b, #86e3ce); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🎬 AI VIDEO PRODUCER — GOOGLE FLOW PIPELINE
        </h1>
        <p style="color: #8b949e; font-size: 1.15rem;">
            Nhập Prompt ➔ AI Tự Động Sinh Kịch Bản ➔ Google Flow Vẽ Bối Cảnh Từng Cảnh ➔ Xuất Video Hoàn Chỉnh
        </p>
    </div>
    """, unsafe_allow_html=True)

    # State quản lý
    if "current_scripts" not in st.session_state:
        st.session_state.current_scripts = []
    if "completed_videos" not in st.session_state:
        st.session_state.completed_videos = []

    # Thanh trạng thái Google Flow
    is_cdp_connected = check_chrome_flow_status()
    col_st1, col_st2 = st.columns([3, 1])
    with col_st1:
        if is_cdp_connected:
            st.success("🟢 **Google Flow CDP Sẵn Sàng**: Trình duyệt Chrome đã mở cổng 9222 và sẵn sàng kết nối Google Flow!")
        else:
            st.info("ℹ️ **Cổng 9222**: Khi bấm tạo video, hệ thống sẽ tự động kết nối với Chrome Google Flow của bạn.")
    with col_st2:
        if st.button("🔄 Kiểm tra kết nối", key="btn_refresh_status"):
            st.rerun()

    st.markdown("---")

    # BƯỚC 1: NHẬP PROMPT
    st.markdown("### 📝 Bước 1: Nhập Prompt / Ý Tưởng Video")
    col_p1, col_p2 = st.columns([3, 2])

    with col_p1:
        prompt_text = st.text_area(
            "Nhập chủ đề hoặc prompt chi tiết của bạn:",
            value="3 bí ẩn khoa học kỳ thú nhất vũ trụ mà con người chưa có lời giải đáp. Phong cách hài hước, cuốn hút.",
            height=120,
            help="Bạn có thể nhập 1 chủ đề chung hoặc nhập danh sách nhiều chủ đề (mỗi dòng 1 video)."
        )

    with col_p2:
        num_videos = st.number_input("Số lượng video muốn tạo:", min_value=1, max_value=10, value=1, step=1)
        lang = st.selectbox("Ngôn ngữ video:", ["Tiếng Việt", "English"], index=0)
        lang_code = "vi" if lang == "Tiếng Việt" else "en"
        voice_default = "vi-VN-HoaiMyNeural" if lang_code == "vi" else "en-US-EmmaNeural"

    # Nút bấm hành động
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        btn_gen_script = st.button("✨ 1. Tạo Kịch Bản Phân Cảnh (Xem trước kịch bản)", use_container_width=True)
    with col_btn2:
        btn_one_click = st.button("⚡ TẠO TỰ ĐỘNG TỪ A-Z (Kịch bản ➔ Google Flow ➔ Video)", type="primary", use_container_width=True)

    # XỬ LÝ 1: SINH KỊCH BẢN ĐỂ XEM TRƯỚC
    if btn_gen_script:
        if not prompt_text.strip():
            st.warning("Vui lòng nhập Prompt / Ý tưởng trước.")
        else:
            st.session_state.current_scripts = []
            lines = [l.strip() for l in prompt_text.strip().split("\n") if l.strip()]
            
            with st.spinner("AI đang động não viết kịch bản phân cảnh..."):
                for idx in range(num_videos):
                    topic = lines[idx] if idx < len(lines) else (prompt_text.strip() if num_videos == 1 else f"{prompt_text.strip()} (Tập {idx+1})")
                    ok, script_data = generate_script(topic=topic, style_preset=DEFAULT_IMAGE_STYLE, language=lang_code)
                    if ok and "scenes" in script_data:
                        st.session_state.current_scripts.append({
                            "title": topic,
                            "video_index": idx + 1,
                            "scenes": script_data["scenes"]
                        })
                    else:
                        st.error(f"Lỗi tạo kịch bản cho video {idx+1}: {script_data}")
            
            if st.session_state.current_scripts:
                st.success(f"🎉 Đã sinh thành công kịch bản cho {len(st.session_state.current_scripts)} video! Bạn có thể xem chi tiết bên dưới.")

    # HIỂN THỊ KỊCH BẢN ĐÃ SINH
    if st.session_state.current_scripts:
        st.markdown("---")
        st.markdown("### 📋 Kịch Bản Chi Tiết Cho Từng Video")
        
        for sc_item in st.session_state.current_scripts:
            v_idx = sc_item["video_index"]
            v_title = sc_item["title"]
            scenes = sc_item["scenes"]
            
            with st.expander(f"🎬 Kịch bản Video #{v_idx}: {v_title} ({len(scenes)} phân cảnh)", expanded=True):
                df_scenes = pd.DataFrame(scenes)
                col_rename = {
                    "scene_num": "Cảnh #",
                    "narration": "Lời thoại (TTS)",
                    "video_prompt": "Mô tả bối cảnh gửi Google Flow (Visual Prompt)"
                }
                st.dataframe(df_scenes.rename(columns=col_rename), use_container_width=True)

        st.markdown("### 🍌 Bước 2: Dùng Google Flow Vẽ Bối Cảnh & Xuất Video")
        if st.button("🚀 BẮT ĐẦU DÙNG GOOGLE FLOW TẠO CÁC VIDEO THEO KỊCH BẢN TRÊN", type="primary", use_container_width=True):
            btn_one_click = True  # Kích hoạt quy trình sản xuất theo các kịch bản đã có

    # XỬ LÝ 2: CHẠY QUY TRÌNH SẢN XUẤT GOOGLE FLOW & RENDER VIDEO
    if btn_one_click:
        if not prompt_text.strip():
            st.warning("Vui lòng nhập Prompt / Ý tưởng trước.")
            return

        # Đảm bảo kết nối Google Flow
        if not is_cdp_connected:
            with st.spinner("Đang tự động kết nối Google Chrome cổng 9222..."):
                controller = get_flow_controller()
                controller.connect()

        # Nếu chưa có kịch bản, tự động sinh kịch bản ngay
        if not st.session_state.current_scripts:
            lines = [l.strip() for l in prompt_text.strip().split("\n") if l.strip()]
            with st.spinner("Đang sinh kịch bản cho các video..."):
                for idx in range(num_videos):
                    topic = lines[idx] if idx < len(lines) else (prompt_text.strip() if num_videos == 1 else f"{prompt_text.strip()} (Tập {idx+1})")
                    ok, script_data = generate_script(topic=topic, style_preset=DEFAULT_IMAGE_STYLE, language=lang_code)
                    if ok and "scenes" in script_data:
                        st.session_state.current_scripts.append({
                            "title": topic,
                            "video_index": idx + 1,
                            "scenes": script_data["scenes"]
                        })

        if not st.session_state.current_scripts:
            st.error("Không thể tạo kịch bản. Vui lòng kiểm tra lại Ollama hoặc Prompt.")
            return

        # BẮT ĐẦU CHẠY VÒNG LẶP SẢN XUẤT TỪNG VIDEO
        st.session_state.completed_videos = []
        prog_bar = st.progress(0)
        status_txt = st.empty()
        log_txt = st.empty()

        total_vids = len(st.session_state.current_scripts)
        run_ts = time.strftime("%Y%m%d_%H%M%S")
        batch_dir = os.path.join(TEMP_DIR, f"web_batch_{run_ts}")
        os.makedirs(batch_dir, exist_ok=True)

        for v_i, sc_item in enumerate(st.session_state.current_scripts):
            v_idx = sc_item["video_index"]
            v_title = sc_item["title"]
            scenes = sc_item["scenes"]
            v_work_dir = os.path.join(batch_dir, f"video_{v_idx}")
            os.makedirs(v_work_dir, exist_ok=True)

            status_txt.markdown(f"**▶ Video {v_idx}/{total_vids}:** `{v_title}`")

            # 1. Sinh Audio TTS
            for s_i, sc in enumerate(scenes):
                sc_num = sc.get("scene_num", s_i + 1)
                audio_file = os.path.join(v_work_dir, f"scene_{sc_num:03d}.mp3")
                generate_tts(text=sc["narration"], output_path=audio_file, voice=voice_default)
                sc["audio_path"] = audio_file
                sc["audio_duration"] = get_audio_duration(audio_file)

            # 2. Sinh ảnh bối cảnh Google Flow cho TỪNG PHÂN CẢNH
            for s_i, sc in enumerate(scenes):
                sc_num = sc.get("scene_num", s_i + 1)
                img_file = os.path.join(v_work_dir, f"scene_{sc_num:03d}_bg.png")
                sc["image_path"] = img_file
                sc["use_video_ai"] = False

                prompt_sc = sc.get("video_prompt") or sc.get("narration") or "Stickman cinematic scene"
                log_txt.text(f"[Google Flow] Đang vẽ Cảnh {sc_num}/{len(scenes)}: \"{prompt_sc[:50]}...\"")

                ok_flow, res_flow = generate_flow_image(
                    prompt=prompt_sc,
                    output_path=img_file,
                    orientation="vertical",
                    style_preset=DEFAULT_IMAGE_STYLE,
                    fallback_to_sd=True
                )
                if not ok_flow or not os.path.exists(img_file):
                    st.error(f"Lỗi khi vẽ cảnh {sc_num}: {res_flow}")
                    return


            # 3. Phân tích Timestamps Whisper
            log_txt.text(f"[Whisper] Đang đồng bộ phụ đề Karaoke cho video {v_idx}...")
            all_words = []
            cum_time = 0.0
            for sc in scenes:
                ok_w, words = get_word_timestamps(sc["audio_path"], language=lang_code)
                if ok_w and words:
                    for w in words:
                        all_words.append({
                            "word": w["word"],
                            "start": w["start"] + cum_time,
                            "end": w["end"] + cum_time
                        })
                cum_time += sc.get("audio_duration", 5.0)

            # 4. Biên tập & Render Video
            log_txt.text(f"[MoviePy & FFmpeg] Đang ghép các bối cảnh và burn phụ đề cho video {v_idx}...")
            ok_ren, compiled_vids, err_ren = compile_video_pipeline(
                scenes=scenes,
                words_timestamps=all_words,
                max_duration=120.0,
                orientation="vertical"
            )

            if ok_ren and compiled_vids:
                final_out = os.path.join(OUTPUT_DIR, f"video_batch_{run_ts}_v{v_idx:02d}.mp4")
                import shutil
                shutil.copy2(compiled_vids[0], final_out)
                st.session_state.completed_videos.append(final_out)

            prog_bar.progress(int((v_i + 1) / total_vids * 100))

        prog_bar.progress(100)
        status_txt.success(f"🎉 ĐÃ HOÀN TẤT: Xuất bản thành công {len(st.session_state.completed_videos)}/{total_vids} video hoàn chỉnh bằng Google Flow!")
        log_txt.empty()

    # HIỂN THỊ DANH SÁCH VIDEO THÀNH PHẨM
    if st.session_state.completed_videos:
        st.markdown("---")
        st.markdown("### 📥 Video Thành Phẩm Hoàn Chỉnh")
        cols = st.columns(min(len(st.session_state.completed_videos), 3))
        for idx, vid_path in enumerate(st.session_state.completed_videos):
            with cols[idx % len(cols)]:
                st.markdown(f"#### 🎬 Video #{idx + 1}")
                st.caption(f"`{os.path.basename(vid_path)}`")
                if os.path.exists(vid_path):
                    st.video(vid_path)
                    with open(vid_path, "rb") as f:
                        st.download_button(
                            label=f"💾 Tải Video #{idx + 1}",
                            data=f,
                            file_name=os.path.basename(vid_path),
                            mime="video/mp4",
                            key=f"dl_v_{idx}"
                        )
