# Chức năng: Giao diện Streamlit sản xuất video tự động hàng loạt từ Prompt (Auto Batch Pipeline).
# Lý do tạo: Đáp ứng trọn vẹn yêu cầu người dùng: nhập prompt -> tự động sinh kịch bản -> lặp tạo nhiều video hoàn chỉnh.
# Trích dẫn: Tích hợp với src/batch_producer.py và src/flow_browser_service.py.

import os
import sys
import time
import streamlit as st
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.batch_producer import run_batch_video_loop
from src.config import OUTPUT_DIR, TTS_VOICES_VI, TTS_VOICES_EN, DEFAULT_IMAGE_STYLE
from src.flow_browser_service import get_flow_controller


def check_chrome_flow_status() -> bool:
    """Kiểm tra xem Chrome Google Flow (cổng CDP 9222) có đang sẵn sàng không."""
    try:
        controller = get_flow_controller()
        return controller.connect()
    except Exception:
        return False


def run_batch_ui():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(90deg, #ff7e5f, #feb47b, #86e3ce); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            ⚡ TỰ ĐỘNG SẢN XUẤT NHIỀU VIDEO (AUTO BATCH PIPELINE)
        </h1>
        <p style="color: #8b949e; font-size: 1.1rem;">
            Nhập ý tưởng/prompt ➔ AI tự động viết kịch bản ➔ Google Flow vẽ bối cảnh từng cảnh ➔ Render xuất xưởng hàng loạt video hoàn chỉnh.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Khởi tạo state kết quả nếu chưa có
    if "batch_completed_videos" not in st.session_state:
        st.session_state.batch_completed_videos = []
    if "batch_is_running" not in st.session_state:
        st.session_state.batch_is_running = False

    # Khung kiểm tra trạng thái Google Flow CDP
    col_status_1, col_status_2 = st.columns([3, 1])
    with col_status_1:
        is_cdp_connected = check_chrome_flow_status()
        if is_cdp_connected:
            st.success("🟢 **Google Flow CDP sẵn sàng**: Trình duyệt Chrome đã kết nối cổng 9222 và sẵn sàng sinh bối cảnh AI!")
        else:
            st.warning("🟠 **Chrome Google Flow chưa kết nối cổng 9222**: Hãy chắc chắn Chrome đã mở với cờ `--remote-debugging-port=9222` để dùng Google Flow.")
    with col_status_2:
        if st.button("🔄 Kiểm tra kết nối CDP", key="btn_check_cdp"):
            st.rerun()

    st.markdown("---")

    # Form nhập liệu chính
    st.markdown("### 📝 1. Thiết lập Prompt & Số lượng video")
    
    col_input, col_config = st.columns([3, 2])

    with col_input:
        default_prompt = (
            "Top những bí ẩn khoa học kỳ thú nhất vũ trụ mà con người chưa có lời giải đáp.\n"
            "Giải thích bằng phong cách dí dỏm, lôi cuốn và dễ hiểu."
        )
        prompt_input = st.text_area(
            "Nhập Prompt / Ý tưởng hoặc Danh sách các chủ đề (Mỗi dòng 1 chủ đề):",
            value=default_prompt,
            height=150,
            help="Nếu nhập 1 chủ đề và chọn tạo 3 video, AI sẽ tự động chia thành 3 phần video hấp dẫn. Nếu nhập nhiều dòng, mỗi dòng sẽ là 1 video riêng."
        )

    with col_config:
        batch_count = st.slider(
            "Số lượng video muốn tạo (Vòng lặp batch):",
            min_value=1,
            max_value=10,
            value=2,
            step=1,
            help="Hệ thống sẽ tự động chạy vòng lặp sinh lần lượt từng video."
        )

        lang_choice = st.selectbox(
            "Ngôn ngữ video & Giọng đọc:",
            ["Tiếng Việt (vi-VN)", "English (en-US)"],
            index=0
        )
        lang_code = "vi" if "Tiếng Việt" in lang_choice else "en"

        orientation_choice = st.selectbox(
            "Định dạng khung hình:",
            ["Dọc 9:16 (TikTok / YouTube Shorts / Reels)", "Ngang 16:9 (YouTube Video)"],
            index=0
        )
        orientation = "vertical" if "Dọc" in orientation_choice else "horizontal"

        engine_choice = st.selectbox(
            "Mô hình sinh hình ảnh bối cảnh:",
            ["🍌 Google Flow (Nano Banana Pro / Khóa nhân vật Stickman)", "💻 Stable Diffusion 1.5 (Local)"],
            index=0
        )
        image_engine = "flow" if "Google Flow" in engine_choice else "sd"

    # Giọng đọc TTS
    voices_dict = TTS_VOICES_VI if lang_code == "vi" else TTS_VOICES_EN
    selected_voice = list(voices_dict.values())[0]

    st.markdown("---")

    # Nút bắt đầu thực thi
    btn_start = st.button(
        f"🚀 BẮT ĐẦU TỰ ĐỘNG TẠO {batch_count} VIDEO THEO KỊCH BẢN",
        type="primary",
        use_container_width=True
    )

    if btn_start:
        if not prompt_input.strip():
            st.error("Vui lòng nhập Prompt / Ý tưởng trước khi chạy.")
            return

        if image_engine == "flow" and not is_cdp_connected:
            st.error("❌ Không thể chạy Google Flow vì Chrome port 9222 chưa mở! Hãy chạy file `scripts/launch_flow_chrome.bat` (hoặc phím [4] trong `run.bat`) rồi bấm lại.")
            return

        st.session_state.batch_is_running = True
        st.session_state.batch_completed_videos = []

        # Các container hiển thị tiến độ
        progress_overall = st.progress(0)
        overall_text = st.empty()
        
        progress_current = st.progress(0)
        current_text = st.empty()
        
        log_box = st.empty()
        log_lines = []

        def ui_progress_callback(video_num: int, total_videos: int, pct: float, msg: str):
            # Tính phần trăm tổng thể
            overall_pct = int(((video_num - 1) / total_videos) * 100 + (pct / total_videos))
            progress_overall.progress(min(100, max(0, overall_pct)))
            overall_text.markdown(f"**Tổng tiến độ:** Đang xử lý Video **{video_num}/{total_videos}** ({overall_pct}%)")

            # Tiến độ video hiện tại
            progress_current.progress(min(100, max(0, int(pct))))
            current_text.markdown(f"**Video {video_num}:** {msg} ({int(pct)}%)")

            # Ghi log
            log_lines.append(f"[{time.strftime('%H:%M:%S')}] [Video {video_num}/{total_videos}] {msg}")
            log_box.code("\n".join(log_lines[-8:]), language="text")

        try:
            with st.spinner("Đang chạy vòng lặp sản xuất video tự động..."):
                completed_videos, meta_reports = run_batch_video_loop(
                    prompt=prompt_input,
                    count=batch_count,
                    language=lang_code,
                    voice=selected_voice,
                    style_preset=DEFAULT_IMAGE_STYLE,
                    orientation=orientation,
                    image_engine=image_engine,
                    progress_callback=ui_progress_callback
                )

            st.session_state.batch_completed_videos = completed_videos
            st.session_state.batch_is_running = False

            if completed_videos:
                st.balloons()
                st.success(f"🎉 ĐÃ HOÀN TẤT VÒNG LẶP: Sản xuất thành công {len(completed_videos)}/{batch_count} video hoàn chỉnh!")
            else:
                st.error("Không có video nào được hoàn thành. Vui lòng kiểm tra nhật ký lỗi.")

        except Exception as e:
            st.session_state.batch_is_running = False
            st.error(f"Lỗi trong quá trình chạy batch: {e}")

    # Hiển thị bộ sưu tập video thành phẩm
    if st.session_state.batch_completed_videos:
        st.markdown("---")
        st.markdown("### 📥 Bộ Sưu Tập Video Hoàn Thành")
        
        cols = st.columns(min(len(st.session_state.batch_completed_videos), 3))
        for idx, video_path in enumerate(st.session_state.batch_completed_videos):
            col_target = cols[idx % len(cols)]
            with col_target:
                st.markdown(f"#### 🎬 Video #{idx + 1}")
                st.caption(f"`{os.path.basename(video_path)}`")
                if os.path.exists(video_path):
                    st.video(video_path)
                    with open(video_path, "rb") as f:
                        st.download_button(
                            label=f"💾 Tải Video #{idx + 1}",
                            data=f,
                            file_name=os.path.basename(video_path),
                            mime="video/mp4",
                            key=f"dl_batch_{idx}"
                        )
                else:
                    st.warning("File không tồn tại.")
