# Chức năng: Kiểm thử tích hợp End-to-End (E2E) cho toàn bộ luồng sản xuất video Chế độ Turbo Batch.
# Lý do tạo: Chứng minh tính thông suốt từ Kịch bản -> TTS song song -> Flow Batch Queue -> Biên tập & Xuất video MP4.

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.batch_producer import produce_single_video_pipeline


class TestTurboBatchE2E:

    @pytest.fixture
    def setup_dirs(self):
        with tempfile.TemporaryDirectory() as tmp_work, tempfile.TemporaryDirectory() as tmp_out:
            yield tmp_work, tmp_out

    @patch("src.batch_producer.compile_video_pipeline")
    @patch("src.batch_producer.generate_flow_batch_queue")
    @patch("src.batch_producer.generate_scenes_tts_parallel")
    @patch("src.batch_producer.generate_script")
    def test_turbo_mode_e2e_successful_export(
        self,
        mock_script,
        mock_tts_parallel,
        mock_flow_queue,
        mock_compile,
        setup_dirs,
    ):
        """Kiểm thử luồng Turbo Batch hoàn tất thành công từ đầu đến cuối (E2E)."""
        tmp_work, tmp_out = setup_dirs

        # 1. Mock Kịch bản
        mock_script.return_value = (True, {
            "scenes": [
                {"scene_num": 1, "narration": "Cảnh một giới thiệu vũ trụ bao la.", "video_prompt": "Universe galaxy"},
                {"scene_num": 2, "narration": "Cảnh hai khám phá các hành tinh bí ẩn.", "video_prompt": "Solar system planets"},
                {"scene_num": 3, "narration": "Cảnh ba kết luận và lời kêu gọi đăng ký kênh.", "video_prompt": "Spaceship flying"},
            ]
        })

        # 2. Mock TTS song song
        def fake_tts_parallel(scenes, video_work_dir, **kwargs):
            for sc in scenes:
                sc_num = sc["scene_num"]
                dummy_audio = os.path.join(video_work_dir, f"scene_{sc_num:03d}.mp3")
                with open(dummy_audio, "wb") as f:
                    f.write(b"FAKE_MP3_DATA" * 100)
                sc["audio_path"] = dummy_audio
                sc["audio_duration"] = 3.5
            return True, "SUCCESS"

        mock_tts_parallel.side_effect = fake_tts_parallel

        # 3. Mock Flow Batch Queue
        def fake_flow_queue(scenes, output_dir, **kwargs):
            generated_paths = []
            reports = []
            for sc in scenes:
                sc_num = sc["scene_num"]
                dummy_img = os.path.join(output_dir, f"scene_{sc_num:03d}_bg.png")
                with open(dummy_img, "wb") as f:
                    f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
                sc["image_path"] = dummy_img
                sc["use_video_ai"] = False
                generated_paths.append(dummy_img)
                reports.append({"scene_index": sc_num, "status": "completed"})
            return True, generated_paths, reports

        mock_flow_queue.side_effect = fake_flow_queue

        # 4. Mock Video Compiler
        def fake_compile(scenes, words_timestamps, **kwargs):
            raw_video = os.path.join(tmp_work, "raw_compiled.mp4")
            with open(raw_video, "wb") as f:
                f.write(b"FAKE_MP4_VIDEO_HEADER" + b"\x00" * 500)
            return True, [raw_video], None

        mock_compile.side_effect = fake_compile

        # Chạy pipeline với turbo_mode=True
        success, final_path, meta = produce_single_video_pipeline(
            topic="Khám phá vũ trụ bao la",
            video_index=1,
            batch_work_dir=tmp_work,
            output_dir=tmp_out,
            turbo_mode=True,
            flow_workers=4,
            tts_workers=4,
            studio_mode=False,
        )

        assert success is True
        assert os.path.exists(final_path)
        assert final_path.endswith(".mp4")
        assert os.path.getsize(final_path) > 100

        # Kiểm tra metadata và các phân cảnh
        metadata_path = meta.get("metadata_path")
        assert metadata_path is not None
        assert os.path.exists(metadata_path)
        with open(metadata_path, "r", encoding="utf-8") as f:
            saved_meta = json.load(f)
        assert saved_meta["topic"] == "Khám phá vũ trụ bao la"
        assert len(saved_meta["scenes"]) == 3
        for sc in saved_meta["scenes"]:
            assert os.path.exists(sc["image_path"])
            assert os.path.exists(sc["audio_path"])
            assert sc["audio_duration"] == 3.5

        # Đảm bảo hàm song song được gọi đúng cách
        assert mock_tts_parallel.called
        assert mock_flow_queue.called

    @patch("src.batch_producer.compile_video_pipeline")
    @patch("src.batch_producer.generate_flow_image")
    @patch("src.batch_producer.generate_tts")
    @patch("src.batch_producer.generate_script")
    def test_sequential_mode_backward_compatibility(
        self,
        mock_script,
        mock_tts,
        mock_flow_img,
        mock_compile,
        setup_dirs,
    ):
        """Kiểm thử tính tương thích ngược khi turbo_mode=False (Chế độ Tuần tự chuẩn)."""
        tmp_work, tmp_out = setup_dirs

        mock_script.return_value = (True, {
            "scenes": [
                {"scene_num": 1, "narration": "Cảnh tuần tự một.", "video_prompt": "Scene 1"},
                {"scene_num": 2, "narration": "Cảnh tuần tự hai.", "video_prompt": "Scene 2"},
            ]
        })

        def fake_tts(text, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_SEQ" * 200)
            return True, output_path

        mock_tts.side_effect = fake_tts

        def fake_flow_img(prompt, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"IMG_SEQ" * 1000)
            return True, output_path

        mock_flow_img.side_effect = fake_flow_img

        def fake_compile(scenes, **kwargs):
            raw_video = os.path.join(tmp_work, "seq_compiled.mp4")
            with open(raw_video, "wb") as f:
                f.write(b"MP4_SEQ" * 200)
            return True, [raw_video], None

        mock_compile.side_effect = fake_compile

        # Chạy với turbo_mode=False (Mặc định)
        success, final_path, meta = produce_single_video_pipeline(
            topic="Chủ đề tuần tự chuẩn",
            video_index=2,
            batch_work_dir=tmp_work,
            output_dir=tmp_out,
            turbo_mode=False,
            studio_mode=False,
        )

        assert success is True
        assert os.path.exists(final_path)
        assert mock_tts.call_count == 2
        assert mock_flow_img.call_count == 2
