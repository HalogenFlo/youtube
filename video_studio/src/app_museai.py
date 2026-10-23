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


def _render_voice_preview() -> None:
    """Nghe thử giọng VieNeu (theo cảm xúc) và xem trước giọng sẽ gán cho từng vai, trước khi sản xuất."""
    try:
        from src.vieneu_service import PRESET_VOICES, VOICE_PREFIX, generate_vieneu_batch, runtime_python
        from src.voice_casting import VIENEU_VOICE_GENDER, VoiceCaster, emotion_rate
    except ModuleNotFoundError:
        from video_studio.src.vieneu_service import PRESET_VOICES, VOICE_PREFIX, generate_vieneu_batch, runtime_python
        from video_studio.src.voice_casting import VIENEU_VOICE_GENDER, VoiceCaster, emotion_rate
    with st.expander("🔊 Nghe thử giọng đọc (VieNeu) và xem giọng từng vai", expanded=False):
        if not runtime_python().is_file():
            st.warning("Chưa cài VieNeu. Chạy video_studio/scripts/setup_vieneu.ps1 trước.")
            return
        c1, c2 = st.columns(2)
        voice = c1.selectbox("Giọng dẫn chuyện:", PRESET_VOICES, key="prev_voice")
        emotion = c2.selectbox("Cảm xúc câu thoại:", ["neutral", "happy", "excited", "surprised", "angry", "sad", "thinking"], key="prev_emotion")
        sample = st.text_input("Câu đọc thử:", value="Xin chào các bạn, hôm nay mình sẽ dạy các bạn một điều rất thú vị!", key="prev_text")
        caster = VoiceCaster(VOICE_PREFIX + voice)
        male = caster.voice_for("character_1", "Nhân vật nam")[len(VOICE_PREFIX):]
        female = caster.voice_for("character_female", "Nhân vật nữ")[len(VOICE_PREFIX):]
        st.caption(f"Dẫn chuyện: **{voice}** ({VIENEU_VOICE_GENDER[voice]}) · nhân vật nam đầu tiên: **{male}** · nhân vật nữ đầu tiên: **{female}** "
                   f"· tốc độ theo cảm xúc: {emotion_rate(emotion)}")
        if st.button("▶️ Đọc thử", key="prev_btn"):
            out = Path(TEMP_DIR) / "voice_preview.mp3"
            with st.spinner("VieNeu đang đọc (lần đầu tải mô hình, có thể mất 1–2 phút)..."):
                ok, msg = generate_vieneu_batch([(sample, VOICE_PREFIX + voice, emotion_rate(emotion), str(out))])
            if ok and out.exists():
                st.audio(str(out))
            else:
                st.error(msg)


