# Chức năng: Ghép nối hình ảnh, video clip, âm thanh và phụ đề ASS thành video hoàn chỉnh sử dụng MoviePy và FFmpeg.
# Lý do tạo: Tự động hoá khâu biên tập video, áp dụng hiệu ứng chuyển động và xử lý chia nhỏ video khi quá giới hạn.
# Trích dẫn: Sử dụng MoviePy kết hợp gọi FFmpeg CLI qua subprocess để burn phụ đề.

import os
import gc
import subprocess
from typing import List, Dict, Any, Tuple
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    try:
        PIL.Image.ANTIALIAS = getattr(PIL.Image.Resampling, "LANCZOS", getattr(PIL.Image, "LANCZOS", None))
    except Exception:
        pass

from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx
from src.config import TEMP_DIR, OUTPUT_DIR, DEFAULT_FPS, FONT_PATH
from src.subtitle_builder import build_ass_subtitle
from src.visual_beats import apply_visual_beat_motion

# Vá lỗi Moviepy decorator use_clip_fps_by_default làm mất fps trên Python 3.12
try:
    import moviepy.video.VideoClip as _mpy_vc
    _orig_ffmpeg_write = _mpy_vc.ffmpeg_write_video
    def _safe_ffmpeg_write_video(clip, filename, fps, codec="libx264", **kw):
        actual_fps = fps or getattr(clip, "fps", None) or 30
        return _orig_ffmpeg_write(clip, filename, actual_fps, codec=codec, **kw)
    _mpy_vc.ffmpeg_write_video = _safe_ffmpeg_write_video
except Exception:
    pass

def apply_ken_burns(image_path: str, duration: float, orientation: str) -> ImageClip:
    """
    Tạo ImageClip từ ảnh và áp dụng hiệu ứng Ken Burns (zoom-in chậm).
    Đồng thời resize ảnh về kích thước chuẩn của video.
    """
    # Kích thước chuẩn
    target_w, target_h = (480, 848) if orientation == "vertical" else (848, 480)
    
    # Tạo clip từ ảnh tĩnh
    clip = ImageClip(image_path).set_duration(duration)
    
    # Resize về kích thước chuẩn trước khi áp dụng hiệu ứng
    clip = clip.resize(newsize=(target_w, target_h))
    
    # Hiệu ứng Ken Burns: Zoom-in nhẹ từ 1.0 đến 1.12
    # Dùng hàm resize động dựa theo thời gian t
    zoom_fn = lambda t: 1.0 + 0.12 * (t / duration)
    clip_zoom = clip.resize(zoom_fn)
    
    # Cắt lại clip về kích thước chuẩn (crop trung tâm sau khi zoom)
    clip_final = clip_zoom.crop(x_center=clip_zoom.w/2, y_center=clip_zoom.h/2, width=target_w, height=target_h)
    
    return clip_final

def process_video_clip(video_path: str, duration: float, orientation: str) -> VideoFileClip:
    """
    Load video clip Wan 2.1, resize về kích thước chuẩn và đồng bộ thời lượng với audio.
    """
    target_w, target_h = (480, 848) if orientation == "vertical" else (848, 480)
    
    clip = VideoFileClip(video_path)
    
    # Resize về kích thước chuẩn
    clip = clip.resize(newsize=(target_w, target_h))
    
    # Đồng bộ thời lượng (MoviePy tự động freeze frame cuối nếu set_duration dài hơn thời lượng gốc)
    clip = clip.set_duration(duration)
    
    return clip

