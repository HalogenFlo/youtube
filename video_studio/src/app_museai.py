"""Giao diện điều khiển sản xuất Video Hoạt Hình 3D: MuseAI (Viết Kịch Bản) + Google Flow (Sinh Video 3D)."""

from __future__ import annotations

import importlib
import os
import json
import time
from pathlib import Path
from typing import Optional

import streamlit as st

try:
    import src.video_compiler as _vc_mod
    import src.museai_3d_service as _muse_svc
except ModuleNotFoundError:
    import video_studio.src.video_compiler as _vc_mod
    import video_studio.src.museai_3d_service as _muse_svc

_vc_mod = importlib.reload(_vc_mod)
_muse_svc = importlib.reload(_muse_svc)
MuseAIFlowHybridController = _muse_svc.MuseAIFlowHybridController
is_cdp_available = _muse_svc.is_cdp_available
load_hybrid_config = _muse_svc.load_hybrid_config
run_museai_script_to_google_flow_3d_pipeline = _muse_svc.run_museai_script_to_google_flow_3d_pipeline
run_museai_multi_episode_series_pipeline = _muse_svc.run_museai_multi_episode_series_pipeline
OUTPUT_DIR = _muse_svc.OUTPUT_DIR
TEMP_DIR = _muse_svc.TEMP_DIR


