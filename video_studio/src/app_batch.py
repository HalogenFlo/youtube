"""Giao diện điều hành xưởng sản xuất video kiến thức tự động (Luồng gốc tối giản + Đa luồng & Hoạt hình HTML5)."""

import html
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.autonomous_factory import (
    ACTIVE_PROCESSING_STATES,
    STAGE_LABELS_VI,
    add_factory_jobs,
    approve_job_for_publishing,
    cancel_job,
    clear_failed_jobs,
    clear_finished_jobs,
    clear_missing_video_jobs,
    delete_job,
    ensure_factory_worker,
    get_factory_state,
    publish_approved_job,
    rerun_job_stage_or_scene,
    rerun_missing_video_jobs,
    resolve_job_video_and_metadata_paths,
    restart_factory_worker,
    retry_failed_jobs,
    set_factory_paused,
    skip_current_job,
    update_job_metadata_or_script,
)
from src.batch_producer import build_random_video_topics
from src.config import ASSETS_DIR, DEFAULT_IMAGE_STYLE, TTS_VOICES_EN, TTS_VOICES_VI, TTS_VOICES_ZH
from src.flow_browser_service import get_flow_controller, get_flow_readiness
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
        .meta-box { background:#0a141d; border-left:3px solid #49ddb2; padding:14px 16px; border-radius:10px; color:#d0e0ea; margin:10px 0; line-height:1.65; }
        .stButton > button, .stDownloadButton > button { border-radius:11px; font-weight:700; }
        div[data-testid="stProgress"] > div > div { background-color:#46ddb1; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_counts(jobs):
    queued = sum(1 for j in jobs if j.get("status") == "queued")
    running = sum(1 for j in jobs if j.get("status") in ACTIVE_PROCESSING_STATES)
    completed = sum(1 for j in jobs if j.get("status") in ("completed", "ready_for_review", "approved", "published", "needs_review"))
    failed = sum(1 for j in jobs if j.get("status") in ("failed", "cancelled"))
    return {"queued": queued, "running": running, "completed": completed, "failed": failed}


def _render_job(job: Dict[str, Any]) -> None:
    labels = {
        "queued": "Chờ sản xuất",
        "running": "Đang sản xuất",
        "completed": "Hoàn tất",
        "failed": "Cần xử lý",
        "cancelled": "Đã hủy",
    }
    status = str(job.get("status") or "queued")
    stage = str(job.get("current_stage") or job.get("lifecycle_state") or status)
    stage_vi = STAGE_LABELS_VI.get(stage, labels.get(status, status))
    turbo_badge = " · <span style='color:#49ddb2;font-weight:bold;'>⚡ Đa luồng Turbo</span>" if job.get("settings", {}).get("turbo_mode") else ""
    engine_name = job.get("settings", {}).get("image_engine", "flow")
    engine_badge = " · <span style='color:#38bdf8;font-weight:bold;'>🎨 HTML5 Animation</span>" if engine_name in ("html_frames", "cartoon_2d") else ""
    st.markdown(
        f"<div class='job-card'><div class='job-title'>#{job.get('video_index')} · {html.escape(str(job.get('topic','')))}{turbo_badge}{engine_badge}</div>"
        f"<div class='job-meta'>{html.escape(stage_vi)} · {html.escape(str(job.get('message','')))}</div></div>",
        unsafe_allow_html=True,
    )
    st.progress(int(job.get("progress", 0)))
    job_id = job.get("id")
    if status in ACTIVE_PROCESSING_STATES:
        if st.button("⏭️ Bỏ qua video này", key=f"skip_btn_{job_id}", help="Ngắt tiến trình video này và chuyển sang việc tiếp theo ngay lập tức"):
            skip_current_job(job_id)
            st.rerun()
    elif status == "queued":
        if st.button("❌ Hủy việc này", key=f"cancel_btn_{job_id}", help="Xóa video này khỏi hàng đợi"):
            cancel_job(job_id)
            st.rerun()


def _render_completed_card(job: Dict[str, Any], index: int) -> None:
    """
    Hiển thị thẻ thành phẩm đúng như luồng gốc của người dùng:
    - Xem ngay Video MP4
    - Hiển thị trực tiếp Tiêu đề (Title), Mô tả (Description), TikTok Caption và Hashtag ngay bên dưới video
    - Có hộp sao chép nhanh 1-click và nút Tải video MP4 / Metadata JSON
    """
    job_id = str(job.get("id", f"idx_{index}"))
    raw_metadata = job.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    raw_publishing = metadata.get("publishing")
    publishing = raw_publishing if isinstance(raw_publishing, dict) else {}
    pkg = metadata.get("publishing_package") if isinstance(metadata.get("publishing_package"), dict) else {}
    qa_report = metadata.get("qa_report") if isinstance(metadata.get("qa_report"), dict) else {}

    output_path, metadata_path = resolve_job_video_and_metadata_paths(job)
    if not output_path:
        output_path = job.get("output_path") or metadata.get("final_path") or ""
    if not metadata_path:
        metadata_path = metadata.get("metadata_path") or ""

    yt_spec = pkg.get("youtube") if isinstance(pkg.get("youtube"), dict) else {}
    tt_spec = pkg.get("tiktok") if isinstance(pkg.get("tiktok"), dict) else {}
    raw_platforms = publishing.get("platforms")
    platforms = raw_platforms if isinstance(raw_platforms, dict) else {}
    raw_yt = platforms.get("youtube") if isinstance(platforms.get("youtube"), dict) else {}
    raw_tt = platforms.get("tiktok") if isinstance(platforms.get("tiktok"), dict) else {}

    title = (
        yt_spec.get("recommended_title")
        or raw_yt.get("title")
        or publishing.get("title")
        or job.get("topic", "Video kiến thức")
    )
    youtube_title = yt_spec.get("recommended_title") or raw_yt.get("title") or title
    youtube_description = (
        yt_spec.get("description")
        or raw_yt.get("description")
        or publishing.get("description")
        or f"{title} — Giải thích kiến thức trực quan, dễ hiểu."
    )
    tiktok_caption = (
        tt_spec.get("caption")
        or raw_tt.get("caption")
        or publishing.get("tiktok_caption")
        or youtube_description
    )
    raw_hashtags = (
        yt_spec.get("hashtags")
        or tt_spec.get("hashtags")
        or publishing.get("hashtags")
        or ["#khoahoc", "#kienthuc", "#khampha", "#shorts", "#xuhuong"]
    )
    hashtags = " ".join(raw_hashtags) if isinstance(raw_hashtags, list) else str(raw_hashtags)

    hdr_left, hdr_right = st.columns([0.84, 0.16])
    hdr_left.markdown(f"#### {index}. {html.escape(str(title))}")
    if hdr_right.button("🗑️ Xóa", key=f"del_hdr_{job_id}", help="Xóa video này khỏi kho thành phẩm", use_container_width=True):
        delete_job(job_id)
        st.success("Đã xóa video.")
        time.sleep(0.4)
        st.rerun()

    col_vid, col_meta = st.columns([1.0, 1.35], gap="medium")

    with col_vid:
        if output_path and os.path.exists(output_path):
            st.video(output_path)
            dl1, dl2, dl3 = st.columns([1, 1, 0.9])
            with open(output_path, "rb") as video_file:
                dl1.download_button(
                    "⬇️ Tải MP4",
                    video_file,
                    file_name=Path(output_path).name,
                    mime="video/mp4",
                    key=f"video_{job_id}",
                    use_container_width=True,
                )
            if metadata_path and os.path.exists(metadata_path):
                with open(metadata_path, "rb") as metadata_file:
                    dl2.download_button(
                        "📄 Metadata",
                        metadata_file,
                        file_name=Path(metadata_path).name,
                        mime="application/json",
                        key=f"meta_{job_id}",
                        use_container_width=True,
                    )
            if dl3.button("🗑️ Xóa video", key=f"del_vid_{job_id}", help="Xóa video này khỏi kho thành phẩm", use_container_width=True):
                delete_job(job_id)
                st.success("Đã xóa video.")
                time.sleep(0.4)
                st.rerun()
        else:
            st.markdown(
                """
                <div style="background: rgba(251,191,36,0.08); border: 1px dashed rgba(251,191,36,0.4); border-radius: 12px; padding: 18px 14px; text-align: center; margin-bottom: 12px;">
                    <div style="font-size: 28px; margin-bottom: 6px;">⚠️</div>
                    <div style="font-weight: 700; color: #fbbf24; font-size: 0.95rem; margin-bottom: 4px;">File video MP4 không còn trên đĩa</div>
                    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">
                        File MP4 đã bị xóa trong đợt dọn dẹp dung lượng ổ đĩa.<br>
                        Checkpoint âm thanh và hình ảnh các cảnh vẫn còn nguyên.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c_r1, c_r2 = st.columns(2)
            if c_r1.button("🔄 Render lại video này", key=f"re_render_{job_id}", type="primary", use_container_width=True, help="Tự động ghép lại âm thanh và hình ảnh đã có sẵn thành file MP4 hoàn chỉnh"):
                ok, msg = rerun_job_stage_or_scene(job_id, target_stage="rendering")
                if ok:
                    st.success(msg)
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error(msg)
            if c_r2.button("🗑️ Xóa bản ghi này", key=f"del_card_{job_id}", use_container_width=True, help="Xóa job này khỏi kho thành phẩm"):
                delete_job(job_id)
                st.rerun()

    with col_meta:
        st.markdown(
            f"<div class='meta-box'>"
            f"<b>📌 Tiêu đề YouTube (Title):</b> {html.escape(str(youtube_title))}<br><br>"
            f"<b>📝 Mô tả YouTube (Description):</b><br>{html.escape(str(youtube_description)).replace(chr(10), '<br>')}<br><br>"
            f"<b>🎵 Mô tả TikTok (Caption):</b><br>{html.escape(str(tiktok_caption)).replace(chr(10), '<br>')}<br><br>"
            f"<b>🏷️ Hashtag:</b> <span style='color:#55e8b9;font-weight:700;'>{html.escape(str(hashtags))}</span><br>"
            f"<b>🛡️ Nhãn AI:</b> Bật “Altered content” trên YouTube và “AI-generated content” trên TikTok."
            f"</div>",
            unsafe_allow_html=True,
        )

        st.caption("📋 **Sao chép nhanh (Bấm biểu tượng Copy ở góc phải mỗi ô):**")
        st.code(f"""{youtube_title}

{youtube_description}

{hashtags}""", language="text")

        qa_score = qa_report.get("overall_score")
        if qa_score is not None:
            st.caption(f"✅ Điểm kiểm định chất lượng video thực tế (Post-Render QA): **{qa_score}/100**")

        with st.expander("🛠️ Tùy chọn nâng cao (Sửa Tiêu đề / Mô tả / Chạy lại nếu cần)"):
            new_title = st.text_input("Sửa tiêu đề", value=str(youtube_title), key=f"ed_t_{job_id}")
            new_desc = st.text_area("Sửa mô tả", value=str(youtube_description), height=80, key=f"ed_d_{job_id}")
            new_tags = st.text_input("Sửa hashtag", value=str(hashtags), key=f"ed_h_{job_id}")
            c_btn1, c_btn2, c_btn3 = st.columns(3)
            if c_btn1.button("💾 Lưu Tiêu đề", key=f"save_m_{job_id}", use_container_width=True):
                update_job_metadata_or_script(
                    job_id=job_id,
                    title=new_title,
                    description=new_desc,
                    tiktok_caption=new_desc,
                    hashtags=[t.strip() for t in new_tags.split() if t.strip()],
                    lock_edited_fields=True,
                )
                st.success("Đã cập nhật tiêu đề, mô tả và hashtag!")
                time.sleep(0.5)
                st.rerun()
            if c_btn2.button("🔄 Dựng lại video", key=f"rr_v_{job_id}", use_container_width=True):
                rerun_job_stage_or_scene(job_id, target_stage="rendering")
                st.info("Đã đưa vào hàng đợi dựng lại.")
                time.sleep(0.5)
                st.rerun()
            if c_btn3.button("🗑️ Xóa bản ghi", key=f"del_m_{job_id}", use_container_width=True):
                delete_job(job_id)
                st.rerun()


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
          <div class="factory-sub">Chỉ cần nhập chủ đề (hoặc để trống), hệ thống tự viết kịch bản, dựng hoạt hình nhiều frame / Google Flow đa luồng và xuất sẵn Video kèm Tiêu đề, Mô tả, Hashtag.</div>
          <div class="status-row">
            <span class="status-chip ok">● Hoạt hình HTML5 Nhiều Frame sẵn sàng</span>
            <span class="status-chip {'ok' if flow_ready else 'warn'}">● Google Flow {flow_label}</span>
            <span class="status-chip {'warn' if state.get('paused') else 'ok'}">● {line_state}</span>
            <span class="status-chip ok">⚡ Đa luồng Turbo & Tự động tạo Title/Hashtag</span>
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
        st.markdown(
            "<div class='section-kicker'>Kho ý tưởng</div>"
            "<div class='section-title'>Tạo lệnh sản xuất mới</div>"
            "<div class='section-copy'>Chỉ cần nhập chủ đề (mỗi dòng 1 video) rồi bấm Khởi động dây chuyền. AI sẽ tự lo toàn bộ kịch bản, hình ảnh, lồng tiếng, phụ đề, tiêu đề và hashtag.</div>",
            unsafe_allow_html=True,
        )
        content_mode_label = st.selectbox(
            "Loại video",
            [
                "Kể chuyện kiến thức dẫn dắt (Story Explainer)",
                "Dạy tiếng Anh qua cốt truyện (Micro-Drama)",
                "Dạy tiếng Trung cho người Việt",
                "Video kiến thức thông thường",
            ],
            key="factory_content_mode_selector",
        )
        if content_mode_label.startswith("Dạy tiếng Anh"):
            content_mode = "english_vocab_story"
        elif content_mode_label.startswith("Kể chuyện kiến thức"):
            content_mode = "story_explainer"
        elif content_mode_label.startswith("Dạy tiếng Trung"):
            content_mode = "chinese_teaching_vi"
        else:
            content_mode = "knowledge"

        with st.form("factory_order_form", clear_on_submit=False):
            prompt = st.text_area(
                "Chủ đề cụ thể (không bắt buộc)",
                value="",
                height=110,
                placeholder="Để trống để xưởng tự chọn chủ đề ngẫu nhiên. Hoặc nhập mỗi dòng một chủ đề để xuất hàng loạt video.",
                help="Bạn chỉ cần nhập ý tưởng/chủ đề, không cần viết cốt truyện hay chia cảnh.",
            )
            c1, c2 = st.columns(2)
            count = c1.number_input("Số video trong lô", min_value=1, max_value=100, value=1, step=1)
            language_label = c2.selectbox("Ngôn ngữ", ["Tiếng Việt", "English"])
            language = "vi" if language_label == "Tiếng Việt" else "en"
            if content_mode == "chinese_teaching_vi":
                language = "vi"

            orientation_label = st.selectbox("Khung hình", ["Dọc 9:16 (TikTok / Shorts)", "Ngang 16:9 (YouTube)"])
            orientation = "vertical" if orientation_label.startswith("Dọc") else "horizontal"

            media_mode_label = st.selectbox(
                "Chế độ tạo Hình ảnh / Video AI",
                [
                    "🖼️ Vẽ tranh AI theo cốt truyện (Google Flow Image + Chuyển động Camera mượt)",
                    "🎬 Video AI cho mọi cảnh (Google Flow Video - Mỗi cảnh 1 clip chuyển động)",
                    "Hybrid — Cảnh đầu Video AI, các cảnh sau Ảnh AI",
                    "🎨 Vẽ Vector Canvas 2D (Thử nghiệm: Đồ họa vector hình que, không vẽ bối cảnh AI)",
                ],
                index=0,
                help="Khuyên dùng: Chọn 'Vẽ tranh AI theo cốt truyện' để AI vẽ hình ảnh nghệ thuật chi tiết và chân thực đúng theo từng phân cảnh kịch bản.",
            )
            turbo_mode = st.checkbox(
                "⚡ Chế độ Đa luồng Turbo (Tăng tốc sinh song song)",
                value=True,
                help="Chạy nhiều luồng cùng lúc cho cả Giọng đọc TTS, Vẽ frame hoạt hình/ảnh và Render FFmpeg.",
            )
            flow_workers = 4
            tts_workers = 4
            if turbo_mode:
                with st.expander("⚙️ Tinh chỉnh số luồng chạy song song"):
                    tc1, tc2 = st.columns(2)
                    flow_workers = int(tc1.number_input("Số luồng tạo Hoạt hình / Ảnh", min_value=1, max_value=8, value=4, step=1))
                    tts_workers = int(tc2.number_input("Số luồng tạo Giọng đọc (TTS)", min_value=1, max_value=8, value=4, step=1))

            selected_image_engine = "flow"
            if media_mode_label.startswith("🖼️ Vẽ tranh AI") or media_mode_label.startswith("🖼️"):
                selected_image_engine = "flow"
                media_mode = "flow_image"
            elif media_mode_label.startswith("🎬 Video AI") or "mọi cảnh" in media_mode_label:
                selected_image_engine = "flow"
                media_mode = "flow_video"
            elif media_mode_label.startswith("Hybrid"):
                selected_image_engine = "flow"
                media_mode = "hybrid"
            elif media_mode_label.startswith("🎨 Vẽ Vector"):
                selected_image_engine = "html_frames"
                media_mode = "html_animation"
            else:
                selected_image_engine = "flow"
                media_mode = "flow_image"

            style_presets_map = {
                "🎥 Hoạt hình 3D kể chuyện (như video mẫu)": "stylized 3D animated feature film, expressive characters, cinematic lighting, detailed environments, consistent materials and character design",
                "🎬 Hoạt hình điện ảnh (Cinematic 2D, sống động, giàu chi tiết)": "vibrant 2D animation, cinematic lighting, beautifully illustrated, cel-shaded, rich colors, detailed background, 4k",
                "🎨 Minh họa truyện kể (Storybook Illustration, ấm áp)": "storybook illustration art, soft painterly style, rich storytelling atmosphere, warm detailed background, 4k",
                "✨ Hoạt hình Anime hiện đại (Modern Anime Style, sắc nét)": "modern anime art style, vibrant aesthetic, detailed character and scenery, studio quality, 4k",
                "📸 Bối cảnh thực tế điện ảnh (Cinematic Photorealistic, 4K)": "cinematic photorealistic, realistic lighting, highly detailed environment, 8k render, masterpiece",
                "✏️ Nhân vật hình que Stickman tối giản (Minimalist Stickman)": "minimalist flat 2d stickman cartoon, clean whiteboard illustration, cel-shaded vector art",
            }
            selected_style_label = st.selectbox(
                "Phong cách mỹ thuật hình ảnh",
                list(style_presets_map.keys()),
                index=0 if media_mode == "flow_video" else 1,
                help="Chọn phong cách để AI vẽ bối cảnh và nhân vật theo đúng định hướng câu chuyện bạn muốn.",
            )
            style_preset = style_presets_map[selected_style_label]

            voices = {**TTS_VOICES_VI, **TTS_VOICES_EN}
            voice_label = st.selectbox("Giọng đọc AI", list(voices.keys()))
            chinese_voice_label = list(TTS_VOICES_ZH.keys())[0]
            if content_mode == "chinese_teaching_vi":
                chinese_voice_label = st.selectbox("Giọng phát âm tiếng Trung", list(TTS_VOICES_ZH.keys()))

            with st.expander("🎙️ Tùy chọn Clone giọng & Tùy biến prompt (Không bắt buộc)"):
                voice_mode_label = st.radio(
                    "Nguồn giọng đọc",
                    ["Giọng có sẵn — nhanh", "Clone giọng local — XTTS-v2"],
                    horizontal=True,
                )
                voice_mode = "clone_local" if voice_mode_label.startswith("Clone") else "edge"
                voice_upload = st.file_uploader("File giọng mẫu (6-30 giây)", type=["wav", "mp3", "m4a"])
                voice_consent = st.checkbox("Tôi xác nhận có quyền sử dụng giọng này.")
                custom_style = st.text_input("Ghi đè phong cách tùy chỉnh (để trống để dùng danh sách trên)", value="")
                if custom_style.strip():
                    style_preset = custom_style.strip()

            submitted = st.form_submit_button("🚀 Khởi động dây chuyền", type="primary", use_container_width=True)

        if submitted:
            if voice_mode == "clone_local" and language not in XTTS_LANGUAGES:
                st.error("XTTS-v2 không hỗ trợ tiếng Việt. Hãy đổi video sang English hoặc chọn giọng có sẵn.")
            elif voice_mode == "clone_local" and (voice_upload is None or not voice_consent):
                st.error("Clone giọng cần file mẫu và xác nhận quyền sử dụng giọng.")
            else:
                production_prompt = prompt.strip()
                random_topics = []
                if not production_prompt:
                    random_topics = build_random_video_topics(int(count), content_mode)
                    production_prompt = "\n".join(random_topics)

                if selected_image_engine == "flow" and not flow_ready and media_mode in ("flow_image", "flow_video", "hybrid"):
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
                    prompt=production_prompt,
                    count=int(count),
                    language=language,
                    voice=voices[voice_label],
                    style_preset=style_preset,
                    orientation=orientation,
                    image_engine=selected_image_engine,
                    media_mode=media_mode,
                    target_scenes=None,
                    voice_mode=voice_mode,
                    voice_reference_path=reference_path,
                    voice_consent_verified=bool(voice_consent if voice_mode == "clone_local" else True),
                    studio_mode=True,
                    content_mode=content_mode,
                    chinese_voice=TTS_VOICES_ZH[chinese_voice_label],
                    turbo_mode=turbo_mode,
                    flow_workers=flow_workers,
                    tts_workers=tts_workers,
                )
                if random_topics:
                    st.success(f"✅ Xưởng đã tự chọn {int(count)} chủ đề và bắt đầu sản xuất: " + "; ".join(random_topics))
                else:
                    st.success(f"✅ Đã đưa {int(count)} video vào dây chuyền sản xuất tự động!")
                time.sleep(0.8)
                st.rerun()

        st.markdown("<br><div class='section-kicker'>Điều khiển xưởng</div>", unsafe_allow_html=True)
        a, b = st.columns(2)
        if state.get("paused"):
            if a.button("▶️ Tiếp tục sản xuất", type="primary", use_container_width=True):
                set_factory_paused(False)
                st.rerun()
        else:
            if a.button("⏸️ Tạm dừng sau video này", use_container_width=True):
                set_factory_paused(True)
                st.rerun()
        if b.button("🔄 Làm mới trạng thái", use_container_width=True):
            st.rerun()

        a2, b2 = st.columns(2)
        if a2.button("Chạy lại việc lỗi", disabled=counts["failed"] == 0, use_container_width=True):
            retry_failed_jobs()
            st.rerun()
        if b2.button("Xóa việc lỗi", disabled=counts["failed"] == 0, use_container_width=True):
            clear_failed_jobs()
            st.rerun()

    with right:
        tab_output, tab_line, tab_log = st.tabs([
            f"🎬 Kho thành phẩm ({counts['completed']})",
            f"⚙️ Dây chuyền đang chạy ({counts['running'] + counts['queued']})",
            "📊 Bảng dữ liệu",
        ])
        with tab_output:
            completed = [
                job for job in jobs
                if job.get("status") in ("completed", "ready_for_review", "approved", "published", "needs_review")
            ]
            if not completed:
                st.info("Video hoàn tất sẽ xuất hiện ngay tại đây cùng Tiêu đề, Mô tả và Hashtag sẵn sàng đăng.")
            else:
                missing_count = sum(1 for j in completed if not resolve_job_video_and_metadata_paths(j)[0])
                if missing_count > 0:
                    st.warning(
                        f"⚠️ Phát hiện **{missing_count}/{len(completed)}** video cũ bị thiếu file MP4 trên đĩa (do đợt dọn rác bộ nhớ trước đó)."
                    )
                    top_b1, top_b2 = st.columns(2)
                    if top_b1.button("🔄 Render lại tất cả video thiếu file", key="bulk_rerun_missing", type="primary", use_container_width=True, help="Tự động sử dụng audio và hình ảnh có sẵn trong checkpoint để ghép lại video MP4"):
                        cnt = rerun_missing_video_jobs()
                        st.success(f"Đã đưa {cnt} video vào hàng đợi dựng lại!")
                        time.sleep(1)
                        st.rerun()
                    if top_b2.button("🧹 Dọn dẹp bản ghi cũ không còn file", key="bulk_clean_missing", use_container_width=True, help="Xóa các mục mồ côi không còn file khỏi danh sách thành phẩm"):
                        removed = clear_missing_video_jobs()
                        st.success(f"Đã dọn dẹp {removed} bản ghi.")
                        time.sleep(1)
                        st.rerun()
                    st.markdown("<hr style='margin: 8px 0 16px 0; border: none; border-top: 1px solid #1e293b;'>", unsafe_allow_html=True)

            for index, job in enumerate(reversed(completed), start=1):
                with st.container(border=True):
                    _render_completed_card(job, index)

        with tab_line:
            active_jobs = [
                job for job in jobs
                if job.get("status") in ACTIVE_PROCESSING_STATES or job.get("status") in ("queued", "failed")
            ]
            if not active_jobs:
                st.info("Dây chuyền đang trống. Nhập chủ đề ở cột trái và bấm 'Khởi động dây chuyền' để bắt đầu.")
            for job in active_jobs[:20]:
                _render_job(job)

        with tab_log:
            rows = []
            for job in reversed(jobs):
                publishing = job.get("metadata", {}).get("publishing", {})
                pkg_yt = job.get("metadata", {}).get("publishing_package", {}).get("youtube", {})
                title_ai = pkg_yt.get("recommended_title") or publishing.get("title", "")
                hashtags_ai = " ".join(pkg_yt.get("hashtags") or publishing.get("hashtags", []))
                rows.append({
                    "Mã": job.get("id"),
                    "Video": job.get("video_index"),
                    "Chủ đề": job.get("topic"),
                    "Trạng thái": job.get("status"),
                    "Tiến độ": f"{job.get('progress', 0)}%",
                    "Tiêu đề (Title)": title_ai,
                    "Hashtag": hashtags_ai,
                    "Cập nhật": job.get("updated_at", ""),
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("Chưa có dữ liệu sản xuất.")

    if counts["running"] > 0 or counts["queued"] > 0:
        time.sleep(2.5)
        st.rerun()
