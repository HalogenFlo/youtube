"""Adversarial stress and boundary tests for Flow Batch Queue Engine.

Milestone 1 Adversarial Verification Suite:
- Vector 1: Boundary values (0 scenes, 1 scene, 100 scenes, negative/zero workers)
- Vector 2: Worker jitter and random latency simulation (detecting thread races)
- Vector 3: In-place dictionary mutation and field preservation
- Vector 4: Backward compatibility of generate_flow_batch (turbo_queue True vs False)
- Vector 5: Robustness against worker exceptions and fallback resilience
"""

import os
import random
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.flow_image_service import (
    FlowImageTask,
    FlowBatchQueueEngine,
    generate_flow_batch_queue,
    generate_flow_batch,
)


class TestFlowBatchQueueAdversarial(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_adv_flow_queue_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # VECTOR 1: BOUNDARY VALUES
    # =========================================================================

    def test_boundary_zero_scenes(self):
        """0 scenes input across all entry points: must not crash or fail."""
        engine = FlowBatchQueueEngine()
        status_called = False

        def status_cb(cur, tot, msg):
            nonlocal status_called
            status_called = True

        # FlowBatchQueueEngine.process_tasks([])
        ok, tasks = engine.process_tasks([], status_callback=status_cb)
        self.assertTrue(ok)
        self.assertEqual(tasks, [])
        self.assertFalse(status_called)

        # generate_flow_batch_queue with 0 scenes
        ok_q, paths_q, reports_q = generate_flow_batch_queue([], self.temp_dir, status_callback=status_cb)
        self.assertTrue(ok_q)
        self.assertEqual(paths_q, [])
        self.assertEqual(reports_q, [])

        # generate_flow_batch with turbo_queue=True on 0 scenes
        ok_b_turbo, paths_b_turbo = generate_flow_batch([], self.temp_dir, turbo_queue=True)
        self.assertTrue(ok_b_turbo)
        self.assertEqual(paths_b_turbo, [])

        # generate_flow_batch with turbo_queue=False on 0 scenes
        ok_b_legacy, paths_b_legacy = generate_flow_batch([], self.temp_dir, turbo_queue=False)
        self.assertTrue(ok_b_legacy)
        self.assertEqual(paths_b_legacy, [])

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_boundary_single_scene_success_and_failure(self, mock_gen, mock_sleep):
        """1 scene edge cases: success and unrecoverable failure (no neighbor for fallback)."""
        # Success case
        def fake_success(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"SINGLE_SCENE_OK")
            return True, output_path

        mock_gen.side_effect = fake_success
        scenes = [{"scene_num": 1, "video_prompt": "Solo scene", "use_video_ai": True}]
        ok, paths, reports = generate_flow_batch_queue(scenes, self.temp_dir, stagger_delay=0.0)
        self.assertTrue(ok)
        self.assertEqual(len(paths), 1)
        self.assertEqual(scenes[0]["image_path"], paths[0])
        self.assertFalse(scenes[0]["use_video_ai"])

        # Failure case with retries exhausted (self-healing cannot find another valid scene)
        mock_gen.side_effect = None
        mock_gen.return_value = (False, "Permanent API 500 error")
        scenes_fail = [{"scene_num": 1, "video_prompt": "Failing solo scene"}]

        ok_fail, paths_fail, reports_fail = generate_flow_batch_queue(
            scenes_fail, self.temp_dir, stagger_delay=0.0
        )

        self.assertFalse(ok_fail)
        self.assertEqual(reports_fail[0]["status"], "failed")
        self.assertNotIn("image_path", scenes_fail[0])

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_boundary_negative_and_zero_workers(self, mock_gen, mock_sleep):
        """Worker count bounds: negative or 0 must clamp to 1, excess must clamp to 4."""
        engine_neg = FlowBatchQueueEngine(max_workers=-10)
        self.assertEqual(engine_neg.max_workers, 1)

        engine_zero = FlowBatchQueueEngine(max_workers=0)
        self.assertEqual(engine_zero.max_workers, 1)

        engine_excess = FlowBatchQueueEngine(max_workers=999)
        self.assertEqual(engine_excess.max_workers, 4)

        # Execution check with negative workers
        def fake_gen(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"DATA")
            return True, output_path

        mock_gen.side_effect = fake_gen
        scenes = [{"scene_num": 1, "video_prompt": "Test"}]
        ok, paths, _ = generate_flow_batch_queue(scenes, self.temp_dir, max_workers=-5, stagger_delay=0.0)
        self.assertTrue(ok)
        self.assertEqual(len(paths), 1)

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_scale_hundred_scenes_integrity(self, mock_gen, mock_sleep):
        """Scale stress: 100 scenes must complete with exact order preservation and no leaks."""
        def fake_gen(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"HUNDRED_SCENES_DATA")
            return True, output_path

        mock_gen.side_effect = fake_gen
        scenes = [
            {"scene_num": i, "video_prompt": f"Prompt {i}", "narration": f"Narration {i}"}
            for i in range(1, 101)
        ]

        ok, paths, reports = generate_flow_batch_queue(
            scenes=scenes,
            temp_dir=self.temp_dir,
            max_workers=4,
            stagger_delay=0.0,
        )

        self.assertTrue(ok)
        self.assertEqual(len(paths), 100)
        self.assertEqual(len(reports), 100)

        # Check strict ordering 1..100
        for i in range(100):
            expected_idx = i + 1
            self.assertEqual(reports[i]["scene_index"], expected_idx)
            self.assertTrue(paths[i].endswith(f"scene_flow_{expected_idx}.png"))
            self.assertEqual(scenes[i]["image_path"], paths[i])
            self.assertFalse(scenes[i]["use_video_ai"])

    # =========================================================================
    # VECTOR 2: WORKER JITTER & RACE CONDITION DETECTION
    # =========================================================================

    @patch("src.flow_image_service.generate_flow_image")
    def test_worker_jitter_random_latency_race_conditions(self, mock_gen):
        """Stress: 25 workers completing with randomized out-of-order jitter."""
        num_tasks = 25

        def jittered_gen(prompt=None, output_path=None, **kwargs):
            # Random sleep 1ms to 15ms to scramble completion order
            time.sleep(random.uniform(0.001, 0.015))
            Path(output_path).write_bytes(f"CONTENT_{output_path}".encode("utf-8"))
            return True, output_path

        mock_gen.side_effect = jittered_gen
        scenes = [
            {"scene_num": i, "video_prompt": f"Prompt jitter {i}"}
            for i in range(1, num_tasks + 1)
        ]

        status_calls = []
        def status_cb(cur, tot, msg):
            status_calls.append((cur, tot))

        ok, paths, reports = generate_flow_batch_queue(
            scenes=scenes,
            temp_dir=self.temp_dir,
            max_workers=4,
            stagger_delay=0.0,
            status_callback=status_cb,
        )

        self.assertTrue(ok)
        self.assertEqual(len(paths), num_tasks)
        self.assertEqual(len(reports), num_tasks)

        # Verify strict order retention despite jitter
        for idx, task_rep in enumerate(reports, start=1):
            self.assertEqual(task_rep["scene_index"], idx)
            self.assertEqual(scenes[idx - 1]["image_path"], paths[idx - 1])
            self.assertTrue(os.path.exists(paths[idx - 1]))

        # Verify status callbacks were called for all completions
        self.assertGreater(len(status_calls), 0)
        self.assertEqual(status_calls[-1], (num_tasks, num_tasks))

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_worker_jitter_with_intermittent_failures_and_self_healing(self, mock_gen, mock_sleep):
        """Adversarial: Jittered execution with arbitrary failures triggering self-healing."""
        # Scenes 3, 7, 11 will permanently fail
        failing_indices = {3, 7, 11}
        num_tasks = 12

        def mock_gen_impl(prompt=None, output_path=None, **kwargs):
            for fail_idx in failing_indices:
                if f"scene_flow_{fail_idx}.png" in output_path:
                    return False, f"Permanent error on scene {fail_idx}"
            Path(output_path).write_bytes(b"VALID_IMAGE_CONTENT")
            return True, output_path

        mock_gen.side_effect = mock_gen_impl
        scenes = [
            {"scene_num": i, "video_prompt": f"Prompt {i}"}
            for i in range(1, num_tasks + 1)
        ]

        ok, paths, reports = generate_flow_batch_queue(
            scenes=scenes,
            temp_dir=self.temp_dir,
            max_workers=3,
            stagger_delay=0.0,
            enable_self_healing=True,
        )

        self.assertTrue(ok, "Self-healing should have recovered all intermittent failures")
        self.assertEqual(len(paths), num_tasks)

        # Inspect failing scenes: should be fallback
        for idx in failing_indices:
            rep = reports[idx - 1]
            self.assertEqual(rep["status"], "fallback")
            self.assertIn("fallback_source", rep["metadata"])
            self.assertTrue(os.path.exists(rep["output_path"]))
            self.assertGreater(os.path.getsize(rep["output_path"]), 0)

        # All scenes must have valid image_path set in-place
        for sc in scenes:
            self.assertIn("image_path", sc)
            self.assertTrue(os.path.exists(sc["image_path"]))
            self.assertFalse(sc["use_video_ai"])

    # =========================================================================
    # VECTOR 3: IN-PLACE DICTIONARY MUTATION & FIELD PRESERVATION
    # =========================================================================

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_inplace_mutation_preserves_custom_fields(self, mock_gen, mock_sleep):
        """In-place dictionary modification must preserve existing keys untouched."""
        def fake_gen(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"IMAGE")
            return True, output_path

        mock_gen.side_effect = fake_gen
        scenes = [
            {
                "scene_num": 1,
                "narration": "Lời dẫn cảnh 1",
                "video_prompt": "Cinematic visual",
                "duration": 4.5,
                "custom_metadata": {"key": "value"},
                "use_video_ai": True,
            }
        ]

        ok, paths, _ = generate_flow_batch_queue(scenes, self.temp_dir, stagger_delay=0.0)
        self.assertTrue(ok)

        sc = scenes[0]
        self.assertEqual(sc["narration"], "Lời dẫn cảnh 1")
        self.assertEqual(sc["video_prompt"], "Cinematic visual")
        self.assertEqual(sc["duration"], 4.5)
        self.assertEqual(sc["custom_metadata"], {"key": "value"})
        self.assertEqual(sc["image_path"], paths[0])
        self.assertFalse(sc["use_video_ai"])

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_missing_scene_num_auto_indexing(self, mock_gen, mock_sleep):
        """Scenes missing 'scene_num' should be safely auto-indexed (1..N)."""
        def fake_gen(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"IMAGE")
            return True, output_path

        mock_gen.side_effect = fake_gen
        scenes = [
            {"narration": "No scene_num 1"},
            {"narration": "No scene_num 2"},
        ]

        ok, paths, reports = generate_flow_batch_queue(scenes, self.temp_dir, stagger_delay=0.0)
        self.assertTrue(ok)
        self.assertEqual(reports[0]["scene_index"], 1)
        self.assertEqual(reports[1]["scene_index"], 2)
        self.assertTrue(paths[0].endswith("scene_flow_1.png"))
        self.assertTrue(paths[1].endswith("scene_flow_2.png"))

    # =========================================================================
    # VECTOR 4: BACKWARD COMPATIBILITY
    # =========================================================================

    @patch("src.flow_image_service.generate_flow_image")
    def test_backward_compatibility_turbo_queue_false(self, mock_gen):
        """generate_flow_batch with turbo_queue=False must behave strictly as legacy."""
        def fake_gen(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"LEGACY_IMG")
            return True, output_path

        mock_gen.side_effect = fake_gen
        scenes = [
            {"scene_num": 1, "video_prompt": "Prompt 1"},
            {"scene_num": 2, "video_prompt": "Prompt 2"},
        ]

        ok, paths = generate_flow_batch(
            scenes=scenes,
            temp_dir=self.temp_dir,
            turbo_queue=False,
            fallback_to_sd=True,
        )

        self.assertTrue(ok)
        self.assertEqual(len(paths), 2)
        # Legacy generate_flow_batch does not mutate scenes
        self.assertNotIn("image_path", scenes[0])
        self.assertNotIn("image_path", scenes[1])

        # Verify failure in legacy mode returns [f"Lỗi ở cảnh {i+1}: {res}"]
        mock_gen.side_effect = None
        mock_gen.return_value = (False, "Legacy fail reason")
        ok_fail, paths_fail = generate_flow_batch(
            scenes=scenes,
            temp_dir=self.temp_dir,
            turbo_queue=False,
        )
        self.assertFalse(ok_fail)
        self.assertEqual(len(paths_fail), 1)
        self.assertIn("Lỗi ở cảnh 1: Legacy fail reason", paths_fail[0])

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_backward_compatibility_turbo_queue_true(self, mock_gen, mock_sleep):
        """generate_flow_batch with turbo_queue=True routes through queue engine."""
        def fake_gen(prompt=None, output_path=None, **kwargs):
            Path(output_path).write_bytes(b"TURBO_IMG")
            return True, output_path

        mock_gen.side_effect = fake_gen
        scenes = [
            {"scene_num": 1, "video_prompt": "Prompt 1"},
            {"scene_num": 2, "video_prompt": "Prompt 2"},
        ]

        ok, paths = generate_flow_batch(
            scenes=scenes,
            temp_dir=self.temp_dir,
            turbo_queue=True,
            max_workers=2,
        )

        self.assertTrue(ok)
        self.assertEqual(len(paths), 2)
        # Mutates scenes in-place when turbo_queue is active
        self.assertIn("image_path", scenes[0])
        self.assertIn("image_path", scenes[1])

    # =========================================================================
    # VECTOR 5: UNEXPECTED WORKER EXCEPTIONS
    # =========================================================================

    @patch("src.flow_image_service.time.sleep")
    @patch("src.flow_image_service.generate_flow_image")
    def test_unexpected_exception_in_worker_graceful_handling(self, mock_gen, mock_sleep):
        """If generate_flow_image raises an unexpected exception, queue must catch it."""
        mock_gen.side_effect = RuntimeError("Fatal hardware / CUDA OOM error")
        scenes = [{"scene_num": 1, "video_prompt": "Crashing prompt"}]

        ok, paths, reports = generate_flow_batch_queue(
            scenes=scenes,
            temp_dir=self.temp_dir,
            stagger_delay=0.0,
        )

        self.assertFalse(ok)
        self.assertEqual(reports[0]["status"], "failed")
        self.assertIn("Fatal hardware / CUDA OOM error", reports[0]["error"])


if __name__ == "__main__":
    unittest.main()
