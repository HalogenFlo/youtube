try:
    from moviepy.editor import VideoFileClip
except ImportError:
    VideoFileClip = None
# Chức năng: Ghép nối hình ảnh, video clip, âm thanh, nhạc nền (BGM ducking) và phụ đề ASS/SRT thành video hoàn chỉnh.
# Hỗ trợ:
# 1. Động cơ MoviePy + FFmpeg (khi có moviepy).
# 2. Động cơ FFmpeg Native trực tiếp (khi không cài moviepy hoặc chạy trên server tối giản).
# 3. Chuẩn hóa thống nhất độ phân giải (mặc định 1080x1920 cho 9:16 hoặc 1920x1080 cho 16:9).
# 4. Chặn lỗi âm thầm (strict_assets=True): Không tự ý thay tài sản lỗi bằng khung hình đen hay âm thanh câm.

import concurrent.futures
import gc
import os
import shutil
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    try:
        PIL.Image.ANTIALIAS = getattr(PIL.Image.Resampling, "LANCZOS", getattr(PIL.Image, "LANCZOS", None))
    except Exception:
        pass

from src.config import DEFAULT_FPS, FONT_PATH, MUSIC_DIR, OUTPUT_DIR, TEMP_DIR
from src.subtitle_builder import build_ass_subtitle, build_srt_subtitle
from src.visual_beats import _FallbackVisualClip, apply_visual_beat_motion


def _safe_delete_file(filepath: str, max_retries: int = 4, delay: float = 0.25) -> None:
    """Xóa file tạm thời an toàn trên Windows, chống xung đột process lock (WinError 32)."""
    if not filepath or not os.path.exists(filepath):
        return
    for _ in range(max_retries):
        try:
            os.remove(filepath)
            return
        except Exception:
            time.sleep(delay)


# Vá lỗi Moviepy decorator use_clip_fps_by_default làm mất fps trên Python 3.12 (chỉ khi moviepy được cài đặt)
try:
    import moviepy.video.VideoClip as _mpy_vc
    _orig_ffmpeg_write = getattr(_mpy_vc.ffmpeg_write_video, "_studio_original", _mpy_vc.ffmpeg_write_video)

    def _safe_ffmpeg_write_video(clip, filename, fps, codec="libx264", **kw):
        actual_fps = fps or getattr(clip, "fps", None) or 30
        return _orig_ffmpeg_write(clip, filename, actual_fps, codec=codec, **kw)

    _safe_ffmpeg_write_video._studio_original = _orig_ffmpeg_write
    _mpy_vc.ffmpeg_write_video = _safe_ffmpeg_write_video
except Exception:
    pass


def apply_ken_burns(
    image_path: str,
    duration: float,
    orientation: str,
    target_resolution: Optional[Tuple[int, int]] = None,
) -> Any:
    """
    Tạo ImageClip từ ảnh và áp dụng hiệu ứng Ken Burns (zoom-in chậm).
    Đảm bảo luôn chuẩn hóa sang RGB 3 channels.
    """
    if target_resolution is not None:
        target_w, target_h = int(target_resolution[0]), int(target_resolution[1])
    else:
        target_w, target_h = (480, 848) if orientation == "vertical" else (848, 480)

    from PIL import Image
    import numpy as np

    with Image.open(image_path) as pil_img:
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        img_arr = np.array(pil_img)

    zoom_fn = lambda t: 1.0 + 0.12 * (t / max(0.001, duration))

    try:
        from moviepy.editor import ImageClip
        clip = ImageClip(img_arr).set_duration(duration)
        clip = clip.resize(newsize=(target_w, target_h))
        clip_zoom = clip.resize(zoom_fn)
        clip_final = clip_zoom.crop(
            x_center=clip_zoom.w / 2,
            y_center=clip_zoom.h / 2,
            width=target_w,
            height=target_h,
        )
        return clip_final
    except ImportError:
        return _FallbackVisualClip(img_arr, duration=duration, target_size=(target_w, target_h), zoom_fn=zoom_fn)


