"""Regression coverage for MuseAI whiteboard routing and audible series continuity.

Tests rendering/voiceover order, preservation of the script, and promised lessons.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import museai_3d_service as svc
from src import whiteboard_video as board
from src.museai_story_modes import add_learning_bridges


def story():
    return {"visual_mode": "whiteboard", "story_title": "Lãi kép", "character_anchor": "Bin, black stick figure",
            "episode_learning_summary": "Lãi kép là lãi sinh thêm lãi.", "next_episode_topic": "Tác động của thời gian",
            "scenes": [{"scene_num": 1, "narration": "Lãi sinh thêm lãi.",
                        "whiteboard_items": [{"type": "circle", "x": .5, "y": .4, "label": "100"}]}]}


def test_whiteboard_prompt_and_enrichment_preserve_2d_and_narration():
    prompt = svc.build_museai_story_script_prompt(topic="Lãi kép", visual_mode="whiteboard",
                episode_num=2, total_episodes=3, previous_episode_learning="Tiết kiệm",
                required_episode_topic="Lãi kép")
    assert "whiteboard_items" in prompt and "SERIES LEARNING CONTINUITY" in prompt
    assert "Master Pixar" not in prompt and "Required lesson" in prompt
    source = story()
    parsed = svc.parse_museai_story_json(json.dumps(source))
    enriched = svc.MuseAIFlowHybridController()._enrich_scenes_with_3d_prompts(parsed, "horizontal", "whiteboard")
    assert enriched["character_anchor"] == source["character_anchor"]
    assert enriched["scenes"][0]["narration"] == source["scenes"][0]["narration"]
    assert enriched["scenes"][0]["media_type"] == "whiteboard"
    assert "3D" not in enriched["character_anchor"]


@pytest.mark.parametrize("episode,total,previous,kinds", [
    (1, 1, "", []), (1, 3, "", ["preview"]),
    (2, 3, "Tiết kiệm", ["recap", "preview"]), (3, 3, "Lãi kép", ["recap"])])
def test_series_bridges_are_spoken_and_idempotent(episode, total, previous, kinds):
    source = story()
    result = add_learning_bridges(source, episode, total, "vi", previous)
    bridges = [s for s in result["scenes"] if s.get("series_bridge")]
    assert [s["series_bridge"] for s in bridges] == kinds
    assert all(s["dialogue_lines"][0]["text"] == s["narration"] for s in bridges)
    assert add_learning_bridges(result, episode, total, "vi", previous) == result
    assert source == story()  # input is not mutated
    if episode == total:
        assert result["next_episode_topic"] == ""


def test_missing_next_lesson_does_not_invent_one():
    source = story()
    source.pop("next_episode_topic")
    with pytest.raises(ValueError, match="next_episode_topic"):
        add_learning_bridges(source, 1, 2, "vi")


def test_whiteboard_pipeline_synthesizes_then_draws_and_never_opens_flow(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_3d_script_via_museai",
                        lambda self, **kw: (True, deepcopy(story())))
    def forbidden(*a, **kw):
        pytest.fail("Whiteboard must never call Google Flow")
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "start_fresh_google_flow_project", forbidden)
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_scene_3d_video_on_google_flow", forbidden)
    def tts(scenes, work_dir, language):
        events.append("tts")
        for i, sc in enumerate(scenes):
            path = Path(work_dir) / f"{i}.mp3"
            path.write_bytes(b"audio")
            sc.update(audio_path=str(path), audio_duration=2.25)
        return True, "ok"
    monkeypatch.setattr(svc, "synthesize_museai_scenes_interactive_tts", tts)
    def render(scene, output_path, duration, **kw):
        assert events[0] == "tts"
        assert duration == 2.25 and kw["size"] == (1920, 1080)
        events.append("draw")
        Path(output_path).write_bytes(b"video")
        return True, output_path
    monkeypatch.setattr(board, "render_whiteboard_scene_video", render)
    def merge(scenes, work_dir, final_output_path, *a, **kw):
        assert kw["tts_already_ready"] is True
        assert all(s["media_type"] == "whiteboard" for s in scenes)
        events.append("merge")
        Path(final_output_path).write_bytes(b"result")
        return True, final_output_path
    monkeypatch.setattr(svc, "merge_flow_3d_scenes_into_final_movie", merge)
    ok, path, meta = svc.run_museai_script_to_google_flow_3d_pipeline(
        topic="Lãi kép", visual_mode="whiteboard", orientation="horizontal",
        work_dir=str(tmp_path / "work"), output_dir=str(tmp_path / "out"))
    assert ok, path
    assert events == ["tts", "draw", "merge"]
    assert Path(path).with_suffix(".json").is_file()
    assert meta["video_engine"] == "local_whiteboard_pillow_ffmpeg"


def test_tts_failure_stops_whiteboard_instead_of_exporting_silent_movie(tmp_path, monkeypatch):
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_3d_script_via_museai",
                        lambda self, **kw: (True, story()))
    monkeypatch.setattr(svc, "synthesize_museai_scenes_interactive_tts", lambda *a: (False, "TTS unavailable"))
    ok, error, _ = svc.run_museai_script_to_google_flow_3d_pipeline(
        visual_mode="whiteboard", work_dir=str(tmp_path), output_dir=str(tmp_path / "out"))
    assert not ok and error == "TTS unavailable"


def test_series_passes_exact_promised_topic_and_last_learning_and_resumes_numbering(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "TEMP_DIR", tmp_path)
    calls = []
    def episode(**kw):
        calls.append(kw)
        data = story()
        data["episode_learning_summary"] = f"Bài {kw['episode_num']}"
        data["next_episode_topic"] = f"Chủ đề {kw['episode_num'] + 1}"
        return True, str(tmp_path / f"ep{kw['episode_num']}.mp4"), {"story": data}
    monkeypatch.setattr(svc, "run_museai_script_to_google_flow_3d_pipeline", episode)
    ok, paths, _ = svc.run_museai_multi_episode_series_pipeline(
        total_episodes=2, start_episode_num=4, visual_mode="whiteboard", initial_episode_learning="Bài 3",
        initial_next_episode_topic="Chủ đề 4", work_dir=str(tmp_path / "work"), output_dir=str(tmp_path))
    assert ok and len(paths) == 2
    assert [(c["episode_num"], c["total_episodes"]) for c in calls] == [(4, 5), (5, 5)]
    assert calls[0]["previous_episode_learning"] == "Bài 3"
    assert calls[0]["required_episode_topic"] == "Chủ đề 4"
    assert calls[1]["previous_episode_learning"] == "Bài 4"
    assert calls[1]["required_episode_topic"] == "Chủ đề 5"
    ledger = json.loads((tmp_path / "series_memory_ledger_whiteboard.json").read_text(encoding="utf-8"))
    assert ledger["last_episode_num"] == 5
    assert not (tmp_path / "series_memory_ledger.json").exists()


def test_cancelled_series_reports_failure(tmp_path):
    ok, paths, meta = svc.run_museai_multi_episode_series_pipeline(
        total_episodes=2, work_dir=str(tmp_path), output_dir=str(tmp_path), is_cancelled_callback=lambda: True)
    assert not ok and paths == [] and "bỏ qua" in meta["error"]


def test_series_passes_voice_cast_to_next_episode_and_saves_resume_state(tmp_path, monkeypatch):
    from src.voice_casting import VoiceCaster
    monkeypatch.setattr(svc, "TEMP_DIR", tmp_path)
    casts = []
    def episode(**kwargs):
        caster = VoiceCaster(kwargs["vietnamese_voice"], kwargs["initial_voice_casting"])
        names = ["Bin", "Nam"] if kwargs["episode_num"] == 1 else ["Nam", "Bin"]
        casts.append({name: caster.voice_for("character_1", name) for name in names})
        return True, str(tmp_path / f"episode_{kwargs['episode_num']}.mp4"), {"story": {
            "scenes": [{"voice_casting": caster.assignments()}], "episode_learning_summary": "Lời chào",
            "next_episode_topic": "Làm quen"}}
    monkeypatch.setattr(svc, "run_museai_script_to_google_flow_3d_pipeline", episode)
    ok, _, meta = svc.run_museai_multi_episode_series_pipeline(total_episodes=2,
        work_dir=str(tmp_path / "work"), output_dir=str(tmp_path), vietnamese_voice="vieneu-v3:Mai Anh")
    assert ok and casts[0] == casts[1]
    ledger = json.loads((tmp_path / "series_memory_ledger.json").read_text(encoding="utf-8"))
    assert ledger["voice_casting"] == meta["voice_casting"]
    assert ledger["vietnamese_voice"] == "vieneu-v3:Mai Anh"
    ok, _, _ = svc.run_museai_multi_episode_series_pipeline(total_episodes=1, start_episode_num=3,
        work_dir=str(tmp_path / "resumed"), output_dir=str(tmp_path),
        initial_voice_casting=ledger["voice_casting"], vietnamese_voice=ledger["vietnamese_voice"])
    assert ok and casts[2] == casts[0]


def test_renderer_rejects_bad_duration_and_honors_cancellation(tmp_path):
    ok, _ = board.render_whiteboard_scene_video(story()["scenes"][0], str(tmp_path / "bad.mp4"), float("nan"))
    assert not ok
    ok, error = board.render_whiteboard_scene_video(story()["scenes"][0], str(tmp_path / "cancel.mp4"), 1,
                                                    size=(160, 90), is_cancelled_callback=lambda: True)
    assert not ok and "bỏ qua" in error


def test_real_tts_adapter_does_not_append_fictional_dialogue(tmp_path, monkeypatch):
    from src import tts_service
    captured = []
    def multivoice(lines, output, **kwargs):
        assert kwargs["strict_language"] is True
        captured.extend(lines)
        Path(output).write_bytes(b"a" * 1200)
        return True, output
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", multivoice)
    monkeypatch.setattr(tts_service, "get_audio_duration", lambda _: 1.)
    scene = dict(story()["scenes"][0], media_type="whiteboard")
    ok, error = svc.synthesize_museai_scenes_interactive_tts([scene], str(tmp_path))
    assert ok, error
    assert [line[0] for line in captured] == ["Lãi sinh thêm lãi."]


def test_full_whiteboard_pipeline_outputs_1080p_audio_and_subtitles(tmp_path, monkeypatch):
    from src import video_compiler
    monkeypatch.setattr(video_compiler, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(video_compiler, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_3d_script_via_museai",
                        lambda self, **kw: (True, story()))
    def tts(scenes, work_dir, language):
        for sc in scenes:
            audio = str(Path(work_dir) / "test.wav")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=0.8", audio], check=True, capture_output=True)
            sc.update(audio_path=audio, audio_duration=.8)
        return True, "ok"
    monkeypatch.setattr(svc, "synthesize_museai_scenes_interactive_tts", tts)
    ok, path, meta = svc.run_museai_script_to_google_flow_3d_pipeline(
        visual_mode="whiteboard", orientation="horizontal", work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "out"))
    assert ok, path
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                           capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (video["width"], video["height"]) == (1920, 1080)
    assert abs(float(audio["duration"]) - float(video["duration"])) < .15
    assert abs(float(info["format"]["duration"]) - .8) < .15
    assert meta["story"]["scenes"][0]["subtitle_cues"]
    assert any("Lãi" in p.read_text(encoding="utf-8-sig") for p in tmp_path.glob("*.srt"))


def test_museai_ui_can_select_whiteboard():
    from streamlit.testing.v1 import AppTest
    studio_root = str(Path(__file__).resolve().parents[1])
    app = AppTest.from_string(f"""import sys
