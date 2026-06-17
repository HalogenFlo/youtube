# Chức năng: Quản lý tải nhạc, ghép nhạc nền, tạo file im lặng và mix nhạc nền với giọng đọc.
# Lý do tạo: Phục vụ tính năng học tiếng Anh Self-heal (xử lý xen kẽ giọng đọc, im lặng, nhạc nền thay đổi âm lượng).
# Trích dẫn: Tuân thủ yêu cầu về xử lý âm thanh trong PLAN.md và implementation_plan.md.

import os
import subprocess
import yt_dlp
from typing import Tuple, List, Dict
import src.config
from src.config import (
    DEFAULT_READING_WPM, 
    DEFAULT_PAUSE_BEFORE_SILENT,
    DEFAULT_MUSIC_VOLUME_WITH_VOICE,
    DEFAULT_MUSIC_VOLUME_SILENT_SPEAKER
)

def list_available_music() -> List[str]:
    """Quét thư mục assets/music/*.mp3 và trả về danh sách tên file."""
    music_dir = src.config.MUSIC_DIR
    if not os.path.exists(music_dir):
        return []
    return [f for f in os.listdir(music_dir) if f.lower().endswith('.mp3')]

def download_music_from_url(url: str, custom_name: str) -> Tuple[bool, str]:
    """
    Tải audio từ URL và lưu dưới dạng file MP3 vào thư mục assets/music.
    """
    music_dir = src.config.MUSIC_DIR
    if not custom_name:
        custom_name = "downloaded_music"
    
    # Đảm bảo tên file an toàn
    safe_name = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in custom_name])
    output_filename = f"{safe_name}.mp3"
    output_path = os.path.join(music_dir, output_filename)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(music_dir, safe_name + '.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
            if os.path.exists(output_path):
                return True, output_path
            else:
                # Đôi khi yt-dlp lưu với tên file hơi khác, tìm kiếm file mp3 tương tự
                base_path = os.path.join(music_dir, safe_name)
                for f in os.listdir(music_dir):
                    full_f = os.path.join(music_dir, f)
                    if full_f.startswith(base_path) and f.endswith(".mp3"):
                        return True, full_f
                return False, "Không tìm thấy file MP3 sau khi tải."
    except Exception as e:
        return False, f"Lỗi tải nhạc: {str(e)}"


def create_silence(duration: float, output_path: str) -> Tuple[bool, str]:
    """Tạo file audio im lặng bằng FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=16000:cl=mono",
        "-t", f"{duration:.3f}",
        output_path
    ]
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            startupinfo=startupinfo,
            check=True
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path
        return False, "Không tạo được file silence."
    except Exception as e:
        return False, f"Lỗi tạo silence: {e}"

def get_audio_duration(file_path: str) -> float:
    """Lấy thời lượng (giây) của file audio bằng FFprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
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
            startupinfo=startupinfo,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 5.0

def mix_scene_audio(
    voice_path: str,
    music_path: str,
    start_time: float,
    duration: float,
    music_volume: float,
    output_path: str
) -> Tuple[bool, str]:
    """
    Mix âm thanh của một phân cảnh với nhạc nền:
    - Nhạc nền được loop vô hạn, tua đến start_time, và cắt theo duration.
    - Điều chỉnh âm lượng nhạc nền theo music_volume.
    - Mix nhạc nền với voice_path (giọng đọc hoặc silence).
    - Thời lượng đầu ra bằng đúng duration của phân cảnh.
    """
    if not os.path.exists(voice_path):
        return False, f"Không tìm thấy file voice: {voice_path}"
    if not os.path.exists(music_path):
        return False, f"Không tìm thấy file music: {music_path}"
        
    cmd = [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-ss", f"{start_time:.3f}",
        "-t", f"{duration:.3f}",
        "-stream_loop", "-1",
        "-i", music_path,
        "-filter_complex", f"[1:a]volume={music_volume:.2f}[bg];[0:a][bg]amix=inputs=2:duration=first[a]",
        "-map", "[a]",
        "-ac", "1",
        "-ar", "16000",
        output_path
    ]
    
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            startupinfo=startupinfo,
            check=True
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path
        return False, "Tạo file mixed cho scene thất bại."
    except Exception as e:
        return False, f"Lỗi mix_scene_audio: {e}"

def concat_audio_segments(segments: List[str], output_path: str) -> Tuple[bool, str]:
    """Nối nhiều file audio cùng định dạng thành một file duy nhất bằng FFmpeg concat filter."""
    if not segments:
        return False, "Danh sách segments rỗng."
        
    if len(segments) == 1:
        import shutil
        try:
            shutil.copy(segments[0], output_path)
            return True, output_path
        except Exception as e:
            return False, f"Lỗi sao chép file: {e}"
            
    cmd = ["ffmpeg", "-y"]
    for seg in segments:
        cmd.extend(["-i", seg])
        
    inputs_str = "".join([f"[{i}:a]" for i in range(len(segments))])
    filter_str = f"{inputs_str}concat=n={len(segments)}:v=0:a=1[a]"
    
    cmd.extend([
        "-filter_complex", filter_str,
        "-map", "[a]",
        output_path
    ])
    
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            startupinfo=startupinfo,
            check=True
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path
        return False, "Nối audio thất bại."
    except Exception as e:
        return False, f"Lỗi concat_audio_segments: {e}"

def build_mixed_audio_track(
    scenes: List[Dict],
    speaker_config: Dict[str, Dict],
    music_path: str,
    temp_dir: str,
    output_path: str,
    wpm: int = DEFAULT_READING_WPM,
    pause_before_silent: float = DEFAULT_PAUSE_BEFORE_SILENT
) -> Tuple[bool, str]:
    """
    Tạo audio track hoàn chỉnh từ nhiều scene xen kẽ có/không giọng:
    1. Scene có giọng → dùng file TTS audio
    2. Scene không giọng → tạo silence với duration = WPM timing + pause
    3. Nối tất cả segments theo thứ tự
    4. Overlay nhạc nền lên toàn bộ (volume tự điều chỉnh: nhỏ khi có giọng, lớn hơn khi silence)
    """
    mixed_segments = []
    current_time = 0.0
    
    os.makedirs(temp_dir, exist_ok=True)
    
    for i, scene in enumerate(scenes):
        speaker = scene.get("speaker", "Narrator")
        cfg = speaker_config.get(speaker, {"has_voice": True})
        has_voice = cfg.get("has_voice", True)
        
        scene_mixed_path = os.path.join(temp_dir, f"scene_{i}_mixed.wav")
        
        if has_voice:
            tts_path = scene.get("tts_audio_path")
            if not tts_path or not os.path.exists(tts_path):
                return False, f"Không tìm thấy file TTS cho phân cảnh {i+1}."
                
            duration = get_audio_duration(tts_path)
            if duration <= 0:
                duration = 5.0
                
            vol = DEFAULT_MUSIC_VOLUME_WITH_VOICE
            success, _ = mix_scene_audio(tts_path, music_path, current_time, duration, vol, scene_mixed_path)
            if not success:
                return False, f"Lỗi mix phân cảnh {i+1}"
                
            mixed_segments.append(scene_mixed_path)
            scene["duration"] = duration
            scene["start_time"] = current_time
            current_time += duration
        else:
            # Tính thời lượng từ số từ
            words_count = len(scene.get("narration", "").split())
            reading_duration = (words_count / wpm) * 60.0
            duration = pause_before_silent + reading_duration
            
            silence_path = os.path.join(temp_dir, f"scene_{i}_silence.wav")
            success, _ = create_silence(duration, silence_path)
            if not success:
                return False, f"Lỗi tạo silence cho phân cảnh {i+1}"
                
            vol = DEFAULT_MUSIC_VOLUME_SILENT_SPEAKER
            success, _ = mix_scene_audio(silence_path, music_path, current_time, duration, vol, scene_mixed_path)
            if not success:
                return False, f"Lỗi mix phân cảnh {i+1} (im lặng)"
                
            mixed_segments.append(scene_mixed_path)
            scene["duration"] = duration
            scene["start_time"] = current_time
            current_time += duration
            
    success, _ = concat_audio_segments(mixed_segments, output_path)
    if not success:
        return False, "Không thể ghép nối âm thanh các phân cảnh."
        
    return True, output_path


def list_available_backgrounds() -> List[str]:
    """Quét thư mục assets/backgrounds và trả về danh sách tên file video/ảnh nền."""
    backgrounds_dir = src.config.BACKGROUNDS_DIR
    if not os.path.exists(backgrounds_dir):
        return []
    valid_exts = ('.mp4', '.png', '.jpg', '.jpeg', '.webp', '.bmp')
    return [f for f in os.listdir(backgrounds_dir) if f.lower().endswith(valid_exts)]


def download_background_from_url(url: str, custom_name: str) -> Tuple[bool, str]:
    """
    Tải video nền từ URL và lưu dưới dạng file MP4 vào thư mục assets/backgrounds.
    """
    backgrounds_dir = src.config.BACKGROUNDS_DIR
    if not custom_name:
        custom_name = "downloaded_background"
    
    # Đảm bảo tên file an toàn
    safe_name = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in custom_name])
    output_filename = f"{safe_name}.mp4"
    output_path = os.path.join(backgrounds_dir, output_filename)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(backgrounds_dir, safe_name + '.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
            if os.path.exists(output_path):
                return True, output_path
            else:
                # Tìm file mp4 cùng tên
                base_path = os.path.join(backgrounds_dir, safe_name)
                for f in os.listdir(backgrounds_dir):
                    full_f = os.path.join(backgrounds_dir, f)
                    if full_f.startswith(base_path) and f.endswith(".mp4"):
                        return True, full_f
                return False, "Không tìm thấy file MP4 sau khi tải."
    except Exception as e:
        return False, f"Lỗi tải video nền: {str(e)}"


def download_background_asset(url: str, custom_name: str) -> Tuple[bool, str]:
    """
    Tải video hoặc hình ảnh nền từ URL.
    Nếu là link ảnh trực tiếp -> tải bằng requests.
    Nếu là link video (YouTube...) -> tải bằng yt-dlp.
    """
    import requests
    backgrounds_dir = src.config.BACKGROUNDS_DIR
    if not custom_name:
        custom_name = "downloaded_bg"
        
    safe_name = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in custom_name])
    
    # 1. Kiểm tra xem có phải link ảnh trực tiếp không
    is_image = False
    ext = ""
    url_lower = url.lower().split("?")[0]
    for image_ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        if url_lower.endswith(image_ext):
            is_image = True
            ext = image_ext
            break
            
    if not is_image:
        # Gửi request HEAD nhanh để kiểm tra content-type
        try:
            r = requests.head(url, timeout=5, allow_redirects=True)
            content_type = r.headers.get("content-type", "").lower()
            if "image" in content_type:
                is_image = True
                # Lấy extension từ content-type
                if "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"
                elif "bmp" in content_type:
                    ext = ".bmp"
                else:
                    ext = ".jpg"
        except Exception:
            pass
            
    if is_image:
        # Tải ảnh trực tiếp bằng requests
        if not ext:
            ext = ".jpg"
        output_path = os.path.join(backgrounds_dir, f"{safe_name}{ext}")
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return True, output_path
            return False, f"Không thể tải ảnh. Mã lỗi HTTP: {r.status_code}"
        except Exception as e:
            return False, f"Lỗi tải ảnh trực tiếp: {str(e)}"
    else:
        # Tải video bằng yt-dlp
        return download_background_from_url(url, custom_name)

