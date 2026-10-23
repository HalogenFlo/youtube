"""Phân vai giọng VieNeu: mỗi nhân vật một giọng riêng, cảm xúc câu thoại chỉnh tốc độ đọc."""
from __future__ import annotations

from typing import Any, Dict, List

from src.vieneu_service import PRESET_VOICES, VOICE_PREFIX

# Giới tính từng giọng preset của VieNeu v3 (dùng để chọn giọng nam/nữ đúng vai).
VIENEU_VOICE_GENDER: Dict[str, str] = {
    "Mai Anh": "f",
    "Hải Đăng": "m",
    "Trúc Ly": "f",
    "Thiện Minh": "m",
    "Thùy Dung": "f",
    "Ngọc Huyền": "f",
}

# Tốc độ đọc (%) theo cảm xúc; VieNeu chỉ điều chỉnh được tốc độ nên giữ trong khoảng tự nhiên.
EMOTION_RATE_PCT: Dict[str, int] = {
    "happy": 6,
    "excited": 10,
    "surprised": 6,
    "angry": 8,
    "sad": -10,
    "thinking": -6,
    "neutral": 0,
}


def emotion_rate(emotion: str) -> str:
    return f"{EMOTION_RATE_PCT.get(str(emotion or '').strip().lower(), 0):+d}%"


def recover_voice_casting(scenes: List[Dict[str, Any]]) -> Dict[str, str]:
    """Recover the actual recorded cast from old episode metadata before continuing."""
    recovered = {}
    for scene in scenes:
        for segment in scene.get("dialogue_lines") or []:
            role = str(segment.get("speaker") or "").strip().lower()
            voice = str(segment.get("voice_spec") or "")
            if role == "narrator" or not voice.startswith(VOICE_PREFIX):
                continue
            name = str(segment.get("character_name") or role).strip().lower()
            gender = "f" if role == "character_female" else "m"
            recovered.setdefault(f"{gender}:{name}", voice[len(VOICE_PREFIX):])
    return recovered


class VoiceCaster:
    """Keep a saved character cast across scenes, episodes and resumed series."""

    def __init__(self, narrator_voice: str, assignments: Dict[str, str] | None = None):
        self.narrator_voice = narrator_voice
        narrator_name = narrator_voice[len(VOICE_PREFIX):] if narrator_voice.startswith(VOICE_PREFIX) else ""
        self._pools: Dict[str, List[str]] = {
            gender: [v for v in PRESET_VOICES if VIENEU_VOICE_GENDER.get(v) == gender and v != narrator_name]
            for gender in ("m", "f")
        }
        # Khi hết giọng cùng giới thì mượn giọng khác giới (vẫn khác giọng dẫn chuyện)
        self._fallback = [v for v in PRESET_VOICES if v != narrator_name]
        self._assigned: Dict[str, str] = {
            key: voice for key, voice in (assignments or {}).items()
            if isinstance(key, str) and key.startswith(("m:", "f:"))
            and voice in self._fallback
        }

    def voice_for(self, speaker_role: str, character_name: str) -> str:
        if str(speaker_role or "").strip().lower() == "narrator":
            return self.narrator_voice
        gender = "f" if str(speaker_role or "").strip().lower() == "character_female" else "m"
        key = f"{gender}:{str(character_name or speaker_role).strip().lower()}"
        if key not in self._assigned:
            pool = self._pools[gender] or self._fallback
            idx = sum(k.startswith(gender + ":") for k in self._assigned)
            self._assigned[key] = next((v for v in pool if v not in self._assigned.values()), pool[idx % len(pool)])
        return VOICE_PREFIX + self._assigned[key]

    def assignments(self) -> Dict[str, str]:
        return dict(self._assigned)


def apply_vieneu_casting(segments: List[Dict[str, Any]], caster: VoiceCaster) -> List[Dict[str, Any]]:
    """Trả về bản sao đoạn thoại với giọng VieNeu theo vai + tốc độ theo cảm xúc (chỉ đoạn tiếng Việt)."""
    out: List[Dict[str, Any]] = []
    for seg in segments:
        new = dict(seg)
        is_vi = seg.get("language") == "vi" or (
            "language" not in seg and str(seg.get("voice_spec", "")).startswith("vi-")
        )
        if is_vi:
            new["voice_spec"] = caster.voice_for(str(seg.get("speaker", "")), str(seg.get("character_name", "")))
            new["rate"] = emotion_rate(seg.get("emotion", ""))
        out.append(new)
    return out
