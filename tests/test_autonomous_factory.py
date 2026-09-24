import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import autonomous_factory as factory


class TestAutonomousFactory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "factory_state.json"
        self.state_patch = patch.object(factory, "STATE_PATH", self.state_path)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.temp_dir.cleanup()

    @patch.object(factory, "ensure_factory_worker")
    def test_add_jobs_persists_queue_and_settings(self, worker_mock):
        ids = factory.add_factory_jobs("Mặt Trăng", 3, language="vi", orientation="vertical")
        state = factory.get_factory_state()

        self.assertEqual(len(ids), 3)
        self.assertEqual(len(state["jobs"]), 3)
        self.assertTrue(all(job["status"] == "queued" for job in state["jobs"]))
        self.assertEqual(state["jobs"][0]["settings"]["language"], "vi")
        worker_mock.assert_called_once()

    def test_recover_interrupted_job(self):
        self.state_path.write_text(
            json.dumps({"version": 1, "paused": False, "jobs": [{"id": "abc", "status": "running", "progress": 62}]}),
            encoding="utf-8",
        )
        factory.recover_interrupted_jobs()
        job = factory.get_factory_state()["jobs"][0]
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["progress"], 0)

    @patch.object(factory, "ensure_factory_worker")
    def test_retry_failed_jobs(self, worker_mock):
        self.state_path.write_text(
            json.dumps({"version": 1, "paused": True, "jobs": [{"id": "abc", "status": "failed", "progress": 0}]}),
            encoding="utf-8",
        )
        self.assertEqual(factory.retry_failed_jobs(), 1)
        state = factory.get_factory_state()
        self.assertFalse(state["paused"])
        self.assertEqual(state["jobs"][0]["status"], "queued")
        worker_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
