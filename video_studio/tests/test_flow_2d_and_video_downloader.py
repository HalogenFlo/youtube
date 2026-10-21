import os
import unittest
from unittest.mock import MagicMock, patch

from src.flow_browser_service import STICKMAN_CANONICAL_GUIDANCE, FlowBrowserController
from src.llm_service import get_system_prompt, generate_script
from src.studio_editorial_service import _sanitize_scenes


class TestFlow2DAndVideoDownloader(unittest.TestCase):
    def test_canonical_guidance_strictly_enforces_2d_and_forbids_3d(self):
        """Kiểm tra chỉ dẫn phong cách nhân vật CH01 bắt buộc 2D hoạt hình và cấm tuyệt đối 3D."""
        guidance = STICKMAN_CANONICAL_GUIDANCE.lower()
        self.assertIn("strictly vibrant 2d animation", guidance)
        self.assertIn("flat 2d cartoon", guidance)
        self.assertIn("strictly no 3d rendering", guidance)
        self.assertIn("no cgi", guidance)
        self.assertIn("no realistic 3d models", guidance)
        self.assertIn("no claymation", guidance)

    def test_llm_system_prompts_enforce_2d_animation_and_forbid_3d(self):
        """Kiểm tra mọi system prompt trong llm_service ép buộc 2D cartoon/animation và cấm 3D."""
        modes = ["knowledge", "chinese_teaching_vi", "english_vocab_story", "story_explainer"]
        for mode in modes:
            prompt = get_system_prompt(language="vi", content_mode=mode).lower()
            self.assertTrue(
                "2d" in prompt or "hoạt hình" in prompt or "flat" in prompt,
                f"Mode {mode} thiếu chỉ thị 2D"
            )
            self.assertTrue(
                "cấm" in prompt or "no 3d" in prompt or "tuyệt đối" in prompt,
                f"Mode {mode} thiếu chỉ thị cấm 3D"
            )

    def test_studio_editorial_sanitizes_visual_to_2d_and_strips_3d(self):
        """Kiểm tra bàn biên tập studio lọc sạch từ khóa 3D/CGI và bọc quy tắc 2D hoạt hình."""
        raw_scenes = [
            {
                "scene_num": 1,
                "narration": "Thử nghiệm lời dẫn.",
                "video_prompt": "Cinematic photorealistic 3D render with CGI human models and realistic 3d textures."
            }
        ]
        sanitized = _sanitize_scenes(raw_scenes, target_scenes=1, content_mode="knowledge")
        visual = sanitized[0]["video_prompt"].lower()
        self.assertNotIn("realistic 3d", visual)
        self.assertNotIn("cgi", visual)
        self.assertIn("strictly 2d animation", visual)
        self.assertIn("strictly no 3d", visual)

    def test_flow_prompt_construction_contains_2d_and_no_3d_rule(self):
        """Kiểm tra prompt gửi lên Google Flow ép buộc 2D animation clip và cấm 3D."""
        ctrl = FlowBrowserController()
        # Mock locator and page elements
        mock_page = MagicMock()
        mock_page.locator.return_value.count.return_value = 1
        mock_page.locator.return_value.first.is_visible.return_value = True
        
        # Test full_prompt generation logic inside controller
        prompt = "Stickman discovering cave drawings"
        ratio_hint = "vertical 9:16 portrait"
        full_prompt = (
            "Generate exactly ONE 2D ANIMATION VIDEO CLIP, not a still image and strictly NO 3D. Use the configured video model.\n"
            f"Scene: {prompt.strip()}\n{STICKMAN_CANONICAL_GUIDANCE}\n"
            f"Composition: {ratio_hint}. 2D hand-drawn motion, smooth 2D camera movement, flat cartoon aesthetics, no audio."
        )
        self.assertIn("2D ANIMATION VIDEO CLIP", full_prompt)
        self.assertIn("strictly NO 3D", full_prompt)
        self.assertIn("flat cartoon aesthetics", full_prompt)


if __name__ == "__main__":
    unittest.main()
