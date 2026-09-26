"""Kiểm tra cơ chế Tự Phục Hồi (Self-Healing) khi Google Flow bị quá tải ở một phân cảnh."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.batch_producer import produce_single_video_pipeline


class TestFlowImageSelfHealing(unittest.TestCase):
    @patch("src.batch_producer.generate_script")
    @patch("src.batch_producer.run_studio_editorial_pipeline")
    @patch("src.batch_producer.generate_tts")
    @patch("src.batch_producer.generate_flow_image")
    @patch("src.batch_producer.build_exact_tts_timestamps")
    @patch("src.batch_producer.compile_video_pipeline")
    @patch("src.batch_producer.generate_video_metadata")
    @patch("src.batch_producer.time.sleep")
    def test_pipeline_recovers_when_scene_flow_fails(
        self,
        mock_sleep,
        mock_meta,
        mock_compile,
        mock_whisper,
        mock_flow_img,
        mock_tts,
        mock_editorial,
        mock_script,
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "work"
            out_dir = Path(tmp_dir) / "out"
            work_dir.mkdir(parents=True, exist_ok=True)
            out_dir.mkdir(parents=True, exist_ok=True)

            # Giả lập kịch bản gồm 2 phân cảnh
            mock_script.return_value = (True, {
                "scenes": [
                    {"scene_num": 1, "narration": "Cảnh 1 lời thoại", "video_prompt": "Prompt 1"},
                    {"scene_num": 2, "narration": "Cảnh 2 lời thoại", "video_prompt": "Prompt 2"},
                ]
            })
            mock_editorial.side_effect = lambda topic, script_data, target, **kw: (script_data["scenes"], {"approved": True, "overall_score": 85})
            def mock_gen_tts(text, output_path, **kw):
                Path(output_path).write_bytes(b"MP3_DATA")
                return True, output_path

            mock_tts.side_effect = mock_gen_tts
            mock_whisper.return_value = []

            # Cảnh 1 sinh ảnh thành công
            # Cảnh 2 sinh ảnh thất bại (Google Flow high demand timeout)
            def mock_gen_flow(prompt, output_path, **kwargs):
                if "scene_001" in output_path:
                    Path(output_path).write_bytes(b"PNG_FAKE_IMAGE_1")
                    return True, output_path
                return False, "Google Flow không thể tạo nội dung: Hết thời gian chờ ảnh (90s)"

            mock_flow_img.side_effect = mock_gen_flow

            # Giả lập compile video thành công
            dummy_video = str(work_dir / "compiled.mp4")
            Path(dummy_video).write_bytes(b"MP4_DATA")
            mock_compile.return_value = (True, [dummy_video], "")
            mock_meta.return_value = (True, {"title": "Test Title", "hashtags": ["#test"]})

            success, result_path, run_meta = produce_single_video_pipeline(
                topic="Kiểm tra tự phục hồi",
                video_index=1,
                batch_work_dir=str(work_dir),
                output_dir=str(out_dir),
                language="vi",
                image_engine="flow",
                media_mode="flow_image",
                target_scenes=2,
                studio_mode=False
            )

            # Pipeline không được dừng lại, phải hoàn thành 100% video
            self.assertTrue(success, f"Pipeline thất bại dù có thể tự phục hồi: {result_path}")
            self.assertTrue(os.path.exists(result_path))
            # Cảnh 2 phải kế thừa ảnh từ cảnh 1
            scene_2_img = Path(work_dir) / "video_01" / "scene_002_bg.png"
            self.assertTrue(scene_2_img.exists())
            self.assertEqual(scene_2_img.read_bytes(), b"PNG_FAKE_IMAGE_1")


if __name__ == "__main__":
    unittest.main()
