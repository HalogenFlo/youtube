"""Unit tests for Flow Batch Queue Engine (Milestone 1 - Requirement R1).

Verifies:
- FlowImageTask dataclass structure and status tracking.
- FlowBatchQueueEngine concurrency bounds (clamped 1-4), staggered dispatch.
- Task execution with retries and exponential backoff on transient errors.
- Strict scene order preservation across asynchronous worker completions.
- Self-healing fallback mechanism copying preceding valid images.
- All-fail graceful degradation.
- generate_flow_batch_queue in-place scene mutation and reports.
- Backward compatibility of generate_flow_batch with turbo_queue flag.
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from src.flow_image_service import (
    FlowImageTask,
    FlowBatchQueueEngine,
    generate_flow_batch_queue,
    generate_flow_batch,
)


class TestFlowBatchQueue(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_flow_queue_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. FlowImageTask Dataclass & Status Tracking
    def test_flow_image_task_dataclass_and_status(self):
        out_path = os.path.join(self.temp_dir, "scene_1.png")
        task = FlowImageTask(
            scene_index=1,
            prompt="Stickman researching in a library",
            output_path=out_path,
        )
        self.assertEqual(task.scene_index, 1)
        self.assertEqual(task.prompt, "Stickman researching in a library")
        self.assertEqual(task.output_path, out_path)
        self.assertEqual(task.orientation, "vertical")
        self.assertEqual(task.status, "pending")
        self.assertIsNone(task.error)
        self.assertEqual(task.retries, 0)
        self.assertEqual(task.elapsed_sec, 0.0)
        self.assertIsInstance(task.metadata, dict)

        # Status mutations
        task.status = "running"
        self.assertEqual(task.status, "running")
        task.status = "completed"
        self.assertEqual(task.status, "completed")
        task.status = "fallback"
        self.assertEqual(task.status, "fallback")
        task.status = "failed"
        self.assertEqual(task.status, "failed")

    # 2. Concurrency Bounds & Clamping (1 <= max_workers <= 4)
    def test_flow_batch_queue_engine_concurrency_bounds(self):
        engine_default = FlowBatchQueueEngine()
        self.assertEqual(engine_default.max_workers, 4)
        self.assertEqual(engine_default.max_retries, 3)
        self.assertEqual(engine_default.stagger_delay, 1.5)
        self.assertTrue(engine_default.enable_self_healing)

        # Capped to 4 max
        engine_high = FlowBatchQueueEngine(max_workers=8)
        self.assertEqual(engine_high.max_workers, 4)

        # Lower bound clamped to 1
        engine_zero = FlowBatchQueueEngine(max_workers=0)
        self.assertEqual(engine_zero.max_workers, 1)

        engine_negative = FlowBatchQueueEngine(max_workers=-3)
        self.assertEqual(engine_negative.max_workers, 1)

    # 3. Task Execution & Retry with Backoff
    @patch("src.flow_image_service.generate_flow_image")
    @patch("src.flow_image_service.time.sleep")
    def test_task_execution_and_retry_with_backoff(self, mock_sleep, mock_gen_image):
        out_path = os.path.join(self.temp_dir, "scene_retry.png")
        task = FlowImageTask(
            scene_index=1,
            prompt="Scene with retry prompt",
            output_path=out_path,
        )

        attempts = 0

        def fake_gen(prompt, output_path, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return False, "Google Flow High demand timeout"
            Path(output_path).write_bytes(b"RETRY_SUCCESS_PNG")
            return True, output_path

        mock_gen_image.side_effect = fake_gen

        engine = FlowBatchQueueEngine(max_workers=1, max_retries=3, stagger_delay=0.0)
        success, tasks = engine.process_tasks([task])

        self.assertTrue(success)
        self.assertEqual(len(tasks), 1)
        res_task = tasks[0]
        self.assertEqual(res_task.status, "completed")
        self.assertEqual(res_task.retries, 2)
        self.assertTrue(os.path.exists(out_path))
        self.assertEqual(Path(out_path).read_bytes(), b"RETRY_SUCCESS_PNG")
        # Sleep called for backoff
        self.assertGreaterEqual(mock_sleep.call_count, 2)

    # 4. Strict Order Preservation Across Asynchronous Completion
    @patch("src.flow_image_service.generate_flow_image")
    def test_strict_order_preservation(self, mock_gen_image):
        tasks = [
            FlowImageTask(
                scene_index=i,
                prompt=f"Prompt scene {i}",
                output_path=os.path.join(self.temp_dir, f"scene_{i}.png"),
            )
            for i in [1, 2, 3, 4]
        ]

        def staggered_finish(prompt, output_path, **kwargs):
            # Scene 3 finishes immediately, Scene 1 takes longest
            if "scene_3" in output_path:
                time.sleep(0.01)
            elif "scene_2" in output_path:
                time.sleep(0.03)
            elif "scene_1" in output_path:
                time.sleep(0.08)
            else:
                time.sleep(0.02)
            Path(output_path).write_bytes(f"DATA_{output_path}".encode("utf-8"))
            return True, output_path

        mock_gen_image.side_effect = staggered_finish

        engine = FlowBatchQueueEngine(max_workers=4, stagger_delay=0.0)
        success, returned_tasks = engine.process_tasks(tasks)

        self.assertTrue(success)
        self.assertEqual(len(returned_tasks), 4)
        indices = [t.scene_index for t in returned_tasks]
        self.assertEqual(indices, [1, 2, 3, 4], "Tasks must maintain strict 1..N order")

    # 5. Staggered Dispatch Between Tasks
    @patch("src.flow_image_service.generate_flow_image")
    @patch("src.flow_image_service.time.sleep")
    def test_staggered_dispatch(self, mock_sleep, mock_gen_image):
        tasks = [
            FlowImageTask(
                scene_index=i,
                prompt=f"Prompt scene {i}",
                output_path=os.path.join(self.temp_dir, f"scene_stagger_{i}.png"),
            )
            for i in [1, 2, 3]
        ]

        def fake_gen(prompt, output_path, **kwargs):
            Path(output_path).write_bytes(b"STAGGER_PNG")
            return True, output_path

        mock_gen_image.side_effect = fake_gen

        engine = FlowBatchQueueEngine(max_workers=3, stagger_delay=1.5)
        success, _ = engine.process_tasks(tasks)

        self.assertTrue(success)
        # Check that stagger delay was applied
        sleep_args = [call_args[0][0] for call_args in mock_sleep.call_args_list if call_args[0]]
        stagger_calls = [arg for arg in sleep_args if abs(arg - 1.5) < 0.1 or abs(arg - 0.0) < 0.1]
        self.assertTrue(len(stagger_calls) >= 2 or 1.5 in sleep_args)

    # 6. Self-Healing Fallback (Inheriting Preceding Valid Scene)
    @patch("src.flow_image_service.generate_flow_image")
    @patch("src.flow_image_service.time.sleep")
    def test_self_healing_fallback(self, mock_sleep, mock_gen_image):
        tasks = [
            FlowImageTask(
                scene_index=1,
                prompt="Prompt 1",
                output_path=os.path.join(self.temp_dir, "scene_sh_1.png"),
            ),
            FlowImageTask(
                scene_index=2,
                prompt="Prompt 2 fails completely",
                output_path=os.path.join(self.temp_dir, "scene_sh_2.png"),
            ),
            FlowImageTask(
                scene_index=3,
                prompt="Prompt 3",
                output_path=os.path.join(self.temp_dir, "scene_sh_3.png"),
            ),
        ]

        def mock_gen(prompt, output_path, **kwargs):
            if "scene_sh_2" in output_path:
                return False, "Google Flow High demand timeout after retries"
            Path(output_path).write_bytes(b"VALID_IMAGE_DATA")
            return True, output_path

        mock_gen_image.side_effect = mock_gen

        engine = FlowBatchQueueEngine(
            max_workers=2,
            max_retries=2,
            stagger_delay=0.0,
            enable_self_healing=True,
        )
        success, finished_tasks = engine.process_tasks(tasks)

        self.assertTrue(success)
        self.assertEqual(len(finished_tasks), 3)

        # Scene 1: completed
        self.assertEqual(finished_tasks[0].status, "completed")
        # Scene 2: fallback
        self.assertEqual(finished_tasks[1].status, "fallback")
        self.assertTrue(os.path.exists(finished_tasks[1].output_path))
        self.assertEqual(
            Path(finished_tasks[1].output_path).read_bytes(),
            b"VALID_IMAGE_DATA",
        )
        self.assertEqual(finished_tasks[1].metadata.get("fallback_source_scene"), 1)
        # Scene 3: completed
        self.assertEqual(finished_tasks[2].status, "completed")

    # 7. All Tasks Fail Graceful Handling (Cannot Self-Heal)
    @patch("src.flow_image_service.generate_flow_image")
    @patch("src.flow_image_service.time.sleep")
    def test_all_tasks_fail_graceful(self, mock_sleep, mock_gen_image):
        tasks = [
            FlowImageTask(
                scene_index=1,
                prompt="Prompt 1",
                output_path=os.path.join(self.temp_dir, "scene_fail_1.png"),
            ),
            FlowImageTask(
                scene_index=2,
                prompt="Prompt 2",
                output_path=os.path.join(self.temp_dir, "scene_fail_2.png"),
            ),
        ]
        mock_gen_image.return_value = (False, "Network error / Flow offline")

        engine = FlowBatchQueueEngine(
            max_workers=2,
            max_retries=2,
            stagger_delay=0.0,
            enable_self_healing=True,
        )
        success, finished_tasks = engine.process_tasks(tasks)

        self.assertFalse(success)
        self.assertEqual(finished_tasks[0].status, "failed")
        self.assertEqual(finished_tasks[1].status, "failed")
        self.assertIn("Flow offline", finished_tasks[0].error)

    # 8. generate_flow_batch_queue In-Place Mutation and Reports
    @patch("src.flow_image_service.generate_flow_image")
    def test_generate_flow_batch_queue_in_place_mutation(self, mock_gen_image):
        scenes = [
            {"scene_num": 1, "video_prompt": "Sc 1 Prompt", "narration": "Narr 1"},
            {"scene_num": 2, "video_prompt": "Sc 2 Prompt", "narration": "Narr 2"},
        ]

        def fake_gen(prompt, output_path, **kwargs):
            Path(output_path).write_bytes(b"SCENE_IMAGE")
            return True, output_path

        mock_gen_image.side_effect = fake_gen

        status_logs = []
        def status_cb(current, total, msg):
            status_logs.append((current, total, msg))

        success, img_paths, reports = generate_flow_batch_queue(
            scenes=scenes,
            temp_dir=self.temp_dir,
            orientation="vertical",
            max_workers=2,
            status_callback=status_cb,
            stagger_delay=0.0,
        )

        self.assertTrue(success)
        self.assertEqual(len(img_paths), 2)
        self.assertEqual(len(reports), 2)

        # In-place verification of scenes dict
        self.assertIn("image_path", scenes[0])
        self.assertIn("image_path", scenes[1])
        self.assertEqual(scenes[0]["image_path"], img_paths[0])
        self.assertEqual(scenes[1]["image_path"], img_paths[1])
        self.assertFalse(scenes[0].get("use_video_ai", True))
        self.assertFalse(scenes[1].get("use_video_ai", True))

        # Status callback was called
        self.assertGreater(len(status_logs), 0)

    # 9. generate_flow_batch Backward Compatibility with turbo_queue=True
    @patch("src.flow_image_service.generate_flow_batch_queue")
    @patch("src.flow_image_service.generate_flow_image")
    def test_generate_flow_batch_compatibility(self, mock_gen_image, mock_queue):
        scenes = [
            {"scene_num": 1, "video_prompt": "Prompt 1"},
            {"scene_num": 2, "video_prompt": "Prompt 2"},
        ]
        mock_queue.return_value = (True, ["/path/img1.png", "/path/img2.png"], [{}, {}])

        # turbo_queue=True delegates to generate_flow_batch_queue
        ok, paths = generate_flow_batch(
            scenes=scenes,
            temp_dir=self.temp_dir,
            turbo_queue=True,
            max_workers=4,
        )
        self.assertTrue(ok)
        self.assertEqual(paths, ["/path/img1.png", "/path/img2.png"])
        mock_queue.assert_called_once()

        # turbo_queue=False uses standard flow
        def fake_gen(prompt, output_path, **kwargs):
            Path(output_path).write_bytes(b"LEGACY_PNG")
            return True, output_path

        mock_gen_image.side_effect = fake_gen
        ok_legacy, paths_legacy = generate_flow_batch(
            scenes=scenes,
            temp_dir=self.temp_dir,
            turbo_queue=False,
        )
        self.assertTrue(ok_legacy)
        self.assertEqual(len(paths_legacy), 2)


if __name__ == "__main__":
    unittest.main()
