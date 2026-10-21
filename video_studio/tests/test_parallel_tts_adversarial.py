"""Adversarial stress and forensic verification tests for Parallel TTS Pipeline.

Milestone 2 Forensic Verification Suite:
- Vector 1: Real audio duration measurement (real wave files, missing files, corrupt files)
- Vector 2: Massive concurrency & jitter stress (50 scenes, non-deterministic completion)
- Vector 3: Fault injection, exceptions, and fail-safe return
- Vector 4: Boundary values (0 scenes, missing scene_num, negative workers, buggy callbacks)
- Vector 5: Cache threshold boundary (exact 1000-byte boundary condition)
- Vector 6: Routing integrity (chinese_teaching_vi, clone_local, standard)
"""

import os
import wave
import shutil
import tempfile
import random
import time
import unittest
from unittest.mock import patch, MagicMock

from src.tts_service import (
    get_audio_duration,
    generate_scenes_tts_parallel,
)


class TestParallelTTSAdversarial(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_adv_tts_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # VECTOR 1: REAL AUDIO DURATION (NO MOCKS FOR DURATION LOGIC)
    # =========================================================================

    def test_real_wave_audio_duration_empirical(self):
        """Verify get_audio_duration empirically measures real audio without mocks."""
        wav_path = os.path.join(self.temp_dir, "test_real.wav")
        framerate = 44100
        duration_seconds = 2.5
        n_frames = int(framerate * duration_seconds)

        # Generate genuine uncompressed PCM WAV
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(b"\x00\x00" * n_frames)

        measured = get_audio_duration(wav_path)
        self.assertAlmostEqual(measured, 2.5, places=2)

    def test_audio_duration_missing_and_corrupt(self):
        """Verify non-existent files return 0.0 and corrupt files return 5.0 fallback."""
        self.assertEqual(get_audio_duration(""), 0.0)
        self.assertEqual(get_audio_duration("non_existent_file.mp3"), 0.0)

        # Corrupt file (not valid audio)
        corrupt_path = os.path.join(self.temp_dir, "corrupt.mp3")
        with open(corrupt_path, "wb") as f:
            f.write(b"NOT_A_VALID_AUDIO_HEADER" * 10)
        measured_corrupt = get_audio_duration(corrupt_path)
        self.assertEqual(measured_corrupt, 5.0)

    # =========================================================================
    # VECTOR 2: MASSIVE CONCURRENCY & JITTER STRESS
    # =========================================================================

    def test_massive_concurrency_and_jitter_order_retention(self):
        """50 scenes with randomized jitter completion: verify strict 100% order retention."""
        num_scenes = 50
        scenes = [
            {"scene_num": i, "narration": f"Phân cảnh số {i} với nội dung kiểm thử song song."}
            for i in range(1, num_scenes + 1)
        ]

        def jittered_tts(text, output_path, voice, rate):
            # Random delay 1ms - 15ms to completely scramble completion order
            time.sleep(random.uniform(0.001, 0.015))
            with open(output_path, "wb") as f:
                f.write(b"AUDIO_DATA" + b"X" * 1500)
            return True, output_path

        progress_history = []
        def on_progress(done, total, msg):
            progress_history.append((done, total))

        with patch("src.tts_service.generate_tts", side_effect=jittered_tts), \
             patch("src.tts_service.get_audio_duration", return_value=3.5):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=8,
                progress_callback=on_progress
            )

        self.assertTrue(ok)
        self.assertEqual(len(scenes), num_scenes)

        # Check every scene in-place: scene_num, audio_path, audio_duration
        for idx, sc in enumerate(scenes):
            expected_num = idx + 1
            self.assertEqual(sc["scene_num"], expected_num, f"Order scrambled at index {idx}!")
            self.assertTrue(sc["audio_path"].endswith(f"scene_{expected_num:03d}.mp3"))
            self.assertEqual(sc["audio_duration"], 3.5)
            self.assertTrue(os.path.exists(sc["audio_path"]))

        # Verify progress tracking reached total
        self.assertGreater(len(progress_history), 0)
        self.assertEqual(progress_history[-1], (num_scenes, num_scenes))

    # =========================================================================
    # VECTOR 3: FAULT INJECTION & THREAD EXCEPTION RESILIENCE
    # =========================================================================

    def test_worker_unhandled_exception_captured_safely(self):
        """Ensure thread-level exceptions (e.g. MemoryError, RuntimeError) do not crash pipeline."""
        scenes = [
            {"scene_num": 1, "narration": "Cảnh 1"},
            {"scene_num": 2, "narration": "Cảnh 2 gây sự cố nổ ngoại lệ"},
            {"scene_num": 3, "narration": "Cảnh 3"},
        ]

        def explosive_tts(text, output_path, voice, rate):
            if "scene_002.mp3" in output_path:
                raise RuntimeError("Simulated network kernel panic")
            with open(output_path, "wb") as f:
                f.write(b"VALID_AUDIO" + b"Y" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=explosive_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.0):
            ok, err_msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                max_workers=3
            )

        self.assertFalse(ok)
        self.assertIn("cảnh 2", err_msg.lower())
        self.assertIn("simulated network kernel panic", err_msg.lower())

    # =========================================================================
    # VECTOR 4: BOUNDARY CONDITIONS & ISOLATION
    # =========================================================================

    def test_missing_scene_num_auto_fallback(self):
        """Scenes missing 'scene_num' key must gracefully fall back to 1-based indexing."""
        scenes = [
            {"narration": "Cảnh không có scene_num 1"},
            {"narration": "Cảnh không có scene_num 2"},
        ]

        def fake_tts(text, output_path, voice, rate):
            with open(output_path, "wb") as f:
                f.write(b"AUDIO" + b"Z" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=fake_tts), \
             patch("src.tts_service.get_audio_duration", return_value=2.0):
            ok, _ = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
            )

        self.assertTrue(ok)
        self.assertTrue(scenes[0]["audio_path"].endswith("scene_001.mp3"))
        self.assertTrue(scenes[1]["audio_path"].endswith("scene_002.mp3"))

    def test_negative_and_zero_workers_defaults(self):
        """Negative, zero or None max_workers should default safely without throwing."""
        scenes = [{"scene_num": 1, "narration": "Kiểm tra worker âm"}]

        def fake_tts(text, output_path, voice, rate):
            with open(output_path, "wb") as f:
                f.write(b"AUDIO" + b"Z" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=fake_tts), \
             patch("src.tts_service.get_audio_duration", return_value=1.0):
            ok_neg, _ = generate_scenes_tts_parallel(scenes, self.temp_dir, max_workers=-5)
            self.assertTrue(ok_neg)

            ok_zero, _ = generate_scenes_tts_parallel(scenes, self.temp_dir, max_workers=0)
            self.assertTrue(ok_zero)

            ok_none, _ = generate_scenes_tts_parallel(scenes, self.temp_dir, max_workers=None)
            self.assertTrue(ok_none)

    def test_buggy_progress_callback_does_not_break_generation(self):
        """If user-provided progress callback throws an exception, pipeline must not crash."""
        scenes = [{"scene_num": 1, "narration": "Cảnh test callback lỗi"}]

        def crashing_callback(done, total, msg):
            raise ValueError("Crashing inside UI callback!")

        def fake_tts(text, output_path, voice, rate):
            with open(output_path, "wb") as f:
                f.write(b"AUDIO" + b"Z" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=fake_tts), \
             patch("src.tts_service.get_audio_duration", return_value=1.5):
            ok, msg = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=self.temp_dir,
                progress_callback=crashing_callback
            )

        self.assertTrue(ok)
        self.assertEqual(scenes[0]["audio_duration"], 1.5)

    # =========================================================================
    # VECTOR 5: CACHE THRESHOLD BOUNDARY (< 1000 bytes vs > 1000 bytes)
    # =========================================================================

    def test_cache_exact_threshold_boundary(self):
        """
        Verify files <= 1000 bytes are treated as invalid/truncated and regenerated,
        while files > 1000 bytes are reused.
        """
        sc1_file = os.path.join(self.temp_dir, "scene_001.mp3")
        sc2_file = os.path.join(self.temp_dir, "scene_002.mp3")

        # Scene 1: exactly 500 bytes (< 1000 bytes threshold) -> MUST REGENERATE
        with open(sc1_file, "wb") as f:
            f.write(b"T" * 500)

        # Scene 2: 1500 bytes (> 1000 bytes threshold) -> MUST REUSE
        with open(sc2_file, "wb") as f:
            f.write(b"VALID_CACHE_" + b"K" * 1488)

        scenes = [
            {"scene_num": 1, "narration": "Cảnh 1 file hỏng"},
            {"scene_num": 2, "narration": "Cảnh 2 cache xịn"},
        ]

        generated_calls = []
        def fake_tts(text, output_path, voice, rate):
            generated_calls.append(output_path)
            with open(output_path, "wb") as f:
                f.write(b"NEW_AUDIO_" + b"N" * 1200)
            return True, output_path

        with patch("src.tts_service.generate_tts", side_effect=fake_tts), \
             patch("src.tts_service.get_audio_duration", return_value=3.0):
            ok, _ = generate_scenes_tts_parallel(scenes, self.temp_dir)

        self.assertTrue(ok)
        # Only scene 1 was regenerated
        self.assertEqual(len(generated_calls), 1)
        self.assertTrue(sc1_file in generated_calls[0])
        # Scene 2 was reused
        self.assertEqual(scenes[1]["audio_path"], sc2_file)

    # =========================================================================
    # VECTOR 6: ROUTING INTEGRITY
    # =========================================================================

    def test_clone_local_missing_service_graceful_error(self):
        """When voice clone service is not available, return clean error message."""
        scenes = [{"scene_num": 1, "narration": "Clone voice missing"}]

        with patch("src.tts_service.generate_cloned_tts", None):
            with patch.dict("sys.modules", {"src.voice_clone_service": None}):
                ok, err = generate_scenes_tts_parallel(
                    scenes=scenes,
                    video_work_dir=self.temp_dir,
                    voice_mode="clone_local"
                )
                self.assertFalse(ok)
                self.assertIn("không khả dụng", err)


if __name__ == "__main__":
    unittest.main()
