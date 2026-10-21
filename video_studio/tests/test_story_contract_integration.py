# Chức năng: Kiểm thử tích hợp luồng 5 khâu hạ nguồn theo sơ đồ mermaid-diagram.svg.
# Mục đích: Đảm bảo studio editorial pipeline và batch producer tích hợp đồng bộ 5 hợp đồng hạ nguồn.

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.studio_editorial_service import run_studio_editorial_pipeline
from src.batch_producer import produce_single_video_pipeline, split_prompt_to_video_topics
from src.story_contract_models import build_downstream_contracts_report, normalize_architected_scene


def test_studio_editorial_pipeline_generates_downstream_contracts():
    raw_script = {
        "scenes": [
            {
                "scene_num": 1,
                "narration": "Ngày xửa ngày xưa, con người thời nguyên thủy chưa có tiếng nói.",
                "video_prompt": "Ancient primitive humans gathered around a fire in a cave, flat 2D cartoon, hand-drawn vector art illustration, strictly no 3d, no cgi, no text on image",
            },
            {
                "scene_num": 2,
                "narration": "Họ dùng cử chỉ và các âm thanh giản đơn để giao tiếp.",
                "video_prompt": "Caveman pointing at a mammoth drawing on a stone wall, flat 2D cartoon, vibrant cel-shaded vector art, strictly no 3d, no text on image",
            },
        ]
    }

    scenes, report = run_studio_editorial_pipeline(
        topic="Sự ra đời của ngôn ngữ loài người",
        script_data=raw_script,
        target_scenes=2,
        language="vi",
        content_mode="knowledge",
    )

    assert len(scenes) == 2
    for sc in scenes:
        assert "audio_contract" in sc
        assert "image_contract" in sc
        assert "render_contract" in sc
        assert "sound_contract" in sc
        assert "legal_contract" in sc
        assert sc["audio_contract"]["syllables"] > 0
        assert "background_plate" in sc["image_contract"]
        assert sc["render_contract"]["safe_subtitles"] == "bottom_1_6_safe_zone"

    assert "downstream_contracts" in report
    downstream = report["downstream_contracts"]
    assert downstream["total_scenes"] == 2
    assert downstream["audio_summary"]["total_syllables"] > 0
    assert downstream["image_summary"]["background_plates_count"] == 2
    assert downstream["render_summary"]["engine"] == "Visual Beats & Progressive Layering"
    assert downstream["sound_summary"]["bgm_ducking_enabled"] is True
    assert len(downstream["legal_summary"]["sources"]) > 0
    assert "General Educational" in downstream["legal_summary"]["sources"][0] or "Educational" in downstream["legal_summary"]["sources"][0]


def test_produce_single_video_pipeline_metadata_packaging(tmp_path):
    mock_batch_dir = tmp_path / "batch_temp"
    mock_output_dir = tmp_path / "output"
    mock_batch_dir.mkdir(parents=True, exist_ok=True)
    mock_output_dir.mkdir(parents=True, exist_ok=True)

    fake_video = mock_batch_dir / "rendered_fake.mp4"
    fake_video.write_bytes(b"fake_video_bytes_1234567890")

    mock_script_data = {
        "scenes": [
            {
                "scene_num": 1,
                "narration": "Xin chào các bạn đến với lịch sử ngôn ngữ.",
                "video_prompt": "Friendly stickman guide waving in a prehistoric cave, flat 2D cartoon, no 3d, no text",
            }
        ]
    }

    with patch("src.batch_producer.generate_script", return_value=(True, mock_script_data)), \
         patch("src.batch_producer.generate_scenes_tts_parallel", return_value=(True, "ok")), \
         patch("src.batch_producer.generate_flow_batch_queue", return_value=(True, [], [])), \
         patch("src.batch_producer.compile_video_pipeline", return_value=(True, [str(fake_video)], "")):

        success, path_or_err, meta = produce_single_video_pipeline(
            topic="Nguồn gốc ngôn ngữ",
            video_index=1,
            batch_work_dir=str(mock_batch_dir),
            output_dir=str(mock_output_dir),
            language="vi",
            turbo_mode=True,
            target_scenes=1,
            studio_mode=True,
        )

        assert success is True
        assert os.path.exists(path_or_err)
        assert "downstream_contracts" in meta
        assert meta["downstream_contracts"]["total_scenes"] == 1

        metadata_path = meta.get("metadata_path")
        assert metadata_path is not None
        assert os.path.exists(metadata_path)

        with open(metadata_path, "r", encoding="utf-8") as f:
            saved_json = json.load(f)
            assert "downstream_contracts" in saved_json
            assert saved_json["downstream_contracts"]["audio_summary"]["total_syllables"] > 0
            assert saved_json["scenes"][0]["render_contract"]["safe_subtitles"] == "bottom_1_6_safe_zone"
