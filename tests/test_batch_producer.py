# Chức năng: Kiểm thử tự động đơn vị cho module Auto Batch Video Producer (src/batch_producer.py).

import unittest
from unittest.mock import patch, MagicMock
from src.batch_producer import split_prompt_to_video_topics, get_audio_duration, build_exact_tts_timestamps
from src.llm_service import generate_video_metadata
from src.llm_service import generate_script
from src.voice_clone_service import generate_cloned_tts


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
        self.assertTrue(metadata["requires_ai_label"])
        self.assertTrue(metadata["platforms"]["youtube"]["set_altered_content"])
        self.assertTrue(metadata["platforms"]["tiktok"]["enable_ai_generated_label"])

    @patch("src.llm_service.call_ollama")
    def test_metadata_filters_generic_spam_and_marks_sensitive_topics(self, mock_call):
        mock_call.return_value = (True, {
            "title": "Kiến thức sức khỏe cơ bản",
            "description": "Nội dung tổng quan.",
            "tiktok_caption": "Tìm hiểu kiến thức.",
            "hashtags": ["#SucKhoe", "#fyp", "#viral", "#KienThuc"],
            "ai_disclosure": "Nội dung được hỗ trợ bởi AI.",
            "risk_flags": [],
        })
        ok, metadata = generate_video_metadata(
            "Kiến thức sức khỏe", [{"narration": "Thông tin về sức khỏe."}], "vi"
        )
        self.assertTrue(ok)
        self.assertNotIn("#fyp", [tag.lower() for tag in metadata["hashtags"]])
        self.assertNotIn("#viral", [tag.lower() for tag in metadata["hashtags"]])
        self.assertTrue(metadata["manual_review_required"])
        self.assertIn("health_or_medical", metadata["risk_flags"])

    @patch("src.llm_service.call_ollama", return_value=(True, {"scenes": []}))
    def test_generate_script_requests_exact_scene_count(self, mock_call):
        generate_script("Vũ trụ", language="vi", target_scenes=3)
        self.assertIn("ĐÚNG 3 phân cảnh", mock_call.call_args.args[0])

    def test_xtts_rejects_unsupported_vietnamese_before_loading_model(self):
        ok, message = generate_cloned_tts("Xin chào", "unused.wav", "missing.wav", "vi")
        self.assertFalse(ok)
        self.assertIn("chưa hỗ trợ", message)

    def test_exact_tts_timestamps_preserve_math_words(self):
        words = build_exact_tts_timestamps([
            {"narration": "một cộng một bằng mười", "audio_duration": 5.0}
        ])
        self.assertEqual([item["word"] for item in words], ["một", "cộng", "một", "bằng", "mười"])
        self.assertLess(words[-1]["end"], 5.0)


if __name__ == "__main__":
    unittest.main()
