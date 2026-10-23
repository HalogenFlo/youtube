import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vieneu_service import PRESET_VOICES, VOICE_PREFIX  # noqa: E402
from src.voice_casting import (  # noqa: E402
    VIENEU_VOICE_GENDER,
    VoiceCaster,
    apply_vieneu_casting,
    emotion_rate,
    recover_voice_casting,
)

NARRATOR = VOICE_PREFIX + "Mai Anh"


def test_gender_table_covers_exactly_the_vieneu_presets():
    assert set(VIENEU_VOICE_GENDER) == set(PRESET_VOICES)
    assert set(VIENEU_VOICE_GENDER.values()) == {"m", "f"}


def test_narrator_keeps_selected_voice_and_characters_never_reuse_it():
    caster = VoiceCaster(NARRATOR)
    assert caster.voice_for("narrator", "") == NARRATOR
    voices = [
        caster.voice_for("character_female", "Cô Lan"),
        caster.voice_for("character_1", "Bin"),
        caster.voice_for("character_2", "Ông Tư"),
    ]
    assert NARRATOR not in voices


def test_different_characters_get_different_voices_and_same_character_is_stable():
    caster = VoiceCaster(NARRATOR)
    bin_voice = caster.voice_for("character_1", "Bin")
    tu_voice = caster.voice_for("character_2", "Ông Tư")
    assert bin_voice != tu_voice
    assert caster.voice_for("character_1", "Bin") == bin_voice
    assert caster.voice_for("character_1", "bin") == bin_voice  # không phân biệt hoa thường


def test_gender_follows_role():
    caster = VoiceCaster(VOICE_PREFIX + "Thiện Minh")
    f_voice = caster.voice_for("character_female", "Cô Lan")
    m_voice = caster.voice_for("character_1", "Bin")
    assert VIENEU_VOICE_GENDER[f_voice[len(VOICE_PREFIX):]] == "f"
    assert VIENEU_VOICE_GENDER[m_voice[len(VOICE_PREFIX):]] == "m"


def test_pool_exhaustion_still_returns_valid_voices():
    caster = VoiceCaster(NARRATOR)
    got = {caster.voice_for("character_1", f"Nam{i}") for i in range(8)}
    assert got and all(v.startswith(VOICE_PREFIX) for v in got)
    assert all(v[len(VOICE_PREFIX):] in PRESET_VOICES for v in got)


def test_emotion_rate_is_percent_string_within_vieneu_limits():
    assert emotion_rate("neutral") == "+0%"
    assert emotion_rate("") == "+0%"
    assert emotion_rate("không biết") == "+0%"
    assert int(emotion_rate("sad").rstrip("%")) < 0 < int(emotion_rate("excited").rstrip("%"))
    for e in ("happy", "excited", "surprised", "angry", "sad", "thinking"):
        assert -30 <= int(emotion_rate(e).rstrip("%")) <= 30


def test_apply_casting_changes_only_vietnamese_segments():
    segs = [
        {"speaker": "narrator", "text": "Chào các bạn", "voice_spec": "vi-VN-HoaiMyNeural|story_warm", "rate": "+0%", "language": "vi"},
        {"speaker": "character_1", "character_name": "Bin", "text": "Wow!", "voice_spec": "vi-VN-NamMinhNeural|char_boy_bright",
         "rate": "+0%", "language": "vi", "emotion": "surprised"},
        {"speaker": "narrator", "text": "Good morning", "voice_spec": "en-US-JennyNeural", "rate": "+0%", "language": "en"},
    ]
    out = apply_vieneu_casting(segs, VoiceCaster(NARRATOR))
    assert out[0]["voice_spec"] == NARRATOR
    assert out[1]["voice_spec"].startswith(VOICE_PREFIX) and out[1]["voice_spec"] != NARRATOR
    assert int(out[1]["rate"].rstrip("%")) > 0  # ngạc nhiên -> nhanh hơn
    assert out[2]["voice_spec"] == "en-US-JennyNeural" and out[2]["rate"] == "+0%"
    assert segs[0]["voice_spec"] == "vi-VN-HoaiMyNeural|story_warm"  # không sửa đổi đầu vào


def test_saved_cast_survives_reversed_order_and_new_characters():
    first = VoiceCaster(NARRATOR)
    voices = {name: first.voice_for("character_1", name) for name in ("Bin", "Nam")}
    resumed = VoiceCaster(NARRATOR, first.assignments())
    assert {name: resumed.voice_for("character_1", name) for name in ("Nam", "Bin")} == voices
    snapshot = resumed.assignments()
    snapshot.clear()
    assert resumed.voice_for("character_1", "Bin") == voices["Bin"]
    assert resumed.voice_for("character_female", "Lan") != NARRATOR


def test_old_metadata_cast_can_be_recovered_without_reading_narrator_or_english():
    old = [{"dialogue_lines": [
        {"speaker": "character_1", "character_name": "Bin", "voice_spec": "vieneu-v3:Thiện Minh"},
        {"speaker": "narrator", "voice_spec": NARRATOR},
        {"speaker": "character_2", "character_name": "Sam", "voice_spec": "en-US-GuyNeural"}]}]
    restored = VoiceCaster(NARRATOR, recover_voice_casting(old))
    assert restored.voice_for("character_1", "Bin") == "vieneu-v3:Thiện Minh"
