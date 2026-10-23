# Chức năng: Động cơ Hoạt hình 2D & Render Nhiều Frame HTML5 Canvas (HTML Multi-Frame Cartoon Animator).
# Cảm hứng từ các Agent Video Skill mã nguồn mở:
# - HyperFrames (nexu-io/html-video): HTML + CSS + Canvas/SVG -> Headless Chromium + FFmpeg -> MP4
# - Canvas Video Animation Skill (siegerts/skill-canvas-video): HTML5 Canvas deterministic frame stepping
# - HTML Animation to MP4 (AZR-Software-Solutions/html-animation-to-mp4): Virtual clock & frame batching
# Hỗ trợ:
# 1. Sinh file HTML5 Canvas tự chứa (scene_XXX_anim.html) với nhân vật hoạt hình 2D cử động, chớp mắt,
#    vẫy tay, nhép miệng 1:1 theo biên độ âm thanh giọng đọc (Audio-Reactive Lip-Sync), hạt ánh sáng parallax.
# 2. Chụp nhiều frame tất định (Deterministic Multi-Frame Batch Capture) qua Headless Chromium hoặc
#    Vector Frame Pipe tốc độ cao và đóng gói thành MP4 bằng FFmpeg.
# 3. Hỗ trợ chạy đa luồng (ThreadPoolExecutor) để sinh hàng loạt phân cảnh hoạt hình song song.

from __future__ import annotations

import base64
import concurrent.futures
import json
import math
import os
import subprocess
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.config import DEFAULT_FPS, FONT_PATH


_CHROMIUM_SEMAPHORE = threading.Semaphore(2)


def extract_audio_envelope(
    audio_path: str,
    fps: int = 30,
    duration: float = 5.0,
) -> List[float]:
    """
    Trích xuất biên độ âm lượng (RMS envelope [0.0..1.0]) theo từng khung hình (fps)
    từ file âm thanh giọng đọc thực tế để điều khiển nhép miệng nhân vật 2D (lip-sync)
    và hiệu ứng nhịp điệu hình ảnh.
    """
    total_frames = max(1, int(round(duration * fps)))
    if not audio_path or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        return [
            round(0.35 + 0.35 * abs(math.sin(i * 0.45)) * (1.0 if (i % 9) != 0 else 0.1), 3)
            for i in range(total_frames)
        ]

    sample_rate = 16000
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", audio_path,
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "s16le",
        "-",
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if res.returncode != 0 or not res.stdout:
            raise RuntimeError("Empty PCM")
        samples = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) == 0:
            raise RuntimeError("Zero samples")

        samples_per_frame = max(1, int(sample_rate / fps))
        env: List[float] = []
        for f_idx in range(total_frames):
            start = f_idx * samples_per_frame
            end = min(len(samples), start + samples_per_frame)
            if start >= len(samples):
                env.append(0.0)
            else:
                chunk = samples[start:end]
                rms = float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) > 0 else 0.0
                env.append(rms)

        max_rms = max(env) if env else 0.01
        if max_rms < 1e-4:
            max_rms = 1.0
        norm_env = [round(min(1.0, (v / max_rms) ** 0.75), 3) for v in env]
        return norm_env
    except Exception:
        return [
            round(0.35 + 0.35 * abs(math.sin(i * 0.45)) * (1.0 if (i % 9) != 0 else 0.1), 3)
            for i in range(total_frames)
        ]


