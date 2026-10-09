# Chức năng: Kiểm thử tự động vị trí phụ đề ở đáy màn hình, kích thước font thu nhỏ và dọn dẹp file temp audio an toàn.
# Lý do tạo: Đảm bảo tuân thủ quy tắc Red -> Green -> Refactor theo yêu cầu người dùng.

import os
import re
import tempfile
import unittest
from pathlib import Path

from src.subtitle_builder import build_ass_subtitle, build_bilingual_ass_subtitle
from src.video_compiler import _safe_delete_file


class TestSubtitleBottomLayoutAndFileLock(unittest.TestCase):

    def test_build_ass_subtitle_vertical_is_bottom_and_compact(self):
        """Kiểm tra phụ đề video dọc: Alignment=2 (Bottom Center), MarginV=260, Fontsize<=48."""
        sample_words = [
            {"word": "Xin", "start": 0.0, "end": 0.3},
            {"word": "chào", "start": 0.3, "end": 0.6},
            {"word": "các", "start": 0.6, "end": 0.9},
            {"word": "bạn", "start": 0.9, "end": 1.2},
        ]
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            temp_path = f.name

        try:
            ok, out_path = build_ass_subtitle(sample_words, temp_path, orientation="vertical")
            self.assertTrue(ok)
            content = Path(out_path).read_text(encoding="utf-8")

            # Tìm Style: Default line
            style_line = [line for line in content.splitlines() if line.startswith("Style: Default")][0]
            parts = style_line.split(",")
            font_size = int(parts[2])
            alignment = int(parts[18])
            margin_v = int(parts[21])

            # Kiểm tra font size thu nhỏ <= 48 (trước đây là 72)
            self.assertLessEqual(font_size, 48)
            self.assertEqual(font_size, 44)

            # Kiểm tra căn ở đáy màn hình (Alignment 2: Bottom Center thay vì 5: Center)
            self.assertEqual(alignment, 2)

            # Kiểm tra MarginV nằm ở vùng an toàn đáy (260 thay vì 960 giữa màn hình)
            self.assertEqual(margin_v, 260)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_build_bilingual_ass_subtitle_vertical_is_bottom_and_compact(self):
        """Kiểm tra phụ đề song ngữ: vị trí Y dời xuống đáy (>1400), font nhỏ gọn."""
        sample_words = [{"word": "Hello", "start": 0.0, "end": 0.5}]
        sample_trans = [{"start": 0.0, "end": 0.5, "text": "Xin chào"}]
        sample_speakers = [{"speaker": "Default", "start": 0.0, "end": 0.5}]

        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            temp_path = f.name

        try:
            ok, out_path = build_bilingual_ass_subtitle(
                sample_words, sample_trans, sample_speakers, temp_path, orientation="vertical"
            )
            self.assertTrue(ok)
            content = Path(out_path).read_text(encoding="utf-8")

            # Kiểm tra tọa độ \pos(x, y) phải ở nửa dưới màn hình (y >= 1400)
            pos_matches = re.findall(r"\\pos\((\d+),(\d+)\)", content)
            self.assertTrue(len(pos_matches) > 0)
            for x_str, y_str in pos_matches:
                y = int(y_str)
                self.assertGreaterEqual(y, 1400, f"Tọa độ Y {y} quá cao, nằm giữa màn hình gây che hình ảnh!")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_safe_delete_file_handles_locked_or_nonexistent_safely(self):
        """Kiểm tra _safe_delete_file không crash khi file không tồn tại hoặc lỗi."""
        # File không tồn tại
        _safe_delete_file("non_existent_file_123456.m4a")

        # File thật
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"sample audio content")
            real_path = f.name

        self.assertTrue(os.path.exists(real_path))
        _safe_delete_file(real_path)
        self.assertFalse(os.path.exists(real_path))


if __name__ == "__main__":
    unittest.main()
