"""
Unit tests kiểm thử khả năng phòng thủ dữ liệu (Defensive Data Types & Normalization)
Đảm bảo hệ thống KHÔNG BAO GIỜ bị crash với 'str' object has no attribute 'get'
khi LLM Ollama hoặc hệ thống trả về mảng chuỗi (list of str) hoặc dữ liệu phi-dict.
"""

import pytest
from typing import Any, Dict, List
from src.studio_editorial_service import _sanitize_scenes
from src.batch_producer import build_exact_tts_timestamps, normalize_chinese_teaching_scenes
from src.studio_skill_registry import record_skill_outcome, _load_scores
from src.video_compiler import split_scenes_into_parts
from src.flow_browser_service import get_flow_readiness


def test_sanitize_scenes_handles_string_scenes():
    """Kiểm tra _sanitize_scenes tự động bọc chuỗi thành scene dict hợp lệ mà không quăng AttributeError."""
    raw_scenes = [
        "Cảnh 1: Giới thiệu nguồn gốc ngôn ngữ thời tiền sử",
        "Cảnh 2: Sự hình thành của các âm thanh và ký hiệu đầu tiên",
        "Cảnh 3: Kết luận về vai trò của ngôn ngữ trong văn minh",
    ]
    cleaned = _sanitize_scenes(raw_scenes, target_scenes=3, content_mode="english_vocab_story")
    assert len(cleaned) == 3
    for i, sc in enumerate(cleaned, start=1):
        assert isinstance(sc, dict)
        assert sc["scene_num"] == i
        assert "Cảnh" in sc["narration"]
        assert "video_prompt" in sc
        assert "No readable text" in sc["video_prompt"]


def test_sanitize_scenes_handles_mixed_scenes():
    """Kiểm tra _sanitize_scenes xử lý mảng lẫn lộn cả dict và str."""
    raw_scenes = [
        {"scene_num": 1, "narration": "Lời dẫn cảnh 1", "video_prompt": "Cinematic visual 1"},
        "Cảnh 2: Lời dẫn dạng chuỗi thô từ LLM",
        {"narration": "Lời dẫn cảnh 3 không có scene_num"},
    ]
    cleaned = _sanitize_scenes(raw_scenes, target_scenes=3, content_mode="knowledge")
    assert len(cleaned) == 3
    assert cleaned[0]["scene_num"] == 1
    assert cleaned[1]["scene_num"] == 2
    assert "dạng chuỗi" in cleaned[1]["narration"]
    assert cleaned[2]["scene_num"] == 3


def test_build_exact_tts_timestamps_handles_string_scenes():
    """Kiểm tra build_exact_tts_timestamps không bị crash khi scenes chứa phần tử là str."""
    raw_scenes = [
        "Đây là lời dẫn phân cảnh thứ nhất",
        {"scene_num": 2, "narration": "Đây là cảnh thứ hai", "audio_duration": 4.0},
    ]
    timestamps = build_exact_tts_timestamps(raw_scenes)
    assert isinstance(timestamps, list)
    assert len(timestamps) > 0
    words = [item["word"] for item in timestamps]
    assert "Đây" in words


def test_split_scenes_into_parts_handles_string_scenes():
    """Kiểm tra split_scenes_into_parts trong video_compiler không bị crash khi scenes chứa str."""
    raw_scenes = [
        "Cảnh 1 chuỗi",
        {"audio_duration": 6.0},
    ]
    parts = split_scenes_into_parts(raw_scenes, max_duration=60.0)
    assert len(parts) == 1
    assert len(parts[0]) == 2


def test_studio_skill_registry_handles_non_dict_scores(monkeypatch, tmp_path):
    """Kiểm tra record_skill_outcome không crash nếu cache JSON chứa giá trị lỗi kiểu chuỗi."""
    import src.studio_skill_registry as reg
    fake_score_file = tmp_path / "studio_skill_scores.json"
    import json
    # Giả lập file JSON bị lỗi kiểu dữ liệu (chứa string thay vì dict)
    fake_score_file.write_text(json.dumps({
        "education_factcheck_v1": "corrupted_string_value",
        "general_factcheck_v1": 85.5
    }), encoding="utf-8")
    monkeypatch.setattr(reg, "SCORE_PATH", fake_score_file)
    
    # Không được ném AttributeError: 'str' object has no attribute 'get'
    reg.record_skill_outcome(["education_factcheck_v1", "general_factcheck_v1"], success=True)
    updated = json.loads(fake_score_file.read_text(encoding="utf-8"))
    assert isinstance(updated["education_factcheck_v1"], dict)
    assert "score" in updated["education_factcheck_v1"]
    assert "runs" in updated["education_factcheck_v1"]


def test_generate_video_metadata_handles_string_scenes(monkeypatch):
    """Kiểm tra generate_video_metadata không bị crash khi scenes chứa phần tử là str."""
    from src.llm_service import generate_video_metadata
    import src.llm_service as llm_mod

    # Mock call_ollama để test không phụ thuộc vào Ollama service
    monkeypatch.setattr(
        llm_mod,
        "call_ollama",
        lambda prompt, system_prompt, model: (True, {
            "title": "Tiêu đề video test",
            "description": "Mô tả video test",
            "hashtags": ["#test", "#video"],
        })
    )

    raw_scenes = [
        "Lời dẫn cảnh một dạng chuỗi",
        "Lời dẫn cảnh hai dạng chuỗi",
    ]
    ok, meta = generate_video_metadata("nguồn gốc ngôn ngữ", raw_scenes)
    assert ok is True
    assert meta["title"] == "Tiêu đề video test"


def test_get_flow_readiness_handles_corrupted_tabs(monkeypatch):
    """Kiểm tra get_flow_readiness không bị crash khi response từ Chrome CDP chứa list chuỗi."""
    import urllib.request
    import io

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def read(self):
            return b'["https://example.com", "not_a_dict_tab"]'

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=2.0: FakeResponse())
    # Không được ném AttributeError: 'str' object has no attribute 'get'
    status = get_flow_readiness(port=9222)
    assert status in ("disconnected", "login_required", "ready")


def test_defensive_editorial_report_extraction():
    """Kiểm tra logic trích xuất skill_ids an toàn ngay cả khi metadata['editorial_report'] là str."""
    metadata = {
        "topic": "nguồn gốc ngôn ngữ",
        "editorial_report": "chưa được duyệt do timeout"  # String thay vì Dict!
    }
    editorial_report = metadata.get("editorial_report") if isinstance(metadata, dict) else {}
    skill_ids = editorial_report.get("selected_skill_ids", []) if isinstance(editorial_report, dict) else []
    assert skill_ids == []

