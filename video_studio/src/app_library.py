"""Giao diện Thư viện video: xem, chỉnh title/hashtag/mô tả, mô tả cố định liên hệ, tải và xóa video."""
from __future__ import annotations

import hashlib
import os

import streamlit as st

try:
    from src import video_library as lib
except ModuleNotFoundError:
    from video_studio.src import video_library as lib


def _key(prefix: str, name: str) -> str:
    return f"{prefix}_{hashlib.md5(name.encode('utf-8')).hexdigest()[:10]}"


def _tags_to_text(tags) -> str:
    return " ".join(tags or [])


def _text_to_tags(text: str):
    return [t if t.startswith("#") else f"#{t}" for t in text.replace(",", " ").split() if t.strip("#")]


def _render_header_settings() -> dict:
    cfg = lib.load_library_config()
    with st.expander("📩 Mô tả cố định đặt ở đầu mọi video (liên hệ mua pipeline, Gemini Pro, MuseAI)", expanded=False):
        header = st.text_area(
            "Nội dung đặt ở ĐẦU phần mô tả:",
            value=cfg["description_header"],
            height=90,
            help="Áp dụng cho tất cả video trong thư viện. Hãy thay phần [ĐIỀN ZALO / EMAIL CỦA BẠN] bằng thông tin liên hệ thật.",
        )
        if st.button("💾 Lưu mô tả cố định", key="lib_save_header"):
            lib.save_library_config({"description_header": header})
            st.success("Đã lưu. Mọi video bên dưới dùng nội dung này ở đầu mô tả.")
            cfg["description_header"] = header
        if "[ĐIỀN" in header:
            st.warning("Bạn chưa thay thông tin liên hệ thật trong mô tả cố định.")
        if len(header.encode("utf-8")) > 2000:
            st.warning("Đoạn liên hệ quá dài: phần xuất ra sẽ được rút gọn để dành chỗ cho nội dung và hashtag. Hãy giữ thông tin liên hệ ngắn gọn.")
    return cfg


def render_video_library() -> None:
    st.markdown("## 📚 Thư viện video đã tạo")
    cfg = _render_header_settings()
    col_a, col_b = st.columns([1, 4])
    if col_a.button("🔄 Làm mới", key="lib_refresh"):
        st.rerun()

    items = lib.scan_library()
    col_b.caption(f"{len(items)} video · thư mục: `{lib.DEFAULT_OUTPUT_DIR}`")
    if not items:
        st.info("Chưa có video nào. Hãy sản xuất video ở tab 'Sản xuất video'.")
        return

    selected_video = st.selectbox("Chọn video để xem hoặc tải", options=[item["name"] for item in items],
                                  index=None, placeholder="Chọn một video…", key="lib_selected_video",
                                  format_func=lambda name: next(item["metadata"]["title"] for item in items if item["name"] == name))

    for item in items:
        path, name, meta = item["path"], item["name"], item["metadata"]
        with st.expander(f"🎬 {meta['title']}  ·  {item['created']}  ·  {item['size_mb']} MB", expanded=name == selected_video):
            col_v, col_m = st.columns([1, 1.4])
            with col_v:
                if name == selected_video:
                    st.video(path)
                    with open(path, "rb") as fh:
                        st.download_button("⬇️ Tải video", fh, file_name=name, mime="video/mp4",
                                           key=_key("dl", name), use_container_width=True)
                else:
                    st.caption("Chọn video ở danh sách phía trên để xem hoặc tải.")
                st.caption(f"`{name}`")
            with col_m:
                title = st.text_input("Tiêu đề (≤100 ký tự)", value=meta["title"], max_chars=100, key=_key("t", name))
                tags_yt = st.text_input("Hashtag YouTube (tối đa 5)", value=_tags_to_text(meta["hashtags_youtube"]), key=_key("hy", name))
                tags_tt = st.text_input("Hashtag TikTok (tối đa 5)", value=_tags_to_text(meta["hashtags_tiktok"]), key=_key("ht", name))
                body = st.text_area("Nội dung mô tả", value=meta["description_body"], height=110, key=_key("b", name))
                caption = st.text_area("Caption TikTok (hashtag tự gắn khi lưu)", value=meta["tiktok_caption_body"], height=110, key=_key("c", name))
                st.caption(f"Hashtag kênh tự giữ: {meta['channel_hashtag']}. Hashtag chủ đề áp dụng cho phần sao chép bên dưới sau khi lưu.")
                if st.button("💾 Lưu chỉnh sửa", key=_key("save", name)):
                    lib.update_metadata(path, {
                        "title": title,
                        "hashtags_youtube": _text_to_tags(tags_yt),
                        "hashtags_tiktok": _text_to_tags(tags_tt),
                        "description_body": body,
                        "tiktok_caption": caption,
                    })
                    for field in ("t", "hy", "ht", "b", "c"):
                        st.session_state.pop(_key(field, name), None)
                    st.success("Đã lưu.")
                    st.rerun()

            st.markdown("**📋 Mô tả YouTube hoàn chỉnh (đã có liên hệ cố định ở đầu):**")
            st.code(lib.compose_description(cfg["description_header"], meta), language="text")
            st.markdown("**📋 Caption TikTok:**")
            st.code(meta["tiktok_caption"], language="text")
            st.markdown("**✅ Trước khi đăng (chính sách nội dung AI):**")
            for step in meta["platform_steps"]:
                st.markdown(f"- {step}")
            for note in meta["compliance_notes"]:
                st.caption(f"• {note}")

            st.markdown("---")
            confirm = st.checkbox("Tôi chắc chắn muốn xóa video này (không thể khôi phục)", key=_key("cf", name))
            if st.button("🗑️ Xóa video", key=_key("del", name), type="secondary", disabled=not confirm):
                ok, msg = lib.delete_video(path)
                (st.success if ok else st.error)(msg)
                if ok:
                    if selected_video == name:
                        st.session_state.pop("lib_selected_video", None)
                    st.rerun()
