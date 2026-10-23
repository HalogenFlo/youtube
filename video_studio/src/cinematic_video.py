# Chức năng: Dựng cảnh video từ các shot ngắn, có continuity và cache theo prompt.
# Lý do: Tránh lặp một clip ngắn cho cả đoạn thoại dài.
# Tham khảo: https://deepmind.google/technologies/veo/
import hashlib
import json
import math
import subprocess
from pathlib import Path

CINEMATIC_STYLE = 'stylized 3D animated feature film, expressive characters, cinematic lighting, detailed environments, consistent materials and character design'


def plan_shots(scene, previous=None):
    duration = max(.5, float(scene.get('audio_duration') or scene.get('expected_duration_sec') or 6))
    count = max(1, math.ceil(duration / 6))
    action = str(scene.get('video_prompt') or scene.get('visual_prompt') or scene.get('narration') or '')
    before = str(scene.get('state_before') or (previous or {}).get('state_after') or 'Establish the situation described in the scene')
    after = str(scene.get('state_after') or scene.get('consequence') or 'Complete the described action before cutting away')
    shots = []
    for i in range(count):
        authored = scene.get('shots') or []
        detail = authored[i] if isinstance(authored,list) and i<len(authored) and isinstance(authored[i],dict) else {}
        camera = ('wide establishing shot', 'medium action shot', 'close-up reaction shot')[i % 3]
        camera = str(detail.get('camera') or camera)
        shot_action = str(detail.get('action') or action)
        phase = 'begin the action' if i == 0 else ('show the result and reaction' if i == count-1 else 'develop the action without restarting it')
        shots.append(dict(index=i+1, duration=duration/count, camera=camera, prompt=(
            f'Generate at least {duration/count:.2f} seconds. Single continuous {camera}. Scene: {shot_action}. This is shot {i+1}/{count}: {phase}. '
            f'Initial story state: {detail.get("state_before") or before}. Final scene state: {detail.get("state_after") or after}. '
            f'Cause: {scene.get("cause") or "Continue the preceding event"}. '
            'Show physical character action, expressive eyes and facial reaction, secondary environmental motion. '
            'Preserve the same character identity, clothing, props, screen direction and lighting across shots. '
            'No title cards, no slideshow, no freeze frame, no repeated walk cycle. One deliberate camera move only.'
        )))
    return shots


def generate_cinematic_scene(scene, output_path, generate_clip, previous=None, **kwargs):
    shots = plan_shots(scene, previous)
    scene['cinematic_shots'] = shots
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    segments = []
    for shot in shots:
        cancel = kwargs.get('is_cancelled_callback')
        if cancel and cancel():
            return False, 'Đã hủy dựng shot.'
        digest = hashlib.sha256(json.dumps([shot,kwargs.get('style_preset')],sort_keys=True).encode()).hexdigest()[:16]
        clip = output.with_name(f'{output.stem}_shot{shot["index"]:02d}_{digest}.mp4')
        if not clip.exists() or clip.stat().st_size == 0:
            clip_kwargs = dict(kwargs)
            status = kwargs.get('status_callback')
            if status:
                status(0, f'Shot {shot["index"]}/{len(shots)}: {shot["camera"]}')
                clip_kwargs['status_callback'] = lambda seconds, message: status(seconds, f'Shot {shot["index"]}/{len(shots)}: {message}')
            ok, message = generate_clip(prompt=shot['prompt'], output_path=str(clip), **clip_kwargs)
            if not ok:
                return False, f'Shot {shot["index"]}/{len(shots)}: {message}'
        probe = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(clip)],capture_output=True,text=True)
        try:
            available = float(json.loads(probe.stdout)['format']['duration'])
        except (ValueError, KeyError, TypeError):
            return False, f'Shot {shot["index"]} không phải clip hợp lệ.'
        if available + .1 < shot['duration']:
            return False, f'Shot {shot["index"]} quá ngắn ({available:.1f}s); cần {shot["duration"]:.1f}s. Không lặp clip để bù.'
        segment = clip.with_name(clip.stem+'_cut.mp4')
        result = subprocess.run(['ffmpeg','-v','error','-y','-i',str(clip),'-t',str(shot['duration']),'-an','-r','30','-c:v','libx264','-preset','fast','-pix_fmt','yuv420p',str(segment)],capture_output=True,text=True)
        if result.returncode:
            return False, result.stderr[-500:]
        segments.append(segment)
    listing = output.with_suffix('.shots.txt')
    listing.write_text(''.join("file '"+str(p.resolve()).replace('\\','/').replace("'","'\\''")+"'\n" for p in segments),encoding='utf-8')
    result = subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(output)],capture_output=True,text=True)
    return (True,str(output)) if result.returncode == 0 else (False,result.stderr[-500:])
