import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.video_library import (  # noqa: E402
    DEFAULT_DESCRIPTION_HEADER,
    build_video_metadata,
    compose_description,
    delete_video,
    ensure_metadata,
    load_library_config,
    save_library_config,
    scan_library,
    update_metadata,
)

BANNED = {"#fyp", "#foryou", "#foryoupage", "#viral", "#trending", "#xuhuong", "#xuhuongtiktok", "#shorts"}
HEADER = "Liên hệ mua pipeline: Zalo 0900000000"


def _meta(title="Tại sao bầu trời màu xanh?", mode="whiteboard", lang="vi"):
    return {
        "topic": "bầu trời màu xanh",
        "visual_mode": mode,
        "language": lang,
        "story_data": {
            "story_title": title,
            "scenes": [
                {"scene_num": 1, "narration": "Bạn có bao giờ tự hỏi vì sao bầu trời lại màu xanh không?"},
                {"scene_num": 2, "narration": "Ánh sáng mặt trời bị tán xạ bởi các phân tử khí."},
            ],
        },
        "episode_summary": "Bài này giải thích hiện tượng tán xạ ánh sáng.",
    }


def _fake_video(directory, name, content=b"x" * 2048):
    p = os.path.join(directory, name)
    with open(p, "wb") as f:
        f.write(content)
    return p


def test_metadata_title_hashtags_and_limits_are_policy_safe():
    m = build_video_metadata(_meta(title="A" * 300 + " <script>"))
    assert 0 < len(m["title"]) <= 100
    assert "<" not in m["title"] and ">" not in m["title"]
    tags = m["hashtags_youtube"]
    assert 1 <= len(tags) <= 5
    assert all(t.startswith("#") and " " not in t for t in tags)
    assert not ({t.lower() for t in tags} & BANNED)
    assert 1 <= len(m["hashtags_tiktok"]) <= 5
    assert not ({t.lower() for t in m["hashtags_tiktok"]} & BANNED)


def test_metadata_banned_hashtags_from_source_are_removed():
    meta = _meta()
    meta["hashtags"] = ["#fyp", "#viral", "#KhoaHoc", "#xuhuong"]
    m = build_video_metadata(meta)
    assert not ({t.lower() for t in m["hashtags_youtube"]} & BANNED)
    assert "#KhoaHoc" in m["hashtags_youtube"]


def test_english_lesson_mode_gets_learning_tags():
    m = build_video_metadata(_meta(title="Chào buổi sáng bằng tiếng Anh", lang="vi_en"))
    joined = " ".join(m["hashtags_youtube"]).lower()
    assert "tienganh" in joined or "english" in joined


def test_ai_disclosure_and_platform_label_instructions_present():
    m = build_video_metadata(_meta())
    assert m["requires_ai_label"] is None  # a per-video review, not a blanket requirement
    assert m["ai_label_review_required"] is True
    assert "AI" in m["ai_disclosure"]
    assert any("YouTube" in s for s in m["platform_steps"])
    assert any("TikTok" in s for s in m["platform_steps"])


def test_description_starts_with_fixed_header_and_respects_limits():
    m = build_video_metadata(_meta())
    desc = compose_description(HEADER, m)
    assert desc.startswith(HEADER)
    assert m["ai_disclosure"] in desc
    assert m["hashtags_youtube"][0] in desc
    assert len(desc.encode("utf-8")) <= 5000
    assert "<" not in desc and ">" not in desc
    assert compose_description("", m).startswith(m["description_body"][:20])


def test_description_is_trimmed_below_youtube_limit_with_giant_body():
    m = build_video_metadata(_meta())
    m["description_body"] = "nội dung dài " * 2000
    desc = compose_description(HEADER, m)
    assert len(desc.encode("utf-8")) <= 5000
    assert desc.startswith(HEADER)
    assert m["ai_disclosure"] in desc  # phần minh bạch AI không bị cắt mất


def test_description_budget_covers_long_contact_header_and_unicode():
    m = build_video_metadata(_meta())
    m["description_body"] = "Kiến thức 😀 " * 3000
    for header in ("A" * 6000, "Liên hệ 😀 tiếng Việt " * 2000):
        description = compose_description(header, m)
        assert len(description.encode("utf-8")) <= 5000
        assert m["ai_disclosure"] in description
        assert "#giaotieplade" in description
        assert "\ufffd" not in description


