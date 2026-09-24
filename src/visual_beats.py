# Chức năng: Bộ điều phối Progressive Layering & Visual Beats (Diễn hoạt phân lớp theo nhịp thoại).
# Lý do tạo: Tối ưu hóa chuyển động video từ ảnh tĩnh Google Flow, khớp nhịp từng mili-giây với voiceover mà không tốn tài nguyên render Video Diffusion.
# Trích dẫn: Học hỏi từ kiến trúc Visual Beats Engine trong dự án tiktok-ytb.

from typing import List, Dict, Any, Tuple
from moviepy.editor import ImageClip
import math


def calculate_visual_beats(scene_duration: float, num_beats: int = 2) -> List[Dict[str, Any]]:
    """
    Tự động chia thời lượng phân cảnh thành các nhịp hiệu ứng (Beats).
    Ví dụ cảnh dài 6s có 2 beats:
    - Beat 0 (0s - 3s): Zoom-in (scale 1.0 -> 1.08) tập trung vào nhân vật.
    - Beat 1 (3s - 6s): Zoom-out nhẹ hoặc Pan/Slide giữ sự chú ý của người xem.
    """
    if scene_duration <= 3.0:
        return [{
            "at": 0.0,
            "duration": scene_duration,
            "effect": "zoom_in",
            "scale_range": (1.0, 1.08),
            "focus": (0.5, 0.5)
        }]

    beat_len = scene_duration / num_beats
    beats = []
    effects = ["zoom_in", "zoom_out", "slide_left"]
    
    for i in range(num_beats):
        beats.append({
            "at": i * beat_len,
            "duration": beat_len,
            "effect": effects[i % len(effects)],
            "scale_range": (1.0, 1.08) if i % 2 == 0 else (1.08, 1.0),
            "focus": (0.5, 0.45) if i == 0 else (0.5, 0.5)
        })
    return beats


def apply_visual_beat_motion(
    image_path: str,
    duration: float,
    orientation: str = "vertical",
    beats: List[Dict[str, Any]] = None
) -> ImageClip:
    """
    Áp dụng hiệu ứng Visual Beat động học mượt mà lên ảnh phân cảnh (Google Flow / SD).
    Khác với zoom tuyến tính thông thường, Visual Beat tạo cảm giác 'thở' (breathing motion)
    giúp người xem tập trung cao độ vào lời dẫn.
    """
    target_w, target_h = (1080, 1920) if orientation == "vertical" else (1920, 1080)
    
    base_clip = ImageClip(image_path).set_duration(duration)
    base_clip = base_clip.resize(newsize=(target_w, target_h))

    if not beats:
        # Chuyển động điện ảnh một chiều: zoom cực chậm từ 1.00 đến 1.03
        # Giúp khung hình sống động tự nhiên nhưng không làm giật lắc bối cảnh
        def subtle_zoom(t: float) -> float:
            progress = min(1.0, max(0.0, t / max(duration, 0.001)))
            return 1.0 + 0.03 * progress

        zoomed_clip = base_clip.resize(subtle_zoom)
        final_clip = zoomed_clip.crop(
            x_center=zoomed_clip.w / 2,
            y_center=zoomed_clip.h / 2,
            width=target_w,
            height=target_h
        )
        return final_clip

    # Trường hợp có custom beats chỉ định
    def dynamic_zoom(t: float) -> float:
        current_beat = beats[0]
        for b in beats:
            if t >= b["at"]:
                current_beat = b
            else:
                break
        
        rel_t = t - current_beat["at"]
        b_dur = max(0.001, current_beat["duration"])
        progress = min(1.0, max(0.0, rel_t / b_dur))
        
        # Smooth interpolation bằng hàm Cosine (Ease-in-out)
        smooth_progress = 0.5 * (1.0 - math.cos(progress * math.pi))
        
        s_min, s_max = current_beat.get("scale_range", (1.0, 1.03))
        return s_min + (s_max - s_min) * smooth_progress

    # Áp dụng zoom động
    zoomed_clip = base_clip.resize(dynamic_zoom)

    # Cắt crop về khung hình chuẩn
    final_clip = zoomed_clip.crop(
        x_center=zoomed_clip.w / 2,
        y_center=zoomed_clip.h / 2,
        width=target_w,
        height=target_h
    )

    return final_clip

