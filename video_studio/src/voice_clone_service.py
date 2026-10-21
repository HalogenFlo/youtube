"""Clone giọng local bằng Coqui XTTS-v2 (chỉ tải model khi được sử dụng)."""

from __future__ import annotations

import importlib.util
import os
import threading
from typing import Optional, Tuple


XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_LANGUAGES = {"en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"}
_MODEL = None
_MODEL_LOCK = threading.Lock()


def voice_clone_available() -> bool:
    return importlib.util.find_spec("TTS") is not None


def _get_model():
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            import torch
            from TTS.api import TTS

            device = "cuda" if torch.cuda.is_available() else "cpu"
            _MODEL = TTS(XTTS_MODEL).to(device)
        return _MODEL


def generate_cloned_tts(
    text: str,
    output_path: str,
    reference_audio: str,
    language: str,
) -> Tuple[bool, str]:
    """Sinh WAV bằng giọng tham chiếu, không gửi audio ra dịch vụ bên ngoài."""
    if not text.strip():
        return False, "Nội dung lồng tiếng đang trống."
    if language not in XTTS_LANGUAGES:
        return False, (
            f"XTTS-v2 chưa hỗ trợ ngôn ngữ '{language}'. "
            "Tiếng Việt nên dùng Edge TTS hoặc engine OpenVoice/Fish Speech riêng."
        )
    if not reference_audio or not os.path.exists(reference_audio):
        return False, "Không tìm thấy file giọng mẫu."
    if not voice_clone_available():
        return False, "Chưa cài coqui-tts. Hãy chạy: pip install coqui-tts==0.27.5"

    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        model = _get_model()
        model.tts_to_file(
            text=text,
            speaker_wav=reference_audio,
            language=language,
            file_path=output_path,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True, output_path
        return False, "XTTS chạy xong nhưng không tạo được file âm thanh."
    except Exception as exc:
        return False, f"Lỗi clone giọng local: {exc}"