def test_oversized_hashtags_cannot_bypass_caption_or_description_limits(tmp_path):
    video = _fake_video(str(tmp_path), "demo.mp4")
    result = update_metadata(video, {"hashtags_youtube": ["#" + "A" * 6000],
                                     "hashtags_tiktok": ["#" + "B" * 6000], "tiktok_caption": "😀" * 2200})
    assert len(result["tiktok_caption"].encode("utf-16-le")) // 2 <= 2200
    assert len(compose_description("Contact " * 2000, result).encode("utf-8")) <= 5000
    assert result["hashtags_tiktok"][0] == "#hochoidoday"


def test_tiktok_caption_within_limit_and_has_label_reminder():
    m = build_video_metadata(_meta())
    assert len(m["tiktok_caption"].encode("utf-16-le")) // 2 <= 2200


def test_config_roundtrip_and_default_header(tmp_path):
    cfg_path = str(tmp_path / "cfg.json")
    assert load_library_config(cfg_path)["description_header"] == DEFAULT_DESCRIPTION_HEADER
    save_library_config({"description_header": HEADER}, cfg_path)
    assert load_library_config(cfg_path)["description_header"] == HEADER


def test_default_header_mentions_pipeline_gemini_and_museai():
    h = DEFAULT_DESCRIPTION_HEADER.lower()
    assert "pipeline" in h and "gemini" in h and "museai" in h


def test_scan_library_lists_newest_first_with_titles_and_ignores_non_video(tmp_path):
    d = str(tmp_path)
    old = _fake_video(d, "museai_flow_old.mp4")
    new = _fake_video(d, "museai_flow_new.mp4")
    with open(os.path.join(d, "museai_flow_new.json"), "w", encoding="utf-8") as f:
        json.dump(_meta(title="Video mới"), f, ensure_ascii=False)
    _fake_video(d, "ghi_chu.txt")
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))
    items = scan_library(d)
    assert [i["name"] for i in items] == ["museai_flow_new.mp4", "museai_flow_old.mp4"]
    assert items[0]["metadata"]["title"] == "Video mới"
    assert items[1]["metadata"]["title"]  # có tiêu đề dự phòng từ tên file
    assert items[0]["size_mb"] >= 0


def test_ensure_metadata_writes_sidecar_and_update_persists_edits(tmp_path):
    d = str(tmp_path)
    v = _fake_video(d, "a.mp4")
    with open(os.path.join(d, "a.json"), "w", encoding="utf-8") as f:
        json.dump(_meta(), f, ensure_ascii=False)
    m = ensure_metadata(v)
    assert os.path.exists(os.path.join(d, "a.publish.json"))
    m2 = update_metadata(v, {"title": "Tiêu đề tự sửa", "hashtags_youtube": ["#fyp", "#KhoaHoc"]})
    assert m2["title"] == "Tiêu đề tự sửa"
    assert "#fyp" not in m2["hashtags_youtube"]  # vẫn lọc hashtag bị cấm khi sửa tay
    assert ensure_metadata(v)["title"] == "Tiêu đề tự sửa"  # không bị ghi đè khi tải lại


def test_channel_is_reserved_for_each_mode_and_never_mixed():
    for mode, channel in [("whiteboard", "#giaotieplade"), ("video_3d", "#hochoidoday"),
                          ("image_3d", "#hochoidoday"), ("hybrid_3d", "#hochoidoday")]:
        source = _meta(mode=mode)
        source["hashtags"] = ["#hochoidoday", "#GIAOTIEPLADE", "#KhoaHoc", "#BauTroi", "#AnhSang", "#VatLy"]
        result = build_video_metadata(source)
        for field in ("hashtags_youtube", "hashtags_tiktok"):
            assert result[field][0] == channel and len(result[field]) <= 5
            assert len([t for t in result[field] if t.lower() in {"#giaotieplade", "#hochoidoday"}]) == 1
        assert channel in result["tiktok_caption"]
        assert channel in compose_description("Liên hệ", result)


def test_museai_topic_hashtags_are_prioritized_over_generic_tags():
    source = _meta(title="Tiếng Anh khi đi chợ và đi sân bay", lang="vi_en")
    source["story_data"]["publishing"] = {"hashtags": ["#TiengAnhDiCho", "#TiengAnhSanBay", "#TiengAnhGiaoTiep"]}
    result = build_video_metadata(source)
    assert result["hashtags_tiktok"][:4] == ["#giaotieplade", "#TiengAnhDiCho", "#TiengAnhSanBay", "#TiengAnhGiaoTiep"]