def burn_subtitles(video_in: str, ass_path: str, video_out: str, part_num: int = 0, total_parts: int = 0) -> Tuple[bool, str]:
    """
    Sử dụng FFmpeg CLI để burn phụ đề ASS lên video và thêm watermark phân phần (nếu có).
    Sử dụng relative path cho file ASS để tránh lỗi escape ký tự ổ đĩa trên Windows.
    """
    if not os.path.exists(video_in):
        return False, f"Không tìm thấy file video nguồn: {video_in}"
    if not os.path.exists(ass_path):
        return False, f"Không tìm thấy file phụ đề: {ass_path}"

    # Chuyển đổi đường dẫn tuyệt đối sang tương đối hoặc chuẩn hóa dấu gạch chéo cho FFmpeg
    # FFmpeg filter ass trên Windows yêu cầu dấu gạch chéo xuôi '/' và escape dấu ':'
    # Cách an toàn nhất là di chuyển/copy file ASS về thư mục làm việc hiện tại và dùng tên tương đối.
    # Hoặc chuẩn hóa đường dẫn tuyệt đối:
    norm_ass_path = ass_path.replace("\\", "/")
    if ":" in norm_ass_path:
        # Thay thế C:/path thành C\\:/path
        drive, path = norm_ass_path.split(":", 1)
        norm_ass_path = f"{drive}\\:{path}"
        
    # Tạo video filter
    vf_filters = [f"ass='{norm_ass_path}'"]
    
    # Thêm watermark phần nếu chia làm nhiều phần
    if total_parts > 1 and part_num > 0:
        watermark_text = f"Phần {part_num}/{total_parts}"
        # Filter drawtext để vẽ chữ lên video
        # Fontfile chỉ định dùng Montserrat-Bold.ttf
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
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",            # Chất lượng cao
        "-c:a", "aac",           # Re-encode audio sang AAC để tương thích tốt
        "-b:a", "192k",
        video_out
    ]
    
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            startupinfo=startupinfo,
            check=True
        )
        if os.path.exists(video_out) and os.path.getsize(video_out) > 0:
            return True, video_out
        else:
            return False, "FFmpeg chạy thành công nhưng không tạo ra video output hoặc file trống."
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg burn phụ đề thất bại: {e.stderr}"

def split_scenes_into_parts(
    scenes: List[Dict[str, Any]], 
    max_duration: float
) -> List[List[Dict[str, Any]]]:
    """
    Chia danh sách phân cảnh thành các nhóm (mỗi nhóm đại diện cho 1 phần video)
    sao cho thời lượng mỗi nhóm không vượt quá max_duration.
    """
    parts = []
    current_part = []
    current_duration = 0.0
    
    for scene in scenes:
        scene_dur = scene.get("audio_duration", 5.0)
        
        # Nếu thêm scene này vào vượt quá giới hạn và phần hiện tại đã có kịch bản
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

