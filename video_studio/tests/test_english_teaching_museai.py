"""Test language-isolated English lesson voices, continuity, and illustration choice.

Prevents Vietnamese explanations from being synthesized with an English voice,
English samples from being synthesized with a Vietnamese voice, and unsafe fallback.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import museai_3d_service as svc
from src.english_teaching import build_english_lesson_segments, tagged_language_segments
from src.english_teaching import prepare_whiteboard_lesson
from src.museai_story_modes import add_learning_bridges


def lesson_scene():
    return {"scene_num": 1, "content_mode": "english_teaching_vi", "speech_segments": [
        {"language": "vi", "text": "Để chào buổi sáng, bạn nói:"},
        {"language": "en", "text": "Good morning!"},
        {"language": "vi", "text": "Nghĩa là chào buổi sáng."}],
        "whiteboard_items": [{"type": "text", "text": "Good morning!", "x": .5, "y": .2},
                             {"type": "illustration", "asset": "clock", "x": .5, "y": .5}]}


def test_each_language_gets_its_own_voice_without_adding_text():
    sc = lesson_scene()
    lines = svc.build_scene_dialogue_segments(sc, language="vi_en")
    assert [s["language"] for s in lines] == ["vi", "en", "vi"]
    assert [s["voice_spec"].split("-")[0] for s in lines] == ["vi", "en", "vi"]
    assert "Good morning!" in sc["narration"]
    assert len(lines) == 3
    assert svc.build_scene_dialogue_segments(sc, language="vi_en") == lines


def test_json_parser_and_whiteboard_enrichment_keep_english_voice_labels():
    story = {"content_mode": "english_teaching_vi", "visual_mode": "whiteboard", "scenes": [lesson_scene()]}
    parsed = svc.parse_museai_story_json(json.dumps(story))
    result = svc.MuseAIFlowHybridController()._enrich_scenes_with_3d_prompts(parsed, "vertical", "whiteboard")
    assert result["scenes"][0]["speech_segments"][1]["language"] == "en"
    assert result["scenes"][0]["dialogue_lines"][1]["voice_spec"].startswith("en-")
    assert result["scenes"][0]["whiteboard_items"][1]["asset"] == "clock"


def test_split_3d_shots_does_not_repeat_the_entire_bilingual_scene():
    sc = lesson_scene()
    svc.build_scene_dialogue_segments(sc, language="vi_en")
    shots = svc.expand_scenes_to_match_story_beats([sc], language="vi_en", max_words_per_shot=6)
    rebuilt = [seg["text"] for shot in shots for seg in svc.build_scene_dialogue_segments(shot, language="vi_en")]
    assert rebuilt == [s["text"] for s in lesson_scene()["speech_segments"]]


def test_lesson_voice_adapter_passes_exact_vi_en_vi_sequence(tmp_path, monkeypatch):
    from src import tts_service
    captured = []
    def generate(lines, output, **kwargs):
        assert kwargs["strict_language"] is True
        captured.extend(lines)
        Path(output).write_bytes(b"a" * 1300)
        return True, output
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", generate)
    monkeypatch.setattr(tts_service, "get_audio_duration", lambda _: 3.2)
    sc = lesson_scene()
    ok, error = svc.synthesize_museai_scenes_interactive_tts([sc], str(tmp_path), "vi_en")
    assert ok, error
    assert [v.split("-")[0] for _, v, _ in captured] == ["vi", "en", "vi"]
    assert captured[1][0] == "Good morning!" and captured[1][2] == "-8%"
    assert sc["audio_duration"] == 3.2


def test_bilingual_tts_failure_never_falls_back_to_one_voice(tmp_path, monkeypatch):
    from src import tts_service
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", lambda *a, **kw: (False, "English voice unavailable"))
    def forbidden(*a, **kw):
        pytest.fail("Must not read the bilingual lesson with one fallback voice")
    monkeypatch.setattr(tts_service, "generate_tts", forbidden)
    ok, error = svc.synthesize_museai_scenes_interactive_tts([lesson_scene()], str(tmp_path), "vi_en")
    assert not ok and "English voice unavailable" in error


def test_lesson_requires_explicit_languages_and_does_not_guess_ascii_vietnamese():
    with pytest.raises(ValueError, match="speech_segments"):
        build_english_lesson_segments({"narration": "Xin chao. Good morning!"}, "vi-VN-HoaiMyNeural")
    with pytest.raises(ValueError, match="vi hoặc en"):
        build_english_lesson_segments({"speech_segments": [{"language": "fr", "text": "Bonjour"}]}, "vi-VN-HoaiMyNeural")


def test_series_bridges_are_vietnamese_and_can_pronounce_tagged_examples_in_english():
    story = {"content_mode": "english_teaching_vi", "scenes": [lesson_scene()],
             "next_episode_topic": "Cách dùng [en]Good afternoon[/en]"}
    result = add_learning_bridges(story, 2, 3, "vi_en", "Cách chào buổi sáng")
    intro = svc.build_scene_dialogue_segments(result["scenes"][0], language="vi_en")
    outro = svc.build_scene_dialogue_segments(result["scenes"][-1], language="vi_en")
    assert intro[0]["text"].startswith("Ở tập trước") and intro[0]["language"] == "vi"
    assert outro[0]["language"] == "vi" and outro[1]["text"] == "Good afternoon"
    assert outro[1]["voice_spec"].startswith("en-")


def test_bilingual_prompt_contract_for_whiteboard_and_3d():
    for mode in ("whiteboard", "video_3d"):
        prompt = svc.build_museai_story_script_prompt(topic="Chào hỏi", language="vi_en", visual_mode=mode)
        assert 'content_mode="english_teaching_vi"' in prompt
        assert "speech_segments" in prompt
        assert "Keep each segment monolingual" in prompt


def test_whiteboard_has_spoken_context_before_question_and_english():
    sc = lesson_scene()
    sc["lesson_context"] = "Bạn gặp người bạn mới vào buổi sáng và muốn mở lời thân thiện."
    original = {"content_mode": "english_teaching_vi", "scenes": [sc]}
    prepared = prepare_whiteboard_lesson(original)
    assert prepare_whiteboard_lesson(prepared) == prepared
    assert original["scenes"][0]["speech_segments"][0]["text"] != sc["lesson_context"]
    segments = svc.build_scene_dialogue_segments(prepared["scenes"][0], language="vi_en")
    assert segments[0]["text"] == sc["lesson_context"] and segments[0]["language"] == "vi"
    assert segments[1]["text"] == sc["speech_segments"][0]["text"]
    assert segments[2]["text"] == "Good morning!" and segments[2]["voice_spec"].startswith("en-")
    assert prepared["scenes"][0]["narration"].startswith(sc["lesson_context"])
    rebuilt = prepare_whiteboard_lesson(prepared)
    assert sum(s.get("lesson_part") == "context" for s in rebuilt["scenes"][0]["speech_segments"]) == 1
    legacy = deepcopy(prepared)
    legacy["scenes"][0]["speech_segments"][0].pop("lesson_part")
    assert len(prepare_whiteboard_lesson(legacy)["scenes"][0]["speech_segments"]) == 4
    prompt = svc.build_museai_story_script_prompt(topic="Chào hỏi", language="vi_en", visual_mode="whiteboard")
    assert "lesson_context" in prompt and "CONTEXT BEFORE PHRASES" in prompt
    assert 'publishing={"hashtags"' in prompt


def test_missing_context_cannot_silently_produce_flashcards():
    with pytest.raises(ValueError, match="thiếu lesson_context"):
        prepare_whiteboard_lesson({"scenes": [lesson_scene()]})
    sc = lesson_scene()
    sc["lesson_context"] = "Hãy nói [en]Hello[/en]"
    with pytest.raises(ValueError, match="chỉ gồm lời dẫn tiếng Việt"):
        prepare_whiteboard_lesson({"scenes": [sc]})


def test_production_whiteboard_routes_the_context_into_real_speech_order(tmp_path, monkeypatch):
    from src import whiteboard_video
    sc = lesson_scene()
    sc["lesson_context"] = "Bạn gặp một người bạn mới và muốn bắt chuyện vào buổi sáng."
    story = {"story_title": "Chào hỏi", "content_mode": "english_teaching_vi", "scenes": [sc]}
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_3d_script_via_museai", lambda *a, **kw: (True, deepcopy(story)))
    spoken = []
    def tts(scenes, work, language):
        spoken.extend(svc.build_scene_dialogue_segments(scenes[0], language=language))
        return True, "ok"
    monkeypatch.setattr(svc, "synthesize_museai_scenes_interactive_tts", tts)
    monkeypatch.setattr(whiteboard_video, "render_whiteboard_story_scenes", lambda scenes, *a, **kw: (
        scenes[0].update(video_path=str(tmp_path / "frame.mp4")) or True, "ok"))
    def merge(scenes, work, output, *a, **kw):
        Path(output).write_bytes(b"output")
        return True, output
    monkeypatch.setattr(svc, "merge_flow_3d_scenes_into_final_movie", merge)
    ok, output, meta = svc.run_museai_script_to_google_flow_3d_pipeline(
        topic="Chào hỏi", language="vi_en", visual_mode="whiteboard", whiteboard_ai_enabled=False,
        work_dir=str(tmp_path / "work"), output_dir=str(tmp_path))
    assert ok, output
    assert spoken[0]["text"] == sc["lesson_context"]
    assert [s["language"] for s in spoken] == ["vi", "vi", "en", "vi"]
    saved = json.loads(Path(output).with_suffix(".json").read_text(encoding="utf-8"))
    assert saved["language"] == "vi_en"
    assert saved["story"]["scenes"][0]["narration"].startswith(sc["lesson_context"])


def test_added_illustrations_are_available_to_museai_without_using_the_hand_as_art(tmp_path, monkeypatch):
    from src import whiteboard_illustrations as library
    monkeypatch.setattr(library, "ASSET_DIR", tmp_path)
    for name in ("school.png", "apple.webp", "hand_photo_v1.png", "study_desk_v1.png", "notes.txt"):
        (tmp_path / name).write_bytes(b"test")
    assert library.custom_illustration_files() == ["apple.webp", "school.png"]
    prompt = svc.build_museai_story_script_prompt(language="vi_en", visual_mode="whiteboard")
    assert "apple.webp" in prompt and "school.png" in prompt
    assert "hand_photo_v1.png" not in prompt


def test_tagged_english_does_not_leak_markup_into_the_spoken_text():
    segments = tagged_language_segments("Mời bạn đọc: [en]Hello[/en]. Nghĩa là xin chào.")
    assert [s["language"] for s in segments] == ["vi", "en", "vi"]
    assert segments[1]["text"] == "Hello"
    with pytest.raises(ValueError):
        tagged_language_segments("Thiếu thẻ: [en]Hello")


def test_short_english_never_receives_a_vietnamese_padding_prefix(tmp_path, monkeypatch):
    from src import tts_service
    calls = []
    def failure(text, output_path, voice, rate, **kwargs):
        calls.append((text, voice, kwargs))
        return False, "No audio was received"
    monkeypatch.setattr(tts_service, "_run_edge_tts_direct", failure)
    monkeypatch.setattr(tts_service.time, "sleep", lambda _: None)
    ok, _ = tts_service.generate_tts("Hello", str(tmp_path / "a.mp3"), voice="en-US-JennyNeural", strict_language=True)
    assert not ok and calls
    assert all(text == "Hello" and voice.startswith("en-") and kw["strict_language"] for text, voice, kw in calls)


def test_lesson_does_not_substitute_test_tones_when_speech_service_is_missing(tmp_path, monkeypatch):
    from src import tts_service
    monkeypatch.setitem(sys.modules, "edge_tts", None)
    def forbidden(*args):
        pytest.fail("A pronunciation lesson must never use a synthetic test tone as speech")
    monkeypatch.setattr(tts_service, "_synthesize_offline_speech_audio_ffmpeg", forbidden)
    ok, _ = tts_service._run_edge_tts_direct("Hello", str(tmp_path / "a.mp3"), "en-US-JennyNeural", "+0%", strict_language=True)
    assert not ok


def test_english_subtitles_start_at_the_measured_english_audio_boundary(tmp_path, monkeypatch):
    from src import tts_service
    from src.batch_producer import build_exact_tts_timestamps
    def synthesize(lines, output, **kwargs):
        kwargs["segment_timing_callback"]([
            {"text": text, "voice": voice, "duration": duration}
            for (text, voice, _), duration in zip(lines, (1.8, 1., 1.5))])
        Path(output).write_bytes(b"a" * 1300)
        return True, output
    monkeypatch.setattr(tts_service, "generate_multivoice_tts", synthesize)
    monkeypatch.setattr(tts_service, "get_audio_duration", lambda _: 4.3)
    scene = lesson_scene()
    ok, error = svc.synthesize_museai_scenes_interactive_tts([scene], str(tmp_path), "vi_en")
    assert ok, error
    cues = build_exact_tts_timestamps([scene])
    english = next(cue for cue in cues if cue["word"] == "Good")
    assert english["start"] == 1.8
    assert scene["tts_segment_timings"][1]["end"] == 2.8
    # Cache restores these boundaries rather than reverting to whole-scene estimates.
    cached = lesson_scene()
    ok, _ = svc.synthesize_museai_scenes_interactive_tts([cached], str(tmp_path), "vi_en")
    assert ok and cached["tts_segment_timings"] == scene["tts_segment_timings"]
