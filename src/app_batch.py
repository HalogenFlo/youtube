"""Giao diện điều hành xưởng sản xuất video kiến thức tự động."""

import html
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.autonomous_factory import (
    add_factory_jobs,
    clear_finished_jobs,
    ensure_factory_worker,
    get_factory_state,
    retry_failed_jobs,
    set_factory_paused,
)
from src.config import DEFAULT_IMAGE_STYLE, TTS_VOICES_EN, TTS_VOICES_VI
from src.flow_browser_service import get_flow_readiness


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
    st.markdown(f"#### {index}. {title}")
    if output_path and os.path.exists(output_path):
        st.video(output_path)
    st.markdown(
        f"<div class='meta-box'><b>Tiêu đề đăng:</b> {html.escape(title)}<br>"
        f"<b>Hashtag:</b> {html.escape(hashtags)}<br>"
        f"<b>Mô tả:</b> {html.escape(publishing.get('description',''))}</div>",
        unsafe_allow_html=True,
    )
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
            c1, c2 = st.columns(2)
            count = c1.number_input("Số video", min_value=1, max_value=100, value=10, step=1)
            language_label = c2.selectbox("Ngôn ngữ", ["Tiếng Việt", "English"])
            language = "vi" if language_label == "Tiếng Việt" else "en"
            c3, c4 = st.columns(2)
            orientation_label = c3.selectbox("Khung hình", ["Dọc 9:16", "Ngang 16:9"])
            orientation = "vertical" if orientation_label.startswith("Dọc") else "horizontal"
            voices = TTS_VOICES_VI if language == "vi" else TTS_VOICES_EN
            voice_label = c4.selectbox("Giọng đọc", list(voices.keys()))
            style_preset = st.text_input("Phong cách hình ảnh", value=DEFAULT_IMAGE_STYLE)
            submitted = st.form_submit_button("Khởi động dây chuyền", type="primary", use_container_width=True)

        if submitted:
            if not prompt.strip():
                st.warning("Hãy nhập ít nhất một chủ đề.")
            elif not flow_ready:
                st.error("Google Flow chưa sẵn sàng. Hãy chạy run.bat và đăng nhập Flow trong cửa sổ Chrome riêng trước khi bắt đầu.")
            else:
                add_factory_jobs(prompt=prompt.strip(), count=int(count), language=language, voice=voices[voice_label], style_preset=style_preset, orientation=orientation, image_engine="flow")
                st.success(f"Đã đưa {int(count)} video vào dây chuyền. Bạn có thể để trang chạy tự động.")
                st.rerun()

        st.markdown("<br><div class='section-kicker'>Điều khiển xưởng</div>", unsafe_allow_html=True)
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
        if b2.button("Dọn lịch sử", disabled=(counts["completed"] + counts["failed"] == 0), use_container_width=True):
            clear_finished_jobs()
            st.rerun()
        if flow_status == "login_required":
            st.warning("Chrome điều khiển đã mở nhưng Google Flow chưa đăng nhập. Hãy đăng nhập một lần trong cửa sổ Chrome Flow, sau đó bấm Làm mới trạng thái.")
        elif flow_status == "disconnected":
            st.warning("Chrome điều khiển chưa mở. Chạy `run.bat` để mở đúng phiên Google Flow.")

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
