import os
# MoviePy compatibility shim for headless/FFmpeg-native environments where moviepy is not installed
import sys
import types
import subprocess
import json

try:
    import moviepy.editor  # noqa: F401
except ImportError:
    class _ShimAudioClip:
        def __init__(self, filename_or_func=None, duration=0.0, fps=44100):
            self.filename = str(filename_or_func) if isinstance(filename_or_func, str) else ""
            self.duration = float(duration or 0.0)
            if self.filename and os.path.exists(self.filename):
                try:
                    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", self.filename]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if res.returncode == 0:
                        data = json.loads(res.stdout or "{}")
                        self.duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
                except Exception:
                    pass
        def subclip(self, start=0.0, end=None):
            return _ShimAudioClip(duration=max(0.0, float((end if end is not None else self.duration)) - float(start)))
        def write_audiofile(self, out_path, *a, **kw):
            pass
        def close(self):
            pass

    class _ShimVideoFileClip:
        def __init__(self, path):
            self.filename = str(path)
            self.duration = 0.0
            self.audio = None
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    data = json.loads(res.stdout or "{}")
                    self.duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
                    streams = data.get("streams", [])
                    if any(s.get("codec_type") == "audio" for s in streams):
                        self.audio = _ShimAudioClip(duration=self.duration)
            except Exception:
                pass
        def subclip(self, start=0.0, end=None):
            c = _ShimVideoFileClip(self.filename)
            c.duration = max(0.0, float((end if end is not None else self.duration)) - float(start))
            return c
        def set_duration(self, d):
            self.duration = float(d)
            return self
        def set_audio(self, a):
            self.audio = a
            return self
        def fx(self, func, *args, **kwargs):
            return func(self, *args, **kwargs)
        def resize(self, *args, **kwargs):
            return self
        def crop(self, *args, **kwargs):
            return self
        def close(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

    def _shim_loop(clip, duration=None, n=None):
        if duration is not None:
            clip.duration = float(duration)
        return clip

    def _shim_concat_audio(clips):
        total = sum(getattr(c, "duration", 0.0) for c in clips)
        return _ShimAudioClip(duration=total)

    mp_mod = types.ModuleType("moviepy")
    mp_editor = types.ModuleType("moviepy.editor")
    mp_video = types.ModuleType("moviepy.video")
    mp_video_fx = types.ModuleType("moviepy.video.fx")
    mp_video_fx_all = types.ModuleType("moviepy.video.fx.all")

    mp_editor._IS_SHIM = True
    mp_editor.VideoFileClip = _ShimVideoFileClip
    mp_editor.AudioFileClip = _ShimAudioClip
    mp_editor.AudioClip = _ShimAudioClip
    mp_editor.ImageClip = _ShimVideoFileClip
    mp_editor.ColorClip = _ShimVideoFileClip
    mp_editor.CompositeVideoClip = lambda clips, *a, **kw: clips[0] if clips else _ShimVideoFileClip("")
    mp_editor.CompositeAudioClip = lambda clips, *a, **kw: clips[0] if clips else _ShimAudioClip(duration=0.0)
    mp_editor.concatenate_videoclips = lambda clips, *a, **kw: _ShimVideoFileClip("")
    mp_editor.concatenate_audioclips = _shim_concat_audio
    mp_video_fx_all.loop = _shim_loop

    mp_mod.editor = mp_editor
    mp_mod.video = mp_video
    mp_video.fx = mp_video_fx
    mp_video_fx.all = mp_video_fx_all

    sys.modules["moviepy"] = mp_mod
    sys.modules["moviepy.editor"] = mp_editor
    sys.modules["moviepy.video"] = mp_video
    sys.modules["moviepy.video.fx"] = mp_video_fx
    sys.modules["moviepy.video.fx.all"] = mp_video_fx_all
