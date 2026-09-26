"""Giao diện điều hành xưởng sản xuất video kiến thức tự động."""

import html
import hashlib
import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from src.autonomous_factory import (
    add_factory_jobs,
    clear_failed_jobs,
    clear_finished_jobs,
    ensure_factory_worker,
    get_factory_state,
    retry_failed_jobs,
    set_factory_paused,
)
from src.config import ASSETS_DIR, DEFAULT_IMAGE_STYLE, TTS_VOICES_EN, TTS_VOICES_VI
from src.flow_browser_service import get_flow_readiness, get_flow_controller
from src.voice_clone_service import XTTS_LANGUAGES, voice_clone_available


def check_chrome_flow_status() -> bool:
    """Giữ API cũ cho nơi gọi bên ngoài; chỉ True khi dự án Flow dùng được."""
    return get_flow_readiness() == "ready"


def _inject_factory_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
        .stApp { background: #081018; }
        [data-testid="stHeader"] { background: rgba(8,16,24,.76); }
        [data-testid="stSidebar"] { background: #0b151f; border-right: 1px solid #1d2b38; }
        .block-container { max-width: 1420px; padding-top: 1.6rem; }
        .factory-hero { position:relative; overflow:hidden; padding:28px 32px; margin-bottom:20px; border:1px solid #233747; border-radius:24px; background:radial-gradient(circle at 92% 15%, rgba(47,217,163,.18), transparent 30%),linear-gradient(135deg,#101f2c 0%,#0b1721 60%,#0c1b24 100%); }
        .factory-hero:after { content:""; position:absolute; right:42px; top:26px; width:112px; height:112px; border:1px solid rgba(63,231,178,.35); border-radius:50%; box-shadow:0 0 80px rgba(47,217,163,.15); }
        .eyebrow { color:#47e0b2; font-size:.72rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }
        .factory-title { margin:8px 0 6px; color:#f5fbff; font-size:2.45rem; line-height:1.05; font-weight:800; letter-spacing:-.045em; }
        .factory-sub { color:#9db0bf; max-width:760px; font-size:.98rem; }
        .status-row { display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; }
        .status-chip { padding:7px 11px; border-radius:999px; background:#122431; color:#b9c9d5; border:1px solid #243b4c; font-size:.78rem; }
        .status-chip.ok { color:#55e8b9; border-color:rgba(85,232,185,.35); background:rgba(35,150,112,.12); }
        .status-chip.warn { color:#ffc96b; border-color:rgba(255,201,107,.35); background:rgba(180,120,25,.12); }
        [data-testid="stMetric"] { background:#0e1a24; border:1px solid #1e303e; padding:16px 18px; border-radius:16px; }
        [data-testid="stMetricValue"] { color:#f4fbff; font-weight:800; }
        div[data-testid="stForm"] { border:1px solid #233746; background:#0d1923; border-radius:20px; padding:20px; }
        .section-kicker { color:#5ae4ba; font-size:.74rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; margin-bottom:4px; }
        .section-title { color:#f3f8fb; font-size:1.35rem; font-weight:750; margin-bottom:4px; }
        .section-copy { color:#8fa4b4; font-size:.86rem; margin-bottom:14px; }
        .job-card { background:#0d1923; border:1px solid #203443; border-radius:16px; padding:15px 17px; margin:8px 0; }
        .job-title { color:#edf7fb; font-weight:700; font-size:.92rem; margin-bottom:5px; }
        .job-meta { color:#8197a7; font-size:.76rem; }
        .meta-box { background:#0a141d; border-left:3px solid #49ddb2; padding:12px 14px; border-radius:8px; color:#b9cad5; }
        .stButton > button, .stDownloadButton > button { border-radius:11px; font-weight:700; }
        div[data-testid="stProgress"] > div > div { background-color:#46ddb1; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_counts(jobs):
    return {status: sum(job.get("status") == status for job in jobs) for status in ("queued", "running", "completed", "failed")}


def _render_job(job):
    labels = {"queued": "Chờ sản xuất", "running": "Đang sản xuất", "completed": "Hoàn tất", "failed": "Cần xử lý"}
    st.markdown(
        f"<div class='job-card'><div class='job-title'>#{job.get('video_index')} · {html.escape(job.get('topic',''))}</div>"
        f"<div class='job-meta'>{labels.get(job.get('status'), job.get('status'))} · {html.escape(job.get('message',''))}</div></div>",
        unsafe_allow_html=True,
    )
    st.progress(int(job.get("progress", 0)))


def _render_completed_card(job, index):
    metadata = job.get("metadata", {})
    publishing = metadata.get("publishing", {})
    output_path = job.get("output_path", "")
    title = publishing.get("title") or job.get("topic", "Video kiến thức")
    hashtags = " ".join(publishing.get("hashtags", []))
    platforms = publishing.get("platforms", {})
    youtube_meta = platforms.get("youtube", {})
    tiktok_meta = platforms.get("tiktok", {})
    youtube_title = youtube_meta.get("title", title)
    youtube_description = youtube_meta.get("description", publishing.get("description", ""))
    tiktok_caption = tiktok_meta.get("caption", publishing.get("tiktok_caption", youtube_description))
    editorial = metadata.get("editorial_report", {})
    st.markdown(f"#### {index}. {title}")
    if output_path and os.path.exists(output_path):
        st.video(output_path)
    st.markdown(
        f"<div class='meta-box'><b>YouTube title:</b> {html.escape(youtube_title)}<br>"
        f"<b>YouTube description:</b> {html.escape(youtube_description)}<br>"
        f"<b>TikTok caption:</b> {html.escape(tiktok_caption)}<br>"
        f"<b>Hashtag:</b> {html.escape(hashtags)}<br>"
        f"<b>Nhãn AI:</b> Bật “Altered content” trên YouTube và “AI-generated content” trên TikTok.</div>",
        unsafe_allow_html=True,
    )
    if publishing.get("manual_review_required"):
        risk_text = ", ".join(publishing.get("risk_flags", []))
        st.warning(f"Metadata cần kiểm tra thủ công trước khi đăng. Nhóm rủi ro: {risk_text}")
    if editorial:
        score = editorial.get("overall_score")
        skill_names = [item.get("name", item.get("id", "")) for item in editorial.get("selected_skills", [])]
        if score is not None:
            st.caption(f"Studio QA: {score}/100 · Kỹ năng: {', '.join(filter(None, skill_names))}")
        warnings = editorial.get("remaining_warnings", [])
        if warnings:
            st.warning("Studio còn cảnh báo: " + "; ".join(str(item) for item in warnings))
    if output_path and os.path.exists(output_path):
        with open(output_path, "rb") as video_file:
            st.download_button("Tải video MP4", video_file, file_name=Path(output_path).name, mime="video/mp4", key=f"video_{job.get('id')}", use_container_width=True)
    metadata_path = metadata.get("metadata_path")
    if metadata_path and os.path.exists(metadata_path):
        with open(metadata_path, "rb") as metadata_file:
            st.download_button("Tải metadata JSON", metadata_file, file_name=Path(metadata_path).name, mime="application/json", key=f"meta_{job.get('id')}", use_container_width=True)


def run_batch_ui():
    _inject_factory_css()
    ensure_factory_worker()
    state = get_factory_state()
    jobs = state.get("jobs", [])
    counts = _status_counts(jobs)
    flow_status = get_flow_readiness()
    flow_ready = flow_status == "ready"
    flow_label = {
        "ready": "đã sẵn sàng",
        "login_required": "cần đăng nhập",
        "disconnected": "chưa kết nối",
    }.get(flow_status, "chưa kết nối")
    line_state = "Đang tạm dừng" if state.get("paused") else ("Đang sản xuất" if counts["running"] else "Sẵn sàng nhận việc")

    st.markdown(
        f"""
        <div class="factory-hero">
          <div class="eyebrow">Autonomous Knowledge Studio</div>
          <div class="factory-title">Xưởng video kiến thức AI</div>
          <div class="factory-sub">Nạp một chủ đề, để hệ thống tự viết kịch bản, tạo cảnh bằng Google Flow, dựng video và đóng gói tiêu đề cùng hashtag sẵn đăng.</div>
          <div class="status-row">
            <span class="status-chip {'ok' if flow_ready else 'warn'}">● Google Flow {flow_label}</span>
            <span class="status-chip {'warn' if state.get('paused') else 'ok'}">● {line_state}</span>
            <span class="status-chip">Lưu hàng đợi tự động</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Đang chờ", counts["queued"])
    metric_cols[1].metric("Đang chạy", counts["running"])
    metric_cols[2].metric("Đã hoàn tất", counts["completed"])
    metric_cols[3].metric("Cần xử lý", counts["failed"])

    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([1.05, 1.55], gap="large")

    with left:
        st.markdown("<div class='section-kicker'>Kho ý tưởng</div><div class='section-title'>Tạo lệnh sản xuất mới</div><div class='section-copy'>Mỗi dòng là một video riêng. Nếu chỉ có một chủ đề, AI sẽ tự chia thành nhiều tập.</div>", unsafe_allow_html=True)
        with st.form("factory_order_form", clear_on_submit=False):
            prompt = st.text_area("Chủ đề hoặc danh sách chủ đề", value="Những bí ẩn khoa học khiến con người phải suy nghĩ lại", height=135, help="Có thể nhập nhiều dòng, mỗi dòng là một video.")
            st.info("Số video là số thành phẩm trong lô; số phân cảnh là số đoạn ghép bên trong mỗi video.")
            c1, c2 = st.columns(2)
            count = c1.number_input("Số video trong lô", min_value=1, max_value=100, value=1, step=1)
            language_label = c2.selectbox("Ngôn ngữ", ["Tiếng Việt", "English"])
            language = "vi" if language_label == "Tiếng Việt" else "en"
            c3, c4 = st.columns(2)
            orientation_label = c3.selectbox("Khung hình", ["Dọc 9:16", "Ngang 16:9"])
            orientation = "vertical" if orientation_label.startswith("Dọc") else "horizontal"
            target_scenes = c4.number_input(
                "Số phân cảnh mỗi video", min_value=1, max_value=12, value=5, step=1,
                help="5 cảnh thường tương đương khoảng 25-50 giây. Đây không phải 5 video.",
            )

            media_mode_label = st.selectbox(
                "Chế độ phương tiện Google Flow",
                [
                    "🎬 Video Flow cho mọi cảnh (Mỗi phân cảnh 1 video nhỏ ghép thành video lớn)",
                    "Hybrid — Cảnh đầu video Flow, còn lại ảnh",
                    "Nhanh & ổn định — Ảnh Flow + chuyển động",
                ],
                index=2,
                help="Khuyên dùng ảnh Flow + chuyển động. Video Flow mọi cảnh có thể bị xếp hàng rất lâu khi Google quá tải.",
            )
            studio_mode = st.checkbox(
                "Studio biên tập local nhiều vai",
                value=True,
                help="Thêm vòng kiểm chứng, sửa hook, độ rõ ràng, tính nhất quán hình ảnh và chính sách trước khi sản xuất.",
            )
            if media_mode_label.startswith("🎬 Video Flow") or "mọi cảnh" in media_mode_label:
                media_mode = "flow_video"
            elif media_mode_label.startswith("Hybrid"):
                media_mode = "hybrid"
            else:
                media_mode = "flow_image"

            voices = {**TTS_VOICES_VI, **TTS_VOICES_EN}
            voice_mode_label = st.radio(
                "Nguồn giọng đọc",
                ["Giọng có sẵn — nhanh", "Clone giọng local — XTTS-v2"],
                horizontal=True,
            )
            voice_mode = "clone_local" if voice_mode_label.startswith("Clone") else "edge"
            voice_label = st.selectbox("Giọng có sẵn", list(voices.keys()))
            voice_upload = st.file_uploader(
                "File giọng mẫu cho chế độ clone (6-30 giây)", type=["wav", "mp3", "m4a"],
                help="Chỉ được dùng giọng của bạn hoặc giọng đã được chủ sở hữu cho phép.",
            )
            voice_consent = st.checkbox("Tôi xác nhận đây là giọng của tôi hoặc tôi có quyền sử dụng giọng này.")
            st.caption("XTTS-v2 local hỗ trợ English và 15 ngôn ngữ khác, nhưng chưa hỗ trợ tiếng Việt. Video tiếng Việt hiện dùng giọng có sẵn.")
            if not voice_clone_available():
                st.error("Engine clone local chưa được cài đặt.")
            style_preset = st.text_input("Phong cách hình ảnh", value=DEFAULT_IMAGE_STYLE)
            submitted = st.form_submit_button("Khởi động dây chuyền", type="primary", use_container_width=True)

        if submitted:
            if not prompt.strip():
                st.warning("Hãy nhập ít nhất một chủ đề.")
            elif voice_mode == "clone_local" and language not in XTTS_LANGUAGES:
                st.error("XTTS-v2 không hỗ trợ tiếng Việt. Hãy đổi video sang English hoặc chọn giọng có sẵn.")
            elif voice_mode == "clone_local" and (voice_upload is None or not voice_consent):
                st.error("Clone giọng cần file mẫu và xác nhận quyền sử dụng giọng.")
            else:
                # Trải nghiệm 1-Click: Nếu Flow chưa mở, tự động khởi chạy Chrome ngay lập tức
                if not flow_ready and media_mode in ("flow_image", "flow_video", "hybrid"):
                    with st.spinner("Đang tự động khởi chạy Chrome Google Flow..."):
                        ctrl = get_flow_controller()
                        flow_ok, flow_msg = ctrl.connect()
                        if not flow_ok:
                            st.info(f"[*] {flow_msg} — Dây chuyền sẽ tự kết nối lại trong nền khi Chrome sẵn sàng.")

                reference_path = ""
                if voice_mode == "clone_local" and voice_upload is not None:
                    voice_dir = Path(ASSETS_DIR) / "voices"
                    voice_dir.mkdir(parents=True, exist_ok=True)
                    voice_bytes = voice_upload.getvalue()
                    digest = hashlib.sha256(voice_bytes).hexdigest()[:12]
                    suffix = Path(voice_upload.name).suffix.lower() or ".wav"
                    reference_file = voice_dir / f"voice_{digest}{suffix}"
                    reference_file.write_bytes(voice_bytes)
                    reference_path = str(reference_file)
                add_factory_jobs(
                    prompt=prompt.strip(), count=int(count), language=language,
                    voice=voices[voice_label], style_preset=style_preset,
                    orientation=orientation, image_engine="flow",
                    media_mode=media_mode,
                    target_scenes=int(target_scenes), voice_mode=voice_mode,
                    voice_reference_path=reference_path,
                    studio_mode=studio_mode,
                )
                st.success(f"✅ Đã đưa {int(count)} video × {int(target_scenes)} phân cảnh vào dây chuyền. Đang tự động sản xuất...")
                time.sleep(1)
                st.rerun()

        st.markdown("<br><div class='section-kicker'>Điều khiển xưởng</div>", unsafe_allow_html=True)
        if flow_status != "ready":
            if st.button("🚀 Mở nhanh Chrome Google Flow (Cổng 9222)", type="primary" if flow_status == "disconnected" else "secondary", use_container_width=True):
                with st.spinner("Đang kết nối Chrome Google Flow..."):
                    flow_ok, flow_msg = get_flow_controller().connect()
                    if flow_ok:
                        st.success("Google Flow đã sẵn sàng!")
                    else:
                        st.info(flow_msg)
                    time.sleep(1)
                    st.rerun()
        a, b = st.columns(2)
        if state.get("paused"):
            if a.button("Tiếp tục sản xuất", type="primary", use_container_width=True):
                set_factory_paused(False)
                st.rerun()
        else:
            if a.button("Tạm dừng sau video này", use_container_width=True):
                set_factory_paused(True)
                st.rerun()
        if b.button("Làm mới trạng thái", use_container_width=True):
            st.rerun()
        a2, b2 = st.columns(2)
        if a2.button("Chạy lại việc lỗi", disabled=counts["failed"] == 0, use_container_width=True):
            retry_failed_jobs()
            st.rerun()
        if b2.button("Xóa việc lỗi", disabled=counts["failed"] == 0, use_container_width=True):
            clear_failed_jobs()
            st.rerun()
        if flow_status == "login_required":
            st.warning("Chrome điều khiển đã mở nhưng Google Flow chưa đăng nhập. Hãy đăng nhập một lần trong cửa sổ Chrome Flow, sau đó bấm Làm mới trạng thái.")
        elif flow_status == "disconnected":
            st.warning("Chrome điều khiển chưa mở. Bấm nút 'Mở nhanh Chrome Google Flow' ở trên hoặc bấm 'Khởi động dây chuyền' để hệ thống tự mở.")

    with right:
        tab_line, tab_output, tab_log = st.tabs(["Dây chuyền", "Kho thành phẩm", "Bảng dữ liệu"])
        with tab_line:
            active_jobs = [job for job in jobs if job.get("status") in {"running", "queued", "failed"}]
            if not active_jobs:
                st.info("Dây chuyền đang trống. Tạo một lệnh sản xuất để bắt đầu.")
            for job in active_jobs[:20]:
                _render_job(job)
            if len(active_jobs) > 20:
                st.caption(f"Còn {len(active_jobs) - 20} việc khác đang trong hàng đợi.")
        with tab_output:
            completed = [job for job in jobs if job.get("status") == "completed"]
            if not completed:
                st.info("Video hoàn tất sẽ xuất hiện ở đây cùng tiêu đề, mô tả và hashtag.")
            for index, job in enumerate(reversed(completed), start=1):
                with st.container(border=True):
                    _render_completed_card(job, index)
        with tab_log:
            rows = []
            for job in reversed(jobs):
                publishing = job.get("metadata", {}).get("publishing", {})
                rows.append({"Mã": job.get("id"), "Video": job.get("video_index"), "Chủ đề": job.get("topic"), "Trạng thái": job.get("status"), "Tiến độ": f"{job.get('progress', 0)}%", "Tiêu đề AI": publishing.get("title", ""), "Cập nhật": job.get("updated_at", "")})
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("Chưa có dữ liệu sản xuất.")

    # Tự động cập nhật giao diện theo thời gian thực nếu đang có việc chạy hoặc trong hàng đợi
    if counts["running"] > 0 or counts["queued"] > 0:
        time.sleep(2.5)
        st.rerun()

