# Chức năng: Kiểm tra shot pacing và ghép clip chuyển động thật.
# Lý do: Không lặp một clip ngắn để lấp đoạn thoại dài.
import tempfile
import subprocess
from pathlib import Path
from src.cinematic_video import plan_shots, generate_cinematic_scene


def test_shots_cover_voice_duration():
    shots=plan_shots({'audio_duration':17,'video_prompt':'Lumi discovers a broken bridge'})
    assert len(shots)==3
    assert abs(sum(s['duration'] for s in shots)-17)<.001
    assert max(s['duration'] for s in shots)<=6
    assert len({s['camera'] for s in shots})==3


def test_3d_style_survives_editor():
    from src.studio_editorial_service import _sanitize_scenes
    scene=_sanitize_scenes([{'narration':'Lumi finds a clue.', 'video_prompt':'A stylized 3D girl discovers a glowing stone under a tree.'}],style_preset='stylized 3D animated feature film')[0]
    assert '3D' in scene['video_prompt']
    assert 'strictly no 3d' not in scene['video_prompt'].lower()


def test_authored_action_used_in_shots():
    shots=plan_shots({'audio_duration':5,'video_prompt':'Generic setting', 'shots':[{'action':'Lumi lifts the stone','camera':'low angle close-up'}]})
    assert 'Lumi lifts the stone' in shots[0]['prompt']
    assert shots[0]['camera']=='low angle close-up'


def test_shot_failure_never_falls_back():
    with tempfile.TemporaryDirectory() as tmp:
        ok,message=generate_cinematic_scene({'audio_duration':10},str(Path(tmp)/'scene.mp4'),
            lambda **kw:(False,'generation failed'))
        assert not ok and 'Shot 1/2' in message


def test_real_ffmpeg_shot_assembly():
    with tempfile.TemporaryDirectory() as tmp:
        calls=[]
        def generate(**kwargs):
            calls.append(kwargs)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                'testsrc2=size=160x90:rate=30:duration=4','-c:v','libx264',kwargs['output_path']],check=True)
            return True,kwargs['output_path']
        output=str(Path(tmp)/'scene.mp4')
        ok,message=generate_cinematic_scene({'audio_duration':7,'video_prompt':'A traveler crosses a bridge'},output,generate)
        assert ok,message
        assert len(calls)==2
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',output,'-f','null','-'],check=True)
