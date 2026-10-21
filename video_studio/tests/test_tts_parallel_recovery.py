# Chức năng: Kiểm thử tự động cơ chế phục hồi giọng đọc khi gặp lỗi NoAudioReceived hoặc nghẽn mạng song song.

import os
import pytest
from unittest.mock import patch
from src.tts_service import generate_tts, generate_scenes_tts_parallel


def test_generate_tts_smart_prefix_recovery(tmp_path):
    output_file = tmp_path / "test_recovered.mp3"
    
    # Mô phỏng: Lần gọi ban đầu bị lỗi NoAudioReceived, lần sau thành công khi có tiền tố
    attempt_counter = 0

    def mock_direct(text, output_path, voice, rate):
        nonlocal attempt_counter
        attempt_counter += 1
        if "Và rồi" in text or "Thế là" in text or attempt_counter > 6:
            with open(output_path, "wb") as f:
                f.write(b"MOCK_AUDIO_DATA_" * 100)
            return True, output_path
        return False, "edge_tts.exceptions.NoAudioReceived: No audio was received."

    with patch("src.tts_service._run_edge_tts_direct", side_effect=mock_direct), \
         patch("src.tts_service.time.sleep", return_value=None):
        ok, res = generate_tts("Tổ tiên loài người", str(output_file), voice="vi-VN-HoaiMyNeural")
        assert ok is True
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 1000


def test_generate_scenes_tts_parallel_sequential_recovery(tmp_path):
    scenes = [
        {"scene_num": 1, "narration": "Cảnh 1 chào bạn."},
        {"scene_num": 2, "narration": "Cảnh 2 ban đầu bị nghẽn."},
    ]

    worker_calls = {}

    def mock_gen_tts(text, output_path, voice, rate):
        call_count = worker_calls.get(output_path, 0) + 1
        worker_calls[output_path] = call_count
        if "scene_002" in output_path and call_count == 1:
            # Lần đầu chạy song song bị nghẽn
            return False, "edge-tts: No audio was received."
        # Lần sau phục hồi tuần tự thì thành công
        with open(output_path, "wb") as f:
            f.write(b"AUDIO_DATA_" * 120)
        return True, output_path

    with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
         patch("src.tts_service.get_audio_duration", return_value=5.0), \
         patch("src.tts_service.time.sleep", return_value=None):
        ok, msg = generate_scenes_tts_parallel(
            scenes=scenes,
            video_work_dir=str(tmp_path),
            voice="vi-VN-HoaiMyNeural",
            max_workers=2,
        )

        assert ok is True
        assert "audio_path" in scenes[0]
        assert "audio_path" in scenes[1]
        assert os.path.exists(scenes[1]["audio_path"])
