# Chức năng: Kiểm thử tự động cho module Google Flow, Visual Beats và cơ chế Fallback.
# Lý do tạo: Tuân thủ quy tắc Red -> Green -> Refactor và verification trước khi hoàn tất.
# Trích dẫn: Unittest cho các pure functions và flow service.

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.visual_beats import calculate_visual_beats
from src.flow_browser_service import load_flow_config, STICKMAN_CANONICAL_GUIDANCE
from src.flow_image_service import generate_flow_image


class TestFlowEngine(unittest.TestCase):
    
    def test_visual_beats_calculation_short_scene(self):
        """Kiểm thử tính toán beats cho phân cảnh ngắn (<= 3s)."""
        beats = calculate_visual_beats(scene_duration=2.5, num_beats=2)
        self.assertEqual(len(beats), 1)
        self.assertEqual(beats[0]["effect"], "zoom_in")
        self.assertEqual(beats[0]["duration"], 2.5)

    def test_visual_beats_calculation_normal_scene(self):
        """Kiểm thử tính toán beats cho phân cảnh thông thường (> 3s)."""
        beats = calculate_visual_beats(scene_duration=6.0, num_beats=2)
        self.assertEqual(len(beats), 2)
        self.assertAlmostEqual(beats[0]["duration"], 3.0)
        self.assertAlmostEqual(beats[1]["duration"], 3.0)
        self.assertEqual(beats[0]["effect"], "zoom_in")
        self.assertEqual(beats[1]["effect"], "zoom_out")

    def test_flow_config_profile_mapping(self):
        """Kiểm thử cấu hình flow_config.json chứa đúng profile np368057@gmail.com."""
        cfg = load_flow_config()
        self.assertEqual(cfg.get("profile_directory"), "Default")
        self.assertEqual(cfg.get("user_email"), "np368057@gmail.com")
        self.assertEqual(cfg.get("cdp_port"), 9222)
        self.assertIn("Nano Banana Pro", cfg.get("default_model", ""))

    def test_mascot_asset_exists(self):
        """Kiểm thử file ảnh mascot Stickman tồn tại trên đĩa."""
        cfg = load_flow_config()
        mascot_path = ROOT / cfg.get("mascot_reference_path")
        self.assertTrue(mascot_path.exists(), f"Mascot file không tồn tại: {mascot_path}")
        self.assertGreater(mascot_path.stat().st_size, 1000)

    def test_canonical_stickman_guidance(self):
        """Kiểm thử chuỗi prompt guidance khoá nhân vật Stickman CH01."""
        self.assertIn("CH01", STICKMAN_CANONICAL_GUIDANCE)
        self.assertIn("#8CCFE8", STICKMAN_CANONICAL_GUIDANCE)
        self.assertIn("minimalist stickman", STICKMAN_CANONICAL_GUIDANCE.lower())


if __name__ == "__main__":
    unittest.main()