def run_museai_ui() -> None:
    """Render giao diện điều khiển MuseAI + Google Flow Hybrid 3D Pipeline."""
    st.markdown(
        """
        <div style="background: radial-gradient(circle at 90% 10%, rgba(59, 130, 246, 0.25), transparent 40%), linear-gradient(135deg, #0b1528 0%, #110e24 100%);
                    border: 1px solid rgba(96, 165, 250, 0.35); border-radius: 20px; padding: 24px 28px; margin-bottom: 24px;">
            <div style="color: #60a5fa; font-size: 0.8rem; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase;">
                🎬 MuseAI Studio — Hoạt hình 3D &amp; Người que bàn tay vẽ
            </div>
            <h1 style="color: #f0f9ff; font-size: 2.2rem; font-weight: 800; margin: 6px 0 10px 0; letter-spacing: -0.02em;">
                Từ kịch bản MuseAI đến video hoàn chỉnh
            </h1>
            <p style="color: #cbd5e1; font-size: 0.95rem; margin: 0; line-height: 1.6;">
                1. <b>MuseAI</b>: Viết kịch bản, lời đọc và bố cục từng cảnh.<br>
                2. <b>Chọn cách dựng</b>: Hoạt hình 3D qua Google Flow hoặc người que, sơ đồ và bàn tay vẽ ngay trên máy.<br>
                3. <b>Hoàn thiện</b>: Lồng tiếng, phụ đề và xuất MP4. Series tự nhắc bài trước, giới thiệu bài sau.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    view = st.radio("Chế độ:", ["🎬 Sản xuất video", "📚 Thư viện video"], horizontal=True, label_visibility="collapsed")
    if view.startswith("📚"):
        try:
            from src.app_library import render_video_library
        except ModuleNotFoundError:
            from video_studio.src.app_library import render_video_library
        render_video_library()
        return

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
        st.info("🌐 MuseAI viết · Flow dựng 3D · Máy dựng người que")

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

    _render_voice_preview()

    # Form cấu hình sản xuất video 3D
    with st.form("museai_flow_production_form", clear_on_submit=False):
        st.markdown("### 📝 1. Thiết lập kịch bản và series")
        topic = st.text_area(
            "Ý tưởng / Đề tài (để trống để MuseAI tự nghĩ):",
            value="",
            height=90,
            placeholder="Nhập cốt truyện của bạn vào đây (VD: Chú mèo máy vượt đại dương đi tìm hòn đảo pha lê...) hoặc để trống để MuseAI tự sáng tác...",
            help="MuseAI viết kịch bản theo đề tài, kèm bố cục người que hoặc mô tả cảnh 3D theo lựa chọn bên dưới.",
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
            lang_opt = st.selectbox("Ngôn ngữ kịch bản / lời dẫn:",
                                   ["Tiếng Việt (vi)", "English (en)", "Dạy tiếng Anh: giảng Việt + phát âm Anh"], index=0)
            lang = "vi_en" if lang_opt.startswith("Dạy tiếng Anh") else "vi" if "Tiếng Việt" in lang_opt else "en"

        visual_mode_opt = st.radio(
            "🎨 Kiểu video:",
            [
                "🎬 Tạo Video 3D Chuyển Động (MuseAI ➔ Google Flow Veo — ~6-9s/cảnh)",
                "🖼️ Tạo Hình 3D Liên Tục Siêu Tốc — 0 Tín Dụng (MuseAI ➔ Google Flow Nano Banana 2.1 + Chuyển động Visual Beats đổi hình liên tục ~3-4s/câu)",
                "⚡ Kết Hợp Hybrid Thông Minh (Mở đầu & Cao trào dùng Video 3D Veo + Dẫn dắt dùng Hình 3D Nano Banana liên tục)",
                "✏️ Whiteboard minh họa màu / Người que + Bàn tay thật cầm bút (dựng trên máy)",
            ],
            index=0,
            help=(
                "• Tạo Video 3D (Veo): Mỗi nhịp 6-9s là 1 video hoạt hình 3D chuyển động hoàn chỉnh.\n"
                "• Tạo Hình 3D Liên Tục (Nano Banana 2.1 - 0 tín dụng): MuseAI chia nhỏ từng câu (~3-4s/hình) để Google Flow vẽ Hình 3D Pixar khóa cứng nhân vật 7-Point DNA, kết hợp chuyển động máy quay Visual Beats (zoom_in, zoom_out, pan) cực kỳ cuốn hút và nhanh gấp 8 lần!\n"
                "• Kết Hợp Hybrid: Dùng video ở cảnh mở đầu và cao trào.\n"
                "• Whiteboard: Bàn tay thật đi theo nét viền rồi tô màu. MuseAI mô tả hình cần cho từng cảnh; Google Flow tạo hình mới khi kho chưa có. Ảnh đã tạo được lưu để dùng lại. Xuất 1080p."
            ),
        )
        if "Người que" in visual_mode_opt:
            visual_mode_code = "whiteboard"
        elif "Tạo Hình 3D Liên Tục" in visual_mode_opt:
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
                "⚡ Đọc kịch bản đang có sẵn trên tab MuseAI (nếu trùng đề tài)",
                value=False,
                help="Mặc định TẮT để MuseAI luôn viết kịch bản mới 100% theo cốt truyện bạn vừa nhập. Chỉ bật khi bạn muốn lấy lại kịch bản đang mở sẵn trên tab MuseAI.",
            )
            with_tts = c_adv1.checkbox("🎙️ Lồng tiếng (Dẫn chuyện + Nhân vật) & Phụ đề", value=True)
            from src.vieneu_service import PRESET_VOICES, VOICE_PREFIX, runtime_python
            voice_engine = st.selectbox("Giọng giảng tiếng Việt", ["VieNeu v3 Turbo (chạy trên máy)", "Edge TTS"],
                                        index=0 if runtime_python().is_file() else 1)
            vietnamese_voice = ""
            if voice_engine.startswith("VieNeu"):
                preset = st.selectbox("Chọn giọng VieNeu", PRESET_VOICES)
                vietnamese_voice = VOICE_PREFIX + preset
                st.caption("VieNeu đọc lời Việt; đoạn phát âm Anh dùng giọng Anh riêng. Lần đầu cần tải mô hình; ảnh đã tạo vẫn dùng lại.")
            story_timeout = c_adv2.number_input(
                "Chờ MuseAI (giây):",
                min_value=60, max_value=600,
                value=int(cfg.get("story_timeout_seconds", 180)), step=30
            )
            st.caption(
                "🎞️ **Series nhiều tập:** Tập đầu giới thiệu bài sau; tập giữa nhắc bài trước và giới thiệu bài sau; "
                "tập cuối ôn bài trước và khép lại. Lời nối tập được lồng tiếng và có phụ đề khi bật lồng tiếng. "
                "Người que dùng bố cục riêng từng cảnh, thời lượng nét vẽ căn theo lời đọc."
            )
            st.caption("🇻🇳 → 🇬🇧 Chọn 'Dạy tiếng Anh' để giải thích bằng giọng Việt, từ/câu mẫu bằng giọng Anh; "
                       "bài vẽ tay dẫn vào tình huống trước, rồi mới dạy cách nói và luyện lại. Phụ đề theo đúng thứ tự lời đọc.")
            from src.whiteboard_illustrations import ILLUSTRATIONS, custom_illustration_files
            whiteboard_ai_enabled = st.checkbox("✨ AI tự tạo minh họa mới khi cần (Google Flow)", value=True,
                help="Không giới hạn trong kho hình mẫu: MuseAI mô tả vật thể, nhân vật và tình huống; Google Flow tạo hình 2D cùng phong cách. Cần đăng nhập Flow khi có hình mới; ảnh đã tạo được dùng lại.")
            st.caption(f"🎨 Kho hình: {len(ILLUSTRATIONS)} loại minh họa + {len(custom_illustration_files())} ảnh bổ sung. "
                       "Đây là kho dùng nhanh; AI có thể tạo thêm hình theo bài học. Có thể bổ sung PNG/WebP riêng.")

            try:
                from src.flow_character_vault import load_character_vault, build_7_point_character_dna
            except ModuleNotFoundError:
                from video_studio.src.flow_character_vault import load_character_vault, build_7_point_character_dna

            vault_chars = load_character_vault()
            char_options = ["🤖 Tự động để MuseAI thiết kế & Khóa chuẩn 7-Point DNA"] + [
                f"🔒 {c.get('name')} ({c.get('id')})" for c in vault_chars
            ]
            selected_char_label = st.selectbox(
                "🎭 Kho nhân vật 3D (dành cho các kiểu video Google Flow):",
                char_options,
                index=0,
                help="Chọn 1 nhân vật cố định từ kho hoặc để MuseAI tự tạo và tự động nâng cấp lên chuẩn 7-Point Character DNA (giữ nguyên mặt, tóc, mắt, quần áo 100%).",
            )
            custom_char_dna = st.text_input(
                "✍️ Mô tả nhân vật riêng (người que hoặc 3D, tùy chọn):",
                value="",
                placeholder="VD người que: Bin, đầu tròn, nét đen, thân xanh dương; hoặc mô tả nhân vật 3D...",
            )

        submit_btn = st.form_submit_button(
            "🎬 BẮT ĐẦU SẢN XUẤT VIDEO",
            type="primary",
            use_container_width=True
        )

    if submit_btn:
        st.markdown("### 📡 Tiến độ sản xuất video")
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
                f"- **Nhân vật xuyên suốt:** `{char_str[:160]}...`",
                "",
                "| Khung hình | Vai trò & Nhịp truyện | Lời đọc / Lời thoại | Trạng thái dựng |",
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
                live_story_state["scene_status"][s_num] = "⏳ Đang chờ dựng cảnh"
            _render_live_scenes_board()

        def on_scene_status(scene_idx: int, total_sc: int, status_code: str, video_path: Optional[str]):
            if status_code == "rendering":
                live_story_state["scene_status"][scene_idx] = (
                    "✏️ Đang vẽ nét viền và tô màu minh họa..." if visual_mode_code == "whiteboard"
                    else "🎬 Đang tạo cảnh trên Google Flow...")
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
            init_learning = ""
            init_next_topic = ""
            init_voice_casting = {}
            start_episode = 1

            if custom_char_dna and custom_char_dna.strip():
                init_char_anchor = (custom_char_dna.strip() if visual_mode_code == "whiteboard"
                                    else build_7_point_character_dna(custom_char_dna.strip()))
            elif visual_mode_code != "whiteboard" and selected_char_label and not selected_char_label.startswith("🤖"):
                for vc in vault_chars:
                    if f"({vc.get('id')})" in selected_char_label:
                        init_char_anchor = str(vc.get("character_dna") or "")
                        init_env_anchor = str(vc.get("environment_dna") or "")
                        break

            if "Viết tiếp tập mới" in series_mode_opt:
                eff_reuse = False
                ledger_file = Path(TEMP_DIR) / ("series_memory_ledger_whiteboard.json" if visual_mode_code == "whiteboard"
                                                else "series_memory_ledger.json")
                if not ledger_file.exists():
                    st.error("Chưa có series đã lưu cho kiểu video này. Hãy tạo series trước khi chọn viết tiếp.")
                    return
                if ledger_file.exists():
                    try:
                        ldata = json.loads(ledger_file.read_text(encoding="utf-8"))
                        init_voice_casting = dict(ldata.get("voice_casting") or {})
                        saved_narrator = str(ldata.get("vietnamese_voice") or "")
                        if not init_voice_casting:
                            from src.voice_casting import recover_voice_casting
                            for previous_video in reversed(ldata.get("episode_video_paths") or []):
                                previous_meta = Path(previous_video).with_suffix(".json")
                                if previous_meta.is_file():
                                    saved = json.loads(previous_meta.read_text(encoding="utf-8"))
                                    saved_narrator = saved_narrator or str(saved.get("vietnamese_voice") or "")
                                    previous_story = saved.get("story_data") or saved.get("story") or saved
                                    for name, voice in recover_voice_casting(previous_story.get("scenes") or []).items():
                                        init_voice_casting.setdefault(name, voice)
                        if saved_narrator and saved_narrator != vietnamese_voice:
                            vietnamese_voice = saved_narrator
                            st.info(f"Series tiếp tục dùng giọng dẫn đã lưu: {saved_narrator.removeprefix('vieneu-v3:')}.")
                        init_prev_summary = str(ldata.get("previous_episodes_summary") or "")
                        init_learning = str(ldata.get("last_episode_learning") or init_prev_summary)
                        init_next_topic = str(ldata.get("next_episode_topic") or "")
                        start_episode = int(ldata.get("last_episode_num") or 0) + 1
                        if not init_char_anchor:
                            init_char_anchor = str(ldata.get("locked_character_anchor") or "")
                        if not init_env_anchor:
                            init_env_anchor = str(ldata.get("locked_environment_anchor") or "")
                    except (ValueError, OSError, TypeError):
                        st.error("Không đọc được bộ nhớ series. Hãy kiểm tra file lưu trước khi viết tiếp.")
                        return

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
                    initial_episode_learning=init_learning,
                    initial_next_episode_topic=init_next_topic,
                    initial_voice_casting=init_voice_casting,
                    start_episode_num=start_episode,
                    whiteboard_ai_enabled=whiteboard_ai_enabled,
                    vietnamese_voice=vietnamese_voice,
                    progress_callback=on_progress,
                    on_script_ready_callback=on_script_ready,
                    on_scene_status_callback=on_scene_status,
                )
                if success and ep_paths:
                    progress_bar.progress(1.0)
                    st.balloons()
                    st.success(f"🎉 ĐÃ HOÀN TẤT {len(ep_paths)} TẬP VIDEO!")
                    for ep_i, ep_file in enumerate(ep_paths, start=start_episode):
                        if os.path.exists(ep_file):
                            st.markdown(f"#### 📺 Tập {ep_i}: `{Path(ep_file).name}`")
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
                    whiteboard_ai_enabled=whiteboard_ai_enabled,
                    vietnamese_voice=vietnamese_voice,
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
                    st.success(f"🎉 ĐÃ HOÀN TẤT VIDEO: {Path(final_video_or_err).name}")

                    st.markdown("### 📺 Xem trước video hoàn chỉnh")
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
                        with st.expander("📖 Xem kịch bản do MuseAI sáng tác"):
                            st.json(story_data)
                else:
                    progress_bar.progress(0.0)
                    st.error(f"❌ Quá trình sản xuất gặp lỗi: {final_video_or_err}")

        except Exception as exc:
            st.error(f"❌ Ngoại lệ hệ thống: {exc}")
