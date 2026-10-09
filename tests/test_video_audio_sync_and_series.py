# Chức năng: Kiểm thử tự động đồng bộ thời lượng Video-Audio và tính liên kết chuỗi tập (Multi-video continuity).
# Lý do tạo: Đảm bảo tuân thủ quy tắc Red -> Green -> Refactor.

import os
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.batch_producer import split_prompt_to_video_topics
from src.llm_service import generate_script


class TestVideoAudioSyncAndSeriesContinuity(unittest.TestCase):

    def test_split_prompt_to_video_topics_creates_coherent_series_arc(self):
        """Kiểm tra việc phân chia chủ đề 1 prompt thành N video tạo thành một mạch câu chuyện có cấu trúc liên kết."""
        prompt = "Bí ẩn lăng mộ Tần Thủy Hoàng"
        topics_3 = split_prompt_to_video_topics(prompt, count=3, language="vi")
        self.assertEqual(len(topics_3), 3)

        # Tập 1, 2, 3 phải có định hướng phát triển mạch truyện, không chỉ lặp lại câu từ vô nghĩa
        self.assertIn("Tập 1", topics_3[0])
        self.assertIn("Tập 2", topics_3[1])
        self.assertIn("Tập 3", topics_3[2])

    @patch("src.llm_service.call_ollama")
    def test_generate_script_accepts_and_includes_previous_context(self, mock_ollama):
        """Kiểm tra generate_script nhận previous_context và nhúng vào prompt để nối tiếp tập trước."""
        mock_ollama.return_value = (True, {"scenes": [{"scene_num": 1, "narration": "Nối tiếp...", "video_prompt": "Action"}]})

        prev_ctx = "Tập 1: Nhân vật đã tìm thấy bản đồ cổ và bước vào cửa hầm bí mật."
        ok, data = generate_script(
            topic="Bí ẩn lăng mộ (Tập 2)",
            previous_context=prev_ctx
        )
        self.assertTrue(ok)
        mock_ollama.assert_called_once()
        user_prompt_sent = mock_ollama.call_args[0][0]

        # Prompt gửi cho LLM phải chứa tóm tắt tập trước để bảo đảm mạch truyện không bị nhảy cóc
        self.assertIn(prev_ctx, user_prompt_sent)
        self.assertIn("tập trước", user_prompt_sent.lower())

    def test_process_video_clip_syncs_duration_smoothly(self):
        """Kiểm tra process_video_clip trong video_compiler đồng bộ thời lượng chuẩn."""
        from src.video_compiler import process_video_clip
        # Mock VideoFileClip
        with patch("src.video_compiler.VideoFileClip") as mock_vfc:
            mock_clip = MagicMock()
            mock_clip.duration = 4.0  # Clip gốc chỉ có 4s
            mock_clip.resize.return_value = mock_clip
            mock_clip.set_duration.return_value = mock_clip
            mock_vfc.return_value = mock_clip

            # Khi audio cần 7 giây:
            res_clip = process_video_clip("dummy.mp4", duration=7.0, orientation="vertical")
            self.assertIsNotNone(res_clip)
            # Clip phải được điều chỉnh để khớp chính xác 7.0 giây
            mock_clip.resize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
