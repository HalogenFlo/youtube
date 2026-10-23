"""Run local VieNeu speech in an isolated environment without changing studio dependencies.

Source/API: https://github.com/pnnbao97/VieNeu-TTS (SDK 3.8.3, v3 Turbo ONNX).
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile

STUDIO = Path(__file__).resolve().parents[1]
VOICE_PREFIX = "vieneu-v3:"
PRESET_VOICES = ("Mai Anh", "Hải Đăng", "Trúc Ly", "Thiện Minh", "Thùy Dung", "Ngọc Huyền")


def runtime_python():
    root = STUDIO / "runtimes" / "vieneu"
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def is_vieneu_voice(voice):
    return str(voice).startswith(VOICE_PREFIX)


def generate_vieneu_batch(requests):
    """Synthesize (text, voice, rate, output) together; fail explicitly, never swap engines."""
    if not requests:
        return True, ""
    python = runtime_python()
    if not python.is_file():
        return False, "Chưa cài VieNeu. Chạy video_studio/scripts/setup_vieneu.ps1 trước."
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "VieNeu cần FFmpeg để xuất giọng đọc MP3."
    try:
        with tempfile.TemporaryDirectory(prefix="vieneu_") as temporary:
            jobs = []
            for index, (text, voice, rate, output) in enumerate(requests):
                preset = str(voice)[len(VOICE_PREFIX):]
                if not is_vieneu_voice(voice) or not preset.strip():
                    raise ValueError("Giọng VieNeu không hợp lệ.")
                if not re.fullmatch(r"[+-]?\d+%", str(rate)):
                    raise ValueError("Tốc độ VieNeu phải là phần trăm, ví dụ +0% hoặc -8%.")
                speed = 1 + int(str(rate).rstrip("%")) / 100
                if not .5 <= speed <= 2:
                    raise ValueError("Tốc độ VieNeu phải nằm trong khoảng -50% đến +100%.")
                jobs.append({"text": text, "voice": preset, "wav": str(Path(temporary) / f"{index}.wav"),
                             "output": str(output), "speed": speed})
            manifest = Path(temporary) / "jobs.json"
            manifest.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
            environment = dict(os.environ, PYTHONUTF8="1", HF_HOME=str(STUDIO / "models" / "vieneu"),
                               HF_HUB_DISABLE_TELEMETRY="1")
            result = subprocess.run([str(python), str(STUDIO / "scripts" / "vieneu_worker.py"), str(manifest)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    env=environment, timeout=1800)
            if result.returncode:
                return False, f"VieNeu không tạo được giọng đọc: {(result.stderr or result.stdout)[-2000:]}"
            for job in jobs:
                Path(job["output"]).parent.mkdir(parents=True, exist_ok=True)
                encoded = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", job["wav"],
                                          "-af", f"atempo={job['speed']}", "-codec:a", "libmp3lame",
                                          "-b:a", "192k", job["output"]], capture_output=True, timeout=120)
                if encoded.returncode or not Path(job["output"]).is_file() or Path(job["output"]).stat().st_size <= 1000:
                    return False, "Không thể chuyển âm thanh VieNeu sang MP3."
        return True, str(requests[-1][3])
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"Lỗi VieNeu: {exc}"
