# Chức năng: Kiểm thử tự động đảm bảo video sinh ra có đầy đủ âm thanh giọng đọc TTS và xuất đúng thư mục output.
# Lý do tạo: Ngăn ngừa hồi quy lỗi "video sinh ra không có tiếng nói" và "không xuất output mà lưu trong temp".

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.video_compiler import compile_video_pipeline
from src.tts_service import generate_tts
from src.config import OUTPUT_DIR, TEMP_DIR


class TestAudioAndOutput(unittest.TestCase):

    def test_compiled_video_has_audio_and_reaches_output(self):
        """Kiểm thử compile_video_pipeline đảm bảo video có audio track và không bị câm."""
        test_dir = Path(TEMP_DIR) / "test_audio_verify"
        test_dir.mkdir(parents=True, exist_ok=True)

        # 1. Tạo 2 đoạn audio TTS mẫu
        audio1 = str(test_dir / "scene_1.mp3")
        audio2 = str(test_dir / "scene_2.mp3")

        generate_tts("Xin chào, đây là kiểm tra âm thanh phân cảnh một.", audio1, voice="vi-VN-HoaiMyNeural")
        generate_tts("Phân cảnh hai kiểm tra việc ghép tiếng nói vào video.", audio2, voice="vi-VN-HoaiMyNeural")

        self.assertTrue(os.path.exists(audio1) and os.path.getsize(audio1) > 1000)
        self.assertTrue(os.path.exists(audio2) and os.path.getsize(audio2) > 1000)

        # Tạo ảnh mẫu
        from PIL import Image
        img1 = str(test_dir / "scene_1.png")
        img2 = str(test_dir / "scene_2.png")
        Image.new("RGB", (480, 848), (20, 40, 60)).save(img1)
        Image.new("RGB", (480, 848), (60, 20, 40)).save(img2)

        scenes = [
            {"scene_num": 1, "audio_path": audio1, "audio_duration": 2.5, "image_path": img1, "use_video_ai": False},
            {"scene_num": 2, "audio_path": audio2, "audio_duration": 2.5, "image_path": img2, "use_video_ai": False},
        ]
        words = [
            {"word": "Xin", "start": 0.1, "end": 0.5},
            {"word": "chào", "start": 0.5, "end": 1.0},
            {"word": "hai", "start": 2.6, "end": 3.2},
        ]

        ok, compiled_videos, err = compile_video_pipeline(
            scenes=scenes,
            words_timestamps=words,
            max_duration=60.0,
            orientation="vertical"
        )

        self.assertTrue(ok, f"Compile video thất bại: {err}")
        self.assertTrue(len(compiled_videos) > 0)

        final_video = compiled_videos[0]
        self.assertTrue(os.path.exists(final_video), f"File không tồn tại: {final_video}")
        self.assertGreater(os.path.getsize(final_video), 10000, "File video quá nhỏ")

        # Kiểm tra file video xuất ra CÓ AUDIO STREAM
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(final_video)
        self.assertIsNotNone(clip.audio, "Video KHÔNG có audio stream (bị câm)!")
        self.assertGreater(clip.audio.duration, 2.0, "Thời lượng audio quá ngắn!")
        clip.close()


if __name__ == "__main__":
    unittest.main()