def compile_video_pipeline(
    scenes: List[Dict[str, Any]],
    words_timestamps: List[Dict[str, Any]],
    max_duration: float = 60.0,
    orientation: str = "vertical"
) -> Tuple[bool, List[str], str]:
    """
    Pipeline hoàn chỉnh biên tập video:
    1. Phân chia các phân cảnh thành các phần dựa trên max_duration.
    2. Gom nhóm word-level timestamps tương ứng với từng phần.
    3. Biên tập video thô bằng MoviePy.
    4. Tạo file ASS karaoke cho từng phần (reset timestamp về 0s).
    5. Burn phụ đề và watermark bằng FFmpeg.
    Trả về: (Success, list_of_final_video_paths, error_message)
    """
    temp_files = []
    final_videos = []
    
    try:
        # 1. Chia nhỏ phân cảnh
        parts_scenes = split_scenes_into_parts(scenes, max_duration)
        total_parts = len(parts_scenes)
        
        # Biến đếm vị trí từ trong words_timestamps
        word_idx = 0
        cumulative_time = 0.0 # Thời gian tích lũy toàn bộ kịch bản
        
        for part_idx, part_scenes in enumerate(parts_scenes):
            part_num = part_idx + 1
            print(f"--- Đang xử lý Phần {part_num}/{total_parts} ---")
            
            # Tính thời lượng phần hiện tại
            part_duration = sum(s.get("audio_duration", 5.0) for s in part_scenes)
            part_start_time = cumulative_time
            part_end_time = part_start_time + part_duration
            
            # 2. Gom nhóm từ thuộc phần này và reset mốc thời gian về 0s
            part_words = []
            while word_idx < len(words_timestamps):
                word = words_timestamps[word_idx]
                # Nếu từ nằm trong khoảng thời gian của phần này
                if word["start"] < part_end_time + 0.1: # Thêm sai số nhỏ
                    # Dịch chuyển mốc thời gian về 0s
                    shifted_word = {
                        "word": word["word"],
                        "start": max(0.0, word["start"] - part_start_time),
                        "end": max(0.0, word["end"] - part_start_time)
                    }
                    part_words.append(shifted_word)
                    word_idx += 1
                else:
                    break
            
            # 3. Tạo các clip phân cảnh bằng MoviePy
            scene_clips = []
            current_scene_start = 0.0
            
            for scene in part_scenes:
                audio_path = scene.get("audio_path", "")
                audio_dur = scene.get("audio_duration", 5.0)
                
                # Load audio
                if audio_path and os.path.exists(audio_path):
                    audio_clip = AudioFileClip(audio_path)
                else:
                    # Fallback nếu không có audio
                    audio_clip = None
                
                # Load hình ảnh hoặc video
                visual_clip = None
                if scene.get("use_video_ai", False):
                    video_path = scene.get("video_path", "")
                    if video_path and os.path.exists(video_path):
                        visual_clip = process_video_clip(video_path, audio_dur, orientation)
                else:
                    image_path = scene.get("image_path", "")
                    if image_path and os.path.exists(image_path):
                        try:
                            visual_clip = apply_visual_beat_motion(image_path, audio_dur, orientation)
                        except Exception as e:
                            print(f"[WARNING] Lỗi apply_visual_beat_motion, fallback Ken Burns: {e}")
                            visual_clip = apply_ken_burns(image_path, audio_dur, orientation)
                
                # Nếu không load được tài nguyên nào, tạo clip đen làm fallback
                if visual_clip is None:
                    target_w, target_h = (480, 848) if orientation == "vertical" else (848, 480)
                    # Tạo clip màu đen
                    from moviepy.video.VideoClip import ColorClip
                    visual_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=audio_dur)
                
                # Gán audio vào visual clip
                if audio_clip:
                    visual_clip = visual_clip.set_audio(audio_clip)
                    
                scene_clips.append(visual_clip)
                current_scene_start += audio_dur
            
            # Nối các phân cảnh của phần này
            if not scene_clips:
                continue
                
            print(f"Đang kết nối các clip cho Phần {part_num}...")
            # Sử dụng method="compose" để ghép các clip chuẩn xác
            part_video_raw = concatenate_videoclips(scene_clips, method="compose")
            
            # Xuất video thô
            raw_output_path = os.path.join(TEMP_DIR, f"part_{part_num}_raw.mp4")
            temp_files.append(raw_output_path)
            
            print(f"Đang render video thô cho Phần {part_num}...")
            part_video_raw.write_videofile(
                raw_output_path,
                fps=DEFAULT_FPS,
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None
            )
            
            # Đóng các clip để giải phóng bộ nhớ
            part_video_raw.close()
            for c in scene_clips:
                c.close()
            
            # 4. Tạo phụ đề ASS cho phần này
            ass_path = os.path.join(TEMP_DIR, f"part_{part_num}.ass")
            temp_files.append(ass_path)
            build_ass_subtitle(part_words, ass_path, orientation)
            
            # 5. Burn phụ đề bằng FFmpeg
            final_output_path = os.path.join(
                OUTPUT_DIR, 
                f"video_final_part{part_num}.mp4" if total_parts > 1 else "video_final.mp4"
            )
            print(f"Đang burn phụ đề cho Phần {part_num}...")
            success, burn_err = burn_subtitles(
                raw_output_path, 
                ass_path, 
                final_output_path, 
                part_num, 
                total_parts
            )
            
            if not success:
                return False, [], f"Lỗi ở khâu burn phụ đề Phần {part_num}: {burn_err}"
                
            final_videos.append(final_output_path)
            cumulative_time += part_duration
            
        return True, final_videos, ""
        
    except Exception as e:
        return False, [], f"Lỗi trong quá trình compile video: {str(e)}"
    finally:
        # Xóa các file tạm nếu muốn giữ sạch sẽ (ở đây giữ lại trong temp để debug nếu cần, hoặc xóa)
        # Để đảm bảo dọn dẹp RAM
        gc.collect()