def _detect_scene_visual_theme(prompt: str, narration: str, scene_idx: int) -> Dict[str, Any]:
    text = f"{prompt} {narration}".lower()
    if any(k in text for k in ["đom đóm", "firefly", "forest", "rừng", "đêm", "bamboo", "sinh học"]):
        return {
            "theme_id": "biolum_forest",
            "bg_top": "#071426",
            "bg_bottom": "#0f2e3d",
            "accent_primary": "#4ade80",
            "accent_secondary": "#facc15",
            "card_bg": "rgba(12, 34, 54, 0.86)",
            "particle_color": "#bef264",
            "badge_label": f"KHÁM PHÁ SINH HỌC • CẢNH {scene_idx}",
            "prop_type": "firefly",
        }
    if any(k in text for k in ["phòng thí nghiệm", "lab", "hóa học", "luciferin", "enzyme", "oxy", "tế bào", "y sinh", "khoa học"]):
        return {
            "theme_id": "science_lab",
            "bg_top": "#0d1b3e",
            "bg_bottom": "#1e1b4b",
            "accent_primary": "#38bdf8",
            "accent_secondary": "#a855f7",
            "card_bg": "rgba(17, 24, 60, 0.88)",
            "particle_color": "#7dd3fc",
            "badge_label": f"CƠ CHẾ PHÂN TỬ • CẢNH {scene_idx}",
            "prop_type": "molecule",
        }
    if any(k in text for k in ["vũ trụ", "sao hỏa", "bầu trời", "hành tinh", "space", "mặt trời"]):
        return {
            "theme_id": "cosmos",
            "bg_top": "#090a1f",
            "bg_bottom": "#1e1646",
            "accent_primary": "#f472b6",
            "accent_secondary": "#60a5fa",
            "card_bg": "rgba(20, 18, 52, 0.88)",
            "particle_color": "#fde047",
            "badge_label": f"VŨ TRỤ & VẬT LÝ • CẢNH {scene_idx}",
            "prop_type": "planet",
        }
    palettes = [
        ("#0b192c", "#1e3e62", "#38bdf8", "#facc15", "#bae6fd"),
        ("#122620", "#1f4538", "#4ade80", "#fbbf24", "#d9f99d"),
        ("#1f1638", "#34225c", "#c084fc", "#38bdf8", "#f5d0fe"),
    ]
    p = palettes[(scene_idx - 1) % len(palettes)]
    return {
        "theme_id": "cartoon_studio",
        "bg_top": p[0],
        "bg_bottom": p[1],
        "accent_primary": p[2],
        "accent_secondary": p[3],
        "card_bg": "rgba(15, 25, 45, 0.86)",
        "particle_color": p[4],
        "badge_label": f"HOẠT HÌNH 2D STUDIO • CẢNH {scene_idx}",
        "prop_type": "spark",
    }


def build_scene_cartoon_html(
    scene: Dict[str, Any],
    scene_idx: int = 1,
    total_scenes: int = 3,
    duration: float = 5.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    audio_envelope: Optional[List[float]] = None,
) -> str:
    """
    Tạo file HTML5 Canvas tự chứa (Self-contained Multi-Frame HTML Animation) cho một phân cảnh.
    Cung cấp cả:
    - window.renderFrameAt(t, duration)
    - window.renderFrameBatch(startFrame, count, fps, duration)
    - Chế độ chạy trực tiếp trên trình duyệt (Space: Play/Pause, R: Restart)
    """
    from src.cartoon_timeline import build_timeline_html
    return build_timeline_html(scene, scene_idx, duration, width, height, fps,
                               audio_envelope or extract_audio_envelope('', fps, duration))


def _render_cartoon_frames_python_pipe(
    scene: Dict[str, Any],
    output_mp4_path: str,
    audio_path: Optional[str],
    duration: float,
    width: int,
    height: int,
    fps: int,
    audio_envelope: List[float],
    scene_idx: int,
) -> Tuple[bool, str]:
    """
    Bộ dựng Vector 2D Cartoon đa frame trực tiếp qua ống dẫn FFmpeg (image2pipe) tốc độ cao:
    Vẽ nhân vật hoạt hình 2D nhép miệng theo audio_envelope, chớp mắt, hạt ánh sáng đom đóm,
    thẻ infographic và chuyển động camera mượt mà ở tốc độ ~60 FPS trên mọi môi trường.
    """
    from src.cartoon_timeline import frame_commands, render_image, scene_plan
    plan = scene_plan(scene, scene_idx)
    total_frames = max(1, int(round(duration * fps)))
    cmd = [
        "ffmpeg", "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
    ]
    if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        cmd.extend(["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k"])
    else:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"])

    cmd.extend([
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-crf", "19",
        "-movflags", "+faststart",
        "-shortest",
        output_mp4_path,
    ])

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for f_idx in range(total_frames):
            t = f_idx / float(fps)
            voice_amp = audio_envelope[f_idx] if f_idx < len(audio_envelope) else 0.35
            img = render_image(frame_commands(plan, t, duration, voice_amp), width, height)

            proc.stdin.write(img.tobytes())

        proc.stdin.close()
        proc.stdin = None
        _, stderr_bytes = proc.communicate(timeout=120)
        if proc.returncode != 0:
            return False, f"FFmpeg pipe error: {stderr_bytes.decode('utf-8', errors='replace')[-300:]}"
        return True, output_mp4_path
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        return False, f"Vector pipe render error: {e}"


