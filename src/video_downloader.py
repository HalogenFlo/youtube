# Chức năng: Tải video từ URL (YouTube/TikTok...) bằng yt-dlp và tách audio 16kHz mono bằng FFmpeg.
# Lý do tạo: Phục vụ luồng Remake video (tải video nguồn để transcribe và viết lại kịch bản).
# Trích dẫn: Sử dụng thư viện yt-dlp và gọi FFmpeg qua subprocess.

import os
import subprocess
import yt_dlp
from typing import Tuple
from src.config import DOWNLOAD_DIR

def extract_audio(video_path: str, audio_path: str) -> Tuple[bool, str]:
    """
    Sử dụng FFmpeg để tách âm thanh từ video sang định dạng WAV 16kHz mono.
    """
    if not os.path.exists(video_path):
        return False, f"Không tìm thấy file video nguồn: {video_path}"
        
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                   # Bỏ video
        "-acodec", "pcm_s16le",  # Định dạng PCM 16-bit
        "-ar", "16000",          # Sample rate 16kHz (Whisper tối ưu)
        "-ac", "1",              # Mono channel
        audio_path
    ]
    
    try:
        # Chạy FFmpeg lệnh ẩn không hiện cửa sổ console trên Windows
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
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            return True, audio_path
        else:
            return False, "FFmpeg chạy thành công nhưng không tạo ra file audio hoặc file trống."
    except FileNotFoundError:
        return False, "Không tìm thấy FFmpeg trên hệ thống. Hãy chắc chắn FFmpeg đã được cài đặt và thêm vào PATH."
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg gặp lỗi khi chuyển đổi: {e.stderr}"

def download_and_extract(url: str) -> Tuple[bool, str, str, str]:
    """
    Tải video từ URL và tách âm thanh.
    Trả về: (Success, video_path, audio_path, error_message)
    """
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'cookiesfrombrowser': ('chrome', 'edge'),
    }

    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Lấy thông tin metadata và tải video
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)
            
            # Nếu vì lý do nào đó extension thay đổi (ví dụ: mkv, webm)
            # Ta cần cập nhật lại đường dẫn thực tế tồn tại
            if not os.path.exists(video_path):
                # Thử tìm file cùng tên cơ bản trong thư mục
                base_name = os.path.splitext(video_path)[0]
                for f in os.listdir(DOWNLOAD_DIR):
                    full_f = os.path.join(DOWNLOAD_DIR, f)
                    if full_f.startswith(base_name) and os.path.isfile(full_f):
                        video_path = full_f
                        break
            
            if not os.path.exists(video_path):
                return False, "", "", "Tải video thành công nhưng không xác định được đường dẫn file tải về."
                
            # Đặt đường dẫn file audio output
            video_dir, video_file = os.path.split(video_path)
            video_name, _ = os.path.splitext(video_file)
            audio_path = os.path.join(video_dir, f"{video_name}.wav")
            
            # Trích xuất audio
            success, audio_err = extract_audio(video_path, audio_path)
            if not success:
                return False, video_path, "", f"Tải video thành công nhưng không thể tách audio: {audio_err}"
                
            return True, video_path, audio_path, ""
            
    except yt_dlp.utils.DownloadError as e:
        return False, "", "", f"Lỗi tải video từ yt-dlp: {str(e)}"
    except Exception as e:
        return False, "", "", f"Lỗi không xác định khi tải video: {str(e)}"

def download_douyin_video(url: str, output_dir: str = DOWNLOAD_DIR) -> Tuple[bool, str, str, str]:
    """
    Tải video Douyin/TikTok sử dụng cookie trình duyệt tự động và User-Agent máy tính để bypass chặn.
    Trả về: (Success, video_path, audio_path, error_message)
    """
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        # Trích xuất cookie từ Chrome và Edge đã cài đặt trên máy người dùng để vượt qua xác thực
        'cookiesfrombrowser': ('chrome', 'edge'),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Referer': 'https://www.douyin.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)
            
            if not os.path.exists(video_path):
                base_name = os.path.splitext(video_path)[0]
                for f in os.listdir(output_dir):
                    full_f = os.path.join(output_dir, f)
                    if full_f.startswith(base_name) and os.path.isfile(full_f):
                        video_path = full_f
                        break
            
            if not os.path.exists(video_path):
                return False, "", "", "Tải video Douyin thành công nhưng không tìm thấy file."
                
            video_dir, video_file = os.path.split(video_path)
            video_name, _ = os.path.splitext(video_file)
            audio_path = os.path.join(video_dir, f"{video_name}.wav")
            
            success, audio_err = extract_audio(video_path, audio_path)
            if not success:
                return False, video_path, "", f"Tải video thành công nhưng không thể tách audio: {audio_err}"
                
            return True, video_path, audio_path, ""
            
    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e)
        return False, "", "", (
            f"Không thể tải video từ link Douyin/TikTok do cơ chế chặn của nền tảng.\n"
            f"Chi tiết lỗi: {err_msg}\n\n"
            f"💡 Gợi ý:\n"
            f"1. Hãy đảm bảo bạn đã đăng nhập Douyin/TikTok trên một trong các trình duyệt (Chrome, Edge, Firefox) trên máy tính này.\n"
            f"2. Bạn cũng có thể nâng cấp thư viện tải bằng lệnh: pip install -U yt-dlp\n"
            f"3. Nếu vẫn không được, hãy tải thủ công video về máy và chọn tính năng 'Upload file từ máy tính' trên giao diện."
        )
    except Exception as e:
        return False, "", "", f"Lỗi không xác định khi tải video Douyin: {str(e)}"


