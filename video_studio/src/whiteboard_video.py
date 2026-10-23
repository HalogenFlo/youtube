# ==============================================================================
# WHITEBOARD: bàn tay thật cầm bút, nét viền được vẽ trước rồi tô màu minh họa.
# ------------------------------------------------------------------------------
# Thiết kế (học từ videomake_gpt / cs-board / stickman-video-director):
#   - Vẽ bằng Pillow từng "item" (text / circle / box / arrow / stickman) thành 1 layer RGBA riêng
#     (mask partition: mỗi item là 1 khối nội dung được "mở khóa" theo thời gian).
#   - Theo các nét liền trên ảnh; đầu bút ảnh tay thật bám đúng điểm đang được mở.
#   - Frame được đẩy thẳng vào FFmpeg (rawvideo qua stdin) cùng audio TTS -> mp4. 0 credit Google Flow.
#   - Minh họa 2D màu pastel trên nền trắng, hỗ trợ thêm sơ đồ và người que.
# ==============================================================================
from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFont

from src.whiteboard_drawing import trace_outline, brush_plan, draw_progress
from src.whiteboard_illustrations import ASSET_DIR, ILLUSTRATIONS, illustration_image, local_image_path

VALID_TYPES = {"text", "circle", "box", "arrow", "stickman", "illustration", "image", "ai_image"}
VALID_EMOTIONS = {"happy", "sad", "surprised", "angry", "neutral", "thinking"}
ACCENT_COLORS = {
    "black": (20, 20, 20),
    "red": (214, 48, 49),
    "blue": (9, 132, 227),
    "green": (0, 168, 107),
}
INK = ACCENT_COLORS["black"]
SS = 2  # supersampling khi vẽ từng item cho nét mịn
FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _clamp01(v: Any, default: float = 0.5) -> float:
    try:
        value = float(v)
        return max(0.0, min(1.0, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _num(v: Any, default: float, lo: float = 0.01, hi: float = 1.0) -> float:
    try:
        value = float(v)
        return max(lo, min(hi, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _load_font(px: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, max(8, int(px)))
            except Exception:
                continue
    return ImageFont.load_default()


# ------------------------------------------------------------------------------
# LAYOUT
# ------------------------------------------------------------------------------
def _normalize_item(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    t = str(raw.get("type") or "").strip().lower()
    if t not in VALID_TYPES:
        return None
    item: Dict[str, Any] = {
        "type": t,
        "x": _clamp01(raw.get("x"), 0.5),
        "y": _clamp01(raw.get("y"), 0.5),
        "color": str(raw.get("color") or "black").strip().lower(),
    }
    if item["color"] not in ACCENT_COLORS:
        item["color"] = "black"
    label = str(raw.get("label") or raw.get("text") or "").strip()
    if t == "text":
        if not label:
            return None
        item["text"] = label
        item["size"] = _num(raw.get("size"), 0.07, 0.02, 0.2)
    elif t == "circle":
        item["r"] = _num(raw.get("r"), 0.12, 0.02, 0.5)
        item["label"] = label
    elif t == "box":
        item["w"] = _num(raw.get("w"), 0.35, 0.05, 1.0)
        item["h"] = _num(raw.get("h"), 0.15, 0.04, 1.0)
        item["label"] = label
    elif t == "arrow":
        item["x2"] = _clamp01(raw.get("x2"), min(1.0, item["x"] + 0.2))
        item["y2"] = _clamp01(raw.get("y2"), item["y"])
        item["label"] = label
    elif t == "stickman":
        emo = str(raw.get("emotion") or "neutral").strip().lower()
        item["emotion"] = emo if emo in VALID_EMOTIONS else "neutral"
        item["h"] = _num(raw.get("h"), 0.26, 0.08, 0.6)
        item["name"] = str(raw.get("name") or "").strip()
    elif t == "ai_image":
        item["prompt"] = str(raw.get("prompt") or "").strip()
        item["w"] = _num(raw.get("w"), .55, .05, .92)
        item["h"] = _num(raw.get("h"), .45, .05, .72)
    elif t in {"illustration", "image"}:
        item["asset"] = str(raw.get("asset") or "").strip()
        if not item["asset"]:
            return None
        item["w"] = _num(raw.get("w"), .55, .05, .92)
        item["h"] = _num(raw.get("h"), .45, .05, .72)
        if t == "illustration" and item["asset"] not in ILLUSTRATIONS:
            item["type"] = "ai_image"
            item["prompt"] = str(raw.get("prompt") or raw.get("description")
                                 or ("An educational illustration of " + item.pop("asset").replace("_", " "))).strip()
        elif t == "image" and raw.get("ai_generated") and raw.get("generation_prompt"):
            item["ai_generated"] = True
            item["generation_prompt"] = str(raw["generation_prompt"])
    return item


def _first_words(text: str, n: int = 6) -> str:
    words = re.sub(r"\s+", " ", str(text or "")).strip().split(" ")
    return " ".join(words[:n]).rstrip(" ,.;:!?")


def layout_scene_items(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Trả về danh sách item hợp lệ (tọa độ chuẩn hóa 0..1). Nếu scene không có `whiteboard_items`
    hợp lệ thì tự bố cục: tiêu đề + 1 nhân vật que cho mỗi nhân vật có thoại."""
    scene = scene if isinstance(scene, dict) else {}
    raw_items = scene.get("whiteboard_items")
    if isinstance(raw_items, list):
        items = [it for it in (_normalize_item(r) for r in raw_items[:40]) if it]
        if items:
            return items

    title = str(scene.get("whiteboard_title") or "").strip() or _first_words(scene.get("narration", ""))
    items: List[Dict[str, Any]] = []
    if title:
        items.append({"type": "text", "x": 0.5, "y": 0.18, "color": "black", "text": title, "size": 0.075})

    chars: List[Tuple[str, str]] = []
    seen = set()
    for line in scene.get("dialogue_lines") or []:
        if not isinstance(line, dict) or str(line.get("speaker") or "") == "narrator":
            continue
        name = str(line.get("character_name") or line.get("speaker") or "").strip()
        if name and name not in seen:
            seen.add(name)
            emo = str(line.get("emotion") or "neutral").strip().lower()
            chars.append((name, emo if emo in VALID_EMOTIONS else "neutral"))
    if not chars:
        chars = [("", "neutral")]
    chars = chars[:3]
    for i, (name, emo) in enumerate(chars):
        x = (i + 1) / (len(chars) + 1)
        items.append({"type": "stickman", "x": x, "y": 0.68, "color": "black", "emotion": emo, "h": 0.28, "name": name})
    return items


def compute_reveal_schedule(n_items: int, duration: float) -> List[Tuple[float, float]]:
    """Lịch lộ hình tuần tự cho n item: bắt đầu sau ~0.4s, xong trước 90% thời lượng cảnh."""
    if n_items <= 0:
        return []
    duration = max(0.5, float(duration))
    start = min(0.4, duration * 0.1)
    end = duration * 0.9
    slot = (end - start) / n_items
    return [(start + i * slot, start + i * slot + slot * 0.9) for i in range(n_items)]


# ------------------------------------------------------------------------------
# VẼ TỪNG ITEM
# ------------------------------------------------------------------------------
class _Canvas:
    """Canvas RGBA siêu mẫu (SS x) để vẽ 1 item rồi thu nhỏ."""

    def __init__(self, size: Tuple[int, int]):
        self.w, self.h = size
        self.img = Image.new("RGBA", (self.w * SS, self.h * SS), (255, 255, 255, 0))
        self.d = ImageDraw.Draw(self.img)
        self.lw = max(2, int(self.w * 0.006)) * SS

    def px(self, nx: float, ny: float) -> Tuple[float, float]:
        return nx * self.w * SS, ny * self.h * SS

    def finish(self) -> Image.Image:
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def _draw_text_centered(
    cv: _Canvas,
    text: str,
    cx: float,
    cy: float,
    size_frac: float,
    color: Tuple[int, int, int],
    max_w_px: Optional[float] = None,
):
    px = max(10, int(size_frac * cv.w * SS))
    max_w = min(max_w_px or cv.w * SS * 0.9, 2 * min(cx, cv.w * SS - cx) - cv.lw)
    max_w = max(20, max_w)
    # Wrap before shrinking: long Vietnamese labels remain readable on 1080p boards.
    while True:
        font = _load_font(px)
        lines = []
        current = ""
        for word in str(text).split():
            candidate = f"{current} {word}".strip()
            if current and cv.d.textlength(candidate, font=font) > max_w:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
        wrapped = "\n".join(lines)
        bbox = cv.d.multiline_textbbox((0, 0), wrapped, font=font, spacing=px // 5)
        if px <= 10 or (bbox[2] <= max_w and bbox[3] - bbox[1] <= cv.h * SS * .16):
            break
        px = max(10, int(px * .9))
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cv.d.multiline_text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), wrapped,
                        font=font, fill=color, spacing=px // 5, align="center")


def _draw_face(cv: _Canvas, cx: float, cy: float, r: float, emotion: str):
    d, lw = cv.d, max(2, cv.lw // 2 * 2 // 2)
    ink = INK
    ex, ey = r * 0.38, r * 0.15
    eye_r = r * (0.2 if emotion == "surprised" else 0.11)
    for sx in (-1, 1):
        ox = cx + sx * ex
        oy = cy - ey
        if emotion == "surprised":
            d.ellipse([ox - eye_r, oy - eye_r, ox + eye_r, oy + eye_r], outline=ink, width=lw, fill=(255, 255, 255, 255))
            d.ellipse([ox - eye_r * 0.35, oy - eye_r * 0.35, ox + eye_r * 0.35, oy + eye_r * 0.35], fill=ink)
        else:
            d.ellipse([ox - eye_r, oy - eye_r, ox + eye_r, oy + eye_r], fill=ink)
    my = cy + r * 0.42
    if emotion == "happy":
        d.arc([cx - r * 0.42, my - r * 0.3, cx + r * 0.42, my + r * 0.3], 20, 160, fill=ink, width=lw)
    elif emotion == "sad":
        d.arc([cx - r * 0.35, my, cx + r * 0.35, my + r * 0.5], 200, 340, fill=ink, width=lw)
    elif emotion == "surprised":
        d.ellipse([cx - r * 0.12, my - r * 0.12, cx + r * 0.12, my + r * 0.16], outline=ink, width=lw)
    elif emotion == "angry":
        d.line([cx - r * 0.5, cy - r * 0.45, cx - r * 0.12, cy - r * 0.28], fill=ink, width=lw)
        d.line([cx + r * 0.5, cy - r * 0.45, cx + r * 0.12, cy - r * 0.28], fill=ink, width=lw)
        d.line([cx - r * 0.3, my + r * 0.05, cx + r * 0.3, my + r * 0.05], fill=ink, width=lw)
    elif emotion == "thinking":
        d.line([cx - r * 0.5, cy - r * 0.42, cx - r * 0.15, cy - r * 0.5], fill=ink, width=lw)
        d.line([cx - r * 0.2, my + r * 0.05, cx + r * 0.3, my], fill=ink, width=lw)
    else:
        d.line([cx - r * 0.28, my, cx + r * 0.28, my], fill=ink, width=lw)


def _draw_stickman(cv: _Canvas, item: Dict[str, Any]):
    d = cv.d
    cx, cy = cv.px(item["x"], item["y"])
    total_h = item["h"] * cv.h * SS
    r = total_h * 0.16
    lw = cv.lw
    color = ACCENT_COLORS[item["color"]]
    head_cy = cy - total_h / 2 + r
    d.ellipse([cx - r, head_cy - r, cx + r, head_cy + r], outline=INK, width=lw, fill=(255, 255, 255, 255))
    _draw_face(cv, cx, head_cy, r, item["emotion"])
    neck = head_cy + r
    hip = neck + total_h * 0.38
    d.line([cx, neck, cx, hip], fill=color, width=lw)
    shoulder = neck + total_h * 0.08
    arm = total_h * 0.26
    emo = item["emotion"]
    up = emo in ("happy", "surprised", "angry")
    d.line([cx, shoulder, cx - arm, shoulder + (-arm * 0.6 if up else arm * 0.7)], fill=color, width=lw)
    d.line([cx, shoulder, cx + arm, shoulder + (-arm * 0.6 if emo in ("happy", "surprised") else arm * 0.7)], fill=color, width=lw)
    leg = total_h * 0.34
    d.line([cx, hip, cx - leg * 0.45, hip + leg], fill=color, width=lw)
    d.line([cx, hip, cx + leg * 0.45, hip + leg], fill=color, width=lw)
    if item.get("name"):
        _draw_text_centered(cv, item["name"], cx, hip + leg + total_h * 0.09, 0.04, INK)


def _draw_arrow(cv: _Canvas, item: Dict[str, Any]):
    x1, y1 = cv.px(item["x"], item["y"])
    x2, y2 = cv.px(item["x2"], item["y2"])
    color = ACCENT_COLORS[item["color"]]
    lw = cv.lw
    cv.d.line([x1, y1, x2, y2], fill=color, width=lw)
    ang = math.atan2(y2 - y1, x2 - x1)
    head = cv.w * SS * 0.03
    for off in (math.radians(150), math.radians(-150)):
        cv.d.line([x2, y2, x2 + head * math.cos(ang + off), y2 + head * math.sin(ang + off)], fill=color, width=lw)
    if item.get("label"):
        _draw_text_centered(cv, item["label"], (x1 + x2) / 2, (y1 + y2) / 2 - cv.h * SS * 0.03, 0.045, color)


def _draw_item_layer(item: Dict[str, Any], size: Tuple[int, int]) -> Image.Image:
    if item["type"] == "ai_image":
        raise ValueError("Cần tạo minh họa AI trước khi dựng tay vẽ.")
    cv = _Canvas(size)
    color = ACCENT_COLORS[item["color"]]
    t = item["type"]
    if t == "text":
        cx, cy = cv.px(item["x"], item["y"])
        _draw_text_centered(cv, item["text"], cx, cy, item["size"], color)
    elif t == "circle":
        cx, cy = cv.px(item["x"], item["y"])
        r = item["r"] * cv.w * SS
        cv.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=cv.lw)
        if item.get("label"):
            _draw_text_centered(cv, item["label"], cx, cy, 0.05, color, max_w_px=r * 1.7)
    elif t == "box":
        cx, cy = cv.px(item["x"], item["y"])
        w, h = item["w"] * cv.w * SS / 2, item["h"] * cv.h * SS / 2
        cv.d.rectangle([cx - w, cy - h, cx + w, cy + h], outline=color, width=cv.lw)
        if item.get("label"):
            _draw_text_centered(cv, item["label"], cx, cy, 0.05, color, max_w_px=w * 1.8)
    elif t == "arrow":
        _draw_arrow(cv, item)
    elif t == "stickman":
        _draw_stickman(cv, item)
    elif t in {"illustration", "image"}:
        if t == "illustration":
            image = illustration_image(item["asset"])
        else:
            with Image.open(local_image_path(item["asset"])) as source:
                image = source.convert("RGBA")
        content_bounds = image.getchannel("A").getbbox()
        if content_bounds:
            image = image.crop(content_bounds)
        # Contain within the requested box; never distort a person or a local drawing.
        max_w, max_h = item["w"] * cv.w * SS, item["h"] * cv.h * SS
        ratio = min(max_w / image.width, max_h / image.height)
        image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)
        cx, cy = cv.px(item["x"], item["y"])
        cv.img.alpha_composite(image, (round(cx - image.width / 2), round(cy - image.height / 2)))
    return cv.finish()


def _make_hand_sprite(width: int) -> Tuple[Image.Image, Tuple[int, int]]:
    """Photographic transparent hand; anchor is the calibrated physical marker nib."""
    with Image.open(ASSET_DIR / "hand_photo_v1.png") as source:
        sprite = source.convert("RGBA")
        # Nib coordinates are measured on the 1024 x 1536 production sprite.
        ratio = width / sprite.width
        sprite = sprite.resize((width, round(sprite.height * ratio)), Image.Resampling.LANCZOS)
    return sprite, (round(347 * ratio), round(94 * ratio))


# ------------------------------------------------------------------------------
# RENDERER
# ------------------------------------------------------------------------------
class WhiteboardRenderer:
    def __init__(self, items: List[Dict[str, Any]], duration: float, size: Tuple[int, int] = (1080, 1920), show_hand: bool = True):
        self.items = items
        self.duration = max(0.5, float(duration))
        self.size = size
        self.schedule = compute_reveal_schedule(len(items), self.duration)
        self.layers: List[Image.Image] = [_draw_item_layer(it, size) for it in items]
        self.bboxes: List[Tuple[int, int, int, int]] = []
        for layer in self.layers:
            bb = layer.getchannel("A").getbbox()
            self.bboxes.append(bb if bb else (0, 0, 1, 1))
        self.crops = [layer.crop(bb) for layer, bb in zip(self.layers, self.bboxes)]
        self.outlines_and_paths = [trace_outline(crop) for crop in self.crops]
        self.fill_paths = [brush_plan(crop.size, max(12, round(min(size) * .055))) for crop in self.crops]
        self._done_count = 0
        self._done_frame = Image.new("RGB", size, (255, 255, 255))
        self.show_hand = show_hand
        self.hand, self.hand_tip = _make_hand_sprite(max(60, int(min(size) * .62)))

    def _done_image(self, k: int) -> Image.Image:
        """Ảnh nền đã vẽ xong k item đầu (cache tích lũy)."""
        if k < self._done_count:
            self._done_count = 0
            self._done_frame = Image.new("RGB", self.size, (255, 255, 255))
        for idx in range(self._done_count, k):
            self._done_frame.paste(self.layers[idx], (0, 0), self.layers[idx])
        self._done_count = k
        return self._done_frame

    def _extend_arm(self, frame: Image.Image, hx: int, hy: int) -> None:
        """Continue the photographed forearm to the frame edge using its own texture."""
        hw, hh = self.hand.size
        bottom = hy + hh
        if bottom >= frame.size[1]:
            return
        strip = self.hand.crop((0, max(0, hh - 24), hw, hh))
        strip = strip.resize((hw, frame.height - bottom + 1), Image.Resampling.BICUBIC)
        frame.paste(strip, (hx, bottom - 1), strip)

    def _drawing_image(self, index: int, progress: float) -> Tuple[Image.Image, Tuple[float, float]]:
        crop = self.crops[index]
        outline, path = self.outlines_and_paths[index]
        is_color = self.items[index]["type"] in {"illustration", "image"}
        if not is_color:
            mask, tip = draw_progress(path, progress, crop.size)
            result = crop.copy()
            result.putalpha(ImageChops.multiply(crop.getchannel("A"), mask))
            return result, tip
        if progress < .62:
            mask, tip = draw_progress(path, progress / .62, crop.size)
            result = outline.copy()
            result.putalpha(ImageChops.multiply(outline.getchannel("A"), mask))
            return result, tip
        # Once the contour is drawn, sweep a broad marker along rows to add color.
        result = outline.copy()
        mask, tip = draw_progress(self.fill_paths[index], (progress - .62) / .38, crop.size)
        colored = crop.copy()
        colored.putalpha(ImageChops.multiply(crop.getchannel("A"), mask))
        result.alpha_composite(colored)
        return result, tip

    def render_frame(self, t: float) -> Image.Image:
        completed = sum(1 for _, t1 in self.schedule if t >= t1)
        frame = self._done_image(completed).copy()
        if completed < len(self.items):
            t0, t1 = self.schedule[completed]
            if t >= t0:
                p = (t - t0) / (t1 - t0)
                x0, y0, x1, y1 = self.bboxes[completed]
                region, tip = self._drawing_image(completed, p)
                frame.paste(region, (x0, y0), region)
                if self.show_hand:
                    hx = round(x0 + tip[0] - self.hand_tip[0])
                    hy = round(y0 + tip[1] - self.hand_tip[1])
                    self._extend_arm(frame, hx, hy)
                    frame.paste(self.hand, (hx, hy), self.hand)
        return frame


# ------------------------------------------------------------------------------
# XUẤT VIDEO
# ------------------------------------------------------------------------------
def render_whiteboard_scene_video(
    scene: Dict[str, Any],
    output_path: str,
    duration: float,
    audio_path: Optional[str] = None,
    size: Tuple[int, int] = (1080, 1920),
    fps: int = 24,
    is_cancelled_callback: Optional[Callable[[], bool]] = None,
) -> Tuple[bool, str]:
    """Render 1 cảnh whiteboard ra mp4 (pipe frame RGB vào FFmpeg, ghép audio nếu có)."""
    proc = None
    try:
        duration = float(duration)
        if not math.isfinite(duration) or duration <= 0 or fps <= 0 or any(v <= 0 or v % 2 for v in size):
            return False, "Thời lượng/FPS phải dương và kích thước khung hình phải là số chẵn."
        if audio_path and not os.path.isfile(audio_path):
            return False, f"Không tìm thấy âm thanh: {audio_path}"
        items = layout_scene_items(scene)
        renderer = WhiteboardRenderer(items, duration, size)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        w, h = size
        cmd = ["ffmpeg", "-y", "-nostats", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
        if audio_path and os.path.exists(audio_path):
            cmd += ["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-t", f"{duration:.3f}"]
        else:
            cmd += ["-an", "-t", f"{duration:.3f}"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path]
        # A temporary error log avoids a full stderr pipe blocking a long render.
        with tempfile.TemporaryFile() as error_log:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=error_log)
            total_frames = max(1, int(math.ceil(duration * fps)))
            try:
                for i in range(total_frames):
                    if is_cancelled_callback and is_cancelled_callback():
                        return False, "Đã bỏ qua theo yêu cầu người dùng"
                    proc.stdin.write(renderer.render_frame(i / fps).tobytes())
                proc.stdin.close()
            except BrokenPipeError:
                pass
            proc.wait(timeout=max(30, duration * 2))
            error_log.seek(0)
            err = error_log.read().decode("utf-8", errors="replace")
        if proc.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 500:
            return False, f"FFmpeg lỗi render whiteboard: {err[-400:]}"
        return True, output_path
    except Exception as exc:
        return False, f"Lỗi render whiteboard: {type(exc).__name__}: {exc}"
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass


def render_whiteboard_story_scenes(scenes: List[Dict[str, Any]], work_dir: str,
                                   orientation: str = "vertical", with_audio: bool = True,
                                   on_scene_status_callback=None, progress_callback=None,
                                   is_cancelled_callback=None) -> Tuple[bool, str]:
    """Render all boards using measured TTS durations; audio is muxed by the compiler."""
    size = (1080, 1920) if orientation == "vertical" else (1920, 1080)
    for idx, scene in enumerate(scenes, 1):
        if is_cancelled_callback and is_cancelled_callback():
            return False, "Đã bỏ qua theo yêu cầu người dùng"
        if with_audio and not (scene.get("audio_path") and os.path.isfile(scene["audio_path"])):
            return False, f"Cảnh {idx} chưa có âm thanh TTS."
        duration = float(scene.get("audio_duration") or max(3., len(str(scene.get("narration") or "").split()) / 3.))
        scene["audio_duration"] = duration
        output = os.path.join(work_dir, f"whiteboard_{idx:03d}.mp4")
        if on_scene_status_callback:
            on_scene_status_callback(idx, len(scenes), "rendering", None)
        if progress_callback:
            progress_callback(25 + (idx - 1) / len(scenes) * 55, f"Đang vẽ nét viền và tô màu: cảnh {idx}/{len(scenes)}")
        ok, error = render_whiteboard_scene_video(scene, output, duration, size=size,
                                                  is_cancelled_callback=is_cancelled_callback)
        if not ok:
            if on_scene_status_callback:
                on_scene_status_callback(idx, len(scenes), "failed", None)
            return False, error
        scene.update(video_path=output, use_video_ai=True, media_type="whiteboard")
        if on_scene_status_callback:
            on_scene_status_callback(idx, len(scenes), "completed", output)
    return True, "Đã vẽ xong các cảnh whiteboard."