def process_video_clip(
    video_path: str,
    duration: float,
    orientation: str,
    target_resolution: Optional[Tuple[int, int]] = None,
) -> Any:
    """
    Load video clip, resize về kích thước chuẩn và đồng bộ thời lượng với audio.
    - Nếu video ngắn hơn audio: Loop chuyển động liên tục (chống đứng hình / freeze frame).
    - Nếu video dài hơn audio: Cắt gọn vừa vặn thời lượng audio (chống lệch nhịp).
    """
    if target_resolution is not None:
        target_w, target_h = int(target_resolution[0]), int(target_resolution[1])
    else:
        target_w, target_h = (1080, 1920) if orientation == "vertical" else (1920, 1080)

    clip = VideoFileClip(video_path)
    clip = clip.resize(newsize=(target_w, target_h))

    orig_duration = float(clip.duration or 0.0)
    if orig_duration > 0 and duration > 0:
        if abs(orig_duration - duration) > 0.15:
            try:
                from moviepy.video.fx.all import speedx
                clip = speedx(clip, final_duration=duration)
            except Exception:
                if orig_duration > duration:
                    clip = clip.subclip(0, duration)
                else:
                    clip = clip.set_duration(duration)
        else:
            clip = clip.set_duration(duration)
    else:
        clip = clip.set_duration(duration)

    return clip


def burn_subtitles(
    video_in: str,
    ass_path: str,
    video_out: str,
    part_num: int = 0,
    total_parts: int = 0,
) -> Tuple[bool, str]:
    """
    Sử dụng FFmpeg CLI để burn phụ đề ASS lên video và thêm watermark phân phần (nếu có).
    """
    if not os.path.exists(video_in):
        return False, f"Không tìm thấy file video nguồn: {video_in}"
    if not os.path.exists(ass_path):
        return False, f"Không tìm thấy file phụ đề: {ass_path}"

    norm_ass_path = ass_path.replace("\\", "/")
    if ":" in norm_ass_path:
        drive, path = norm_ass_path.split(":", 1)
        norm_ass_path = f"{drive}\\:{path}"

    vf_filters = [f"ass='{norm_ass_path}'"]

    if total_parts > 1 and part_num > 0:
        watermark_text = f"Phần {part_num}/{total_parts}"
        norm_font_path = FONT_PATH.replace("\\", "/")
        if ":" in norm_font_path:
            f_drive, f_path = norm_font_path.split(":", 1)
            norm_font_path = f"{f_drive}\\:{f_path}"

        drawtext_filter = (
            f"drawtext=fontfile='{norm_font_path}':text='{watermark_text}':"
            f"x=(w-text_w)/2:y=60:fontsize=36:fontcolor=white:box=1:"
            f"boxcolor=black@0.6:boxborderw=10"
        )
        vf_filters.append(drawtext_filter)

    vf_string = ",".join(vf_filters)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_in,
        "-vf", vf_string,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "192k",
        video_out,
    ]

    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            check=True,
        )
        if os.path.exists(video_out) and os.path.getsize(video_out) > 0:
            return True, video_out
        return False, "FFmpeg chạy thành công nhưng không tạo ra video output hoặc file trống."
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg burn phụ đề thất bại: {e.stderr}"


def split_scenes_into_parts(
    scenes: List[Dict[str, Any]],
    max_duration: float,
) -> List[List[Dict[str, Any]]]:
    """
    Chia danh sách phân cảnh thành các nhóm (mỗi nhóm đại diện cho 1 phần video)
    sao cho thời lượng mỗi nhóm không vượt quá max_duration.
    """
    parts = []
    current_part = []
    current_duration = 0.0

    for scene in scenes:
        scene_dur = float(scene.get("audio_duration", 5.0)) if isinstance(scene, dict) else 5.0

        if current_duration + scene_dur > max_duration and current_part:
            parts.append(current_part)
            current_part = [scene]
            current_duration = scene_dur
        else:
            current_part.append(scene)
            current_duration += scene_dur

    if current_part:
        parts.append(current_part)

    return parts


