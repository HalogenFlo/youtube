# Chức năng: Bộ điều phối Progressive Layering & Visual Beats (Diễn hoạt phân lớp theo nhịp thoại).
# Lý do tạo: Tối ưu hóa chuyển động video từ ảnh tĩnh Google Flow, khớp nhịp từng mili-giây với voiceover.
# Hỗ trợ Lazy Import cho MoviePy và cung cấp Fallback Clip dựa trên Pillow/NumPy khi môi trường không cài MoviePy.

from typing import List, Dict, Any, Tuple, Optional, Callable
import math


class _FallbackVisualClip:
    """Đối tượng Clip tương thích giao diện MoviePy (get_frame, size, w, h, duration, close) dùng Pillow & NumPy."""

    def __init__(self, img_arr, duration: float, target_size: Tuple[int, int], zoom_fn: Optional[Callable[[float], float]] = None):
        import numpy as np
        from PIL import Image

        self._raw_arr = np.asarray(img_arr, dtype=np.uint8)
        if self._raw_arr.ndim == 2:
            self._raw_arr = np.stack([self._raw_arr] * 3, axis=-1)
        elif self._raw_arr.ndim == 3 and self._raw_arr.shape[2] == 4:
            self._raw_arr = self._raw_arr[:, :, :3]

        self.w, self.h = int(target_size[0]), int(target_size[1])
        self.size = (self.w, self.h)
        self.duration = float(duration)
        self._zoom_fn = zoom_fn
        self._base_pil = Image.fromarray(self._raw_arr).convert("RGB").resize((self.w, self.h))

    def set_duration(self, dur: float):
        self.duration = float(dur)
        return self

    def get_frame(self, t: float):
        import numpy as np
        scale = float(self._zoom_fn(t)) if self._zoom_fn else 1.0
        if abs(scale - 1.0) < 1e-4:
            return np.asarray(self._base_pil, dtype=np.uint8)
        zw = max(self.w, int(round(self.w * scale)))
        zh = max(self.h, int(round(self.h * scale)))
        zoomed = self._base_pil.resize((zw, zh))
        left = max(0, (zw - self.w) // 2)
        top = max(0, (zh - self.h) // 2)
        cropped = zoomed.crop((left, top, left + self.w, top + self.h))
        return np.asarray(cropped, dtype=np.uint8)

    def close(self):
        pass


def calculate_visual_beats(scene_duration: float, num_beats: int = 2) -> List[Dict[str, Any]]:
    """
    Tự động chia thời lượng phân cảnh thành các nhịp hiệu ứng (Beats).
    """
    if scene_duration <= 3.0:
        return [{
            "at": 0.0,
            "duration": scene_duration,
            "effect": "zoom_in",
            "scale_range": (1.0, 1.08),
            "focus": (0.5, 0.5),
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
            "focus": (0.5, 0.45) if i == 0 else (0.5, 0.5),
        })
    return beats


def apply_visual_beat_motion(
    image_path: str,
    duration: float,
    orientation: str = "vertical",
    beats: Optional[List[Dict[str, Any]]] = None,
    target_resolution: Optional[Tuple[int, int]] = None,
) -> Any:
    """
    Áp dụng hiệu ứng Visual Beat động học mượt mà lên ảnh phân cảnh (Google Flow / SD).
    Đảm bảo ảnh luôn chuẩn hóa sang 3 channels RGB.
    """
    if target_resolution is not None:
        target_w, target_h = int(target_resolution[0]), int(target_resolution[1])
    else:
        target_w, target_h = (1080, 1920) if orientation == "vertical" else (1920, 1080)

    from PIL import Image
    import numpy as np

    with Image.open(image_path) as pil_img:
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        img_arr = np.array(pil_img)

    if not beats:
        def subtle_zoom(t: float) -> float:
            progress = min(1.0, max(0.0, t / max(duration, 0.001)))
            return 1.0 + 0.03 * progress
        zoom_fn = subtle_zoom
    else:
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
            smooth_progress = 0.5 * (1.0 - math.cos(progress * math.pi))
            s_min, s_max = current_beat.get("scale_range", (1.0, 1.03))
            return s_min + (s_max - s_min) * smooth_progress
        zoom_fn = dynamic_zoom

    try:
        from moviepy.editor import ImageClip
        base_clip = ImageClip(img_arr).set_duration(duration)
        base_clip = base_clip.resize(newsize=(target_w, target_h))
        zoomed_clip = base_clip.resize(zoom_fn)
        final_clip = zoomed_clip.crop(
            x_center=zoomed_clip.w / 2,
            y_center=zoomed_clip.h / 2,
            width=target_w,
            height=target_h,
        )
        return final_clip
    except ImportError:
        return _FallbackVisualClip(img_arr, duration=duration, target_size=(target_w, target_h), zoom_fn=zoom_fn)
