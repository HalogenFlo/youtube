# Chức năng: Bộ công cụ kiểm thử tự động (Unit, Integration, Regression) cho tính năng Học Tiếng Anh Self-heal.
# Lý do tạo: Đảm bảo toàn bộ các thành phần mới và cũ hoạt động chính xác, không gây lỗi hệ thống (regression).
# Trích dẫn: Tuân thủ yêu cầu kiểm thử trong PLAN.md và implementation_plan.md.

import os
import sys
import unittest
import shutil
from typing import Dict, Any, List

# Thêm thư mục gốc vào path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đọc tham số CLI --unit-only
UNIT_ONLY = "--unit-only" in sys.argv
if UNIT_ONLY:
    sys.argv.remove("--unit-only")

from src.config import TEMP_DIR, OUTPUT_DIR, MUSIC_DIR, SPEAKER_COLORS
from src.subtitle_builder import calculate_word_timings, split_translation_to_lines, build_bilingual_ass_subtitle
from src.music_service import list_available_music, create_silence, mix_scene_audio, build_mixed_audio_track
from src.selfheal_compiler import compile_selfheal_video
from src.llm_service import generate_selfheal_script
from src.tts_service import generate_tts


class TestSelfHealUnit(unittest.TestCase):
    
    def setUp(self):
        self.test_temp_dir = os.path.join(TEMP_DIR, "test_selfheal")
        os.makedirs(self.test_temp_dir, exist_ok=True)
        
    def tearDown(self):
        if os.path.exists(self.test_temp_dir):
            shutil.rmtree(self.test_temp_dir)

    # --- Word Timing Tests ---
    def test_calculate_word_timings(self):
        narration = "Hello world this is a test"
        wpm = 120
        scene_start = 2.0
        
        words = calculate_word_timings(narration, scene_start, wpm)
        self.assertEqual(len(words), 6)
        
        # Kiểm tra start/end hợp lệ và tăng dần
        prev_end = scene_start
        for w in words:
            self.assertGreaterEqual(w["start"], prev_end)
            self.assertGreater(w["end"], w["start"])
            prev_end = w["end"]
            
        # Tổng thời lượng của 6 từ ở 120 WPM: 6 / 120 * 60 = 3.0s (cộng thêm các sai số min duration nếu có)
        total_dur = words[-1]["end"] - scene_start
        self.assertGreaterEqual(total_dur, 3.0)

    def test_calculate_word_timings_single_word(self):
        narration = "Hello"
        words = calculate_word_timings(narration, 0.0, 120)
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0]["word"], "Hello")
        self.assertEqual(words[0]["start"], 0.0)

    def test_calculate_word_timings_custom_wpm(self):
        narration = "Hello world this is a test"
        words_slow = calculate_word_timings(narration, 0.0, 80)
        words_fast = calculate_word_timings(narration, 0.0, 200)
        
        dur_slow = words_slow[-1]["end"]
        dur_fast = words_fast[-1]["end"]
        self.assertGreater(dur_slow, dur_fast)

    def test_calculate_word_timings_with_offset(self):
        narration = "Hello world"
        offset = 15.5
        words = calculate_word_timings(narration, offset, 120)
        self.assertGreaterEqual(words[0]["start"], offset)

    # --- Translation Split Tests ---
    def test_split_translation_comma(self):
        translation = "Hãy nhắm mắt lại, và hít thở thật sâu."
        parts = split_translation_to_lines(translation, 2)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].endswith(","))

    def test_split_translation_conjunction(self):
        translation = "Tôi đi làm và tôi gặp bạn bè"
        parts = split_translation_to_lines(translation, 2)
        self.assertEqual(len(parts), 2)
        # Sẽ tách quanh liên từ "và"
        self.assertEqual(parts[0], "Tôi đi làm")
        self.assertEqual(parts[1], "và tôi gặp bạn bè")

    def test_split_translation_fallback_even(self):
        # Không dấu câu, không liên từ
        translation = "một hai ba bốn năm sáu bảy tám"
        parts = split_translation_to_lines(translation, 2)
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[0].split()), 4)

    def test_split_translation_more_lines_than_words(self):
        translation = "một hai"
        parts = split_translation_to_lines(translation, 5)
        # Trả về tối đa số từ, phần còn lại rỗng
        self.assertEqual(len(parts), 5)
        self.assertEqual(parts[0], "một")
        self.assertEqual(parts[1], "hai")
        self.assertEqual(parts[2], "")

    def test_split_translation_single(self):
        translation = "Xin chào Việt Nam"
        parts = split_translation_to_lines(translation, 1)
        self.assertEqual(parts, ["Xin chào Việt Nam"])

    # --- Bilingual ASS Subtitle Tests ---
    def test_build_bilingual_ass_multi_speaker(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
            {"word": "How", "start": 1.5, "end": 2.0},
            {"word": "are", "start": 2.0, "end": 2.5},
        ]
        translations = [
            {"scene_idx": 0, "text": "Xin chào thế giới", "start": 0.0, "end": 1.2},
            {"scene_idx": 1, "text": "Bạn thế nào", "start": 1.2, "end": 3.0}
        ]
        speaker_segments = [
            {"speaker": "Interviewer", "color": "&H0000FFFF", "start": 0.0, "end": 1.2},
            {"speaker": "Guest", "color": "&H0000FF00", "start": 1.2, "end": 3.0}
        ]
        
        ass_path = os.path.join(self.test_temp_dir, "test_bilingual.ass")
        success, path = build_bilingual_ass_subtitle(
            words, translations, speaker_segments, ass_path, orientation="vertical", show_translation=True
        )
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(path))
        
        # Đọc nội dung kiểm tra style
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Style: Speaker_Interviewer", content)
            self.assertIn("Style: Speaker_Guest", content)
            self.assertIn("Style: Vietnamese", content)
            self.assertIn("&H0000FFFF", content)
            self.assertIn("&H0000FF00", content)
            self.assertIn("Dialogue:", content)

    def test_build_bilingual_ass_english_only(self):
        words = [{"word": "Hello", "start": 0.0, "end": 1.0}]
        translations = [{"scene_idx": 0, "text": "Xin chào", "start": 0.0, "end": 1.0}]
        speaker_segments = [{"speaker": "Interviewer", "color": "&H0000FFFF", "start": 0.0, "end": 1.0}]
        
        ass_path = os.path.join(self.test_temp_dir, "test_en_only.ass")
        success, path = build_bilingual_ass_subtitle(
            words, translations, speaker_segments, ass_path, orientation="vertical", show_translation=False
        )
        
        self.assertTrue(success)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertNotIn("\\N{\\rVietnamese}", content)

    # --- Music Service Tests ---
    def test_list_available_music_empty(self):
        # Trỏ MUSIC_DIR tạm thời vào thư mục rỗng
        original_music_dir = sys.modules['src.config'].MUSIC_DIR
        temp_music_dir = os.path.join(self.test_temp_dir, "empty_music")
        sys.modules['src.config'].MUSIC_DIR = temp_music_dir
        
        files = list_available_music()
        self.assertEqual(files, [])
        
        # Restore
        sys.modules['src.config'].MUSIC_DIR = original_music_dir

    def test_create_silence(self):
        silence_path = os.path.join(self.test_temp_dir, "silence.wav")
        success, path = create_silence(2.5, silence_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)


