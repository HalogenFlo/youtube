# Chức năng: Bộ kiểm định chất lượng video độc lập SAU KHI RENDER (Independent Post-Render Video QA).

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.story_contract_models import (
    QAIssue,
    QAReport,
    compute_file_sha256,
    validate_contract_boundary,
)


DEFAULT_QA_WEIGHTS: Dict[str, float] = {
    "stream_and_container": 20.0,
    "platform_specs": 10.0,
    "visual_defects_and_continuity": 15.0,
    "scene_completeness_and_timing": 15.0,
    "audio_quality_and_balance": 15.0,
    "subtitle_sync_and_safe_zone": 15.0,
    "hook_pacing_and_metadata": 10.0,
}


def _has_cli_tool(tool_name: str) -> bool:
    return shutil.which(tool_name) is not None


def probe_media_file(video_path: str) -> Dict[str, Any]:
    if not video_path or not os.path.exists(video_path):
        return {"exists": False, "error": f"File không tồn tại: {video_path}"}
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        return {"exists": True, "size_bytes": 0, "decodable": False, "error": "File rỗng (0 bytes)."}

    if not _has_cli_tool("ffprobe"):
        return {
            "exists": True,
            "size_bytes": file_size,
            "ffprobe_available": False,
            "decodable": None,
            "error": "Không tìm thấy công cụ ffprobe trên hệ thống.",
        }

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        video_path,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        if res.returncode != 0:
            return {
                "exists": True,
                "size_bytes": file_size,
                "ffprobe_available": True,
                "decodable": False,
                "error": (res.stderr or "ffprobe trả mã lỗi khác 0").strip(),
            }
        data = json.loads(res.stdout or "{}")
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        fps = 0.0
        if video_stream:
            r_frame_rate = str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1")
            if "/" in r_frame_rate:
                num, den = r_frame_rate.split("/", 1)
                fps = float(num) / float(den) if float(den) != 0 else 0.0
            else:
                try:
                    fps = float(r_frame_rate)
                except Exception:
                    fps = 0.0

        duration = float(
            fmt.get("duration")
            or (video_stream or {}).get("duration")
            or (audio_stream or {}).get("duration")
            or 0.0
        )
        width = int((video_stream or {}).get("width") or 0)
        height = int((video_stream or {}).get("height") or 0)

        return {
            "exists": True,
            "size_bytes": file_size,
            "ffprobe_available": True,
            "decodable": bool(video_stream is not None and duration > 0),
            "duration_sec": round(duration, 3),
            "has_video": video_stream is not None,
            "has_audio": audio_stream is not None,
            "video_codec": (video_stream or {}).get("codec_name", ""),
            "pix_fmt": (video_stream or {}).get("pix_fmt", ""),
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "audio_codec": (audio_stream or {}).get("codec_name", ""),
            "sample_rate": int((audio_stream or {}).get("sample_rate") or 0),
            "channels": int((audio_stream or {}).get("channels") or 0),
            "audio_duration_sec": round(float((audio_stream or {}).get("duration") or duration), 3) if audio_stream else 0.0,
        }
    except Exception as exc:
        return {
            "exists": True,
            "size_bytes": file_size,
            "ffprobe_available": True,
            "decodable": False,
            "error": f"Lỗi khi chạy ffprobe: {exc}",
        }


