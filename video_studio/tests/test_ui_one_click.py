"""Kiểm tra luồng tự động 1-Click trên UI của xưởng sản xuất video."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src import autonomous_factory as factory
from src.app_batch import _status_counts


class TestUIOneClickFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "test_ui_factory_state.json"
        self.state_patch = patch.object(factory, "STATE_PATH", self.state_path)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.temp_dir.cleanup()

    @patch.object(factory, "ensure_factory_worker")
    def test_add_factory_jobs_one_click(self, mock_worker):
        """Xác nhận việc submit job từ form UI diễn ra tức thì với 1 click."""
        job_ids = factory.add_factory_jobs(
            prompt="Bí ẩn tam giác quỷ Bermuda",
            count=1,
            language="vi",
            media_mode="flow_image",
            target_scenes=3,
            studio_mode=False
        )
        self.assertEqual(len(job_ids), 1)
        state = factory.get_factory_state()
        added_job = next((j for j in state["jobs"] if j["id"] == job_ids[0]), None)
        self.assertIsNotNone(added_job)
        self.assertEqual(added_job["status"], "queued")
        self.assertEqual(added_job["settings"]["target_scenes"], 3)
        self.assertEqual(added_job["settings"]["media_mode"], "flow_image")
        mock_worker.assert_called_once()

    def test_status_counts_for_auto_refresh(self):
        """Xác nhận cơ chế đếm trạng thái để kích hoạt auto-refresh thời gian thực."""
        mock_jobs = [
            {"id": "1", "status": "running"},
            {"id": "2", "status": "queued"},
            {"id": "3", "status": "completed"},
        ]
        counts = _status_counts(mock_jobs)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["queued"], 1)
        self.assertEqual(counts["completed"], 1)
        # Khi có running hoặc queued > 0, UI sẽ tự động kích hoạt auto-refresh
        should_refresh = counts["running"] > 0 or counts["queued"] > 0
        self.assertTrue(should_refresh)

        # Khi tất cả đã completed, UI dừng auto-refresh
        mock_jobs_done = [{"id": "3", "status": "completed"}]
        counts_done = _status_counts(mock_jobs_done)
        should_refresh_done = counts_done["running"] > 0 or counts_done["queued"] > 0
        self.assertFalse(should_refresh_done)


if __name__ == "__main__":
    unittest.main()