def _resolve_default_bgm_path(bgm_path: Optional[str], auto_bgm: bool = True) -> Optional[str]:
    if bgm_path and os.path.exists(bgm_path) and os.path.getsize(bgm_path) > 0:
        return bgm_path
    if not auto_bgm:
        return None
    if os.path.exists(MUSIC_DIR):
        candidates = sorted(
            os.path.join(MUSIC_DIR, fn)
            for fn in os.listdir(MUSIC_DIR)
            if fn.lower().endswith(".mp3") and os.path.getsize(os.path.join(MUSIC_DIR, fn)) > 1000
        )
        if candidates:
            return candidates[0]
    return None


def _get_media_duration_seconds(path: str, default: float = 8.0) -> float:
    """Đo thời lượng thực tế (giây) của file video/audio bằng ffprobe hoặc MoviePy."""
    if not path or not os.path.exists(path):
        return default
    try:
        res = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if res.returncode == 0 and res.stdout.strip():
            val = float(res.stdout.strip())
            if val > 0.1:
                return val
    except Exception:
        pass
    try:
        clip = VideoFileClip(path)
        val = float(clip.duration or 0.0)
        clip.close()
        if val > 0.1:
            return val
    except Exception:
        pass
    return default


def _compile_part_with_ffmpeg_native(
    part_scenes: List[Dict[str, Any]],
    raw_output_path: str,
    orientation: str = "vertical",
    target_resolution: Optional[Tuple[int, int]] = None,
    bgm_path: Optional[str] = None,
    bgm_volume_speech: float = 0.24,
    strict_assets: bool = True,
    render_workers: int = 4,
    auto_bgm: bool = True,
) -> Tuple[bool, str]:
    """
    Động cơ dựng video đa luồng trực tiếp bằng FFmpeg CLI + Pillow/RGB chuẩn hóa:
    - Mã hóa song song từng phân cảnh (ThreadPoolExecutor) giúp tăng tốc 3x-5x.
    - Đồng bộ thời lượng khung hình video khớp 1:1 với câu thoại qua setpts (KHÔNG lặp lại khung hình -stream_loop).
    - Tự động hòa âm nhạc nền phòng thu (BGM ducking) với giọng đọc để âm thanh rõ, đầy đặn.
    - Kiểm tra tài sản nghiêm ngặt khi strict_assets=True.
    """
    if target_resolution is not None:
        target_w, target_h = int(target_resolution[0]), int(target_resolution[1])
    else:
        target_w, target_h = (1080, 1920) if orientation == "vertical" else (1920, 1080)

    batch_uid = uuid.uuid4().hex[:8]
    concat_list_path = os.path.join(TEMP_DIR, f"concat_{batch_uid}.txt")
    temp_artifacts: List[str] = []
    ordered_segments: Dict[int, str] = {}

    def _encode_single_scene(idx: int, scene: Dict[str, Any]) -> Tuple[int, bool, str, List[str]]:
        local_temps: List[str] = []
        if not isinstance(scene, dict):
            return idx, False, f"Phân cảnh {idx} không đúng định dạng dict.", local_temps

        audio_path = str(scene.get("audio_path") or "")
        audio_dur = max(0.2, float(scene.get("audio_duration") or scene.get("expected_duration_sec") or 5.0))
        if not audio_path or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            if strict_assets:
                return idx, False, f"Phân cảnh {idx} thiếu file âm thanh hợp lệ: {audio_path}", local_temps

        use_vid = bool(scene.get("use_video_ai", False))
        video_path = str(scene.get("video_path") or "")
        image_path = str(scene.get("image_path") or scene.get("asset_path") or "")

        seg_out = os.path.join(TEMP_DIR, f"seg_{batch_uid}_{idx:03d}.mp4")
        local_temps.append(seg_out)

        if use_vid and video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            vid_dur = max(0.5, _get_media_duration_seconds(video_path, default=audio_dur))
            pts_factor = max(0.5, min(3.5, audio_dur / vid_dur))
            vf = (
                f"setpts={pts_factor:.4f}*PTS,"
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},fps={DEFAULT_FPS},format=yuv420p"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-t", f"{audio_dur:.3f}",
                "-vf", vf,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "20",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                "-shortest",
                seg_out,
            ]
        elif image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 0:
            from PIL import Image
            rgb_temp_img = os.path.join(TEMP_DIR, f"rgb_{batch_uid}_{idx:03d}.png")
            local_temps.append(rgb_temp_img)
            with Image.open(image_path) as im:
                rgb_im = im.convert("RGB").resize((target_w, target_h))
                rgb_im.save(rgb_temp_img, "PNG")

            vf = f"scale={target_w}:{target_h},fps={DEFAULT_FPS},format=yuv420p"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-framerate", str(DEFAULT_FPS),
                "-i", rgb_temp_img,
                "-i", audio_path,
                "-t", f"{audio_dur:.3f}",
                "-vf", vf,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "20",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                "-shortest",
                seg_out,
            ]
        else:
            if strict_assets:
                return idx, False, f"Phân cảnh {idx} thiếu tài sản hình ảnh/video hợp lệ.", local_temps
            return idx, False, f"Không tìm thấy tài sản cho cảnh {idx}.", local_temps

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0 or not os.path.exists(seg_out) or os.path.getsize(seg_out) == 0:
            return idx, False, f"Lỗi FFmpeg khi dựng phân cảnh {idx}: {res.stderr[-400:] if res.stderr else 'unknown'}", local_temps
        return idx, True, seg_out, local_temps

    try:
        actual_workers = max(1, min(int(render_workers or 4), len(part_scenes)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as pool:
            futs = [pool.submit(_encode_single_scene, idx, sc) for idx, sc in enumerate(part_scenes, start=1)]
            for fut in concurrent.futures.as_completed(futs):
                idx, ok_seg, seg_or_err, local_temps = fut.result()
                temp_artifacts.extend(local_temps)
                if not ok_seg:
                    return False, seg_or_err
                ordered_segments[idx] = seg_or_err

        mp4_segments = [ordered_segments[i] for i in sorted(ordered_segments.keys()) if os.path.exists(ordered_segments[i])]
        if not mp4_segments:
            return False, "Không có phân đoạn video nào được tạo."

        with open(concat_list_path, "w", encoding="utf-8") as cf:
            for seg in mp4_segments:
                escaped = os.path.abspath(seg).replace("'", "'\\''")
                cf.write(f"file '{escaped}'\n")

        resolved_bgm = _resolve_default_bgm_path(bgm_path, auto_bgm=auto_bgm)
        concat_out = raw_output_path if not resolved_bgm else (raw_output_path + ".nobgm.mp4")
        if concat_out != raw_output_path:
            temp_artifacts.append(concat_out)

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "19",
            "-c:a", "aac",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            concat_out,
        ]
        res_c = subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_c.returncode != 0 or not os.path.exists(concat_out):
            return False, f"Lỗi nối các phân cảnh bằng FFmpeg: {res_c.stderr[-400:] if res_c.stderr else 'unknown'}"

        if resolved_bgm and os.path.exists(resolved_bgm) and concat_out != raw_output_path:
            cmd_bgm = [
                "ffmpeg", "-y",
                "-i", concat_out,
                "-stream_loop", "-1",
                "-i", resolved_bgm,
                "-filter_complex",
                f"[0:a]volume=1.25[voice];[1:a]volume={bgm_volume_speech:.2f}[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.92[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                raw_output_path,
            ]
            res_b = subprocess.run(cmd_bgm, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_b.returncode != 0 or not os.path.exists(raw_output_path):
                shutil.copy2(concat_out, raw_output_path)

        return True, raw_output_path
    finally:
        _safe_delete_file(concat_list_path)
        for seg in temp_artifacts:
            _safe_delete_file(seg)


def compile_video_pipeline(
    scenes: List[Dict[str, Any]],
    words_timestamps: List[Dict[str, Any]],
    max_duration: float = 60.0,
    orientation: str = "vertical",
    target_resolution: Optional[Tuple[int, int]] = None,
    bgm_path: Optional[str] = None,
    strict_assets: bool = True,
    output_srt_path: Optional[str] = None,
    output_ass_path: Optional[str] = None,
) -> Tuple[bool, List[str], str]:
    """
    Pipeline hoàn chỉnh biên tập video:
    1. Phân chia các phân cảnh thành các phần dựa trên max_duration.
    2. Gom nhóm word-level timestamps tương ứng với từng phần.
    3. Biên tập video thô bằng MoviePy (nếu có) hoặc FFmpeg Native Engine (không phụ thuộc MoviePy).
    4. Tạo file ASS karaoke và SRT cho từng phần (reset timestamp về 0s).
    5. Burn phụ đề và watermark bằng FFmpeg.
    Trả về: (Success, list_of_final_video_paths, error_message)
    """
    final_videos: List[str] = []
    render_uid = uuid.uuid4().hex
    if not scenes:
        return False, [], "Danh sách phân cảnh trống, không thể dựng video."

    if target_resolution is None:
        target_resolution = (1080, 1920) if orientation == "vertical" else (1920, 1080)

    try:
        parts_scenes = split_scenes_into_parts(scenes, max_duration)
        total_parts = len(parts_scenes)

        word_idx = 0
        cumulative_time = 0.0

        # Kiểm tra xem có MoviePy khả dụng hay không
        has_moviepy = False
        try:
            import moviepy.editor as _mp_ed  # noqa: F401
            has_moviepy = not getattr(_mp_ed, "_IS_SHIM", False)
        except ImportError:
            has_moviepy = False

        for part_idx, part_scenes in enumerate(parts_scenes):
            part_num = part_idx + 1
            print(f"--- Đang xử lý Phần {part_num}/{total_parts} ---")

            part_duration = sum(
                (float(s.get("audio_duration", 5.0)) if isinstance(s, dict) else 5.0)
                for s in part_scenes
            )
            part_start_time = cumulative_time
            part_end_time = part_start_time + part_duration

            part_words = []
            while word_idx < len(words_timestamps):
                word = words_timestamps[word_idx]
                if word["start"] < part_end_time + 0.1:
                    shifted_word = {
                        "word": word["word"],
                        "start": max(0.0, word["start"] - part_start_time),
                        "end": max(0.0, word["end"] - part_start_time),
                    }
                    part_words.append(shifted_word)
                    word_idx += 1
                else:
                    break

            raw_output_path = os.path.join(TEMP_DIR, f"render_{render_uid}_part_{part_num}_raw.mp4")

            if has_moviepy:
                from moviepy.editor import AudioFileClip, concatenate_audioclips, concatenate_videoclips
                from moviepy.audio.AudioClip import AudioClip

                scene_clips = []
                part_audio_clips = []

                for s_i, scene in enumerate(part_scenes, start=1):
                    audio_path = scene.get("audio_path", "") if isinstance(scene, dict) else ""
                    audio_dur = float(scene.get("audio_duration", 5.0)) if isinstance(scene, dict) else 5.0

                    audio_clip = None
                    if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                        try:
                            audio_clip = AudioFileClip(audio_path)
                            if audio_clip.duration:
                                audio_clip = audio_clip.set_duration(min(audio_clip.duration, audio_dur))
                                audio_dur = float(audio_clip.duration)
                        except Exception as e:
                            print(f"[WARNING] Lỗi load audio {audio_path}: {e}")
                            audio_clip = None

                    if audio_clip is None:
                        if strict_assets:
                            return False, [], f"Phân cảnh {s_i} thiếu hoặc lỗi giải mã file âm thanh: {audio_path}"
                        audio_clip = AudioClip(lambda t: 0.0, duration=audio_dur)
                    part_audio_clips.append(audio_clip)

                    visual_clip = None
                    if isinstance(scene, dict) and scene.get("use_video_ai", False):
                        video_path = scene.get("video_path", "")
                        if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                            try:
                                visual_clip = process_video_clip(
                                    video_path, audio_dur, orientation, target_resolution=target_resolution
                                )
                                visual_clip = visual_clip.without_audio()
                            except Exception as e:
                                print(f"[WARNING] Lỗi load video AI {video_path}: {e}")
                                visual_clip = None

                    if visual_clip is None:
                        image_path = scene.get("image_path", "") if isinstance(scene, dict) else ""
                        if image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                            try:
                                visual_clip = apply_visual_beat_motion(
                                    image_path, audio_dur, orientation, target_resolution=target_resolution
                                )
                            except Exception as e:
                                print(f"[WARNING] Lỗi apply_visual_beat_motion, fallback Ken Burns: {e}")
                                visual_clip = apply_ken_burns(
                                    image_path, audio_dur, orientation, target_resolution=target_resolution
                                )

                    if visual_clip is None:
                        if strict_assets:
                            return False, [], f"Phân cảnh {s_i} thiếu hoặc lỗi giải mã tài sản hình ảnh/video."
                        from moviepy.video.VideoClip import ColorClip
                        visual_clip = ColorClip(size=target_resolution, color=(15, 20, 28), duration=audio_dur)

                    visual_clip = visual_clip.set_duration(audio_dur)
                    scene_clips.append(visual_clip)

                if not scene_clips:
                    continue

                part_video_raw = concatenate_videoclips(scene_clips, method="compose")
                if part_audio_clips:
                    combined_audio = concatenate_audioclips(part_audio_clips)
                    total_audio_dur = float(combined_audio.duration or 0.0)
                    if total_audio_dur > 0:
                        part_video_raw = part_video_raw.set_duration(total_audio_dur)
                    part_video_raw = part_video_raw.set_audio(combined_audio)

                temp_audio_name = f"temp-audio-{uuid.uuid4().hex[:8]}-part{part_num}.m4a"
                part_temp_audio = os.path.join(TEMP_DIR, temp_audio_name)

                part_video_raw.write_videofile(
                    raw_output_path,
                    fps=DEFAULT_FPS,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=part_temp_audio,
                    remove_temp=False,
                    verbose=False,
                    logger=None,
                )

                part_video_raw.close()
                for c in scene_clips:
                    try:
                        c.close()
                        if hasattr(c, "reader") and c.reader:
                            c.reader.close()
                        if hasattr(c, "clip") and c.clip:
                            c.clip.close()
                            if hasattr(c.clip, "reader") and c.clip.reader:
                                c.clip.reader.close()
                    except Exception:
                        pass
                for a in part_audio_clips:
                    try:
                        a.close()
                    except Exception:
                        pass
                gc.collect()
                _safe_delete_file(part_temp_audio)
            else:
                # Sử dụng động cơ FFmpeg Native trực tiếp
                ok_raw, err_raw = _compile_part_with_ffmpeg_native(
                    part_scenes=part_scenes,
                    raw_output_path=raw_output_path,
                    orientation=orientation,
                    target_resolution=target_resolution,
                    bgm_path=bgm_path,
                    strict_assets=strict_assets,
                )
                if not ok_raw:
                    return False, [], err_raw

            # 4. Tạo phụ đề ASS và SRT cho phần này
            ass_path = output_ass_path if total_parts == 1 and output_ass_path else os.path.join(TEMP_DIR, f"render_{render_uid}_part_{part_num}.ass")
            build_ass_subtitle(part_words, ass_path, orientation)

            srt_path = output_srt_path or os.path.join(TEMP_DIR, f"render_{render_uid}_part_{part_num}.srt")
            build_srt_subtitle(part_words, srt_path, orientation)

            # 5. Burn phụ đề bằng FFmpeg
            final_output_path = os.path.join(
                OUTPUT_DIR,
                f"video_final_{render_uid}_part{part_num}.mp4" if total_parts > 1 else f"video_final_{render_uid}.mp4",
            )
            success, burn_err = burn_subtitles(
                raw_output_path,
                ass_path,
                final_output_path,
                part_num,
                total_parts,
            )

            if not success:
                return False, [], f"Lỗi ở khâu burn phụ đề Phần {part_num}: {burn_err}"

            final_videos.append(final_output_path)
            cumulative_time += part_duration

        return True, final_videos, ""

    except Exception as e:
        return False, [], f"Lỗi trong quá trình compile video: {str(e)}"
    finally:
        gc.collect()
