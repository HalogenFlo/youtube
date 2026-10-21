# -*- coding: utf-8 -*-
"""Unit tests cho tính năng số phân cảnh tự động linh hoạt theo cốt truyện (Dynamic Story Scenes)."""

import pytest
from unittest.mock import patch, MagicMock
from src.llm_service import generate_script
from src.studio_editorial_service import _sanitize_scenes, run_studio_editorial_pipeline
from src.autonomous_factory import add_factory_jobs, get_factory_state


def test_generate_script_prompt_dynamic_scenes_when_none():
    """Kiểm tra generate_script với target_scenes=None không gò ép số cảnh cứng."""
    with patch("src.llm_service.call_ollama") as mock_ollama:
        mock_ollama.return_value = (True, {"scenes": [{"scene_num": 1, "narration": "test", "video_prompt": "prompt"}]})
        
        generate_script(
            topic="Bí ẩn tam giác quỷ Bermuda",
            target_scenes=None,
            content_mode="story_explainer"
        )
        
        call_args = mock_ollama.call_args[0]
        user_prompt = call_args[0]
        
        # Không được chứa câu ép cứng "Kịch bản phải có ĐÚNG X phân cảnh"
        assert "Kịch bản phải có ĐÚNG" not in user_prompt
        # Phải chứa chỉ dẫn số phân cảnh tự do theo cốt truyện
        assert "SỐ PHÂN CẢNH TỰ DO THEO CỐT TRUYỆN" in user_prompt
        assert "tối ưu nhất (thường từ 3 đến 8 phân cảnh)" in user_prompt


def test_generate_script_prompt_explicit_scenes_preserved():
    """Bảo toàn tính năng khi người dùng/hệ thống chỉ định rõ target_scenes."""
    with patch("src.llm_service.call_ollama") as mock_ollama:
        mock_ollama.return_value = (True, {"scenes": [{"scene_num": 1, "narration": "test", "video_prompt": "prompt"}]})
        
        generate_script(
            topic="Từ vựng tiếng Anh",
            target_scenes=4,
            content_mode="english_vocab_story"
        )
        
        call_args = mock_ollama.call_args[0]
        user_prompt = call_args[0]
        
        assert "Kịch bản phải có ĐÚNG 4 phân cảnh" in user_prompt


def test_sanitize_scenes_preserves_all_scenes_when_target_scenes_none():
    """_sanitize_scenes không được cắt gọt mảng scenes khi target_scenes là None."""
    mock_scenes = [
        {"scene_num": i, "narration": f"Narration {i}", "video_prompt": f"Action {i} of character"}
        for i in range(1, 8)
    ]
    cleaned = _sanitize_scenes(mock_scenes, target_scenes=None)
    assert len(cleaned) == 7
    for i, sc in enumerate(cleaned, start=1):
        assert sc["scene_num"] == i
        assert f"Narration {i}" in sc["narration"]


def test_sanitize_scenes_slices_when_target_scenes_specified():
    """_sanitize_scenes vẫn cắt đúng số cảnh khi target_scenes được truyền."""
    mock_scenes = [
        {"scene_num": i, "narration": f"Narration {i}", "video_prompt": f"Action {i}"}
        for i in range(1, 6)
    ]
    cleaned = _sanitize_scenes(mock_scenes, target_scenes=3)
    assert len(cleaned) == 3


def test_run_studio_editorial_pipeline_accepts_natural_scene_count():
    """run_studio_editorial_pipeline chấp nhận số cảnh tự nhiên do AI đề xuất khi target_scenes=None."""
    input_scenes = [
        {"scene_num": 1, "narration": "Đoạn 1", "video_prompt": "Scene 1 2D cartoon animation"},
        {"scene_num": 2, "narration": "Đoạn 2", "video_prompt": "Scene 2 2D cartoon animation"},
        {"scene_num": 3, "narration": "Đoạn 3", "video_prompt": "Scene 3 2D cartoon animation"},
        {"scene_num": 4, "narration": "Đoạn 4", "video_prompt": "Scene 4 2D cartoon animation"},
        {"scene_num": 5, "narration": "Đoạn 5", "video_prompt": "Scene 5 2D cartoon animation"},
        {"scene_num": 6, "narration": "Đoạn 6", "video_prompt": "Scene 6 2D cartoon animation"},
    ]
    
    with patch("src.studio_editorial_service.call_ollama") as mock_ollama:
        # LLM trả về bản biên tập giữ nguyên 6 cảnh
        mock_ollama.return_value = (True, {
            "scenes": input_scenes,
            "report": {
                "scores": {"factual_accuracy": 90, "hook_strength": 90, "clarity": 90, "visual_continuity": 90, "policy_safety": 95},
                "issues_fixed": ["Tối ưu hook"],
                "approved": True
            }
        })
        
        scenes, report = run_studio_editorial_pipeline(
            topic="Lịch sử loài người",
            script_data={"scenes": input_scenes},
            target_scenes=None
        )
        
        assert len(scenes) == 6
        assert report.get("approved") is True


def test_add_factory_jobs_stores_target_scenes_none():
    """add_factory_jobs lưu target_scenes=None trong settings của job."""
    with patch("src.autonomous_factory.ensure_factory_worker"):
        job_ids = add_factory_jobs(
            prompt="Chủ đề thử nghiệm cốt truyện tự nhiên",
            count=1,
            target_scenes=None
        )
        assert len(job_ids) == 1
        
        state = get_factory_state()
        added_job = next(j for j in state["jobs"] if j["id"] == job_ids[0])
        assert added_job["settings"]["target_scenes"] is None
