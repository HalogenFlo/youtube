# Chức năng: Kiểm thử tự động đơn vị cho module Auto Batch Video Producer (src/batch_producer.py).

import unittest
from unittest.mock import patch, MagicMock
from src.batch_producer import split_prompt_to_video_topics, get_audio_duration
from src.llm_service import generate_video_metadata


class TestBatchProducer(unittest.TestCase):

    def test_split_prompt_single_to_multiple(self):
        prompt = "Bí mật về đại dương sâu thẳm"
        topics = split_prompt_to_video_topics(prompt, count=3, language="vi")
        self.assertEqual(len(topics), 3)
        self.assertIn("Phần 1", topics[0])
        self.assertIn("Phần 2", topics[1])
        self.assertIn("Phần 3", topics[2])

    def test_split_prompt_multiline(self):
        prompt = "Chủ đề 1: Lịch sử máy bay\nChủ đề 2: Tương lai xe điện\nChủ đề 3: Trí tuệ nhân tạo"
        topics = split_prompt_to_video_topics(prompt, count=3, language="vi")
        self.assertEqual(len(topics), 3)
        self.assertEqual(topics[0], "Chủ đề 1: Lịch sử máy bay")
        self.assertEqual(topics[1], "Chủ đề 2: Tương lai xe điện")
        self.assertEqual(topics[2], "Chủ đề 3: Trí tuệ nhân tạo")

    def test_split_prompt_english(self):
        prompt = "Space exploration facts"
        topics = split_prompt_to_video_topics(prompt, count=2, language="en")
        self.assertEqual(len(topics), 2)
        self.assertIn("Part 1", topics[0])
        self.assertIn("Part 2", topics[1])

    @patch("src.llm_service.call_ollama", return_value=(False, "offline"))
    def test_metadata_has_title_and_hashtags_when_llm_is_offline(self, _mock_call):
        ok, metadata = generate_video_metadata(
            "Bí ẩn về đại dương", [{"narration": "Dưới đáy biển có rất nhiều điều chưa biết."}], "vi"
        )
        self.assertTrue(ok)
        self.assertTrue(metadata["title"])
        self.assertGreaterEqual(len(metadata["hashtags"]), 5)
        self.assertTrue(all(tag.startswith("#") for tag in metadata["hashtags"]))


if __name__ == "__main__":
    unittest.main()
