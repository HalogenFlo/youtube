# ==============================================================================
# WHITEBOARD STICKMAN: video "bàn tay vẽ" (nhân vật que + sơ đồ/chữ hiện dần khi tay lướt qua)
# ------------------------------------------------------------------------------
# Thiết kế (học từ videomake_gpt / cs-board / stickman-video-director):
#   - Vẽ bằng Pillow từng "item" (text / circle / box / arrow / stickman) thành 1 layer RGBA riêng
#     (mask partition: mỗi item là 1 khối nội dung được "mở khóa" theo thời gian).
#   - Mỗi item được lộ dần từ trái sang phải; sprite bàn tay cầm bút bám theo mép lộ.
#   - Frame được đẩy thẳng vào FFmpeg (rawvideo qua stdin) cùng audio TTS -> mp4. 0 credit Google Flow.
#   - Phong cách tối giản: nét mực đen trên nền trắng + tối đa 3 màu nhấn (red / blue / green).
# ==============================================================================
from __future__ import annotations

import math
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

VALID_TYPES = {"text", "circle", "box", "arrow", "stickman"}
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
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return default


def _num(v: Any, default: float, lo: float = 0.01, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
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
        items = [it for it in (_normalize_item(r) for r in raw_items) if it]
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
    px = int(size_frac * cv.w * SS)
    font = _load_font(px)
    max_w = max_w_px if max_w_px else cv.w * SS * 0.92
    while px > 10:
        bbox = cv.d.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_w:
            break
        px = int(px * 0.9)
        font = _load_font(px)
    bbox = cv.d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cv.d.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), text, font=font, fill=color)


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
    return cv.finish()


