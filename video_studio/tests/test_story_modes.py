# Chức năng: Kiểm thử tự động cho 2 thể loại video mới:
# 1. Dạy tiếng Anh qua cốt truyện (Micro-Drama Story)
# 2. Kể chuyện kiến thức dẫn dắt (Story-Led Explainer)

import unittest
from unittest.mock import patch

from src.llm_service import get_system_prompt, generate_script
from src.batch_producer import (
    build_random_video_topics,
    ENGLISH_VOCAB_TOPIC_BANK,
    STORY_EXPLAINER_TOPIC_BANK,
)


class TestStoryModes(unittest.TestCase):

    def test_system_prompt_english_vocab_story(self):
        prompt = get_system_prompt(language="vi", content_mode="english_vocab_story")
        self.assertIn("Micro-Drama", prompt)
        self.assertIn("5 cảnh", prompt)
        self.assertIn("Hook tình huống", prompt)
        self.assertIn("CH01", prompt)

    def test_system_prompt_story_explainer(self):
        prompt = get_system_prompt(language="vi", content_mode="story_explainer")
        self.assertIn("Story-Led Explainer", prompt)
        self.assertIn("câu chuyện khám phá", prompt)
        self.assertIn("Hook", prompt)

    @patch("src.llm_service.call_ollama", return_value=(True, {"scenes": []}))
    def test_generate_script_english_vocab_story(self, mock_call):
        generate_script("Từ vựng Run out of", content_mode="english_vocab_story")
        user_prompt, system_prompt = mock_call.call_args.args[:2]
        self.assertIn("MICRO-DRAMA", user_prompt)
        self.assertIn("Micro-Drama", system_prompt)

    @patch("src.llm_service.call_ollama", return_value=(True, {"scenes": []}))
    def test_generate_script_story_explainer(self, mock_call):
        generate_script("Hành trình tìm ra lửa", content_mode="story_explainer")
        user_prompt, system_prompt = mock_call.call_args.args[:2]
        self.assertIn("Story-Led Explainer", user_prompt)
        self.assertIn("Story-Led Explainer", system_prompt)

    def test_build_random_video_topics_english_vocab(self):
        topics = build_random_video_topics(3, content_mode="english_vocab_story")
        self.assertEqual(len(topics), 3)
        for t in topics:
            self.assertIn(t, ENGLISH_VOCAB_TOPIC_BANK)

    def test_build_random_video_topics_story_explainer(self):
        topics = build_random_video_topics(3, content_mode="story_explainer")
        self.assertEqual(len(topics), 3)
        for t in topics:
            self.assertIn(t, STORY_EXPLAINER_TOPIC_BANK)

    @patch("src.llm_service.call_ollama", return_value=(True, {"scenes": []}))
    def test_default_target_scenes_chinese_and_stories(self, mock_call):
        # Tiếng Trung: mặc định 3 cảnh
        generate_script("Chào hỏi", content_mode="chinese_teaching_vi", target_scenes=None)
        user_prompt_zh = mock_call.call_args_list[-1].args[0]
        self.assertIn("ĐÚNG 3 phân cảnh", user_prompt_zh)

        # Tiếng Anh cốt truyện: mặc định 5 cảnh
        generate_script("Run out of", content_mode="english_vocab_story", target_scenes=None)
        user_prompt_en = mock_call.call_args_list[-1].args[0]
        self.assertIn("ĐÚNG 5 phân cảnh", user_prompt_en)

        # Kể chuyện dẫn dắt: mặc định 5 cảnh
        generate_script("Khám phá lửa", content_mode="story_explainer", target_scenes=None)
        user_prompt_story = mock_call.call_args_list[-1].args[0]
        self.assertIn("ĐÚNG 5 phân cảnh", user_prompt_story)