def analyze_audio_stream_ffmpeg(video_path: str) -> Dict[str, Any]:
    if not _has_cli_tool("ffmpeg") or not os.path.exists(video_path):
        return {"available": False}

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i", video_path,
        "-af", "volumedetect,silencedetect=noise=-42dB:d=1.2",
        "-f", "null",
        "-",
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        stderr = res.stderr or ""
        mean_match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", stderr)
        max_match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", stderr)
        silence_intervals: List[Tuple[float, float, float]] = []
        starts = [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([\d.]+)", stderr)]
        ends = [
            (float(m.group(1)), float(m.group(2)))
            for m in re.finditer(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", stderr)
        ]
        for idx, (end_t, dur) in enumerate(ends):
            start_t = starts[idx] if idx < len(starts) else max(0.0, end_t - dur)
            silence_intervals.append((round(start_t, 2), round(end_t, 2), round(dur, 2)))

        return {
            "available": True,
            "mean_volume_db": float(mean_match.group(1)) if mean_match else None,
            "max_volume_db": float(max_match.group(1)) if max_match else None,
            "silence_intervals": silence_intervals,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def analyze_video_frames_and_black_freeze(
    video_path: str,
    scenes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "available": False,
        "black_intervals": [],
        "freeze_intervals": [],
        "sampled_frames_count": 0,
        "black_frames_ratio": 0.0,
    }
    if not os.path.exists(video_path):
        return result

    try:
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = total_frames / max(1.0, fps)
            sample_steps = max(5, min(30, int(duration * 2)))
            step_frames = max(1, total_frames // sample_steps) if total_frames > 0 else 15

            black_ranges: List[List[float]] = []
            freeze_ranges: List[List[float]] = []
            prev_gray = None
            prev_t = 0.0
            sampled = 0
            black_count = 0

            for f_idx in range(0, max(1, total_frames), step_frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                sampled += 1
                t_sec = round(f_idx / max(1.0, fps), 2)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                mean_luma = float(np.mean(gray))
                std_luma = float(np.std(gray))

                if mean_luma < 10.0 and std_luma < 5.0:
                    black_count += 1
                    if black_ranges and t_sec - black_ranges[-1][1] <= (step_frames / max(1.0, fps)) * 1.5:
                        black_ranges[-1][1] = round(t_sec + step_frames / max(1.0, fps), 2)
                    else:
                        black_ranges.append([t_sec, round(t_sec + step_frames / max(1.0, fps), 2)])

                if prev_gray is not None and prev_gray.shape == gray.shape:
                    diff = float(np.mean(np.abs(gray.astype(float) - prev_gray.astype(float))))
                    if diff < 0.08:
                        if freeze_ranges and t_sec - freeze_ranges[-1][1] <= (step_frames / max(1.0, fps)) * 1.5:
                            freeze_ranges[-1][1] = t_sec
                        else:
                            freeze_ranges.append([prev_t, t_sec])
                prev_gray = gray
                prev_t = t_sec

            cap.release()
            if sampled > 0:
                result["available"] = True
                result["sampled_frames_count"] = sampled
                result["black_intervals"] = [r for r in black_ranges if (r[1] - r[0]) >= 0.25]
                result["freeze_intervals"] = [r for r in freeze_ranges if (r[1] - r[0]) >= 1.5]
                result["black_frames_ratio"] = round(black_count / sampled, 3)
                return result
    except Exception:
        pass

    return result


def parse_and_inspect_ass_subtitle(
    ass_path: str,
    orientation: str = "vertical",
) -> Dict[str, Any]:
    if not ass_path or not os.path.exists(ass_path):
        return {"exists": False}

    try:
        content = Path(ass_path).read_text(encoding="utf-8")
    except Exception as exc:
        return {"exists": True, "parse_error": str(exc)}

    play_res_x = 1080 if orientation == "vertical" else 1920
    play_res_y = 1920 if orientation == "vertical" else 1080
    m_x = re.search(r"PlayResX:\s*(\d+)", content)
    m_y = re.search(r"PlayResY:\s*(\d+)", content)
    if m_x:
        play_res_x = int(m_x.group(1))
    if m_y:
        play_res_y = int(m_y.group(1))

    font_size = 44
    alignment = 2
    margin_l = 50
    margin_r = 50
    margin_v = 260

    for line in content.splitlines():
        if line.startswith("Style: Default,"):
            parts = line.split(",")
            if len(parts) >= 22:
                try:
                    font_size = int(parts[2])
                    alignment = int(parts[18])
                    margin_l = int(parts[19])
                    margin_r = int(parts[20])
                    margin_v = int(parts[21])
                except Exception:
                    pass
            break

    def _parse_ass_time(t_str: str) -> float:
        parts = t_str.strip().split(":")
        if len(parts) != 3:
            return 0.0
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    dialogues: List[Dict[str, Any]] = []
    overflow_lines: List[Dict[str, Any]] = []
    corrupt_diacritic_lines: List[Dict[str, Any]] = []
    high_cps_lines: List[Dict[str, Any]] = []

    max_usable_width_px = max(200, play_res_x - margin_l - margin_r)

    for line in content.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        start_sec = _parse_ass_time(parts[1])
        end_sec = _parse_ass_time(parts[2])
        raw_text = parts[9]
        plain_text = re.sub(r"\{[^}]*\}", "", raw_text).strip()
        dur = max(0.05, end_sec - start_sec)
        char_count = len(plain_text)
        cps = round(char_count / dur, 1)

        est_width_px = char_count * (font_size * 0.56)
        item = {
            "start": round(start_sec, 2),
            "end": round(end_sec, 2),
            "duration": round(dur, 2),
            "text": plain_text,
            "char_count": char_count,
            "cps": cps,
            "est_width_px": round(est_width_px, 1),
        }
        dialogues.append(item)

        if est_width_px > max_usable_width_px * 1.08:
            overflow_lines.append(item)
        if "\ufffd" in plain_text or "???" in plain_text or re.search(r"\\[kK]\d+", plain_text):
            corrupt_diacritic_lines.append(item)
        if cps > 28.0 and char_count > 12:
            high_cps_lines.append(item)

    if orientation == "vertical":
        safe_zone_ok = (alignment == 2) and (180 <= margin_v <= 480) and (font_size <= 54)
    else:
        safe_zone_ok = (alignment == 2) and (50 <= margin_v <= 240) and (font_size <= 48)

    all_text = " ".join(d["text"] for d in dialogues)
    return {
        "exists": True,
        "play_res": (play_res_x, play_res_y),
        "font_size": font_size,
        "alignment": alignment,
        "margin_v": margin_v,
        "max_usable_width_px": max_usable_width_px,
        "dialogues_count": len(dialogues),
        "dialogues": dialogues,
        "all_text": all_text,
        "overflow_lines": overflow_lines,
        "corrupt_diacritic_lines": corrupt_diacritic_lines,
        "high_cps_lines": high_cps_lines,
        "safe_zone_ok": safe_zone_ok,
        "start_sec": dialogues[0]["start"] if dialogues else 0.0,
        "end_sec": dialogues[-1]["end"] if dialogues else 0.0,
    }


def run_rendered_video_qa(
    video_path: str,
    scenes: List[Dict[str, Any]],
    ass_subtitle_path: str = "",
    orientation: str = "vertical",
    target_resolution: Optional[Tuple[int, int]] = None,
    publishing_metadata: Optional[Dict[str, Any]] = None,
    render_id: str = "",
    revision_round: int = 0,
    max_revisions: int = 2,
    weights: Optional[Dict[str, float]] = None,
    strict_no_fallback: bool = True,
    vlm_frame_evaluator: Optional[Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]] = None,
) -> QAReport:
    active_weights = dict(DEFAULT_QA_WEIGHTS)
    if weights:
        active_weights.update(weights)

    issues: List[QAIssue] = []
    category_scores: Dict[str, float] = {k: 100.0 for k in active_weights}

    probe = probe_media_file(video_path)
    video_sha256 = compute_file_sha256(video_path) if probe.get("exists") else ""
    total_scenes = len(scenes or [])
    expected_total_dur = round(
        sum(float(s.get("audio_duration") or s.get("expected_duration_sec") or 5.0) for s in (scenes or []) if isinstance(s, dict)),
        2,
    )

    if not probe.get("exists") or probe.get("size_bytes", 0) == 0:
        issues.append(QAIssue(
            check_id="QA_01_FILE_EXISTS",
            severity="critical",
            scene_id=None,
            time_range=[0.0, 0.0],
            evidence=probe.get("error", f"File không tồn tại hoặc rỗng: {video_path}"),
            suggested_fix="Chạy lại công đoạn dựng phim (rendering) để xuất file MP4 hợp lệ.",
            confidence=1.0,
            status="failed",
        ))
        category_scores["stream_and_container"] = 0.0
    elif probe.get("ffprobe_available") is False:
        issues.append(QAIssue(
            check_id="QA_01_DECODE_STREAMS",
            severity="major",
            scene_id=None,
            time_range=[0.0, expected_total_dur],
            evidence="Không tìm thấy công cụ ffprobe trên hệ thống.",
            suggested_fix="Cài đặt FFmpeg/ffprobe vào PATH.",
            confidence=0.0,
            status="not_checked",
        ))
        category_scores["stream_and_container"] = 50.0
    elif not probe.get("decodable"):
        issues.append(QAIssue(
            check_id="QA_01_DECODE_STREAMS",
            severity="critical",
            scene_id=None,
            time_range=[0.0, 0.0],
            evidence=f"File MP4 không giải mã được bằng ffprobe: {probe.get('error', 'Container hỏng')}",
            suggested_fix="Render lại video bằng FFmpeg H.264/AAC.",
            confidence=1.0,
            status="failed",
        ))
        category_scores["stream_and_container"] = 0.0
    else:
        if not probe.get("has_video"):
            issues.append(QAIssue(
                check_id="QA_01_VIDEO_STREAM",
                severity="critical",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence="File MP4 không có luồng hình ảnh (video stream).",
                suggested_fix="Kiểm tra bước ghép clip hình ảnh trong video_compiler.",
                confidence=1.0,
                status="failed",
            ))
            category_scores["stream_and_container"] = 0.0
        if not probe.get("has_audio"):
            issues.append(QAIssue(
                check_id="QA_01_AUDIO_STREAM",
                severity="critical",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence="File MP4 bị câm hoàn toàn (không có audio stream).",
                suggested_fix="Chạy lại công đoạn TTS và ghép âm thanh vào video.",
                confidence=1.0,
                status="failed",
            ))
            category_scores["stream_and_container"] = 0.0
        if probe.get("has_video") and probe.get("has_audio"):
            issues.append(QAIssue(
                check_id="QA_01_STREAM_INTEGRITY",
                severity="info",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence=(
                    f"Giải mã thành công: video={probe.get('video_codec')} ({probe.get('width')}x{probe.get('height')} "
                    f"@{probe.get('fps')}fps), audio={probe.get('audio_codec')} ({probe.get('sample_rate')}Hz, "
                    f"{probe.get('channels')}ch), duration={probe.get('duration_sec')}s."
                ),
                suggested_fix="Không cần sửa.",
                confidence=1.0,
                status="passed",
            ))

    if probe.get("decodable"):
        w = int(probe.get("width", 0))
        h = int(probe.get("height", 0))
        fps = float(probe.get("fps", 0.0))
        is_vertical_actual = h > w
        want_vertical = orientation == "vertical"

        if is_vertical_actual != want_vertical:
            issues.append(QAIssue(
                check_id="QA_02_ASPECT_RATIO_ORIENTATION",
                severity="critical",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence=f"Khung hình thực tế {w}x{h} ngược với cấu hình orientation='{orientation}'.",
                suggested_fix="Render lại đúng tỷ lệ khung hình 9:16 (dọc) hoặc 16:9 (ngang).",
                confidence=1.0,
                status="failed",
            ))
            category_scores["platform_specs"] = 0.0
        else:
            ratio = (w / max(1, h)) if not want_vertical else (h / max(1, w))
            if abs(ratio - (16.0 / 9.0)) > 0.08:
                issues.append(QAIssue(
                    check_id="QA_02_ASPECT_RATIO_PRECISION",
                    severity="major",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Kích thước {w}x{h} lệch tỷ lệ chuẩn 9:16 / 16:9 (ratio={ratio:.3f}).",
                    suggested_fix="Chuẩn hóa độ phân giải về 1080x1920 hoặc 1920x1080.",
                    confidence=0.98,
                    status="failed",
                ))
                category_scores["platform_specs"] -= 40.0
            elif min(w, h) < 720:
                issues.append(QAIssue(
                    check_id="QA_02_RESOLUTION_HD",
                    severity="minor",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Độ phân giải hiện tại {w}x{h} thấp hơn chuẩn Full HD (1080p).",
                    suggested_fix="Nâng độ phân giải xuất lên 1080x1920 hoặc 1920x1080.",
                    confidence=1.0,
                    status="warning",
                ))
                category_scores["platform_specs"] -= 15.0
            else:
                issues.append(QAIssue(
                    check_id="QA_02_PLATFORM_SPECS",
                    severity="info",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Đạt chuẩn nền tảng: {w}x{h}, FPS={fps}, pix_fmt={probe.get('pix_fmt')}.",
                    suggested_fix="Không cần sửa.",
                    confidence=1.0,
                    status="passed",
                ))

        if fps < 23.5:
            issues.append(QAIssue(
                check_id="QA_02_LOW_FPS",
                severity="major",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence=f"Tốc độ khung hình quá thấp ({fps} fps < 24 fps).",
                suggested_fix="Đặt DEFAULT_FPS = 30 khi xuất video.",
                confidence=1.0,
                status="failed",
            ))
            category_scores["platform_specs"] -= 35.0

    if probe.get("decodable"):
        frame_analysis = analyze_video_frames_and_black_freeze(video_path, scenes)
        if not frame_analysis.get("available"):
            issues.append(QAIssue(
                check_id="QA_03_BLACK_AND_FREEZE_SCAN",
                severity="minor",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence="Không thể quét frame video bằng OpenCV/ffmpeg.",
                suggested_fix="Kiểm tra cài đặt opencv-python hoặc ffmpeg.",
                confidence=0.0,
                status="not_checked",
            ))
        else:
            for b_start, b_end in frame_analysis.get("black_intervals", []):
                b_dur = round(b_end - b_start, 2)
                sev = "critical" if b_dur >= 1.0 or frame_analysis.get("black_frames_ratio", 0) >= 0.4 else "major"
                issues.append(QAIssue(
                    check_id="QA_03_BLACK_FRAMES",
                    severity=sev,
                    scene_id=None,
                    time_range=[b_start, b_end],
                    evidence=f"Phát hiện khung hình đen kéo dài {b_dur}s từ {b_start}s đến {b_end}s.",
                    suggested_fix="Kiểm tra tài sản hình ảnh/video tại khoảng thời gian này và render lại.",
                    confidence=0.95,
                    status="failed",
                ))
                category_scores["visual_defects_and_continuity"] -= (60.0 if sev == "critical" else 30.0)

            all_intentional_still = all(not bool(s.get("use_video_ai")) for s in (scenes or []) if isinstance(s, dict))
            for f_start, f_end in frame_analysis.get("freeze_intervals", []):
                f_dur = round(f_end - f_start, 2)
                if not all_intentional_still:
                    issues.append(QAIssue(
                        check_id="QA_03_FROZEN_VIDEO_SEGMENT",
                        severity="major",
                        scene_id=None,
                        time_range=[f_start, f_end],
                        evidence=f"Đoạn video bị đóng băng bất động trong {f_dur}s ({f_start}s - {f_end}s) ở chế độ Video AI.",
                        suggested_fix="Dùng vfx.loop hoặc sinh lại clip cho phân cảnh bị đứng hình.",
                        confidence=0.9,
                        status="failed",
                    ))
                    category_scores["visual_defects_and_continuity"] -= 25.0

    seen_hashes: Dict[str, int] = {}
    for idx, sc in enumerate(scenes or [], start=1):
        if not isinstance(sc, dict):
            continue
        sc_id = sc.get("scene_id") or f"sc_{idx:03d}"
        t_range = sc.get("timeline_range") or [0.0, 5.0]
        v_path = str(sc.get("video_path") if sc.get("use_video_ai") else (sc.get("image_path") or sc.get("asset_path") or ""))
        v_hash = compute_file_sha256(v_path) if (v_path and os.path.exists(v_path)) else ""
        is_fallback = bool(sc.get("is_fallback_asset", False))

        if is_fallback or (v_hash and v_hash in seen_hashes):
            prev_sc_num = seen_hashes.get(v_hash, idx - 1)
            sev = "critical" if strict_no_fallback else "major"
            issues.append(QAIssue(
                check_id="QA_03_DUPLICATE_OR_FALLBACK_SCENE_ASSET",
                severity=sev,
                scene_id=sc_id,
                time_range=list(t_range),
                evidence=f"Cảnh {idx} ({sc_id}) dùng tài sản trùng lặp/fallback từ cảnh {prev_sc_num}.",
                suggested_fix=f"Chạy lại tạo tài sản hình ảnh/video riêng biệt cho cảnh {idx}.",
                confidence=1.0,
                status="failed",
            ))
            category_scores["visual_defects_and_continuity"] -= (50.0 if sev == "critical" else 25.0)
        elif v_hash:
            seen_hashes[v_hash] = idx

    if total_scenes == 0:
        issues.append(QAIssue(
            check_id="QA_04_NO_SCENES",
            severity="critical",
            scene_id=None,
            time_range=[0.0, 0.0],
            evidence="Danh sách phân cảnh trống (0 scenes).",
            suggested_fix="Chạy lại bước biên kịch (scripting).",
            confidence=1.0,
            status="failed",
        ))
        category_scores["scene_completeness_and_timing"] = 0.0
    else:
        scene_nums = [int(s.get("scene_num") or (i + 1)) for i, s in enumerate(scenes) if isinstance(s, dict)]
        expected_nums = list(range(1, len(scene_nums) + 1))
        if scene_nums != expected_nums:
            issues.append(QAIssue(
                check_id="QA_04_SCENE_ORDER_MISMATCH",
                severity="critical",
                scene_id=None,
                time_range=[0.0, expected_total_dur],
                evidence=f"Thứ tự phân cảnh bị lệch: {scene_nums} != {expected_nums}.",
                suggested_fix="Sắp xếp lại phân cảnh theo đúng thứ tự 1..N và dựng lại video.",
                confidence=1.0,
                status="failed",
            ))
            category_scores["scene_completeness_and_timing"] = 0.0

        for idx, sc in enumerate(scenes, start=1):
            if not isinstance(sc, dict):
                continue
            sc_id = sc.get("scene_id") or f"sc_{idx:03d}"
            a_path = str(sc.get("audio_path") or "")
            v_path = str(sc.get("video_path") if sc.get("use_video_ai") else (sc.get("image_path") or sc.get("asset_path") or ""))
            if a_path and not os.path.exists(a_path):
                issues.append(QAIssue(
                    check_id="QA_04_MISSING_SCENE_AUDIO",
                    severity="critical",
                    scene_id=sc_id,
                    time_range=list(sc.get("timeline_range") or [0.0, 0.0]),
                    evidence=f"Cảnh {idx} thiếu file âm thanh lời thoại: {a_path}",
                    suggested_fix=f"Sinh lại TTS cho cảnh {idx}.",
                    confidence=1.0,
                    status="failed",
                ))
                category_scores["scene_completeness_and_timing"] -= 40.0
            if v_path and not os.path.exists(v_path):
                issues.append(QAIssue(
                    check_id="QA_04_MISSING_SCENE_VISUAL",
                    severity="critical",
                    scene_id=sc_id,
                    time_range=list(sc.get("timeline_range") or [0.0, 0.0]),
                    evidence=f"Cảnh {idx} thiếu file hình ảnh/video: {v_path}",
                    suggested_fix=f"Sinh lại tài sản hình ảnh/video cho cảnh {idx}.",
                    confidence=1.0,
                    status="failed",
                ))
                category_scores["scene_completeness_and_timing"] -= 40.0

        if probe.get("decodable"):
            actual_dur = float(probe.get("duration_sec", 0.0))
            drift = actual_dur - expected_total_dur
            if drift < -0.55:
                issues.append(QAIssue(
                    check_id="QA_04_TRUNCATED_SPEECH_DURATION",
                    severity="critical",
                    scene_id=f"sc_{total_scenes:03d}",
                    time_range=[max(0.0, actual_dur), expected_total_dur],
                    evidence=f"Thời lượng video render ({actual_dur:.2f}s) ngắn hơn tổng lời thoại ({expected_total_dur:.2f}s) tới {abs(drift):.2f}s.",
                    suggested_fix="Đồng bộ lại tổng thời lượng video khớp 100% với tổng thời lượng audio các cảnh.",
                    confidence=0.98,
                    status="failed",
                ))
                category_scores["scene_completeness_and_timing"] = 0.0
            elif drift > 1.5:
                issues.append(QAIssue(
                    check_id="QA_04_ABNORMAL_TAIL_GAP",
                    severity="major",
                    scene_id=f"sc_{total_scenes:03d}",
                    time_range=[expected_total_dur, actual_dur],
                    evidence=f"Video dư khoảng trống cuối {drift:.2f}s sau khi lời thoại đã kết thúc.",
                    suggested_fix="Cắt gọn đuôi video khớp với kết thúc của âm thanh.",
                    confidence=0.95,
                    status="failed",
                ))
                category_scores["scene_completeness_and_timing"] -= 25.0

    if probe.get("decodable") and probe.get("has_audio"):
        audio_stats = analyze_audio_stream_ffmpeg(video_path)
        if not audio_stats.get("available"):
            issues.append(QAIssue(
                check_id="QA_05_AUDIO_SIGNAL_ANALYSIS",
                severity="minor",
                scene_id=None,
                time_range=[0.0, probe.get("duration_sec", 0.0)],
                evidence="Không thể chạy bộ phân tích tín hiệu âm thanh volumedetect.",
                suggested_fix="Đảm bảo ffmpeg khả dụng trên hệ thống.",
                confidence=0.0,
                status="not_checked",
            ))
        else:
            mean_db = audio_stats.get("mean_volume_db")
            max_db = audio_stats.get("max_volume_db")
            silences = audio_stats.get("silence_intervals", [])

            if mean_db is not None and mean_db <= -42.0:
                issues.append(QAIssue(
                    check_id="QA_05_SILENT_AUDIO_TRACK",
                    severity="critical",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Âm lượng trung bình quá nhỏ hoặc bị câm (mean_volume={mean_db} dB <= -42 dB).",
                    suggested_fix="Kiểm tra file TTS nguồn và bộ trộn âm thanh trong video_compiler.",
                    confidence=0.99,
                    status="failed",
                ))
                category_scores["audio_quality_and_balance"] = 0.0
            elif mean_db is not None and (mean_db < -30.0 or mean_db > -5.0):
                issues.append(QAIssue(
                    check_id="QA_05_LOUDNESS_OUT_OF_RANGE",
                    severity="minor",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Âm lượng trung bình (mean_volume={mean_db} dB) nằm ngoài dải tối ưu [-30 dB, -5 dB].",
                    suggested_fix="Chuẩn hóa âm lượng giọng đọc về khoảng -16 LUFS.",
                    confidence=0.9,
                    status="warning",
                ))
                category_scores["audio_quality_and_balance"] -= 15.0

            if max_db is not None and max_db >= -0.05 and (mean_db is not None and mean_db > -10.0):
                issues.append(QAIssue(
                    check_id="QA_05_AUDIO_CLIPPING",
                    severity="major",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Phát hiện nguy cơ vỡ tiếng / clipping (max_volume={max_db} dB, mean_volume={mean_db} dB).",
                    suggested_fix="Giảm gain hoặc áp dụng limiter -1.0 dBTP khi xuất audio.",
                    confidence=0.9,
                    status="failed",
                ))
                category_scores["audio_quality_and_balance"] -= 30.0

            for s_start, s_end, s_dur in silences:
                if s_dur >= 2.2:
                    issues.append(QAIssue(
                        check_id="QA_05_ABNORMAL_SILENCE_GAP",
                        severity="major",
                        scene_id=None,
                        time_range=[s_start, s_end],
                        evidence=f"Khoảng lặng bất thường kéo dài {s_dur}s từ {s_start}s đến {s_end}s.",
                        suggested_fix="Cắt khoảng lặng thừa hoặc kiểm tra cảnh bị mất tiếng.",
                        confidence=0.92,
                        status="failed",
                    ))
                    category_scores["audio_quality_and_balance"] -= 25.0

            if mean_db is not None and mean_db > -42.0 and not any(i.check_id.startswith("QA_05_") for i in issues):
                issues.append(QAIssue(
                    check_id="QA_05_AUDIO_SIGNAL_OK",
                    severity="info",
                    scene_id=None,
                    time_range=[0.0, probe.get("duration_sec", 0.0)],
                    evidence=f"Tín hiệu âm thanh đạt chuẩn: mean_volume={mean_db} dB, max_volume={max_db} dB.",
                    suggested_fix="Không cần sửa.",
                    confidence=0.98,
                    status="passed",
                ))

    if ass_subtitle_path:
        if not os.path.exists(ass_subtitle_path):
            issues.append(QAIssue(
                check_id="QA_06_SUBTITLE_FILE_MISSING",
                severity="major",
                scene_id=None,
                time_range=[0.0, expected_total_dur],
                evidence=f"Không tìm thấy file phụ đề .ass: {ass_subtitle_path}",
                suggested_fix="Chạy lại bước tạo phụ đề (subtitle_builder) và burn phụ đề.",
                confidence=1.0,
                status="failed",
            ))
            category_scores["subtitle_sync_and_safe_zone"] -= 50.0
        else:
            sub_info = parse_and_inspect_ass_subtitle(ass_subtitle_path, orientation=orientation)
            if sub_info.get("dialogues_count", 0) == 0:
                issues.append(QAIssue(
                    check_id="QA_06_EMPTY_SUBTITLES",
                    severity="critical",
                    scene_id=None,
                    time_range=[0.0, expected_total_dur],
                    evidence="File phụ đề .ass không có bất kỳ dòng Dialogue nào.",
                    suggested_fix="Tạo lại timestamps từ lời thoại nguồn và xuất lại file .ass.",
                    confidence=1.0,
                    status="failed",
                ))
                category_scores["subtitle_sync_and_safe_zone"] = 0.0
            else:
                sub_end = float(sub_info.get("end_sec", 0.0))
                ref_dur = float(probe.get("duration_sec") or expected_total_dur)
                sync_drift = abs(sub_end - ref_dur)
                if ref_dur > 0 and sync_drift > max(1.2, ref_dur * 0.18):
                    issues.append(QAIssue(
                        check_id="QA_06_SUBTITLE_AUDIO_DESYNC",
                        severity="critical" if sync_drift > 3.0 else "major",
                        scene_id=None,
                        time_range=[min(sub_end, ref_dur), max(sub_end, ref_dur)],
                        evidence=f"Phụ đề kết thúc ở {sub_end:.2f}s nhưng thời lượng âm thanh/video là {ref_dur:.2f}s (lệch {sync_drift:.2f}s).",
                        suggested_fix="Tính lại word timestamps theo đúng thời lượng audio thực tế từng cảnh.",
                        confidence=0.96,
                        status="failed",
                    ))
                    category_scores["subtitle_sync_and_safe_zone"] -= 45.0

                expected_words = []
                for sc in (scenes or []):
                    if isinstance(sc, dict):
                        expected_words.extend(re.findall(r"\b\w+\b", str(sc.get("narration", "")).lower()))
                actual_sub_words = re.findall(r"\b\w+\b", str(sub_info.get("all_text", "")).lower())
                if expected_words:
                    coverage = len(actual_sub_words) / max(1, len(expected_words))
                    if coverage < 0.85:
                        issues.append(QAIssue(
                            check_id="QA_07_SUBTITLE_MISSING_WORDS",
                            severity="major",
                            scene_id=None,
                            time_range=[0.0, ref_dur],
                            evidence=f"Phụ đề chỉ bao phủ {coverage:.0%} số từ của lời thoại ({len(actual_sub_words)}/{len(expected_words)} từ).",
                            suggested_fix="Tạo lại phụ đề từ toàn bộ lời thoại các phân cảnh.",
                            confidence=0.95,
                            status="failed",
                        ))
                        category_scores["subtitle_sync_and_safe_zone"] -= 35.0

                if sub_info.get("corrupt_diacritic_lines"):
                    bad_line = sub_info["corrupt_diacritic_lines"][0]
                    issues.append(QAIssue(
                        check_id="QA_07_SUBTITLE_CORRUPT_DIACRITICS",
                        severity="major",
                        scene_id=None,
                        time_range=[bad_line["start"], bad_line["end"]],
                        evidence=f"Phụ đề chứa ký tự lỗi encoding hoặc thẻ ASS bị vỡ: '{bad_line['text']}'",
                        suggested_fix="Làm sạch từ qua clean_word và lưu file ASS chuẩn UTF-8.",
                        confidence=1.0,
                        status="failed",
                    ))
                    category_scores["subtitle_sync_and_safe_zone"] -= 35.0

                if sub_info.get("overflow_lines"):
                    ov = sub_info["overflow_lines"][0]
                    issues.append(QAIssue(
                        check_id="QA_07_SUBTITLE_FRAME_OVERFLOW",
                        severity="major",
                        scene_id=None,
                        time_range=[ov["start"], ov["end"]],
                        evidence=f"Dòng phụ đề '{ov['text']}' có chiều rộng ước tính {ov['est_width_px']}px vượt quá khung an toàn {sub_info['max_usable_width_px']}px.",
                        suggested_fix="Giảm max_words_per_line hoặc ngắt dòng các từ dài trong subtitle_builder.",
                        confidence=0.92,
                        status="failed",
                    ))
                    category_scores["subtitle_sync_and_safe_zone"] -= 30.0

                if not sub_info.get("safe_zone_ok"):
                    issues.append(QAIssue(
                        check_id="QA_07_SUBTITLE_SAFE_ZONE_VIOLATION",
                        severity="major",
                        scene_id=None,
                        time_range=[0.0, ref_dur],
                        evidence=f"Vị trí phụ đề (Alignment={sub_info.get('alignment')}, MarginV={sub_info.get('margin_v')}, FontSize={sub_info.get('font_size')}) vi phạm vùng an toàn UI TikTok/Shorts.",
                        suggested_fix="Đặt Alignment=2, MarginV=260 (video dọc) và FontSize=44.",
                        confidence=1.0,
                        status="failed",
                    ))
                    category_scores["subtitle_sync_and_safe_zone"] -= 30.0

    from src.flow_browser_service import is_valid_production_image

    for idx, sc in enumerate(scenes or [], start=1):
        if not isinstance(sc, dict):
            continue
        sc_id = sc.get("scene_id") or f"sc_{idx:03d}"
        t_range = list(sc.get("timeline_range") or [0.0, 5.0])
        if not sc.get("use_video_ai"):
            img_p = str(sc.get("image_path") or sc.get("asset_path") or "")
            if img_p and os.path.exists(img_p):
                try:
                    from PIL import Image
                    with Image.open(img_p) as im:
                        w_im, h_im = im.size
                        if w_im >= 180 and h_im >= 180 and not is_valid_production_image(img_p):
                            issues.append(QAIssue(
                                check_id="QA_08_PLACEHOLDER_OR_MONOCHROME_IMAGE",
                                severity="critical",
                                scene_id=sc_id,
                                time_range=t_range,
                                evidence=f"Ảnh phân cảnh {idx} ({img_p}) là ảnh xám đơn sắc hoặc placeholder lỗi.",
                                suggested_fix=f"Sinh lại ảnh 2D hoạt hình màu sắc đầy đủ cho cảnh {idx}.",
                                confidence=0.98,
                                status="failed",
                            ))
                            category_scores["visual_defects_and_continuity"] = 0.0
                except Exception:
                    pass

    if vlm_frame_evaluator is not None and probe.get("decodable"):
        try:
            vlm_res = vlm_frame_evaluator(video_path, scenes)
            for v_issue in vlm_res.get("issues", []):
                issues.append(QAIssue(**v_issue))
        except Exception as exc:
            issues.append(QAIssue(
                check_id="QA_08_SEMANTIC_VISUAL_ALIGNMENT",
                severity="info",
                scene_id=None,
                time_range=[0.0, expected_total_dur],
                evidence=f"Bộ kiểm tra VLM gặp lỗi: {exc}",
                suggested_fix="Người dùng xem preview để duyệt sự ăn khớp giữa hình ảnh và lời thoại.",
                confidence=0.0,
                status="needs_review",
            ))
    else:
        issues.append(QAIssue(
            check_id="QA_08_SEMANTIC_VISUAL_NARRATION_MATCH",
            severity="info",
            scene_id=None,
            time_range=[0.0, expected_total_dur],
            evidence="Đã kiểm tra kỹ thuật ảnh/frame, nhưng chưa có mô hình VLM cục bộ để chấm điểm ngữ nghĩa từng khung hình so với lời thoại.",
            suggested_fix="Kiểm tra trực quan trên trình phát Preview trước khi bấm Duyệt xuất bản.",
            confidence=0.0,
            status="not_checked",
        ))

    if scenes and isinstance(scenes[0], dict):
        first_narr = str(scenes[0].get("narration", "")).strip()
        if len(first_narr.split()) < 4:
            issues.append(QAIssue(
                check_id="QA_09_WEAK_HOOK",
                severity="minor",
                scene_id="sc_001",
                time_range=[0.0, float(scenes[0].get("audio_duration", 3.0))],
                evidence=f"Lời mở đầu (Hook) ở cảnh 1 quá ngắn ({len(first_narr.split())} từ): '{first_narr}'",
                suggested_fix="Viết lại câu mở đầu cảnh 1 nêu trực diện vấn đề hoặc câu hỏi gây tò mò.",
                confidence=0.88,
                status="warning",
            ))
            category_scores["hook_pacing_and_metadata"] -= 15.0

    for k in category_scores:
        category_scores[k] = round(max(0.0, min(100.0, category_scores[k])), 1)

    total_weight = sum(active_weights.values()) or 100.0
    weighted_sum = sum(category_scores[k] * active_weights[k] for k in active_weights)
    overall_score = round(weighted_sum / total_weight, 1)

    critical_count = sum(1 for i in issues if i.severity == "critical" and i.status == "failed")
    major_count = sum(1 for i in issues if i.severity == "major" and i.status == "failed")
    minor_count = sum(1 for i in issues if i.severity == "minor" and i.status in ("failed", "warning"))
    unchecked_count = sum(1 for i in issues if i.status == "not_checked")
    needs_review_count = sum(1 for i in issues if i.status == "needs_review")

    release_blocked = critical_count > 0 or overall_score < 70.0
    passed = (not release_blocked) and (major_count == 0)

    rec_stage = None
    rec_scenes: List[int] = []
    for iss in issues:
        if iss.status != "failed":
            continue
        if iss.scene_id and iss.scene_id.startswith("sc_"):
            try:
                sc_n = int(iss.scene_id.split("_")[1])
                if sc_n not in rec_scenes:
                    rec_scenes.append(sc_n)
            except Exception:
                pass
        if iss.check_id.startswith(("QA_03_DUPLICATE", "QA_04_MISSING_SCENE_VISUAL", "QA_08_PLACEHOLDER")):
            rec_stage = rec_stage or "generating_assets"
        elif iss.check_id.startswith(("QA_04_MISSING_SCENE_AUDIO", "QA_05_SILENT")):
            rec_stage = rec_stage or "tts"
        elif iss.check_id.startswith(("QA_06_", "QA_07_", "QA_01_", "QA_02_", "QA_03_", "QA_04_TRUNCATED")):
            rec_stage = rec_stage or "rendering"

    qa_report = QAReport(
        qa_id=f"qa_{uuid.uuid4().hex[:10]}",
        render_id=render_id or f"rnd_{video_sha256[:8]}",
        video_path=video_path,
        video_sha256=video_sha256,
        overall_score=overall_score,
        category_scores=category_scores,
        weights=active_weights,
        issues=[i.to_dict() for i in issues],
        critical_count=critical_count,
        major_count=major_count,
        minor_count=minor_count,
        unchecked_count=unchecked_count,
        needs_review_count=needs_review_count,
        release_blocked=release_blocked,
        passed=passed,
        revision_round=revision_round,
        max_revisions=max_revisions,
        recommended_stage_to_rerun=rec_stage,
        recommended_scenes_to_rerun=sorted(rec_scenes),
    )
    ok_contract, errs = validate_contract_boundary("qa", qa_report)
    if not ok_contract:
        raise ValueError(f"QAReport sinh ra vi phạm schema: {errs}")
    return qa_report
