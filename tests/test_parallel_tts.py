import os
import inspect
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Import hàm cần kiểm thử từ src.tts_service
# Ở bước RED, hàm generate_scenes_tts_parallel chưa tồn tại trong src.tts_service
from src.tts_service import generate_scenes_tts_parallel


class TestParallelTTS(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_function_existence_and_signature(self):
        """Kiểm tra sự tồn tại của generate_scenes_tts_parallel và các tham số chuẩn."""
        self.assertTrue(callable(generate_scenes_tts_parallel))
        sig = inspect.signature(generate_scenes_tts_parallel)
        params = list(sig.parameters.keys())
        expected_params = [
            "scenes",
            "video_work_dir",
            "voice",
            "voice_mode",
            "content_mode",
            "chinese_voice",
            "voice_reference_path",
            "rate",
            "max_workers",
            "progress_callback",
        ]
        for p in expected_params:
            self.assertIn(p, params, f"Tham số '{p}' thiếu trong chữ ký hàm generate_scenes_tts_parallel")

    def test_strict_order_preservation_with_inverted_delays(self):
        """
        Kiểm tra tính bảo toàn thứ tự phân cảnh 1..N tuyệt đối:
        Giả lập các luồng hoàn thành với thời gian ngược nhau (cảnh 1 chậm nhất, cảnh 4 nhanh nhất),
        mảng scenes đầu ra vẫn giữ nguyên 100% thứ tự cảnh 1, 2, 3, 4 cùng các audio_path/audio_duration tương ứng.
        """
        scenes = [
            {"scene_num": 1, "narration": "Cảnh một: Lời mở đầu của video thí nghiệm."},
            {"scene_num": 2, "narration": "Cảnh hai: Diễn biến câu chuyện đang tăng tốc."},
            {"scene_num": 3, "narration": "Cảnh ba: Cao trào kịch tính xuất hiện."},
            {"scene_num": 4, "narration": "Cảnh bốn: Kết luận bài học và chào tạm biệt."},
        ]

        # Delay ngược: cảnh 1 = 0.25s, cảnh 2 = 0.15s, cảnh 3 = 0.08s, cảnh 4 = 0.02s
        delays = {1: 0.25, 2: 0.15, 3: 0.08, 4: 0.02}

        def mock_generate_tts(text, output_path, voice, rate):
            # Tìm scene_num từ filename (ví dụ: scene_001.mp3 -> 1)
            base = os.path.basename(output_path)
            num = int(base.replace("scene_", "").replace(".mp3", ""))
            delay = delays.get(num, 0.05)
            time.sleep(delay)
            # Ghi file audio giả lập >1000 bytes
            with open(output_path, "wb") as f:
                f.write(b"RIFF" + b"0" * 1500)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_generate_tts), \
             patch("src.tts_service.get_audio_duration", return_value=4.2):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                voice="vi-VN-HoaiMyNeural",
                max_workers=4
            )

        self.assertTrue(ok, f"generate_scenes_tts_parallel thất bại: {msg}")
        self.assertEqual(len(scenes), 4)

        # Kiểm tra thứ tự và in-place mutation
        for idx, sc in enumerate(scenes):
            expected_num = idx + 1
            self.assertEqual(sc["scene_num"], expected_num, f"Thứ tự scene bị đảo lộn tại index {idx}!")
            expected_filename = f"scene_{expected_num:03d}.mp3"
            self.assertTrue(sc.get("audio_path", "").endswith(expected_filename),
                            f"Sai audio_path tại index {idx}: {sc.get('audio_path')}")
            self.assertEqual(sc.get("audio_duration"), 4.2,
                             f"audio_duration không được gán chính xác tại index {idx}")
            self.assertTrue(os.path.exists(sc["audio_path"]),
                            f"File audio không tồn tại: {sc['audio_path']}")

    def test_cache_reuse_skips_tts_generation(self):
        """
        Kiểm tra tái sử dụng cache âm thanh:
        Nếu file audio phân cảnh đã tồn tại trên đĩa và dung lượng > 1000 bytes,
        hệ thống phải bỏ qua việc gọi sinh TTS và gán thẳng audio_path, audio_duration.
        """
        scenes = [
            {"scene_num": 1, "narration": "Cảnh một cần sinh mới."},
            {"scene_num": 2, "narration": "Cảnh hai đã có sẵn trong cache."},
            {"scene_num": 3, "narration": "Cảnh ba cần sinh mới."},
        ]

        # Tạo trước file cho cảnh 2
        cached_file_sc2 = os.path.join(self.work_dir, "scene_002.mp3")
        with open(cached_file_sc2, "wb") as f:
            f.write(b"CACHED_AUDIO_DATA_" + b"X" * 2000)

        generated_calls = []

        def mock_generate_tts(text, output_path, voice, rate):
            generated_calls.append(output_path)
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_DATA_" + b"Y" * 1500)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_generate_tts), \
             patch("src.tts_service.get_audio_duration", return_value=5.5):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                voice="vi-VN-HoaiMyNeural",
                max_workers=4
            )

        self.assertTrue(ok)
        # Chỉ có cảnh 1 và cảnh 3 được gọi generate_tts
        self.assertEqual(len(generated_calls), 2)
        self.assertTrue(any("scene_001.mp3" in call for call in generated_calls))
        self.assertTrue(any("scene_003.mp3" in call for call in generated_calls))
        self.assertFalse(any("scene_002.mp3" in call for call in generated_calls),
                         "Cảnh 2 đã có cache nhưng vẫn bị gọi lại generate_tts!")

        # Kiểm tra cảnh 2 vẫn được cập nhật audio_path và duration đầy đủ
        self.assertEqual(scenes[1]["audio_path"], cached_file_sc2)
        self.assertEqual(scenes[1]["audio_duration"], 5.5)

    def test_error_handling_fails_safely_when_scene_fails(self):
        """
        Kiểm tra xử lý lỗi khi một phân cảnh sinh TTS thất bại:
        Hàm phải trả về (False, error_message) và thông báo lỗi rõ ràng.
        """
        scenes = [
            {"scene_num": 1, "narration": "Cảnh một bình thường."},
            {"scene_num": 2, "narration": "Cảnh hai sẽ gặp lỗi kết nối."},
            {"scene_num": 3, "narration": "Cảnh ba bình thường."},
        ]

        def mock_generate_tts(text, output_path, voice, rate):
            if "scene_002.mp3" in output_path:
                return False, "NoAudioReceived: WebSocket disconnected unexpectedly"
            with open(output_path, "wb") as f:
                f.write(b"AUDIO" + b"0" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_generate_tts), \
             patch("src.tts_service.get_audio_duration", return_value=3.0):
            ok, err_msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                voice="vi-VN-HoaiMyNeural",
                max_workers=4
            )

        self.assertFalse(ok)
        self.assertIn("cảnh 2", err_msg.lower())
        self.assertIn("noaudioreceived", err_msg.lower())

    def test_concurrency_max_workers_bounded(self):
        """
        Kiểm tra giới hạn max_workers trong ThreadPoolExecutor:
        Đảm bảo số worker được truyền vào ThreadPoolExecutor đúng với tham số yêu cầu.
        """
        scenes = [
            {"scene_num": 1, "narration": "Thử nghiệm worker 1"},
            {"scene_num": 2, "narration": "Thử nghiệm worker 2"},
        ]

        active_workers_recorded = []

        def mock_generate_tts(text, output_path, voice, rate):
            active_workers_recorded.append(os.path.basename(output_path))
            with open(output_path, "wb") as f:
                f.write(b"AUDIO" + b"0" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_generate_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.0), \
             patch("src.tts_service.ThreadPoolExecutor", wraps=None) as mock_executor_cls:
            # Cho ThreadPoolExecutor chạy thật hoặc kiểm tra call args
            from concurrent.futures import ThreadPoolExecutor
            mock_executor_cls.side_effect = lambda max_workers: ThreadPoolExecutor(max_workers=max_workers)

            ok, _ = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                max_workers=2
            )
            self.assertTrue(ok)
            mock_executor_cls.assert_called_with(max_workers=2)

    def test_progress_callback_reporting(self):
        """
        Kiểm tra tiến độ được gửi về realtime qua progress_callback:
        progress_callback(done_count, total_count, message).
        """
        scenes = [
            {"scene_num": 1, "narration": "Cảnh 1"},
            {"scene_num": 2, "narration": "Cảnh 2"},
            {"scene_num": 3, "narration": "Cảnh 3"},
        ]

        callbacks = []

        def on_progress(done, total, msg):
            callbacks.append((done, total, msg))

        def mock_generate_tts(text, output_path, voice, rate):
            with open(output_path, "wb") as f:
                f.write(b"AUDIO" + b"0" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_generate_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.5):
            ok, _ = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                progress_callback=on_progress
            )

        self.assertTrue(ok)
        self.assertEqual(len(callbacks), 3)
        # Điểm cuối cùng phải là done=3, total=3
        last_done, last_total, last_msg = callbacks[-1]
        self.assertEqual(last_done, 3)
        self.assertEqual(last_total, 3)
        self.assertIn("3/3", last_msg)

    def test_chinese_teaching_mode_routing(self):
        """
        Kiểm tra chế độ dạy tiếng Trung (chinese_teaching_vi) được điều hướng qua generate_multivoice_tts.
        """
        scenes = [
            {
                "scene_num": 1,
                "narration_vi": "Xin chào các bạn.",
                "chinese_text": "你好",
                "pinyin": "nǐ hǎo",
                "usage_vi": "Dùng để chào hỏi thông dụng.",
            }
        ]

        def _mock_multivoice_impl(segs, out):
            with open(out, "wb") as f:
                f.write(b"MULTIVOICE_AUDIO" + b"0" * 1200)
            return True, out

        mock_multivoice = MagicMock(side_effect=_mock_multivoice_impl)

        with patch("src.tts_service.generate_multivoice_tts", mock_multivoice), \
             patch("src.tts_service.get_audio_duration", return_value=3.8):
            ok, _ = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                content_mode="chinese_teaching_vi"
            )

        self.assertTrue(ok)
        self.assertTrue(mock_multivoice.called)
        self.assertEqual(scenes[0]["audio_duration"], 3.8)

    def test_clone_local_mode_routing(self):
        """
        Kiểm tra chế độ clone_local điều hướng qua generate_cloned_tts và sinh file đuôi .wav.
        """
        scenes = [
            {"scene_num": 1, "narration": "Giọng đọc nhân bản cục bộ."}
        ]

        def _mock_clone_impl(text, output_path, reference_audio, language):
            with open(output_path, "wb") as f:
                f.write(b"CLONED_WAV" + b"0" * 1200)
            return True, output_path

        mock_clone = MagicMock(side_effect=_mock_clone_impl)

        with patch("src.voice_clone_service.generate_cloned_tts", mock_clone, create=True), \
             patch("src.tts_service.generate_cloned_tts", mock_clone, create=True), \
             patch("src.tts_service.get_audio_duration", return_value=4.0):
            ok, _ = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.work_dir,
                voice_mode="clone_local",
                voice_reference_path="test_ref.wav"
            )

        self.assertTrue(ok)
        self.assertTrue(scenes[0]["audio_path"].endswith("scene_001.wav"))

    def test_empty_scenes_graceful_handling(self):
        """Kiểm tra danh sách rỗng xử lý an toàn không báo lỗi."""
        scenes = []
        ok, msg = generate_scenes_tts_parallel(
            scenes=scenes,
            video_work_dir=self.work_dir
        )
        self.assertTrue(ok)
        self.assertIn("không có phân cảnh", msg.lower())


if __name__ == '__main__':
    unittest.main()