def render_html_scene_to_video(
    scene: Dict[str, Any],
    output_mp4_path: str,
    html_out_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    duration: float = 5.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = DEFAULT_FPS,
    scene_idx: int = 1,
    total_scenes: int = 3,
    use_headless_chromium: bool = True,
    batch_size: int = 45,
) -> Tuple[bool, str, str]:
    """
    Sinh file HTML5 Canvas nhiều frame (`scene_XXX_anim.html`) VÀ kết xuất thành video `.mp4`
    có nhân vật cử động + nhép miệng theo âm thanh (`audio_path`).
    Trả về: (success, output_mp4_path_or_error, html_out_path)
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)
    if not html_out_path:
        base_no_ext = os.path.splitext(output_mp4_path)[0]
        html_out_path = f"{base_no_ext}.html"

    envelope = extract_audio_envelope(audio_path or "", fps=fps, duration=duration)
    html_code = build_scene_cartoon_html(
        scene=scene,
        scene_idx=scene_idx,
        total_scenes=total_scenes,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        audio_envelope=envelope,
    )
    with open(html_out_path, "w", encoding="utf-8") as f:
        f.write(html_code)

    from pathlib import Path
    lumi_enabled = (Path(__file__).resolve().parent.parent / "assets/characters/lumi/character.svg").exists()
    use_headless_chromium = use_headless_chromium or lumi_enabled

    if use_headless_chromium:
        driver = None
        browser = None
        playwright = None
        proc = None
        with _CHROMIUM_SEMAPHORE:
            try:
                from playwright.sync_api import sync_playwright
                playwright = sync_playwright().start()
                browser = playwright.chromium.launch(channel="chrome", headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"])
                driver = browser.new_page(viewport={"width": width, "height": height})
                driver.set_content(html_code, wait_until="load")

                total_frames = max(1, int(round(duration * fps)))
                cmd = [
                    "ffmpeg", "-y",
                    "-loglevel", "error",
                    "-f", "image2pipe",
                    "-vcodec", "mjpeg",
                    "-r", str(fps),
                    "-i", "-",
                ]
                if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    cmd.extend(["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k"])
                else:
                    cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"])

                cmd.extend([
                    "-t", f"{duration:.3f}",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "ultrafast",
                    "-crf", "19",
                    "-movflags", "+faststart",
                    "-shortest",
                    output_mp4_path,
                ])

                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                assert proc.stdin is not None

                for start_f in range(0, total_frames, batch_size):
                    count = min(batch_size, total_frames - start_f)
                    b64_list: List[str] = driver.evaluate(
                        f"window.renderFrameBatch({start_f}, {count}, {fps}, {duration:.4f})"
                    )
                    for b64_jpg in b64_list:
                        proc.stdin.write(base64.b64decode(b64_jpg))

                proc.stdin.close()
                proc.stdin = None
                _, stderr_bytes = proc.communicate(timeout=120)
                if proc.returncode == 0 and os.path.exists(output_mp4_path) and os.path.getsize(output_mp4_path) > 0:
                    # Also save a poster PNG frame for storyboard preview
                    poster_png = os.path.splitext(output_mp4_path)[0] + "_poster.png"
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", output_mp4_path, "-ss", f"{min(1.0, duration * 0.3):.2f}", "-frames:v", "1", poster_png],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    return True, output_mp4_path, html_out_path
            except Exception as e:
                print(f"[HTMLAnimator] Headless Chromium chuyển sang Vector Pipe tốc độ cao ({e})")
            finally:
                if driver is not None:
                    try:
                        driver.close()
                    except Exception:
                        pass

                if browser is not None:
                    browser.close()
                if playwright is not None:
                    playwright.stop()
                if proc is not None and proc.poll() is None:
                    proc.kill()
                    proc.communicate()

    if lumi_enabled:
        return False, "Không dựng được Lumi bằng Chrome. Giữ nguyên thiết kế, không thay bằng nhân vật mặc định.", html_out_path

    ok_py, msg_py = _render_cartoon_frames_python_pipe(
        scene=scene,
        output_mp4_path=output_mp4_path,
        audio_path=audio_path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        audio_envelope=envelope,
        scene_idx=scene_idx,
    )
    if ok_py:
        poster_png = os.path.splitext(output_mp4_path)[0] + "_poster.png"
        subprocess.run(
            ["ffmpeg", "-y", "-i", output_mp4_path, "-ss", f"{min(1.0, duration * 0.3):.2f}", "-frames:v", "1", poster_png],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    return ok_py, msg_py, html_out_path


def generate_html_animations_parallel(
    scenes: List[Dict[str, Any]],
    work_dir: str,
    orientation: str = "vertical",
    fps: int = DEFAULT_FPS,
    max_workers: int = 4,
    use_headless_chromium: bool = True,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Sinh đồng thời (đa luồng) các phân cảnh hoạt hình nhiều frame HTML5 Canvas -> MP4
    cho toàn bộ kịch bản, tiết kiệm tối đa thời gian chờ.
    """
    width, height = (1080, 1920) if orientation == "vertical" else (1920, 1080)
    total = len(scenes)
    os.makedirs(work_dir, exist_ok=True)
    errors: List[str] = []

    def _worker(idx_zero: int, sc: Dict[str, Any]) -> Tuple[int, bool, str, str, str]:
        s_num = idx_zero + 1
        if cancel_check and cancel_check():
            return idx_zero, False, "Đã hủy theo yêu cầu người dùng.", "", ""
        dur = max(1.5, float(sc.get("audio_duration") or sc.get("expected_duration_sec") or 5.0))
        aud = str(sc.get("audio_path") or "")
        mp4_out = os.path.join(work_dir, f"scene_{s_num:03d}_html_anim.mp4")
        html_out = os.path.join(work_dir, f"scene_{s_num:03d}_html_anim.html")
        ok, res_mp4, res_html = render_html_scene_to_video(
            scene=sc,
            output_mp4_path=mp4_out,
            html_out_path=html_out,
            audio_path=aud if os.path.exists(aud) else None,
            duration=dur,
            width=width,
            height=height,
            fps=fps,
            scene_idx=s_num,
            total_scenes=total,
            use_headless_chromium=use_headless_chromium,
        )
        poster_path = os.path.splitext(mp4_out)[0] + "_poster.png"
        return idx_zero, ok, res_mp4, res_html, poster_path

    actual_workers = max(1, min(int(max_workers or 4), total))
    with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as pool:
        futures = [pool.submit(_worker, i, s) for i, s in enumerate(scenes)]
        completed_count = 0
        for fut in concurrent.futures.as_completed(futures):
            idx_zero, ok, res_mp4, res_html, poster_path = fut.result()
            completed_count += 1
            s_num = idx_zero + 1
            if not ok:
                errors.append(f"Cảnh {s_num}: {res_mp4}")
            else:
                scenes[idx_zero]["video_path"] = res_mp4
                scenes[idx_zero]["html_frame_path"] = res_html
                scenes[idx_zero]["use_video_ai"] = True
                scenes[idx_zero]["asset_source"] = "html_canvas_multi_frame"
                if os.path.exists(poster_path):
                    scenes[idx_zero]["image_path"] = poster_path
                if progress_callback:
                    progress_callback(completed_count, total, f"Đã dựng xong hoạt hình HTML cảnh {s_num}/{total}")

    if errors:
        return False, scenes, "; ".join(errors)
    return True, scenes, ""
