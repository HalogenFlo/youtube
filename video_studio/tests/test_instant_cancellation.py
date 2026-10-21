"""Unit tests cho cơ chế Instant Cancellation và giải phóng hàng đợi khi hủy việc."""

import unittest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

from src.autonomous_factory import (
    skip_current_job,
    cancel_job,
    recover_stale_running_jobs,
    _next_job,
)
from src.flow_image_service import FlowBatchQueueEngine, FlowImageTask, generate_flow_video, generate_flow_image


class TestInstantCancellationAndQueueRecovery(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmp_dir.name) / "test_factory_state.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_skip_current_job_aborts_and_resets_running_id(self):
        with patch("src.autonomous_factory.STATE_PATH", self.state_file):
            import src.autonomous_factory as factory
            factory._CURRENT_RUNNING_JOB_ID = "job_test_1"
            factory._save_unlocked({
                "version": 1,
                "paused": False,
                "jobs": [
                    {"id": "job_test_1", "status": "running", "progress": 50, "topic": "Test 1"},
                    {"id": "job_test_2", "status": "queued", "progress": 0, "topic": "Test 2"},
                ]
            })

            ok = skip_current_job("job_test_1")
            self.assertTrue(ok)
            self.assertIsNone(factory._CURRENT_RUNNING_JOB_ID)

            state = factory._load_unlocked()
            job1 = next(j for j in state["jobs"] if j["id"] == "job_test_1")
            self.assertEqual(job1["status"], "failed")
            self.assertIn("Đã bỏ qua", job1["message"])

            # _next_job phải nhặt được job_test_2 ngay lập tức
            next_picked = _next_job()
            self.assertIsNotNone(next_picked)
            self.assertEqual(next_picked["id"], "job_test_2")
            self.assertEqual(next_picked["status"], "running")

    def test_recover_stale_running_jobs_unblocks_queue(self):
        with patch("src.autonomous_factory.STATE_PATH", self.state_file):
            import src.autonomous_factory as factory
            factory._CURRENT_RUNNING_JOB_ID = None  # Không có active worker thread
            factory._save_unlocked({
                "version": 1,
                "paused": False,
                "jobs": [
                    {"id": "job_orphan", "status": "running", "progress": 1, "topic": "Orphan Job"},
                    {"id": "job_next", "status": "queued", "progress": 0, "topic": "Next Job"},
                ]
            })

            recovered = recover_stale_running_jobs()
            self.assertEqual(recovered, 1)

            state = factory._load_unlocked()
            job_orphan = next(j for j in state["jobs"] if j["id"] == "job_orphan")
            self.assertEqual(job_orphan["status"], "queued")

            # Sau khi recover, _next_job nhặt job và không bị kẹt deadlock
            picked = _next_job()
            self.assertIsNotNone(picked)
            self.assertEqual(picked["id"], "job_orphan")

    def test_flow_video_and_image_abort_immediately_when_cancelled(self):
        is_cancelled = MagicMock(return_value=True)

        ok_vid, res_vid = generate_flow_video(
            prompt="A dramatic scene",
            output_path="test_out.mp4",
            is_cancelled_callback=is_cancelled,
        )
        self.assertFalse(ok_vid)
        self.assertIn("Đã bỏ qua", res_vid)

        ok_img, res_img = generate_flow_image(
            prompt="A dramatic image",
            output_path="test_out.png",
            is_cancelled_callback=is_cancelled,
        )
        self.assertFalse(ok_img)
        self.assertIn("Đã bỏ qua", res_img)

    def test_flow_batch_queue_aborts_immediately_on_cancellation(self):
        engine = FlowBatchQueueEngine(max_workers=2)
        tasks = [
            FlowImageTask(scene_index=1, prompt="p1", output_path="out1.png"),
            FlowImageTask(scene_index=2, prompt="p2", output_path="out2.png"),
        ]
        is_cancelled = MagicMock(return_value=True)
        ok, res_tasks = engine.process_tasks(tasks, is_cancelled_callback=is_cancelled)
        self.assertFalse(ok)
        for t in res_tasks:
            self.assertIn(t.status, ("failed", "pending"))


if __name__ == "__main__":
    unittest.main()
