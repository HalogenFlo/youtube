import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

st_testing = pytest.importorskip("streamlit.testing.v1")


def _app():
    from src.app_library import render_video_library

    render_video_library()


@pytest.fixture()
def library(tmp_path, monkeypatch):
    import src.video_library as lib

    monkeypatch.setattr(lib, "DEFAULT_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(lib, "CONFIG_PATH", tmp_path / "cfg.json")
    for i, title in enumerate(["Tại sao bầu trời màu xanh?", "Chào buổi sáng bằng tiếng Anh"]):
        (tmp_path / f"v{i}.mp4").write_bytes(b"x" * 4096)
        (tmp_path / f"v{i}.json").write_text(
            json.dumps({"topic": title, "visual_mode": "whiteboard", "story_data": {"story_title": title, "scenes": []}}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.utime(tmp_path / f"v{i}.mp4", (1_000_000 + i, 1_000_000 + i))
    return tmp_path


def test_library_page_renders_all_videos_with_header_and_code_blocks(library):
    at = st_testing.AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception
    titles = [e.label for e in at.expander]
    assert any("Chào buổi sáng" in t for t in titles) and any("bầu trời" in t for t in titles)
    code_blocks = [c.value for c in at.code]
    assert any("PIPELINE" in c and "MuseAI" in c for c in code_blocks)  # mô tả cố định nằm ở đầu mô tả


def test_delete_requires_confirmation_then_removes_video(library):
    at = st_testing.AppTest.from_function(_app, default_timeout=30).run()
    del_btns = [b for b in at.button if "Xóa video" in b.label]
    assert del_btns and all(b.disabled for b in del_btns)  # chưa tick xác nhận -> không xóa được

    confirms = [c for c in at.checkbox if "chắc chắn muốn xóa" in c.label]
    confirms[0].check().run()
    del_btns = [b for b in at.button if "Xóa video" in b.label]
    assert not del_btns[0].disabled
    del_btns[0].click().run()
    remaining = sorted(p.name for p in Path(library).glob("*.mp4"))
    assert len(remaining) == 1


def test_save_header_updates_description_of_all_videos(library):
    import src.video_library as lib

    at = st_testing.AppTest.from_function(_app, default_timeout=30).run()
    area = [t for t in at.text_area if "ĐẦU phần mô tả" in t.label][0]
    area.set_value("Mua pipeline: Zalo 0911111111").run()
    [b for b in at.button if "Lưu mô tả cố định" in b.label][0].click().run()
    assert lib.load_library_config()["description_header"] == "Mua pipeline: Zalo 0911111111"
    assert any(c.value.startswith("Mua pipeline: Zalo 0911111111") for c in at.code)


def test_edit_tiktok_tags_updates_copy_caption_and_restores_channel(library):
    at = st_testing.AppTest.from_function(_app, default_timeout=30).run()
    [t for t in at.text_input if "Hashtag TikTok" in t.label][0].set_value("#BaiHocMoi #hochoidoday").run()
    [b for b in at.button if "Lưu chỉnh sửa" in b.label][0].click().run()
    assert not at.exception
    values = [t.value for t in at.text_input if "Hashtag TikTok" in t.label]
    assert values[0] == "#giaotieplade #BaiHocMoi"
    assert any("#giaotieplade #BaiHocMoi" in c.value for c in at.code)


def test_media_is_loaded_only_after_selecting_one_video(library, monkeypatch):
    import streamlit as st
    shown = []
    downloads = []
    monkeypatch.setattr(st, "video", lambda path, **kw: shown.append(Path(path).name))
    monkeypatch.setattr(st, "download_button", lambda label, data, **kw: downloads.append(kw["file_name"]))
    at = st_testing.AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception and shown == [] and downloads == []
    at.selectbox[0].set_value("v1.mp4").run()
    assert not at.exception and shown == ["v1.mp4"] and downloads == ["v1.mp4"]
    at.selectbox[0].set_value("v0.mp4").run()
    assert not at.exception and shown == ["v1.mp4", "v0.mp4"] and downloads == ["v1.mp4", "v0.mp4"]


def test_deleting_selected_video_clears_player_selection(library):
    at = st_testing.AppTest.from_function(_app, default_timeout=30).run()
    at.selectbox[0].set_value("v1.mp4").run()
    [c for c in at.checkbox if "chắc chắn muốn xóa" in c.label][0].check().run()
    [b for b in at.button if "Xóa video" in b.label][0].click().run()
    assert not at.exception and not (library / "v1.mp4").exists()
    assert at.selectbox[0].value is None
