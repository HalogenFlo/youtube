# Chức năng: Kiểm thử tự động cơ chế chờ video Flow trực tiếp và loại bỏ fallback sang ảnh.
# Lý do tạo: Tuân thủ quy tắc Red -> Green -> Refactor.

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.flow_browser_service import load_flow_config, FlowBrowserController


class TestFlowVideoNoFallback(unittest.TestCase):

    def test_flow_config_has_video_timeout(self):
        """Kiểm tra flow_config có cấu hình video_timeout_seconds >= 1800."""
        cfg = load_flow_config()
        self.assertIn("video_timeout_seconds", cfg)
        self.assertGreaterEqual(cfg["video_timeout_seconds"], 1800)

    def test_network_response_matcher(self):
        """Kiểm tra logic nhận diện URL/Content-Type video (hỗ trợ HTTP 200 và 206 Partial Content)."""
        controller = FlowBrowserController()
        
        # Mock response HTTP 206 Partial Content cho streaming video
        res_206 = MagicMock()
        res_206.url = "https://lh3.googleusercontent.com/abc-xyz"
        res_206.status = 206
        res_206.headers = {"content-type": "video/mp4"}

        # Hàm kiểm tra hợp lệ
        is_video = controller.is_video_response(res_206)
        self.assertTrue(is_video)

        # Mock response HTTP 200 flow-content
        res_200 = MagicMock()
        res_200.url = "https://flow-content.google/video/clip1"
        res_200.status = 200
        res_200.headers = {"content-type": "application/octet-stream"}
        self.assertTrue(controller.is_video_response(res_200))

        # Mock response ảnh thông thường (không phải video)
        res_img = MagicMock()
        res_img.url = "https://flow.google.com/static/icon.png"
        res_img.status = 200
        res_img.headers = {"content-type": "image/png"}
        self.assertFalse(controller.is_video_response(res_img))

    @patch("src.batch_producer.generate_flow_video")
    @patch("src.batch_producer.generate_flow_image")
    @patch("src.batch_producer.generate_script")
    @patch("src.batch_producer.generate_tts")
    def test_batch_producer_no_fallback_in_flow_video_mode(
        self, mock_tts, mock_script, mock_flow_img, mock_flow_vid
    ):
        """Khi ở chế độ flow_video, nếu sinh video thất bại thì KHÔNG fallback sang ảnh hay SD."""
        from src.batch_producer import produce_single_video_pipeline

        mock_script.return_value = (True, {
            "scenes": [
                {"scene_num": 1, "narration": "Cảnh 1", "video_prompt": "Prompt 1"}
            ]
        })
        mock_tts.return_value = (True, "fake_audio.mp3")
        # Giả lập video Flow bị lỗi/hết giờ
        mock_flow_vid.return_value = (False, "Hết thời gian chờ video từ Google Flow (1800s)")

        with patch("src.batch_producer.get_audio_duration", return_value=3.0), \
             patch("os.path.exists", side_effect=lambda p: True if "scene_001.mp3" in p else False):
            success, err_msg, meta = produce_single_video_pipeline(
                topic="Test No Fallback",
                video_index=1,
                batch_work_dir=str(ROOT / "temp" / "test_no_fallback"),
                media_mode="flow_video",
                target_scenes=1,
            )

        # Kết quả phải trả về thất bại với thông báo rõ ràng, KHÔNG gọi generate_flow_image
        self.assertFalse(success)
        mock_flow_img.assert_not_called()
        self.assertIn("Hệ thống dừng theo yêu cầu không fallback", err_msg)


if __name__ == "__main__":
    unittest.main()
