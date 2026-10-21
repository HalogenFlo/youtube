import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import src.autonomous_factory as factory
from src.batch_producer import produce_single_video_pipeline


class TestSkipCancelJob(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_factory_skip_")
        self.state_file = Path(self.temp_dir) / "video_factory_state.json"
        self.patcher = patch.object(factory, "STATE_PATH", self.state_file)
        self.patcher.start()
        factory._save_unlocked({"version": 1, "paused": False, "jobs": []})

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_skip_current_job_aborts_running_job(self):
        """Kiểm tra gọi skip_current_job() sẽ ngắt job đang running và đổi trạng thái."""
        job_id = "job_run_123"
        state = {
            "version": 1,
            "paused": False,
            "jobs": [
                {
                    "id": job_id,
                    "video_index": 1,
                    "topic": "Đang chạy cần bỏ qua",
                    "status": "running",
                    "progress": 35,
                    "message": "Đang tạo ảnh",
                },
                {
                    "id": "job_queue_456",
                    "video_index": 2,
                    "topic": "Việc tiếp theo trong hàng đợi",
                    "status": "queued",
                    "progress": 0,
                    "message": "Chờ sản xuất",
                },
            ],
        }
        factory._save_unlocked(state)

        # Gọi skip_current_job
        skipped = factory.skip_current_job()
        self.assertTrue(skipped)

        # Kiểm tra trạng thái job
        updated_state = factory._load_unlocked()
        job_1 = next(j for j in updated_state["jobs"] if j["id"] == job_id)
        self.assertIn(job_1["status"], ("skipped", "failed"))
        self.assertIn("bỏ qua", job_1["message"].lower())

        # Job 2 trong hàng đợi vẫn an toàn
        job_2 = next(j for j in updated_state["jobs"] if j["id"] == "job_queue_456")
        self.assertEqual(job_2["status"], "queued")

    def test_cancel_specific_queued_job(self):
        """Kiểm tra hủy riêng một job cụ thể trong hàng đợi queued."""
        state = {
            "version": 1,
            "paused": False,
            "jobs": [
                {"id": "job_1", "video_index": 1, "status": "queued", "topic": "Chủ đề 1"},
                {"id": "job_2", "video_index": 2, "status": "queued", "topic": "Chủ đề 2"},
                {"id": "job_3", "video_index": 3, "status": "queued", "topic": "Chủ đề 3"},
            ],
        }
        factory._save_unlocked(state)

        # Hủy riêng job_2
        cancelled = factory.cancel_job("job_2")
        self.assertTrue(cancelled)

        updated_state = factory._load_unlocked()
        job_ids = [j["id"] for j in updated_state["jobs"]]
        self.assertNotIn("job_2", job_ids)
        self.assertIn("job_1", job_ids)
        self.assertIn("job_3", job_ids)

    def test_pipeline_aborts_early_when_cancelled(self):
        """Kiểm tra produce_single_video_pipeline ngắt sớm khi is_cancelled_callback trả về True."""
        call_count = 0
        def mock_is_cancelled():
            nonlocal call_count
            call_count += 1
            return True

        success, result, metadata = produce_single_video_pipeline(
            topic="Bí ẩn vũ trụ",
            video_index=1,
            batch_work_dir=self.temp_dir,
            output_dir=self.temp_dir,
            is_cancelled_callback=mock_is_cancelled,
        )

        self.assertFalse(success)
        self.assertIn("bỏ qua", str(result).lower())
        self.assertGreaterEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
