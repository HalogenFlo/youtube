import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.museai_3d_service import (  # noqa: E402
    _resolve_speaker_role_and_voice,
    build_scene_dialogue_segments,
)
from src.tts_service import resolve_voice_and_prosody  # noqa: E402


def _num(s: str) -> int:
    return int(s.replace("%", "").replace("Hz", "").replace("+", ""))


def test_emotion_modifies_rate_and_pitch_relative_to_neutral():
    base = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_boy_bright")
    happy = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_boy_bright|happy")
    sad = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_boy_bright|sad")
    surprised = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_boy_bright|surprised")
    assert happy[0] == sad[0] == base[0] == "vi-VN-NamMinhNeural"
    assert _num(happy[1]) > _num(base[1]) > _num(sad[1])
    assert _num(happy[2]) > _num(base[2]) > _num(sad[2])
    assert _num(surprised[2]) > _num(happy[2])


def test_unknown_or_neutral_emotion_equals_base():
    base = resolve_voice_and_prosody("vi-VN-HoaiMyNeural|char_female_bright")
    assert resolve_voice_and_prosody("vi-VN-HoaiMyNeural|char_female_bright|neutral") == base
    assert resolve_voice_and_prosody("vi-VN-HoaiMyNeural|char_female_bright|khong_biet") == base


def test_rate_pitch_have_valid_edge_tts_format():
    _, rate, pitch, _ = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_hero_deep|angry")
    assert rate[0] in "+-" and rate.endswith("%")
    assert pitch[0] in "+-" and pitch.endswith("Hz")


def test_same_character_name_always_gets_same_voice_and_names_can_differ():
    a1 = _resolve_speaker_role_and_voice("character_1", "Bin")[2]
    a2 = _resolve_speaker_role_and_voice("character_1", "Bin")[2]
    assert a1 == a2
    voices = {_resolve_speaker_role_and_voice("character_1", n)[2] for n in ("Bin", "Tí", "Nam", "Khoa", "Long", "Hùng")}
    assert len(voices) >= 2  # nhiều nhân vật nam -> không bị dùng chung đúng 1 giọng


def test_segments_carry_line_emotion_into_voice_spec():
    scene = {
        "scene_num": 2,
        "dialogue_lines": [
            {"speaker": "character_1", "character_name": "Bin", "text": "Wow, thật không thể tin được!", "emotion": "surprised"},
            {"speaker": "narrator", "text": "Bin rất ngạc nhiên.", "emotion": "thinking"},
        ],
    }
    segs = build_scene_dialogue_segments(scene, language="vi", total_scenes=4, allow_synthetic_filler=False)
    assert segs[0]["voice_spec"].endswith("|surprised")
    assert segs[1]["voice_spec"].endswith("|thinking")
