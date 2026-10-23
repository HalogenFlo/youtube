"""Verify local VieNeu dispatch, bilingual order, cache identity, and explicit failures.

Protects MuseAI lessons from changing their spoken language or silently swapping models.
API source: https://github.com/pnnbao97/VieNeu-TTS
"""
from pathlib import Path
import json
import sys
import types
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import tts_service, vieneu_service
from src import museai_3d_service as svc


def scene():
    return {"scene_num": 1, "content_mode": "english_teaching_vi", "speech_segments": [
        {"language": "vi", "text": "Bạn hãy nói:"},
        {"language": "en", "text": "Good morning!"},
        {"language": "vi", "text": "Nghĩa là chào buổi sáng."}]}


def test_direct_local_voice_never_calls_edge(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(vieneu_service, "generate_vieneu_batch", lambda jobs: (seen.extend(jobs) or True, "local"))
    monkeypatch.setattr(tts_service, "_run_edge_tts_direct", lambda **kw: pytest.fail("Unexpected Edge fallback"))
    assert tts_service.generate_tts("Xin chào", str(tmp_path / "voice.mp3"), voice="vieneu-v3:Mai Anh")[0]
    assert seen[0][1] == "vieneu-v3:Mai Anh"


def test_mixed_batch_preserves_vi_en_vi_order(tmp_path, monkeypatch):
    local_calls, edge_calls, order = [], [], []
    def local(jobs):
        local_calls.extend(jobs)
        for text, _, _, path in jobs:
            Path(path).write_text(text, encoding="utf-8")
        return True, ""
    def edge(text, output, **kwargs):
        edge_calls.append((text, kwargs["voice"]))
        Path(output).write_text(text, encoding="utf-8")
        return True, output
    class Clip:
        def __init__(self, path=None):
            self.text = Path(path).read_text(encoding="utf-8") if path else ""
        def close(self): pass
        def write_audiofile(self, output, **kw): Path(output).write_bytes(b"audio")
    def concatenate(clips):
        order.extend(c.text for c in clips)
        return Clip()
    monkeypatch.setattr(vieneu_service, "generate_vieneu_batch", local)
    monkeypatch.setattr(tts_service, "generate_tts", edge)
    monkeypatch.setitem(sys.modules, "moviepy.editor", types.SimpleNamespace(AudioFileClip=Clip, concatenate_audioclips=concatenate))
    segments = [("Lời Việt trước", "vieneu-v3:Mai Anh", "+0%"),
                ("Good morning!", "en-US-JennyNeural", "-8%"),
                ("Lời Việt sau", "vieneu-v3:Mai Anh", "+0%")]
    assert tts_service.generate_multivoice_tts(segments, str(tmp_path / "voice.mp3"), strict_language=True)[0]
    assert len(local_calls) == 2 and edge_calls == [("Good morning!", "en-US-JennyNeural")]
    assert order == [s[0] for s in segments]
    assert not list(tmp_path.glob(".voice_segment*"))


def test_model_selection_changes_cache_but_keeps_english(tmp_path, monkeypatch):
    calls = []
    def generate(segments, output, **kwargs):
        calls.append(segments)
        Path(output).write_bytes(b"a" * 1300)
        kwargs["segment_timing_callback"]([{"text": t, "voice": v, "duration": 1} for t, v, _ in segments])
        return True, output
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", generate)
    monkeypatch.setattr(tts_service, "get_audio_duration", lambda _: 3.)
    sc = scene()
    for voice in ("vieneu-v3:Mai Anh", "vieneu-v3:Mai Anh", "vieneu-v3:Hải Đăng"):
        assert svc.synthesize_museai_scenes_interactive_tts([sc], str(tmp_path), "vi_en", voice)[0]
    assert len(calls) == 2
    assert [v for _, v, _ in calls[0]] == ["vieneu-v3:Mai Anh", "en-US-JennyNeural", "vieneu-v3:Mai Anh"]
    meta = json.loads((tmp_path / "scene_001_tts.meta.json").read_text(encoding="utf-8"))
    assert "vieneu-v3:Hải Đăng" in meta["voices_signature"]
    assert [s["start"] for s in meta["tts_segment_timings"]] == [0., 1., 2.]


def test_local_failure_is_returned_without_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", lambda *a, **kw: (False, "Model unavailable"))
    monkeypatch.setattr(tts_service, "generate_tts", lambda *a, **kw: pytest.fail("Silent model swap"))
    ok, error = svc.synthesize_museai_scenes_interactive_tts([{"scene_num": 1, "narration": "Chào các bạn."}],
                        str(tmp_path), "vi", "vieneu-v3:Mai Anh")
    assert not ok and "Model unavailable" in error


def test_missing_runtime_has_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(vieneu_service, "runtime_python", lambda: tmp_path / "missing.exe")
    ok, error = vieneu_service.generate_vieneu_batch([("Xin chào", "vieneu-v3:Mai Anh", "+0%", "unused.mp3")])
    assert not ok and "setup_vieneu.ps1" in error


@pytest.mark.parametrize("failure", ["tts", "compiler", "missing_audio"])
def test_voiced_3d_failure_never_falls_back_to_a_muted_success(tmp_path, monkeypatch, failure):
    from src import batch_producer, video_compiler
    video = tmp_path / "scene.mp4"
    video.write_bytes(b"source video")
    audio = tmp_path / "scene.mp3"
    audio.write_bytes(b"speech")
    sc = {"scene_num": 1, "media_type": "video", "video_path": str(video),
          "audio_duration": 1., "narration": "Chào các bạn.", "vietnamese_voice": "vieneu-v3:Mai Anh"}
    if failure != "missing_audio":
        sc["audio_path"] = str(audio)
    monkeypatch.setattr(svc, "synthesize_museai_scenes_interactive_tts", lambda **kw: (failure != "tts", "VieNeu unavailable"))
    monkeypatch.setattr(batch_producer, "build_exact_tts_timestamps", lambda _: [])
    monkeypatch.setattr(video_compiler, "compile_video_pipeline", lambda **kw: (False, [], "Subtitle compiler failed"))
    monkeypatch.setattr(svc.subprocess, "run", lambda *a, **kw: pytest.fail("Must not export muted fallback"))
    output = tmp_path / "final.mp4"
    ok, error = svc.merge_flow_3d_scenes_into_final_movie([sc], str(tmp_path), str(output))
    assert not ok and error and not output.exists()


def test_cast_persists_across_episode_workdirs_and_reruns(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_service, "get_audio_duration", lambda _: 2.)
    def synthesize(segments, output, **kwargs):
        Path(output).write_bytes(b"a" * 1300)
        return True, output
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", synthesize)
    def episode(names):
        return [{"scene_num": 1, "media_type": "whiteboard", "dialogue_lines": [
            {"speaker": "character_1", "character_name": name, "text": "Chào bạn, hôm nay mình cùng học nhé."}
            for name in names]}]
    def actual_voices(scenes):
        return {s["character_name"]: s["voice_spec"] for s in scenes[0]["dialogue_lines"]}
    first = episode(["Bin", "Nam"])
    assert svc.synthesize_museai_scenes_interactive_tts(first, str(tmp_path / "ep1"), "vi", "vieneu-v3:Mai Anh")[0]
    second = episode(["Nam", "Bin"])
    second[0]["voice_casting"] = first[0]["voice_casting"]
    assert svc.synthesize_museai_scenes_interactive_tts(second, str(tmp_path / "ep2"), "vi", "vieneu-v3:Mai Anh")[0]
    assert actual_voices(first) == actual_voices(second)
    restarted = episode(["Bin", "Nam"])
    assert svc.synthesize_museai_scenes_interactive_tts(restarted, str(tmp_path / "ep2"), "vi", "vieneu-v3:Mai Anh")[0]
    assert actual_voices(restarted) == actual_voices(first)
