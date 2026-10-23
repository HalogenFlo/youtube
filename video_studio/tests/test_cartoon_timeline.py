# Chức năng: Verify action progression, seek determinism and editorial preservation.
# Lý do: Prevent repeated stills and narration loss. Source: https://github.com/heygen-com/hyperframes
import unittest
from unittest.mock import patch
from src.cartoon_timeline import scene_plan, frame_commands, render_image


class TimelineTests(unittest.TestCase):
    def test_seek_is_order_independent(self):
        plan=scene_plan({'video_prompt':'walk into forest and pick an apple'})
        before=frame_commands(plan,3,6)
        frame_commands(plan,5,6)
        self.assertEqual(before,frame_commands(plan,3,6))

    def test_actor_moves_then_stops(self):
        plan=scene_plan({'video_prompt':'forest wave'})
        def shadow(t):
            return next(c for c in frame_commands(plan,t,6) if c[0]=='ellipse' and c[-1]=='#536e64')
        self.assertLess(shadow(0)[1],shadow(2)[1])
        self.assertEqual(shadow(3)[1],shadow(5)[1])

    def test_settings_and_unique_frames(self):
        for setting in ('forest','city','lab','space','sea'):
            plan=scene_plan({'video_prompt':setting+' pick'})
            frames=[render_image(frame_commands(plan,t,6),480,270).tobytes() for t in (0,1,3,4.5,5.9)]
            self.assertEqual(len(set(frames)),5)

    def test_invalid_edit_keeps_narration(self):
        from src.studio_editorial_service import run_studio_editorial_pipeline
        import json
        with patch('src.studio_editorial_service.call_ollama',return_value=(True,json.dumps({'scenes':[{'video_prompt':'forest'}]}))):
            scenes,report=run_studio_editorial_pipeline(topic='Forest',script_data={'scenes':[{'narration':'Original valid narration.', 'video_prompt':'forest'}]},target_scenes=1)
        self.assertEqual(scenes[0]['narration'],'Original valid narration.')
        self.assertFalse(report['llm_editorial_verified'])


if __name__=='__main__':
    unittest.main()