def _make_hand_sprite(width: int) -> Tuple[Image.Image, Tuple[int, int]]:
    """Sprite bàn tay cầm bút vẽ bằng Pillow. Trả về (ảnh RGBA, vị trí mũi bút trong sprite)."""
    s = 4
    w = int(width * s)
    h = int(width * 1.3 * s)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    skin, outline = (247, 200, 166, 255), (40, 30, 30, 255)
    lw = max(3, w // 60)
    # cánh tay đi xuống góc phải
    d.polygon([(w * 0.55, h * 0.45), (w * 0.82, h * 0.40), (w * 1.0, h * 1.0), (w * 0.62, h * 1.0)], fill=skin, outline=outline)
    # bàn tay (nắm)
    d.rounded_rectangle([w * 0.38, h * 0.22, w * 0.82, h * 0.58], radius=w * 0.12, fill=skin, outline=outline, width=lw)
    # bút thân đen chếch trái-trên, đầu bút ở góc trái-trên
    tip = (w * 0.10, h * 0.06)
    d.line([tip, (w * 0.50, h * 0.40)], fill=(25, 25, 25, 255), width=int(w * 0.07))
    d.ellipse([tip[0] - w * 0.03, tip[1] - w * 0.03, tip[0] + w * 0.03, tip[1] + w * 0.03], fill=(25, 25, 25, 255))
    # ngón cái đè lên bút
    d.rounded_rectangle([w * 0.30, h * 0.26, w * 0.56, h * 0.36], radius=w * 0.05, fill=skin, outline=outline, width=lw)
    img = img.resize((w // s, h // s), Image.LANCZOS)
    return img, (int(tip[0] / s), int(tip[1] / s))


# ------------------------------------------------------------------------------
# RENDERER
# ------------------------------------------------------------------------------
class WhiteboardRenderer:
    def __init__(self, items: List[Dict[str, Any]], duration: float, size: Tuple[int, int] = (1080, 1920)):
        self.items = items
        self.duration = max(0.5, float(duration))
        self.size = size
        self.schedule = compute_reveal_schedule(len(items), self.duration)
        self.layers: List[Image.Image] = [_draw_item_layer(it, size) for it in items]
        self.bboxes: List[Tuple[int, int, int, int]] = []
        for layer in self.layers:
            bb = layer.getchannel("A").getbbox()
            self.bboxes.append(bb if bb else (0, 0, 1, 1))
        self._done: Dict[int, Image.Image] = {0: Image.new("RGB", size, (255, 255, 255))}
        self.hand, self.hand_tip = _make_hand_sprite(max(40, int(size[0] * 0.24)))

    def _done_image(self, k: int) -> Image.Image:
        """Ảnh nền đã vẽ xong k item đầu (cache tích lũy)."""
        if k in self._done:
            return self._done[k]
        prev = self._done_image(k - 1).copy()
        prev.paste(self.layers[k - 1], (0, 0), self.layers[k - 1])
        self._done[k] = prev
        return prev

    def _extend_arm(self, frame: Image.Image, hx: int, hy: int) -> None:
        """Kéo dài cánh tay từ đáy sprite xuống mép khung hình cho tự nhiên."""
        hw, hh = self.hand.size
        bottom = hy + hh
        if bottom >= frame.size[1]:
            return
        d = ImageDraw.Draw(frame)
        skin, edge = (247, 200, 166), (40, 30, 30)
        l_top, r_top = hx + hw * 0.62, hx + hw * 1.0
        shift = (frame.size[1] - bottom) * 0.12
        l_bot, r_bot = l_top + shift, r_top + shift
        d.polygon([(l_top, bottom - 1), (r_top, bottom - 1), (r_bot, frame.size[1]), (l_bot, frame.size[1])], fill=skin)
        d.line([(l_top, bottom - 1), (l_bot, frame.size[1])], fill=edge, width=1)
        d.line([(r_top, bottom - 1), (r_bot, frame.size[1])], fill=edge, width=1)

    def render_frame(self, t: float) -> Image.Image:
        completed = sum(1 for _, t1 in self.schedule if t >= t1)
        frame = self._done_image(completed).copy()
        if completed < len(self.items):
            t0, t1 = self.schedule[completed]
            if t >= t0:
                p = (t - t0) / (t1 - t0)
                p = p * p * (3 - 2 * p)  # ease in-out
                x0, y0, x1, y1 = self.bboxes[completed]
                wipe_x = x0 + int((x1 - x0) * p) + 1
                layer = self.layers[completed]
                region = layer.crop((x0, y0, wipe_x, y1))
                frame.paste(region, (x0, y0), region)
                # tay "viết" lượn lên xuống trong khoảng cao của item
                wobble = 0.5 + 0.45 * math.sin(p * math.pi * 6)
                tip_y = y0 + int((y1 - y0) * wobble)
                hx = wipe_x - self.hand_tip[0]
                hy = tip_y - self.hand_tip[1]
                frame.paste(self.hand, (hx, hy), self.hand)
                self._extend_arm(frame, hx, hy)
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
) -> Tuple[bool, str]:
    """Render 1 cảnh whiteboard ra mp4 (pipe frame RGB vào FFmpeg, ghép audio nếu có)."""
    try:
        items = layout_scene_items(scene)
        renderer = WhiteboardRenderer(items, duration, size)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        w, h = size
        cmd = ["ffmpeg", "-y", "-nostats", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
        if audio_path and os.path.exists(audio_path):
            cmd += ["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-t", f"{duration:.3f}"]
        else:
            cmd += ["-an", "-t", f"{duration:.3f}"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", output_path]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        total_frames = max(1, int(round(duration * fps)))
        try:
            for i in range(total_frames):
                proc.stdin.write(renderer.render_frame(i / fps).tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        err = proc.stderr.read().decode("utf-8", errors="replace")
        proc.wait()
        if proc.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 500:
            return False, f"FFmpeg lỗi render whiteboard: {err[-400:]}"
        return True, output_path
    except Exception as exc:
        return False, f"Lỗi render whiteboard: {type(exc).__name__}: {exc}"
