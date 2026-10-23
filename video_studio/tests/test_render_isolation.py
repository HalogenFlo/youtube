# Chức năng: Kiểm tra hai lượt dựng đồng thời không ghi đè video/phụ đề.
# Lý do: Turbo từng dùng chung part_1_raw.mp4; nguồn: báo lỗi người dùng.
import concurrent.futures
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from src import video_compiler as compiler


class RenderIsolationTests(unittest.TestCase):
    def test_parallel_renders_use_distinct_paths(self):
        barrier = threading.Barrier(2)
        raw_paths, ass_paths = [], []
        def raw(**kwargs):
            path = kwargs['raw_output_path']
            raw_paths.append(path)
            Path(path).write_bytes(b'raw')
            barrier.wait(timeout=10)
            return True, path
        def burn(raw_path, ass_path, final_path, *args):
            ass_paths.append(ass_path)
            Path(final_path).write_bytes(b'finished')
            return True, ''
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(compiler, 'TEMP_DIR', directory), \
             patch.object(compiler, 'OUTPUT_DIR', directory), \
             patch.object(compiler, '_compile_part_with_ffmpeg_native', side_effect=raw), \
             patch.object(compiler, 'burn_subtitles', side_effect=burn), \
             patch.dict('sys.modules', {'moviepy.editor': None}):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: compiler.compile_video_pipeline(
                    [{'audio_duration': 1}], [], target_resolution=(320, 180)), range(2)))
            self.assertTrue(all(r[0] for r in results), results)
            self.assertEqual(len(set(raw_paths)), 2)
            self.assertEqual(len(set(ass_paths)), 2)
            self.assertNotEqual(results[0][1], results[1][1])


if __name__ == '__main__':
    unittest.main()
