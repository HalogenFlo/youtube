import os
import unittest
from src.tts_service import generate_tts, sanitize_tts_text


class TestTTSResilience(unittest.TestCase):
    def test_sanitize_tts_text(self):
        # Kiểm tra loại bỏ markdown và thẻ kịch bản
        raw = '**Cảnh 5:** [Nhạc nền bí ẩn] "Liệu chúng ta có đang thực sự hiểu vũ trụ này?" (giọng trầm)'
        clean = sanitize_tts_text(raw)
        self.assertNotIn('[Nhạc nền bí ẩn]', clean)
        self.assertNotIn('**', clean)
        self.assertIn('Liệu chúng ta có đang thực sự hiểu vũ trụ này', clean)

    def test_tts_generation_with_complex_text(self):
        # Kiểm tra sinh giọng đọc thực tế với text chứa ký tự đặc biệt
        out_file = 'temp/test_resilience_output.mp3'
        if os.path.exists(out_file):
            try:
                os.remove(out_file)
            except Exception:
                pass

        test_text = "Những bí ẩn khoa học khiến con người phải suy nghĩ lại."
        ok, path = generate_tts(test_text, out_file, voice="vi-VN-HoaiMyNeural")
        self.assertTrue(ok, f"TTS thất bại: {path}")
        self.assertTrue(os.path.exists(out_file))
        self.assertGreater(os.path.getsize(out_file), 1000)

        # Cleanup
        if os.path.exists(out_file):
            try:
                os.remove(out_file)
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
