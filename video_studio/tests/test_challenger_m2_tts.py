"""Adversarial stress and boundary tests for Milestone 2 Parallel TTS Pipeline.

Challenger M2_2 Adversarial Verification Suite:
- Vector 1: Boundary Conditions (0 scenes, 1 scene, 50 scenes, empty/whitespace text, very long text)
- Vector 2: Cache Corruption & Recovery (0 bytes, 500 bytes, 999 bytes vs >= 1000 bytes)
- Vector 3: Concurrency Edge Cases (max_workers=1, 10, 0, negative, None)
- Vector 4: Backward Compatibility (generate_tts, sanitize_tts_text, get_audio_duration, generate_multivoice_tts)
- Vector 5: Extreme Jitter and Partial Failure Resilience
"""

import os
import shutil
import tempfile
import time
import random
import unittest
from unittest.mock import patch, MagicMock

from src.tts_service import (
    generate_scenes_tts_parallel,
    generate_tts,
    sanitize_tts_text,
    get_audio_duration,
    generate_multivoice_tts,
    VOICE_FALLBACK_MAP,
)


class TestChallengerM2TTS(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_adv_tts_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # VECTOR 1: BOUNDARY CONDITIONS
    # =========================================================================

    def test_boundary_zero_scenes(self):
        """0 scenes input: must return True gracefully without crashing."""
        scenes = []
        progress_called = False

        def cb(done, total, msg):
            nonlocal progress_called
            progress_called = True

        ok, msg = generate_scenes_tts_parallel(
            scenes=scenes,
            video_work_dir=self.temp_dir,
            progress_callback=cb,
        )
        self.assertTrue(ok)
        self.assertIn("không có phân cảnh", msg.lower())
        self.assertFalse(progress_called)

    def test_boundary_single_scene(self):
        """1 scene input: verify proper processing and in-place mutation."""
        scenes = [{"scene_num": 1, "narration": "Phân cảnh duy nhất trong video ngắn."}]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_HEADER_" + b"1" * 1500)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=3.5):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                voice="vi-VN-HoaiMyNeural",
            )

        self.assertTrue(ok, f"Failed: {msg}")
        self.assertEqual(len(scenes), 1)
        self.assertTrue(scenes[0]["audio_path"].endswith("scene_001.mp3"))
        self.assertEqual(scenes[0]["audio_duration"], 3.5)
        self.assertTrue(os.path.exists(scenes[0]["audio_path"]))

    def test_boundary_empty_and_whitespace_narration_fails_safely(self):
        """Empty or whitespace narration must fail safely with descriptive error."""
        # Case A: completely empty string
        scenes_empty = [{"scene_num": 1, "narration": ""}]
        ok, msg = generate_scenes_tts_parallel(
            scenes=scenes_empty,
            video_work_dir=self.temp_dir,
        )
        self.assertFalse(ok)
        self.assertIn("cảnh 1", msg.lower())
        self.assertIn("trống", msg.lower())

        # Case B: whitespace only
        scenes_ws = [{"scene_num": 2, "narration": "   \t\n   "}]
        ok_ws, msg_ws = generate_scenes_tts_parallel(
            scenes=scenes_ws,
            video_work_dir=self.temp_dir,
        )
        self.assertFalse(ok_ws)
        self.assertIn("cảnh 2", msg_ws.lower())
        self.assertIn("trống", msg_ws.lower())

        # Case C: missing narration key
        scenes_missing = [{"scene_num": 3}]
        ok_m, msg_m = generate_scenes_tts_parallel(
            scenes=scenes_missing,
            video_work_dir=self.temp_dir,
        )
        self.assertFalse(ok_m)
        self.assertIn("cảnh 3", msg_m.lower())

    def test_boundary_very_long_narration(self):
        """Very long narration text (5000+ characters) must be handled without crash."""
        long_text = "Lời dẫn khoa học chuyên sâu về vũ trụ và lượng tử. " * 150  # ~7800 chars
        scenes = [{"scene_num": 1, "narration": long_text}]

        received_text = []

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            received_text.append(text)
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_DATA_" + b"L" * 3000)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=120.0):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
            )

        self.assertTrue(ok, f"Failed: {msg}")
        self.assertEqual(len(received_text), 1)
        self.assertEqual(received_text[0], long_text)
        self.assertEqual(scenes[0]["audio_duration"], 120.0)

    def test_boundary_large_scene_count(self):
        """Stress test with 50 scenes: all must complete in exact order."""
        total = 50
        scenes = [
            {"scene_num": i + 1, "narration": f"Nội dung phân cảnh số {i + 1}"}
            for i in range(total)
        ]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            # simulate tiny random jitter
            time.sleep(random.uniform(0.001, 0.01))
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_" + b"X" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=4.0):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=8,
            )

        self.assertTrue(ok, f"50 scenes parallel failed: {msg}")
        self.assertEqual(len(scenes), total)
        for i, sc in enumerate(scenes):
            expected_num = i + 1
            self.assertEqual(sc["scene_num"], expected_num)
            self.assertTrue(sc["audio_path"].endswith(f"scene_{expected_num:03d}.mp3"))
            self.assertEqual(sc["audio_duration"], 4.0)
            self.assertTrue(os.path.exists(sc["audio_path"]))

    # =========================================================================
    # VECTOR 2: CACHE CORRUPTION & RECOVERY (<1000 BYTES)
    # =========================================================================

    def test_cache_zero_byte_file_is_regenerated(self):
        """Existing zero-byte file must NOT be reused; must be regenerated and overwritten."""
        corrupt_path = os.path.join(self.temp_dir, "scene_001.mp3")
        # create 0-byte corrupt file
        with open(corrupt_path, "wb") as f:
            pass
        self.assertEqual(os.path.getsize(corrupt_path), 0)

        scenes = [{"scene_num": 1, "narration": "Cảnh có file 0 byte bị hỏng."}]

        regen_called = False

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            nonlocal regen_called
            regen_called = True
            with open(output_path, "wb") as f:
                f.write(b"NEW_AUDIO_DATA_" + b"V" * 2000)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=5.0):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
            )

        self.assertTrue(ok, f"Failed: {msg}")
        self.assertTrue(regen_called, "File 0-byte phải được sinh lại, không được tái sử dụng!")
        self.assertGreater(os.path.getsize(corrupt_path), 1000)
        self.assertEqual(scenes[0]["audio_path"], corrupt_path)
        self.assertEqual(scenes[0]["audio_duration"], 5.0)

    def test_cache_sub_1000_byte_boundary(self):
        """
        Files <1000 bytes (e.g. 500B, 999B) must be regenerated.
        Files >= 1001 bytes must be reused without calling generate_tts.
        """
        f_500 = os.path.join(self.temp_dir, "scene_001.mp3")
        with open(f_500, "wb") as f:
            f.write(b"CORRUPT_" + b"A" * 492)
        self.assertEqual(os.path.getsize(f_500), 500)

        f_999 = os.path.join(self.temp_dir, "scene_002.mp3")
        with open(f_999, "wb") as f:
            f.write(b"TRUNC_" + b"B" * 993)
        self.assertEqual(os.path.getsize(f_999), 999)

        f_1001 = os.path.join(self.temp_dir, "scene_003.mp3")
        with open(f_1001, "wb") as f:
            f.write(b"VALID_" + b"C" * 995)
        self.assertEqual(os.path.getsize(f_1001), 1001)

        scenes = [
            {"scene_num": 1, "narration": "Cảnh 1 có 500 bytes"},
            {"scene_num": 2, "narration": "Cảnh 2 có 999 bytes"},
            {"scene_num": 3, "narration": "Cảnh 3 có 1001 bytes"},
        ]

        calls = []

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            calls.append(output_path)
            with open(output_path, "wb") as f:
                f.write(b"REGENERATED_" + b"Z" * 1500)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=6.0):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
            )

        self.assertTrue(ok, f"Failed: {msg}")
        # Cảnh 1 và 2 phải được gọi sinh lại
        self.assertIn(f_500, calls)
        self.assertIn(f_999, calls)
        # Cảnh 3 không được gọi sinh lại (reused cache)
        self.assertNotIn(f_1001, calls)
        # Kiểm tra kích thước sau khi tái sinh
        self.assertGreater(os.path.getsize(f_500), 1000)
        self.assertGreater(os.path.getsize(f_999), 1000)

    def test_all_scenes_cached_bypasses_threadpool(self):
        """When 100% scenes are already valid in cache, bypasses ThreadPoolExecutor completely."""
        scenes = [
            {"scene_num": 1, "narration": "Cảnh 1"},
            {"scene_num": 2, "narration": "Cảnh 2"},
        ]
        for sc in scenes:
            path = os.path.join(self.temp_dir, f"scene_{sc['scene_num']:03d}.mp3")
            with open(path, "wb") as f:
                f.write(b"VALID_CACHE_" + b"K" * 1200)

        with patch("src.tts_service.generate_tts") as mock_tts, \
             patch("src.tts_service.ThreadPoolExecutor") as mock_executor, \
             patch("src.tts_service.get_audio_duration", return_value=4.5):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
            )

        self.assertTrue(ok, f"Failed: {msg}")
        self.assertIn("đã có sẵn giọng đọc", msg.lower())
        self.assertFalse(mock_tts.called)
        self.assertFalse(mock_executor.called)
        self.assertEqual(scenes[0]["audio_duration"], 4.5)
        self.assertEqual(scenes[1]["audio_duration"], 4.5)

    # =========================================================================
    # VECTOR 3: CONCURRENCY EDGE CASES
    # =========================================================================

    def test_concurrency_single_worker(self):
        """max_workers=1: strictly sequential execution without thread pool bottleneck."""
        scenes = [
            {"scene_num": 1, "narration": "Cảnh 1 đơn luồng"},
            {"scene_num": 2, "narration": "Cảnh 2 đơn luồng"},
        ]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"SINGLE_" + b"S" * 1100)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.0), \
             patch("src.tts_service.ThreadPoolExecutor", wraps=None) as mock_pool:
            from concurrent.futures import ThreadPoolExecutor
            mock_pool.side_effect = lambda max_workers: ThreadPoolExecutor(max_workers=max_workers)

            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=1,
            )
            self.assertTrue(ok, f"Failed: {msg}")
            mock_pool.assert_called_with(max_workers=1)

    def test_concurrency_high_worker_count(self):
        """max_workers=10: high concurrency execution without crashing."""
        scenes = [
            {"scene_num": i + 1, "narration": f"Cảnh {i + 1} đa luồng cao"}
            for i in range(10)
        ]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"HIGH_" + b"H" * 1100)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=1.5):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=10,
            )
            self.assertTrue(ok, f"Failed: {msg}")

    def test_concurrency_zero_and_negative_workers_fallback(self):
        """
        max_workers=0 or negative values must NOT raise ValueError in ThreadPoolExecutor.
        Must safely fall back to default worker count (4).
        """
        scenes = [{"scene_num": 1, "narration": "Cảnh kiểm tra fallback worker"}]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"FALLBACK_" + b"F" * 1100)
            return True, output_path

        # Test max_workers = 0
        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.0), \
             patch("src.tts_service.ThreadPoolExecutor", wraps=None) as mock_pool:
            from concurrent.futures import ThreadPoolExecutor
            mock_pool.side_effect = lambda max_workers: ThreadPoolExecutor(max_workers=max_workers)

            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=0,
            )
            self.assertTrue(ok, f"Failed: {msg}")
            mock_pool.assert_called_with(max_workers=4)

        # Test max_workers = -3 with fresh scene
        scenes_neg = [{"scene_num": 2, "narration": "Cảnh kiểm tra fallback worker âm"}]
        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.0), \
             patch("src.tts_service.ThreadPoolExecutor", wraps=None) as mock_pool:
            from concurrent.futures import ThreadPoolExecutor
            mock_pool.side_effect = lambda max_workers: ThreadPoolExecutor(max_workers=max_workers)

            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes_neg,
                video_work_dir=self.temp_dir,
                max_workers=-3,
            )
            self.assertTrue(ok, f"Failed: {msg}")
            mock_pool.assert_called_with(max_workers=4)

    # =========================================================================
    # VECTOR 4: BACKWARD COMPATIBILITY & LEGACY APIS
    # =========================================================================

    def test_legacy_generate_tts_empty_and_whitespace(self):
        """generate_tts with empty/whitespace text returns (False, msg)."""
        out_path = os.path.join(self.temp_dir, "test_empty.mp3")
        ok, msg = generate_tts("", out_path)
        self.assertFalse(ok)
        self.assertIn("trống", msg.lower())

        ok_ws, msg_ws = generate_tts("   \n\t  ", out_path)
        self.assertFalse(ok_ws)
        self.assertIn("trống", msg_ws.lower())

    def test_legacy_generate_tts_symbol_only(self):
        """generate_tts with pure symbols returns (False, msg)."""
        out_path = os.path.join(self.temp_dir, "test_symbols.mp3")
        ok, msg = generate_tts("*** ### ~~~ ` _", out_path)
        self.assertFalse(ok)
        self.assertIn("trống hoặc chỉ chứa ký hiệu", msg.lower())

    def test_legacy_sanitize_tts_text(self):
        """sanitize_tts_text cleans markdown, director notes, URLs, whitespace."""
        raw = "   [Nhạc kịch tính] **Cảnh 1:** (giọng trầm) Truy cập https://example.com để xem thêm!   "
        cleaned = sanitize_tts_text(raw)
        self.assertNotIn("[Nhạc kịch tính]", cleaned)
        self.assertNotIn("(giọng trầm)", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertIn("Cảnh 1: Truy cập để xem thêm!", cleaned)

    def test_legacy_get_audio_duration_robustness(self):
        """get_audio_duration with non-existent or empty paths returns 0.0 safely."""
        self.assertEqual(get_audio_duration(""), 0.0)
        self.assertEqual(get_audio_duration(None), 0.0)
        self.assertEqual(get_audio_duration("non_existent_file_xyz.mp3"), 0.0)

    def test_legacy_voice_fallback_map(self):
        """VOICE_FALLBACK_MAP covers standard Vietnamese and English voices."""
        self.assertIn("vi-VN-HoaiMyNeural", VOICE_FALLBACK_MAP)
        self.assertEqual(VOICE_FALLBACK_MAP["vi-VN-HoaiMyNeural"], "vi-VN-NamMinhNeural")
        self.assertIn("vi-VN-NamMinhNeural", VOICE_FALLBACK_MAP)
        self.assertEqual(VOICE_FALLBACK_MAP["vi-VN-NamMinhNeural"], "vi-VN-HoaiMyNeural")

    # =========================================================================
    # VECTOR 5: EXTREME JITTER AND PARTIAL FAILURE RESILIENCE
    # =========================================================================

    def test_extreme_worker_jitter_order_integrity(self):
        """
        20 scenes with inverted and randomized latencies:
        Even when scenes complete out of order, the output array MUST preserve 1..20 strictly.
        """
        count = 20
        scenes = [
            {"scene_num": i + 1, "narration": f"Cảnh {i + 1} thử nghiệm jitter"}
            for i in range(count)
        ]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            # Cảnh có số thứ tự nhỏ hơn lại ngủ lâu hơn (scene 1 ngủ 0.1s, scene 20 ngủ 0.005s)
            num = int(os.path.basename(output_path).replace("scene_", "").replace(".mp3", ""))
            delay = 0.002 * (count - num + 1)
            time.sleep(delay)
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_JITTER_" + b"J" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", side_effect=lambda p: float(int(os.path.basename(p).replace("scene_", "").replace(".mp3", "")) * 1.5)):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=6,
            )

        self.assertTrue(ok, f"Failed: {msg}")
        for i, sc in enumerate(scenes):
            expected_num = i + 1
            self.assertEqual(sc["scene_num"], expected_num)
            self.assertTrue(sc["audio_path"].endswith(f"scene_{expected_num:03d}.mp3"))
            self.assertEqual(sc["audio_duration"], float(expected_num * 1.5))

    def test_partial_failure_identifies_failed_scene(self):
        """When scene 5 out of 10 fails, the error message clearly points out scene 5."""
        scenes = [
            {"scene_num": i + 1, "narration": f"Cảnh {i + 1}"}
            for i in range(10)
        ]

        def mock_gen_tts(text, output_path, voice=None, rate=None, **kwargs):
            if "scene_005.mp3" in output_path:
                return False, "Rate limit exceeded (HTTP 429)"
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_OK_" + b"O" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=mock_gen_tts), \
             patch("src.tts_service.get_audio_duration", return_value=3.0):
            ok, err_msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=4,
            )

        self.assertFalse(ok)
        self.assertIn("cảnh 5", err_msg.lower())
        self.assertIn("429", err_msg)


if __name__ == "__main__":
    unittest.main()