@unittest.skipIf(UNIT_ONLY, "Bỏ qua các test cần GPU, Ollama, Internet hoặc Edge-TTS")
class TestSelfHealIntegration(unittest.TestCase):
    
    def setUp(self):
        self.test_temp_dir = os.path.join(TEMP_DIR, "test_selfheal_integration")
        os.makedirs(self.test_temp_dir, exist_ok=True)
        
    def tearDown(self):
        if os.path.exists(self.test_temp_dir):
            shutil.rmtree(self.test_temp_dir)

    def test_generate_selfheal_script_interview(self):
        # Đòi hỏi Ollama phải chạy tại localhost:11434
        success, data = generate_selfheal_script("Simple conversation about weather", "interview")
        if not success:
            self.skipTest(f"Ollama không phản hồi: {data}")
            
        self.assertTrue(success)
        self.assertIn("scenes", data)
        self.assertIn("speakers", data)
        self.assertGreater(len(data["scenes"]), 0)
        self.assertIn("speaker", data["scenes"][0])
        self.assertIn("narration", data["scenes"][0])

    def test_selfheal_tts_english(self):
        tts_path = os.path.join(self.test_temp_dir, "en_test.mp3")
        success, path = generate_tts(
            text="Hello. Welcome to the English learning class.",
            output_path=tts_path,
            voice="en-US-BrianNeural"
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)

    def test_selfheal_whisper_english(self):
        # Sinh 1 file tts rồi chạy Whisper
        tts_path = os.path.join(self.test_temp_dir, "en_test_wh.mp3")
        success, _ = generate_tts(
            text="Good morning everyone.",
            output_path=tts_path,
            voice="en-US-EmmaNeural"
        )
        self.assertTrue(success)
        
        from src.whisper_service import get_word_timestamps
        success, words = get_word_timestamps(tts_path, language="en")
        self.assertTrue(success)
        self.assertGreater(len(words), 0)
        self.assertEqual(words[0]["word"].lower().strip(".,!?"), "good")


class TestSelfHealRegression(unittest.TestCase):
    
    def test_original_generate_script_unchanged(self):
        # Đảm bảo hàm generate_script gốc không lỗi syntax và cấu trúc đầu ra cũ giữ nguyên
        from src.llm_service import generate_script
        # Chỉ check inspect signature
        import inspect
        sig = inspect.signature(generate_script)
        self.assertIn("topic", sig.parameters)
        self.assertIn("style_preset", sig.parameters)
        self.assertIn("language", sig.parameters)

    def test_original_build_ass_subtitle_unchanged(self):
        from src.subtitle_builder import build_ass_subtitle
        import inspect
        sig = inspect.signature(build_ass_subtitle)
        self.assertIn("words", sig.parameters)
        self.assertIn("output_path", sig.parameters)
        self.assertIn("orientation", sig.parameters)


if __name__ == "__main__":
    unittest.main()