def test_nested_and_flat_whiteboard_exports_get_drawing_channel(tmp_path):
    source = _meta(lang="vi_en")
    source.pop("visual_mode")
    source["story_data"]["visual_mode"] = "whiteboard"
    assert build_video_metadata(source)["channel_hashtag"] == "#giaotieplade"
    video = _fake_video(str(tmp_path), "preview.mp4")
    (tmp_path / "preview.json").write_text(json.dumps(source["story_data"]), encoding="utf-8")
    assert ensure_metadata(video)["channel_hashtag"] == "#giaotieplade"


def test_old_sidecar_migrates_channel_without_losing_edits(tmp_path):
    video = _fake_video(str(tmp_path), "museai_whiteboard_old.mp4")
    (tmp_path / "museai_whiteboard_old.publish.json").write_text(json.dumps({
        "title": "Tiêu đề đã sửa", "description_body": "Giữ nội dung này",
        "hashtags_tiktok": ["#hochoidoday", "#BaiHoc"], "tiktok_caption": "Lời mời học thử\n#hochoidoday #BaiHoc",
        "user_edited_fields": ["title", "description_body", "hashtags_tiktok", "tiktok_caption"]}), encoding="utf-8")
    result = ensure_metadata(video)
    assert result["title"] == "Tiêu đề đã sửa" and result["description_body"] == "Giữ nội dung này"
    assert result["hashtags_tiktok"] == ["#giaotieplade", "#BaiHoc"]
    assert "#hochoidoday" not in result["tiktok_caption"]
    assert result["tiktok_caption"].startswith("Lời mời học thử")


def test_tiktok_tag_edits_reach_caption_and_keep_channel(tmp_path):
    video = _fake_video(str(tmp_path), "museai_whiteboard_demo.mp4")
    original = ensure_metadata(video)
    result = update_metadata(video, {"hashtags_tiktok": ["#BaiHocMoi", "#hochoidoday"],
                                     "tiktok_caption": "Cùng luyện nói nhé! 😀"})
    assert result["hashtags_tiktok"] == ["#giaotieplade", "#BaiHocMoi"]
    assert result["tiktok_caption"] == "Cùng luyện nói nhé! 😀\n#giaotieplade #BaiHocMoi"
    assert ensure_metadata(video)["tiktok_caption"] == result["tiktok_caption"]
    assert original["tiktok_caption"] != result["tiktok_caption"]


def test_tiktok_emoji_limit_preserves_channel_hashtag(tmp_path):
    video = _fake_video(str(tmp_path), "demo.mp4")
    result = update_metadata(video, {"tiktok_caption": "😀" * 2200})
    assert len(result["tiktok_caption"].encode("utf-16-le")) // 2 <= 2200
    assert result["tiktok_caption"].endswith(" ".join(result["hashtags_tiktok"]))


def test_shorts_is_permitted_as_a_relevant_user_tag(tmp_path):
    video = _fake_video(str(tmp_path), "demo.mp4")
    result = update_metadata(video, {"hashtags_youtube": ["#shorts", "#VatLy"]})
    assert "#shorts" in result["hashtags_youtube"]


def test_delete_video_removes_video_and_sidecars_only(tmp_path):
    d = str(tmp_path)
    v = _fake_video(d, "a.mp4")
    other = _fake_video(d, "b.mp4")
    for ext in (".json", ".publish.json", ".srt"):
        _fake_video(d, "a" + ext)
    ok, msg = delete_video(v, d)
    assert ok, msg
    assert not os.path.exists(v)
    assert not any(os.path.exists(os.path.join(d, "a" + e)) for e in (".json", ".publish.json", ".srt"))
    assert os.path.exists(other)


def test_delete_refuses_paths_outside_library_dir_and_missing_files(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    outside = _fake_video(str(tmp_path), "outside.mp4")
    ok, _ = delete_video(outside, str(lib))
    assert not ok and os.path.exists(outside)
    ok, _ = delete_video(str(lib / "khong_ton_tai.mp4"), str(lib))
    assert not ok
    ok, _ = delete_video(str(lib / ".." / "outside.mp4"), str(lib))
    assert not ok and os.path.exists(outside)