sys.path.insert(0, {studio_root!r})
from src.app_museai import run_museai_ui
run_museai_ui()
""").run(timeout=30)
    assert not app.exception
    radio = next(r for r in app.radio if any("Người que" in opt for opt in r.options))
    option = next(opt for opt in radio.options if "Người que" in opt)
    radio.set_value(option).run(timeout=30)
    assert not app.exception
    assert any(r.value == option for r in app.radio)
    language = next(s for s in app.selectbox if any("giảng Việt" in value for value in s.options))
    lesson_option = next(value for value in language.options if "giảng Việt" in value)
    language.set_value(lesson_option).run(timeout=30)
    assert not app.exception
    assert any(s.value == lesson_option for s in app.selectbox)
    ai_option = next(c for c in app.checkbox if "AI tự tạo minh họa" in c.label)
    assert ai_option.value is True


def test_compiler_fps_patch_survives_repeated_ui_reload(monkeypatch, tmp_path):
    import importlib
    import moviepy.video.VideoClip as moviepy_video
    from src import video_compiler
    calls = []
    def fake_writer(clip, filename, fps, **kw):
        calls.append(fps)
    monkeypatch.setattr(moviepy_video, "ffmpeg_write_video", fake_writer)
    importlib.reload(video_compiler)
    importlib.reload(video_compiler)
    clip = type("Clip", (), {"fps": 24})()
    moviepy_video.ffmpeg_write_video(clip, str(tmp_path / "out.mp4"), None)
    assert calls == [24]
