import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.studio_editorial_service import run_studio_editorial_pipeline
from src import studio_skill_registry as registry


class TestStudioEditorial(unittest.TestCase):
    def test_registry_selects_one_skill_per_role(self):
        selected = registry.select_studio_skills("Dạy cách cộng nhị phân")
        roles = [item["role"] for item in selected]
        self.assertEqual(len(roles), len(set(roles)))
        self.assertIn("fact_checker", roles)
        self.assertIn("retention_editor", roles)

    @patch("src.studio_editorial_service.call_ollama")
    def test_editorial_pass_sanitizes_visual_prompts(self, mock_call):
        mock_call.return_value = (True, {
            "scenes": [
                {"scene_num": 1, "narration": "Mở bài", "video_prompt": "Teacher in a classroom"},
                {"scene_num": 2, "narration": "Kết luận", "video_prompt": "Student uses colorful blocks"},
            ],
            "report": {
                "scores": {"factual_accuracy": 90, "hook_strength": 85, "clarity": 88, "visual_continuity": 90, "policy_safety": 95},
                "issues_fixed": [], "remaining_warnings": [], "approved": True,
            },
        })
        scenes, report = run_studio_editorial_pipeline(
            "Cộng nhị phân",
            {"scenes": [
                {"scene_num": 1, "narration": "A", "video_prompt": "A"},
                {"scene_num": 2, "narration": "B", "video_prompt": "B"},
            ]},
            2,
        )
        self.assertEqual(len(scenes), 2)
        self.assertTrue(all("No readable text" in scene["video_prompt"] for scene in scenes))
        self.assertGreaterEqual(report["overall_score"], 80)
        self.assertTrue(report["approved"])

    def test_skill_scores_learn_from_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(registry, "SCORE_PATH", Path(tmp) / "scores.json"):
                registry.record_skill_outcome(["retention_editor_v2"], True)
                selected = registry.select_studio_skills("video kiến thức")
                item = next(skill for skill in selected if skill["id"] == "retention_editor_v2")
                self.assertEqual(item["runs"], 1)

    @patch("src.studio_editorial_service.call_ollama")
    def test_visual_prompt_with_equation_is_replaced_not_only_warned(self, mock_call):
        mock_call.return_value = (True, {
            "scenes": [{
                "scene_num": 1,
                "narration": "Một cộng một bằng mười trong hệ nhị phân.",
                "video_prompt": "Write equation 1+1=10 on a whiteboard",
            }],
            "report": {"scores": {}, "issues_fixed": [], "remaining_warnings": [], "approved": True},
        })
        scenes, _ = run_studio_editorial_pipeline(
            "Cộng nhị phân", {"scenes": mock_call.return_value[1]["scenes"]}, 1
        )
        self.assertNotIn("1+1", scenes[0]["video_prompt"])
        self.assertNotIn("whiteboard", scenes[0]["video_prompt"].lower())
        self.assertIn("geometric blocks", scenes[0]["video_prompt"])


if __name__ == "__main__":
    unittest.main()