def run_museai_ui() -> None:
    """Render giao diện điều khiển MuseAI + Google Flow Hybrid 3D Pipeline."""
    st.markdown(
        """
        <div style="background: radial-gradient(circle at 90% 10%, rgba(59, 130, 246, 0.25), transparent 40%), linear-gradient(135deg, #0b1528 0%, #110e24 100%);
                    border: 1px solid rgba(96, 165, 250, 0.35); border-radius: 20px; padding: 24px 28px; margin-bottom: 24px;">
            <div style="color: #60a5fa; font-size: 0.8rem; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase;">
                🎬 Hybrid 3D Studio v2.5 (Multi-Scene Sequential + Multi-Voice Dialogue)
            </div>
            <h1 style="color: #f0f9ff; font-size: 2.2rem; font-weight: 800; margin: 6px 0 10px 0; letter-spacing: -0.02em;">
                Phim Hoạt Hình 3D (MuseAI ➔ Google Flow)
            </h1>
            <p style="color: #cbd5e1; font-size: 0.95rem; margin: 0; line-height: 1.6;">
                <b>Sự kết hợp hoàn hảo giữa 2 AI hàng đầu trên cùng cửa sổ Chrome (Port 9222):</b><br>
                1. <b>Tab MuseAI</b>: Đóng vai Đạo diễn Pixar viết cốt truyện 3D có đầu có cuối &amp; khóa cứng đặc trưng nhân vật.<br>
                2. <b>Tab Google Flow</b>: Nhận kịch bản và sinh video 3D Pixar/Unreal Engine 5 chân thực cho từng cảnh.<br>
                3. <b>Compiler</b>: Tự động lồng tiếng đọc truyện tiếng Việt, làm phụ đề và ghép thành bộ phim hoàn chỉnh.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cfg = load_hybrid_config()
    cdp_port = int(cfg.get("cdp_port", 9222))
    cdp_online = is_cdp_available(cdp_port)

    # Thẻ trạng thái kết nối Chrome CDP
    col_stat1, col_stat2, col_stat3 = st.columns([1.2, 1.2, 1])
    with col_stat1:
        if cdp_online:
            st.success(f"🟢 Chrome CDP: Đã kết nối (Cổng {cdp_port})")
        else:
            st.warning(f"🟡 Chrome CDP: Chưa mở (Cổng {cdp_port})")

    with col_stat2:
        st.info("🌐 Phối hợp: `muse.ai` + `flow.google.com`")

    with col_stat3:
        if not cdp_online:
            if st.button("🚀 Bật Chrome CDP ngay", use_container_width=True, type="secondary"):
                controller = MuseAIFlowHybridController(cfg)
                ok, msg = controller._launch_chrome_cdp()
                if ok:
                    st.success("Đã mở Chrome kết nối MuseAI và Google Flow!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.caption("✅ Chrome sẵn sàng nhận lệnh tự động.")

    st.markdown("---")

    # Form cấu hình sản xuất video 3D
    with st.form("museai_flow_production_form", clear_on_submit=False):
        st.markdown("### 📝 1. Thiết lập Cốt truyện Hoạt Hình 3D")
        topic = st.text_area(
            "Ý tưởng / Đề tài cốt truyện 3D (Để trống để MuseAI tự nghĩ từ A-Z):",
            value="",
            height=90,
            placeholder="Nhập cốt truyện của bạn vào đây (VD: Chú mèo máy vượt đại dương đi tìm hòn đảo pha lê...) hoặc để trống để MuseAI tự sáng tác...",
            help="MuseAI sẽ viết kịch bản đúng 100% theo cốt truyện bạn nhập và chuyển giao prompt 3D sang Google Flow.",
        )

        col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
        with col_cfg1:
            series_mode_opt = st.selectbox(
                "Chế độ Cốt truyện & Số tập:",
                [
                    "🎬 Phim lẻ 1 tập trọn vẹn (Mở đầu - Cao trào - Kết thúc)",
                    "📺 Ít tập — Mini-Series (2–3 tập nối tiếp nhau)",
                    "📚 Nhiều tập — Series dài kỳ (4–10 tập nối tiếp nhau)",
                    "🔗 Viết tiếp tập mới nối từ tập trước đã lưu",
                ],
                index=0,
                help="Mỗi tập xuất ra 1 video .mp4 hoàn chỉnh có đủ Mở đầu -> Cao trào -> Kết thúc và tự động giữ nguyên tạo hình nhân vật + mạch truyện xuyên suốt các tập.",
            )
            target_scenes = None
        with col_cfg2:
            orientation_opt = st.selectbox(
                "Tỷ lệ khung hình:",
                ["Dọc 9:16 (Shorts / TikTok / Reels)", "Ngang 16:9 (YouTube Chuẩn)"],
                index=0,
            )
            orientation = "vertical" if "9:16" in orientation_opt else "horizontal"
        with col_cfg3:
            lang_opt = st.selectbox("Ngôn ngữ kịch bản / lời dẫn:", ["Tiếng Việt (vi)", "English (en)"], index=0)
            lang = "vi" if "Tiếng Việt" in lang_opt else "en"

        visual_mode_opt = st.radio(
            "🎨 Chế độ Tạo Hình ảnh / Video 3D (kết hợp MuseAI + Google Flow):",
            [
                "🎬 Tạo Video 3D Chuyển Động (MuseAI ➔ Google Flow Veo — ~6-9s/cảnh)",
                "🖼️ Tạo Hình 3D Liên Tục Siêu Tốc — 0 Tín Dụng (MuseAI ➔ Google Flow Nano Banana 2.1 + Chuyển động Visual Beats đổi hình liên tục ~3-4s/câu)",
                "⚡ Kết Hợp Hybrid Thông Minh (Mở đầu & Cao trào dùng Video 3D Veo + Dẫn dắt dùng Hình 3D Nano Banana liên tục)",
            ],
            index=0,
            help=(
                "• Tạo Video 3D (Veo): Mỗi nhịp 6-9s là 1 video hoạt hình 3D chuyển động hoàn chỉnh.\n"
                "• Tạo Hình 3D Liên Tục (Nano Banana 2.1 - 0 tín dụng): MuseAI chia nhỏ từng câu (~3-4s/hình) để Google Flow vẽ Hình 3D Pixar khóa cứng nhân vật 7-Point DNA, kết hợp chuyển động máy quay Visual Beats (zoom_in, zoom_out, pan) cực kỳ cuốn hút và nhanh gấp 8 lần!\n"
                "• Kết Hợp Hybrid: Tiết kiệm tín dụng và thời gian tối đa nhưng vẫn có Video 3D ở cảnh Mở đầu (Hook) và Cao trào (Climax)."
            ),
        )
        if "Tạo Hình 3D Liên Tục" in visual_mode_opt:
            visual_mode_code = "image_3d"
        elif "Hybrid" in visual_mode_opt:
            visual_mode_code = "hybrid_3d"
        else:
            visual_mode_code = "video_3d"

        story_style_opt = st.selectbox(
            "✍️ Phong cách Kịch bản & Lời kể (Kịch bản nói):",
            [
                "🎙️ Kể chuyện Điện ảnh Sâu Sắc & Lô-gic (Văn phong cuốn hút, tự nhiên, không văn mẫu — Khuyên dùng)",
                "🧠 Khám phá Tri thức / Giải thích Khoa học - Lịch sử Triệu View (Phong cách Kurzgesagt / TED-Ed)",
                "🗣️ Phim Hoạt Hình Đối Thoại Sống Động (Tương tác nhân vật ngôi thứ nhất tự nhiên chuẩn Pixar)",
            ],
            index=0,
            help=(
                "Chống hoàn toàn kiểu câu cụt lủn 7-8 chữ ngô nghê hoặc nhân vật tự đọc lời dẫn hành động ngôi thứ 3."
            ),
        )
        if "Khám phá Tri thức" in story_style_opt:
            story_style_code = "viral_knowledge"
        elif "Phim Hoạt Hình Đối Thoại" in story_style_opt:
            story_style_code = "pixar_dialogue"
        else:
            story_style_code = "cinematic_storytelling"

        with st.expander("⚙️ Cấu hình Số tập Series, Đọc kịch bản MuseAI & Lồng tiếng", expanded=True):
            c_ep, c_adv0, c_adv1, c_adv2 = st.columns([1.1, 1.3, 1.1, 0.9])
            total_episodes = c_ep.number_input(
                "Tổng số tập cần sản xuất:",
                min_value=1,
                max_value=12,
                value=3 if "Ít tập" in series_mode_opt else (5 if "Nhiều tập" in series_mode_opt else 1),
                step=1,
                help="Nếu chọn 1 tập: Phim lẻ trọn vẹn. Nếu chọn 2-12 tập: Hệ thống tự động viết tiếp cốt truyện qua từng tập, mỗi tập đều có Mở đầu -> Cao trào -> Kết thúc!",
            )
            reuse_existing_script = c_adv0.checkbox(
                "⚡ Đọc ngay kịch bản 3D đang có sẵn trên tab MuseAI (nếu trùng đề tài)",
                value=False,
                help="Mặc định TẮT để MuseAI luôn viết kịch bản mới 100% theo cốt truyện bạn vừa nhập. Chỉ bật khi bạn muốn lấy lại kịch bản đang mở sẵn trên tab MuseAI.",
            )
            with_tts = c_adv1.checkbox("🎙️ Lồng tiếng (Dẫn chuyện + Nhân vật) & Phụ đề", value=True)
            story_timeout = c_adv2.number_input(
                "Chờ MuseAI (giây):",
                min_value=60, max_value=600,
                value=int(cfg.get("story_timeout_seconds", 180)), step=30
            )
            st.caption(
                "🎞️ **Cơ chế Khung hình & Cốt truyện:** Số khung cảnh (Shots) mỗi tập được **tự động chia khớp 1:1 theo nhịp câu chuyện** "
                "(mỗi nhịp ~6–9s là 1 khung hình video 3D mới, tuyệt đối không lặp lại khung hình cũ). Mỗi tập đều có đủ **Mở đầu ➔ Cao trào ➔ Kết thúc**."
            )

            try:
                from src.flow_character_vault import load_character_vault, build_7_point_character_dna
            except ModuleNotFoundError:
                from video_studio.src.flow_character_vault import load_character_vault, build_7_point_character_dna

            vault_chars = load_character_vault()
            char_options = ["🤖 Tự động để MuseAI thiết kế & Khóa chuẩn 7-Point DNA"] + [
                f"🔒 {c.get('name')} ({c.get('id')})" for c in vault_chars
            ]
            selected_char_label = st.selectbox(
                "🎭 Kho Nhân Vật Cố Định 3D (7-Point Character DNA Lock xuyên suốt mọi cảnh & mọi tập):",
                char_options,
                index=0,
                help="Chọn 1 nhân vật cố định từ kho hoặc để MuseAI tự tạo và tự động nâng cấp lên chuẩn 7-Point Character DNA (giữ nguyên mặt, tóc, mắt, quần áo 100%).",
            )
            custom_char_dna = st.text_input(
                "✍️ Hoặc nhập mô tả Nhân vật cố định riêng (tùy chọn — bỏ trống nếu dùng lựa chọn trên):",
                value="",
                placeholder="VD: Leo, stylized Pixar 3D young explorer in olive-green jacket with brass compass...",
            )

        submit_btn = st.form_submit_button(
            "🎬 BẮT ĐẦU SẢN XUẤT PHIM 3D (MUSEAI ➔ GOOGLE FLOW)",
            type="primary",
            use_container_width=True
        )

    if submit_btn:
        st.markdown("### 📡 Tiến độ Sản Xuất Thời Gian Thực (MuseAI ➔ Google Flow)")
        progress_bar = st.progress(0.0)
        status_box = st.empty()
        script_live_box = st.empty()
        log_box = st.empty()

        logs_history = []
        live_story_state = {"story": None, "scene_status": {}}

        def _render_live_scenes_board():
            story = live_story_state.get("story")
            if not story:
                return
            scenes_list = story.get("scenes", [])
            title_str = story.get("story_title", "Phim Hoạt Hình 3D")
            char_str = story.get("character_anchor", "")
            rows_md = [
                f"#### 📖 Kịch bản đã chia khung khớp nhịp truyện: **{title_str}** ({len(scenes_list)} khung hình)",
                f"- **Nhân vật 3D khóa cứng (`character_anchor`):** `{char_str[:160]}...`",
                "",
                "| Khung hình | Vai trò & Nhịp truyện | Kịch bản Lồng tiếng (🎙️ Dẫn chuyện + 🗣️ Nhân vật tương tác) | Trạng thái đưa vào Google Flow |",
                "| :---: | :--- | :--- | :--- |",
            ]
            for sc in scenes_list:
                s_num = int(sc.get("scene_num", 1))
                s_role = str(sc.get("scene_role", f"Scene {s_num}"))
                s_narr = str(sc.get("dialogue_display") or sc.get("narration") or "")
                st_info = live_story_state["scene_status"].get(s_num, "⏳ Đang chờ đến lượt...")
                rows_md.append(f"| **Khung {s_num}/{len(scenes_list)}** | `{s_role}` | {s_narr} | **{st_info}** |")
            script_live_box.markdown("\n".join(rows_md))

        def on_script_ready(story_data: dict):
            live_story_state["story"] = story_data
            live_story_state["scene_status"] = {}
            for sc in story_data.get("scenes", []):
                s_num = int(sc.get("scene_num", 1))
                live_story_state["scene_status"][s_num] = "⏳ Đang chờ đưa vào Google Flow"
            _render_live_scenes_board()

        def on_scene_status(scene_idx: int, total_sc: int, status_code: str, video_path: Optional[str]):
            if status_code == "rendering":
                live_story_state["scene_status"][scene_idx] = "🎬 Đang đưa vào Google Flow & chờ Veo render 3D..."
            elif status_code == "completed":
                fname = Path(video_path).name if video_path else f"scene_{scene_idx:03d}.mp4"
                live_story_state["scene_status"][scene_idx] = f"✅ Đã xong (`{fname}`)"
            elif status_code == "failed":
                live_story_state["scene_status"][scene_idx] = "❌ Lỗi sinh cảnh này"
            _render_live_scenes_board()

        def on_progress(pct: float, message: str):
            clamped_pct = max(0.0, min(100.0, pct)) / 100.0
            progress_bar.progress(clamped_pct)
            status_box.markdown(f"**Trạng thái hiện tại:** `{message}`")
            logs_history.append(f"[{time.strftime('%H:%M:%S')}] {message}")
            log_box.code("\n".join(logs_history[-12:]), language="text")

        try:
            eff_episodes = int(total_episodes)
            if "Ít tập" in series_mode_opt and eff_episodes < 2:
                eff_episodes = 2
            elif "Nhiều tập" in series_mode_opt and eff_episodes < 4:
                eff_episodes = 4

            init_prev_summary = ""
            init_char_anchor = ""
            init_env_anchor = ""
            eff_reuse = reuse_existing_script

            if custom_char_dna and custom_char_dna.strip():
                init_char_anchor = build_7_point_character_dna(custom_char_dna.strip())
            elif selected_char_label and not selected_char_label.startswith("🤖"):
                for vc in vault_chars:
                    if f"({vc.get('id')})" in selected_char_label:
                        init_char_anchor = str(vc.get("character_dna") or "")
                        init_env_anchor = str(vc.get("environment_dna") or "")
                        break

            if "Viết tiếp tập mới" in series_mode_opt:
                eff_reuse = False
                ledger_file = Path(TEMP_DIR) / "series_memory_ledger.json"
                if ledger_file.exists():
                    try:
                        ldata = json.loads(ledger_file.read_text(encoding="utf-8"))
                        init_prev_summary = str(ldata.get("previous_episodes_summary") or "")
                        if not init_char_anchor:
                            init_char_anchor = str(ldata.get("locked_character_anchor") or "")
                        if not init_env_anchor:
                            init_env_anchor = str(ldata.get("locked_environment_anchor") or "")
                    except Exception:
                        pass

            if eff_episodes > 1 or init_prev_summary:
                success, ep_paths, series_meta = run_museai_multi_episode_series_pipeline(
                    topic=topic.strip(),
                    total_episodes=eff_episodes,
                    target_scenes=target_scenes,
                    language=lang,
                    orientation=orientation,
                    visual_mode=visual_mode_code,
                    story_style=story_style_code,
                    with_tts_and_subtitles=with_tts,
                    reuse_existing_script_for_ep1=eff_reuse,
                    story_timeout_sec=int(story_timeout),
                    initial_previous_summary=init_prev_summary,
                    initial_character_anchor=init_char_anchor,
                    initial_environment_anchor=init_env_anchor,
                    progress_callback=on_progress,
                    on_script_ready_callback=on_script_ready,
                    on_scene_status_callback=on_scene_status,
                )
                if success and ep_paths:
                    progress_bar.progress(1.0)
                    st.balloons()
                    st.success(f"🎉 ĐÃ HOÀN TẤT BỘ SERIES {len(ep_paths)} TẬP PHIM 3D!")
                    for ep_i, ep_file in enumerate(ep_paths, start=1):
                        if os.path.exists(ep_file):
                            st.markdown(f"#### 📺 Tập {ep_i}/{len(ep_paths)}: `{Path(ep_file).name}`")
                            st.video(ep_file)
                            with open(ep_file, "rb") as vf:
                                st.download_button(
                                    f"⬇️ Tải Tập {ep_i} ({Path(ep_file).name})",
                                    vf,
                                    file_name=Path(ep_file).name,
                                    mime="video/mp4",
                                    key=f"dl_ep_{ep_i}",
                                    use_container_width=True,
                                )
                else:
                    progress_bar.progress(0.0)
                    st.error(f"❌ Quá trình sản xuất Series gặp lỗi: {series_meta.get('error', 'Không rõ lỗi')}")
            else:
                success, final_video_or_err, meta = run_museai_script_to_google_flow_3d_pipeline(
                    topic=topic.strip(),
                    target_scenes=target_scenes,
                    language=lang,
                    orientation=orientation,
                    visual_mode=visual_mode_code,
                    story_style=story_style_code,
                    with_tts_and_subtitles=with_tts,
                    reuse_existing_script=eff_reuse,
                    story_timeout_sec=int(story_timeout),
                    locked_character_anchor=init_char_anchor,
                    locked_environment_anchor=init_env_anchor,
                    progress_callback=on_progress,
                    on_script_ready_callback=on_script_ready,
                    on_scene_status_callback=on_scene_status,
                )

                if success and os.path.exists(final_video_or_err):
                    progress_bar.progress(1.0)
                    st.balloons()
                    st.success(f"🎉 ĐÃ HOÀN TẤT BỘ PHIM 3D: {Path(final_video_or_err).name}")

                    st.markdown("### 📺 Xem Trước Phim Hoạt Hình 3D Hoàn Chỉnh")
                    st.video(final_video_or_err)

                    col_dl1, col_dl2 = st.columns(2)
                    with open(final_video_or_err, "rb") as vf:
                        col_dl1.download_button(
                            "⬇️ Tải Video MP4 Hoàn Chỉnh",
                            vf,
                            file_name=Path(final_video_or_err).name,
                            mime="video/mp4",
                            use_container_width=True,
                        )

                    meta_path = str(Path(final_video_or_err).with_suffix(".json"))
                    if os.path.exists(meta_path):
                        with open(meta_path, "rb") as mf:
                            col_dl2.download_button(
                                "📄 Tải Kịch Bản & Metadata (JSON)",
                                mf,
                                file_name=Path(meta_path).name,
                                mime="application/json",
                                use_container_width=True,
                            )

                    story_data = meta.get("story_data", {})
                    if story_data:
                        with st.expander("📖 Xem Kịch bản 3D do MuseAI sáng tác"):
                            st.json(story_data)
                else:
                    progress_bar.progress(0.0)
                    st.error(f"❌ Quá trình sản xuất gặp lỗi: {final_video_or_err}")

        except Exception as exc:
            st.error(f"❌ Ngoại lệ hệ thống: {exc}")
