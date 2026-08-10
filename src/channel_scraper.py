# Chức năng: Quét và trích xuất danh sách toàn bộ video Shorts / Videos từ kênh YouTube.
# Lý do tạo: Phục vụ chức năng cày view tự động theo danh sách kênh mà không cần nhập từng link thủ công.
# Trích dẫn: Sử dụng thư viện yt-dlp với flat-playlist extraction để tối ưu tốc độ.

import os
import json
import re
from typing import List, Dict, Any, Tuple, Optional
import yt_dlp
from src.config import TEMP_DIR

CACHE_DIR = os.path.join(TEMP_DIR, "channel_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Loại bỏ các ký tự đặc biệt để làm tên file hợp lệ."""
    return re.sub(r'[\\/*?:"<>|@]', "_", name).strip()


def normalize_channel_url(channel_url: str, mode: str = "shorts") -> str:
    """
    Chuẩn hóa URL kênh sang tab tương ứng (ví dụ: shorts hoặc videos).
    """
    clean_url = channel_url.strip().rstrip("/")
    if mode == "shorts":
        if not clean_url.endswith("/shorts"):
            return f"{clean_url}/shorts"
    elif mode == "videos":
        if not clean_url.endswith("/videos"):
            return f"{clean_url}/videos"
    return clean_url


def get_channel_cache_path(channel_url: str) -> str:
    """Tạo đường dẫn file cache cho một kênh."""
    safe_name = sanitize_filename(channel_url.replace("https://", "").replace("http://", "").replace("www.youtube.com/", ""))
    return os.path.join(CACHE_DIR, f"{safe_name}.json")


def load_cached_shorts(channel_url: str) -> Optional[List[Dict[str, Any]]]:
    """Tải danh sách video từ cache nếu tồn tại."""
    cache_path = get_channel_cache_path(channel_url)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            return None
    return None


def save_cached_shorts(channel_url: str, videos: List[Dict[str, Any]]) -> None:
    """Lưu danh sách video vào cache JSON."""
    cache_path = get_channel_cache_path(channel_url)
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(videos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Scraper] Không thể ghi cache {cache_path}: {e}")


def extract_channel_videos(
    channel_url: str,
    mode: str = "shorts",
    max_results: int = 5000,
    force_refresh: bool = False
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Trích xuất danh sách video (Shorts hoặc video thường) từ kênh YouTube.
    
    Args:
        channel_url: Link kênh (ví dụ: https://www.youtube.com/@ChannelName)
        mode: 'shorts' hoặc 'videos'
        max_results: Giới hạn số lượng video lấy về (tối đa)
        force_refresh: Bỏ qua cache để quét mới
        
    Returns:
        (Success, list_of_videos, error_message)
        Mỗi phần tử video: {'id': str, 'title': str, 'url': str, 'duration': float}
    """
    target_url = normalize_channel_url(channel_url, mode)
    
    # Kiểm tra cache trước
    if not force_refresh:
        cached = load_cached_shorts(target_url)
        if cached:
            return True, cached[:max_results], ""

    ydl_opts = {
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'playlistend': max_results,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            if not info:
                return False, [], "Không thể trích xuất thông tin từ kênh YouTube này."
            
            entries = info.get('entries', [])
            if not entries:
                return False, [], "Không tìm thấy video/Shorts nào trên kênh đã cung cấp."

            results: List[Dict[str, Any]] = []
            for entry in entries:
                if not entry:
                    continue
                
                vid_id = entry.get('id', '')
                if not vid_id:
                    continue
                
                title = entry.get('title', f"Video {vid_id}")
                duration = float(entry.get('duration') or 0)
                
                if mode == "shorts":
                    url = f"https://www.youtube.com/shorts/{vid_id}"
                else:
                    url = f"https://www.youtube.com/watch?v={vid_id}"

                results.append({
                    "id": vid_id,
                    "title": title,
                    "url": url,
                    "duration": duration,
                    "channel_title": info.get('channel') or info.get('uploader') or ""
                })

            if not results:
                return False, [], "Không tìm thấy video hợp lệ nào."

            # Lưu lại cache
            save_cached_shorts(target_url, results)
            return True, results, ""

    except Exception as e:
        return False, [], f"Lỗi khi quét kênh YouTube: {str(e)}"
