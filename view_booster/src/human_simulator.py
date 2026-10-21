# Chức năng: Mô phỏng các hành vi tự nhiên của người dùng thật (đường cong chuột Bezier, scroll tự nhiên, delay Gaussian, tỉ lệ xem 60-100%, pause/resume).
# Lý do tạo: Vượt qua các mô hình máy học (ML) nhận diện hành vi bot của YouTube.
# Trích dẫn: Sử dụng thuật toán đường cong Bezier bậc 3 (Cubic Bezier) và phân phối chuẩn Gaussian.

import random
import time
import asyncio
from typing import Dict, Any, Tuple, List
from fake_useragent import UserAgent

try:
    ua_generator = UserAgent(platforms=['pc'], browsers=['chrome', 'edge'])
except Exception:
    ua_generator = None


def get_random_user_agent() -> str:
    """Trả về một User-Agent ngẫu nhiên của Chrome/Edge trên máy tính."""
    fallback = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    if ua_generator:
        try:
            return ua_generator.random
        except Exception:
            return fallback
    return fallback


def get_random_viewport() -> Tuple[int, int]:
    """Trả về kích thước màn hình phổ biến ngẫu nhiên."""
    resolutions = [
        (1920, 1080),
        (1366, 768),
        (1536, 864),
        (1440, 900),
        (1280, 720),
        (1600, 900)
    ]
    return random.choice(resolutions)


def get_gaussian_delay(min_sec: float, max_sec: float) -> float:
    """
    Sinh thời gian chờ ngẫu nhiên theo phân phối Gaussian (chuẩn hóa),
    giúp phân bổ delay trông tự nhiên hơn nhiều so với phân phối đều (uniform).
    """
    mean = (min_sec + max_sec) / 2.0
    stddev = max((max_sec - min_sec) / 6.0, 0.2)
    val = random.gauss(mean, stddev)
    return max(min_sec, min(val, max_sec))


async def async_random_sleep(min_sec: float, max_sec: float) -> float:
    """Tạm dừng async trong khoảng ngẫu nhiên."""
    delay = get_gaussian_delay(min_sec, max_sec)
    await asyncio.sleep(delay)
    return delay


def sync_random_sleep(min_sec: float, max_sec: float) -> float:
    """Tạm dừng sync trong khoảng ngẫu nhiên."""
    delay = get_gaussian_delay(min_sec, max_sec)
    time.sleep(delay)
    return delay


def decide_watch_duration(
    video_duration: float,
    min_sec: float = 8.0,
    max_sec: float = 55.0,
    replay_prob: float = 0.25
) -> Dict[str, Any]:
    """
    Tính toán thời gian xem tối ưu cho 1 video/Short:
    - Nếu có duration: xem ngẫu nhiên 60% - 100% thời lượng.
    - Quyết định có xem lại (replay) hay không.
    """
    if video_duration <= 0:
        target_sec = get_gaussian_delay(min_sec, max_sec)
    else:
        # Xem từ 60% đến 100% thời lượng video
        ratio = random.uniform(0.60, 1.0)
        target_sec = max(min_sec, min(video_duration * ratio, max_sec))

    is_replay = (random.random() < replay_prob)
    total_watch_time = target_sec * (1.8 if is_replay else 1.0)

    return {
        "watch_seconds": round(target_sec, 1),
        "is_replay": is_replay,
        "total_watch_time": round(total_watch_time, 1)
    }


def should_skip(skip_prob: float = 0.06) -> bool:
    """
    Mô phỏng xác suất người dùng lướt qua video sớm (5-8%) để tạo tính tự nhiên.
    """
    return random.random() < skip_prob


def should_pause_and_resume(pause_prob: float = 0.08) -> bool:
    """
    Mô phỏng xác suất người dùng tạm dừng (pause) vài giây rồi xem tiếp.
    """
    return random.random() < pause_prob


def generate_bezier_points(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    num_points: int = 12
) -> List[Tuple[int, int]]:
    """
    Tạo chuỗi tọa độ mô phỏng di chuyển chuột tự nhiên bằng đường cong Cubic Bezier.
    """
    ctrl1_x = start_x + (end_x - start_x) * random.uniform(0.1, 0.4) + random.randint(-50, 50)
    ctrl1_y = start_y + (end_y - start_y) * random.uniform(0.1, 0.4) + random.randint(-50, 50)
    ctrl2_x = start_x + (end_x - start_x) * random.uniform(0.6, 0.9) + random.randint(-50, 50)
    ctrl2_y = start_y + (end_y - start_y) * random.uniform(0.6, 0.9) + random.randint(-50, 50)

    points = []
    for i in range(num_points + 1):
        t = i / float(num_points)
        x = (1-t)**3 * start_x + 3*(1-t)**2*t * ctrl1_x + 3*(1-t)*t**2 * ctrl2_x + t**3 * end_x
        y = (1-t)**3 * start_y + 3*(1-t)**2*t * ctrl1_y + 3*(1-t)*t**2 * ctrl2_y + t**3 * end_y
        points.append((int(x), int(y)))
    return points


def get_random_scroll_js(min_px: int = 100, max_px: int = 400) -> str:
    """Tạo đoạn mã JS thực hiện cuộn nhẹ trang ngẫu nhiên."""
    px = random.randint(min_px, max_px) * (1 if random.random() > 0.3 else -1)
    return f"window.scrollBy({{ top: {px}, behavior: 'smooth' }});"
