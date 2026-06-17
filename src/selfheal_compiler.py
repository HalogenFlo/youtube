# Chức năng: Biên dịch video học tiếng Anh Self-heal (xử lý xen kẽ giọng đọc, phụ đề song ngữ nhiều màu và ghép nhạc nền thay đổi âm lượng).
# Lý do tạo: Tách biệt pipeline biên dịch của tính năng Self-heal để giữ an toàn cho pipeline gốc không bị thay đổi.
# Trích dẫn: Tái sử dụng các helper (apply_ken_burns, process_video_clip, burn_subtitles, split_scenes_into_parts) từ video_compiler.py.

import os
import gc
import subprocess
from typing import List, Dict, Any, Tuple
from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.VideoClip import ColorClip

from src.config import TEMP_DIR, OUTPUT_DIR, DEFAULT_FPS, FONT_PATH, DEFAULT_PAUSE_BEFORE_SILENT
from src.tts_service import generate_tts
from src.whisper_service import get_word_timestamps
from src.subtitle_builder import calculate_word_timings, build_bilingual_ass_subtitle
from src.music_service import build_mixed_audio_track, get_audio_duration
from src.video_compiler import apply_ken_burns, process_video_clip, burn_subtitles, split_scenes_into_parts

def compile_selfheal_video(
    scenes: List[Dict[str, Any]],
    speaker_config: Dict[str, Dict[str, Any]],
    music_path: str,
    wpm: int,
    orientation: str,
    show_translation: bool,
    max_duration: float = 60.0,
    bg_video_path: str = None
) -> Tuple[bool, List[str], str]:
    """
    Pipeline biên dịch video Self-heal hoàn chỉnh:
    1. Sinh TTS và tính toán timing cho từng scene (có giọng / im lặng).
    2. Gom nhóm timestamps, translations và speaker segments.
    3. Phân chia các scene thành các phần dựa trên max_duration.
    4. Biên dịch từng phần riêng biệt (ghép nhạc nền, render video, burn phụ đề song ngữ).
    """
    temp_dir = os.path.join(TEMP_DIR, "selfheal_compile")
    os.makedirs(temp_dir, exist_ok=True)
    
    all_words = []
    translations = []
    speaker_segments = []
    cumulative_time = 0.0
    
    # Bước 1: Chuẩn bị âm thanh và timing cho từng scene
    try:
        for i, scene in enumerate(scenes):
            speaker = scene.get("speaker", "Narrator")
            cfg = speaker_config.get(speaker, {"has_voice": True, "voice": "", "color": "&H0000FFFF"})
            has_voice = cfg.get("has_voice", True)
            voice = cfg.get("voice", "")
            color = cfg.get("color", "&H0000FFFF")
            
            scene_start = cumulative_time
            narration = scene.get("narration", "")
            
            if has_voice:
                # Sinh TTS
                tts_path = os.path.join(temp_dir, f"scene_{i}_tts.mp3")
                print(f"[Self-heal] Đang sinh TTS cho phân cảnh {i+1} ({speaker})...")
                success, _ = generate_tts(narration or "", tts_path, voice=voice)
                if not success:
                    return False, [], f"Lỗi sinh giọng đọc cho phân cảnh {i+1}: {speaker}"
                
                # Transcribe lấy timestamps
                print(f"[Self-heal] Đang lấy timestamps Whisper cho phân cảnh {i+1}...")
                success, words_list = get_word_timestamps(tts_path, language="en")
                if not success:
                    # Fallback sang tự tính timing nếu Whisper lỗi
                    print(f"[Self-heal] Whisper lỗi, fallback tính timing tự động cho phân cảnh {i+1}.")
                    words_list = calculate_word_timings(narration, 0.0, wpm)
                
                duration = get_audio_duration(tts_path)
                if duration <= 0:
                    duration = 5.0
                
                # Dịch chuyển mốc thời gian Whisper theo timeline chung
                for w in words_list:
                    w["start"] = round(w["start"] + scene_start, 3)
                    w["end"] = round(w["end"] + scene_start, 3)
                
                scene["tts_audio_path"] = tts_path
                scene["audio_duration"] = duration
                scene["audio_path"] = tts_path  # để tương thích
                
                all_words.extend(words_list)
                
            else:
                # Không giọng (im lặng)
                words_count = len(narration.split())
                reading_duration = (words_count / wpm) * 60.0
                duration = DEFAULT_PAUSE_BEFORE_SILENT + reading_duration
                
                # Tính timings tự động
                words_start = scene_start + DEFAULT_PAUSE_BEFORE_SILENT
                words_list = calculate_word_timings(narration, words_start, wpm)
                
                scene["tts_audio_path"] = ""
                scene["audio_duration"] = duration
                scene["audio_path"] = ""
                
                all_words.extend(words_list)
                
            # Đăng ký thông tin phân cảnh
            scene["start_time"] = scene_start
            
            speaker_segments.append({
                "speaker": speaker,
                "start": scene_start,
                "end": scene_start + duration,
                "color": color
            })
            
            translations.append({
                "scene_idx": i,
                "text": scene.get("translation", ""),
                "start": scene_start,
                "end": scene_start + duration
            })
            
            cumulative_time += duration

        # Bước 2: Chia thành nhiều phần dựa theo max_duration
        parts_scenes = split_scenes_into_parts(scenes, max_duration)
        total_parts = len(parts_scenes)
        
        final_videos = []
        part_cumulative_time = 0.0
        
        for part_idx, part_scenes in enumerate(parts_scenes):
            part_num = part_idx + 1
            print(f"[Self-heal] --- Đang xử lý Phần {part_num}/{total_parts} ---")
            
            part_duration = sum(s.get("audio_duration", 5.0) for s in part_scenes)
            part_start_time = part_cumulative_time
            part_end_time = part_start_time + part_duration
            
            # Cắt các mốc từ cho phần này và dịch chuyển về 0
            part_words = []
            for w in all_words:
                if part_start_time <= w["start"] < part_end_time + 0.05:
                    part_words.append({
                        "word": w["word"],
                        "start": max(0.0, round(w["start"] - part_start_time, 3)),
                        "end": max(0.0, round(w["end"] - part_start_time, 3))
                    })
            
            # Cắt translations cho phần này và dịch chuyển
            part_translations = []
            for trans in translations:
                if trans["start"] < part_end_time + 0.05 and trans["end"] > part_start_time - 0.05:
                    part_translations.append({
                        "scene_idx": trans["scene_idx"],
                        "text": trans["text"],
                        "start": max(0.0, round(trans["start"] - part_start_time, 3)),
                        "end": max(0.0, round(trans["end"] - part_start_time, 3))
                    })
                    
            # Cắt speaker segments cho phần này và dịch chuyển
            part_speaker_segs = []
            for seg in speaker_segments:
                if seg["start"] < part_end_time + 0.05 and seg["end"] > part_start_time - 0.05:
                    part_speaker_segs.append({
                        "speaker": seg["speaker"],
                        "color": seg["color"],
                        "start": max(0.0, round(seg["start"] - part_start_time, 3)),
                        "end": max(0.0, round(seg["end"] - part_start_time, 3))
                    })

            # Tạo audio track hỗn hợp cho phần này
            mixed_audio_path = os.path.join(temp_dir, f"part_{part_num}_mixed.wav")
            print(f"[Self-heal] Đang trộn âm thanh cho Phần {part_num}...")
            success, _ = build_mixed_audio_track(
                part_scenes,
                speaker_config,
                music_path,
                os.path.join(temp_dir, f"mix_temp_{part_num}"),
                mixed_audio_path,
                wpm=wpm
            )
            if not success:
                return False, [], f"Lỗi trộn âm thanh cho Phần {part_num}."
                
            raw_video_with_audio = os.path.join(temp_dir, f"part_{part_num}_with_audio.mp4")

            # Xử lý render visual
            if bg_video_path and os.path.exists(bg_video_path):
                # SỬ DỤNG 1 VIDEO/ẢNH NỀN DUY NHẤT (Render cực nhanh bằng FFmpeg)
                target_w, target_h = (480, 848) if orientation == "vertical" else (848, 480)
                ext = os.path.splitext(bg_video_path)[1].lower()
                is_image = ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
                
                if is_image:
                    print(f"[Self-heal] Sử dụng 1 ảnh nền duy nhất: {bg_video_path}")
                    cmd_bg = [
                        "ffmpeg", "-y",
                        "-loop", "1",
                        "-i", bg_video_path,
                        "-i", mixed_audio_path,
                        "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
                        "-c:v", "libx264",
                        "-preset", "medium",
                        "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        "-t", f"{part_duration:.3f}",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        raw_video_with_audio
                    ]
                else:
                    print(f"[Self-heal] Sử dụng 1 video nền duy nhất: {bg_video_path}")
                    cmd_bg = [
                        "ffmpeg", "-y",
                        "-stream_loop", "-1",
                        "-i", bg_video_path,
                        "-i", mixed_audio_path,
                        "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
                        "-c:v", "libx264",
                        "-preset", "medium",
                        "-crf", "18",
                        "-t", f"{part_duration:.3f}",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        raw_video_with_audio
                    ]
                
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                subprocess.run(
                    cmd_bg,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    check=True
                )
            else:
                # SỬ DỤNG ẢNH/VIDEO TỪNG PHÂN CẢNH (MoviePy)
                scene_clips = []
                for scene in part_scenes:
                    scene_dur = scene.get("audio_duration", 5.0)
                    
                    visual_clip = None
                    if scene.get("use_video_ai", False):
                        video_path = scene.get("video_path", "")
                        if video_path and os.path.exists(video_path):
                            visual_clip = process_video_clip(video_path, scene_dur, orientation)
                    else:
                        image_path = scene.get("image_path", "")
                        if image_path and os.path.exists(image_path):
                            visual_clip = apply_ken_burns(image_path, scene_dur, orientation)
                            
                    if visual_clip is None:
                        target_w, target_h = (480, 848) if orientation == "vertical" else (848, 480)
                        visual_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=scene_dur)
                        
                    scene_clips.append(visual_clip)
                    
                if not scene_clips:
                    continue
                    
                print(f"[Self-heal] Đang ghép nối các clip hình ảnh cho Phần {part_num}...")
                part_video_raw = concatenate_videoclips(scene_clips, method="compose")
                
                raw_output_path = os.path.join(temp_dir, f"part_{part_num}_raw.mp4")
                
                print(f"[Self-heal] Đang xuất video thô cho Phần {part_num}...")
                part_video_raw.write_videofile(
                    raw_output_path,
                    fps=DEFAULT_FPS,
                    codec="libx264",
                    audio_codec="aac",
                    verbose=False,
                    logger=None
                )
                
                part_video_raw.close()
                for c in scene_clips:
                    c.close()
                    
                # Mux video thô với file mixed_audio bằng FFmpeg
                cmd_mux = [
                    "ffmpeg", "-y",
                    "-i", raw_output_path,
                    "-i", mixed_audio_path,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    raw_video_with_audio
                ]
                
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                subprocess.run(
                    cmd_mux,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    check=True
                )
            
            # Tạo phụ đề ASS song ngữ
            ass_path = os.path.join(temp_dir, f"part_{part_num}.ass")
            print(f"[Self-heal] Đang tạo phụ đề song ngữ ASS cho Phần {part_num}...")
            success, _ = build_bilingual_ass_subtitle(
                part_words,
                part_translations,
                part_speaker_segs,
                ass_path,
                orientation=orientation,
                show_translation=show_translation
            )
            if not success:
                return False, [], f"Tạo phụ đề ASS thất bại cho Phần {part_num}."
                
            # Burn phụ đề lên video
            final_output_path = os.path.join(
                OUTPUT_DIR, 
                f"selfheal_final_part{part_num}.mp4" if total_parts > 1 else "selfheal_final.mp4"
            )
            
            print(f"[Self-heal] Đang burn phụ đề lên video cho Phần {part_num}...")
            success, burn_err = burn_subtitles(
                raw_video_with_audio,
                ass_path,
                final_output_path,
                part_num,
                total_parts
            )
            if not success:
                return False, [], f"Lỗi burn phụ đề Phần {part_num}: {burn_err}"
                
            final_videos.append(final_output_path)
            part_cumulative_time += part_duration
            
        return True, final_videos, ""
        
    except Exception as e:
        return False, [], f"Lỗi trong quá trình compile video Self-heal: {str(e)}"
    finally:
        gc.collect()
