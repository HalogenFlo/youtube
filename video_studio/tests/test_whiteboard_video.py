import os
import subprocess
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.whiteboard_video import (  # noqa: E402
    WhiteboardRenderer,
    compute_reveal_schedule,
    layout_scene_items,
    render_whiteboard_scene_video,
)

SIZE = (270, 480)


def test_layout_uses_valid_items_and_drops_invalid():
    scene = {
        "whiteboard_items": [
            {"type": "text", "text": "1 Tỷ $", "x": 0.5, "y": 0.2},
            {"type": "circle", "x": 0.3, "y": 0.5, "r": 0.1},
            {"type": "stickman", "x": 0.7, "y": 0.8, "emotion": "surprised"},
            {"type": "unknown_thing", "x": 0.1, "y": 0.1},
            {"type": "text"},  # thiếu nội dung
            "rác",
        ]
    }
    items = layout_scene_items(scene)
    assert [i["type"] for i in items] == ["text", "circle", "stickman"]
    for it in items:
        assert 0.0 <= it["x"] <= 1.0 and 0.0 <= it["y"] <= 1.0


def test_layout_clamps_out_of_range_coordinates():
    items = layout_scene_items({"whiteboard_items": [{"type": "circle", "x": 5, "y": -2, "r": 0.1}]})
    assert items[0]["x"] == 1.0 and items[0]["y"] == 0.0


def test_layout_auto_fallback_has_title_and_one_stickman_per_speaker():
    scene = {
        "scene_role": "Opening Hook",
        "narration": "Tại sao bầu trời màu xanh?",
        "dialogue_lines": [
            {"speaker": "narrator", "text": "Tại sao bầu trời màu xanh?"},
            {"speaker": "character_1", "character_name": "Bin", "text": "Mình thắc mắc quá!"},
            {"speaker": "character_2", "character_name": "Cô Lan", "text": "Cùng tìm hiểu nhé."},
        ],
    }
    items = layout_scene_items(scene)
    types = [i["type"] for i in items]
    assert types.count("stickman") == 2
    assert "text" in types
    names = [i.get("name") for i in items if i["type"] == "stickman"]
    assert names == ["Bin", "Cô Lan"]


def test_reveal_schedule_is_ordered_and_within_duration():
    sched = compute_reveal_schedule(4, 10.0)
    assert len(sched) == 4
    prev_end = 0.0
    for t0, t1 in sched:
        assert t0 >= prev_end - 1e-6
        assert t1 > t0
        prev_end = t1
    assert sched[-1][1] <= 10.0 * 0.9 + 1e-6
    assert compute_reveal_schedule(0, 5.0) == []


def test_frame_starts_blank_and_ends_fully_drawn_with_hand_visible_midway():
    items = layout_scene_items(
        {"whiteboard_items": [{"type": "circle", "x": 0.5, "y": 0.5, "r": 0.25}, {"type": "text", "text": "A", "x": 0.5, "y": 0.2}]}
    )
    r = WhiteboardRenderer(items, duration=4.0, size=SIZE)
    first = r.render_frame(0.0).convert("L")
    last = r.render_frame(4.0).convert("L")
    assert first.getextrema()[0] == 255  # trắng tinh, chưa có nét vẽ / bàn tay
    assert last.getextrema()[0] < 80  # đã có nét mực đen

    sched = compute_reveal_schedule(len(items), 4.0)
    mid_t = (sched[0][0] + sched[0][1]) / 2
    mid = r.render_frame(mid_t).convert("RGB")
    full = r.render_frame(4.0).convert("RGB")
    assert mid.size == SIZE
    assert list(mid.getdata()) != list(full.getdata())  # đang vẽ dở + có bàn tay


def test_drawn_pixels_grow_monotonically_over_time():
    items = layout_scene_items({"whiteboard_items": [{"type": "circle", "x": 0.5, "y": 0.5, "r": 0.3}]})
    # Test the artwork mask independently of a photographic hand occluding the ink.
    r = WhiteboardRenderer(items, duration=3.0, size=SIZE, show_hand=False)
    final = r.render_frame(3.0).convert("L")
    final_ink = {i for i, p in enumerate(final.getdata()) if p < 90}

    def ink(t):
        # Chỉ đếm điểm mực thuộc hình cuối cùng, loại viền đen của bàn tay đang vẽ
        img = r.render_frame(t).convert("L")
        return sum(1 for i, p in enumerate(img.getdata()) if p < 90 and i in final_ink)

    counts = [ink(t) for t in (0.0, 1.0, 2.0, 3.0)]
    assert counts[0] == 0
    assert counts[1] > 0
    assert counts[1] <= counts[2] <= counts[3] == len(final_ink)


def test_render_scene_video_creates_playable_mp4_with_audio(tmp_path):
    audio = tmp_path / "a.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(audio)],
        check=True, capture_output=True,
    )
    scene = {"whiteboard_items": [{"type": "stickman", "x": 0.5, "y": 0.7, "emotion": "happy"}, {"type": "text", "text": "Xin chào", "x": 0.5, "y": 0.2}]}
    out = tmp_path / "scene.mp4"
    ok, err = render_whiteboard_scene_video(scene, str(out), duration=2.0, audio_path=str(audio), size=SIZE, fps=8)
    assert ok, err
    assert out.exists() and out.stat().st_size > 1000
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "video,270,480" in probe
    assert "audio" in probe


def test_render_scene_video_without_audio_has_no_audio_stream(tmp_path):
    out = tmp_path / "silent.mp4"
    ok, err = render_whiteboard_scene_video({"narration": "Thử"}, str(out), duration=1.0, size=SIZE, fps=8)
    assert ok, err
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "audio" not in probe
