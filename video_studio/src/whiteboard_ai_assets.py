"""Create missing whiteboard illustrations through an injected AI image backend.

Content-addressed PNG assets persist across scenes/episodes. The production
backend is the existing Google Flow browser controller; the renderer stays local.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.whiteboard_illustrations import ASSET_DIR

STYLE_VERSION = "whiteboard-editorial-v1"


def build_whiteboard_image_prompt(subject: str, character_anchor: str = "") -> str:
    return f"""Create ONE original 2D colored whiteboard illustration for an educational video.
SUBJECT / ACTION: {subject.strip()}
Character continuity (when a person is needed): {character_anchor.strip() or 'Friendly editorial people, teal clothing, warm peach skin.'}
STYLE: clean flat editorial illustration, thin continuous charcoal outlines, simple expressive shapes,
pastel teal, light sky blue, peach, cream, sage. The artwork must be easy to trace with a marker.
Composition: one coherent isolated vignette with all objects fully inside the frame, generous white margins.
Pure solid white background (#FFFFFF), evenly lit page. No background scene or paper texture.
No text, letters, captions, numbers, logos, watermark, writing hand or marker in the illustration.
No photo, no realistic rendering, no 3D, no dramatic lighting, no gradients, no shadows or glow.
Only depict objects relevant to the subject. Do not replace an unfamiliar subject with a person at a computer.
"""


def asset_identity(prompt: str) -> str:
    payload = json.dumps({"style_version": STYLE_VERSION, "prompt": prompt}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def prepare_generated_illustration(source: Path, destination: Path) -> None:
    """Normalize model output to PNG and remove only connected near-white page margins.

    White areas enclosed by outlines (eyes/clothes/etc.) stay opaque. Existing
    transparency is preserved. Processing is part of the runtime compositing path.
    """
    with Image.open(source) as image:
        image.load()
        if min(image.size) < 128 or image.width * image.height > 16_777_216:
            raise ValueError("Kích thước ảnh AI không hợp lệ (cần ít nhất 128px, tối đa 16 megapixel).")
        rgba = image.convert("RGBA")
    pixels = np.asarray(rgba)
    rgb = pixels[:, :, :3].astype(int)
    alpha = pixels[:, :, 3]
    ink = (rgb.min(axis=2) < 220) & (alpha > 100)
    if int(ink.sum()) < max(30, rgba.width * rgba.height // 1000):
        raise ValueError("Ảnh AI trống hoặc không có nét minh họa để tay vẽ.")
    white = ((rgb.min(axis=2) >= 244) & (rgb.max(axis=2) - rgb.min(axis=2) <= 12)) | (alpha == 0)
    mask = Image.fromarray((white * 255).astype("uint8")).copy()
    w, h = mask.size
    seeds = ([(x, y) for x in range(0, w, 16) for y in (0, h - 1)]
             + [(x, y) for y in range(0, h, 16) for x in (0, w - 1)])
    for point in seeds:
        if mask.getpixel(point) == 255:
            ImageDraw.floodfill(mask, point, 128)
    connected = np.asarray(mask) == 128
    new_alpha = alpha.copy()
    new_alpha[connected] = 0
    rgba.putalpha(Image.fromarray(new_alpha))
    destination.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(destination, format="PNG")


def valid_cached_asset(path: Path, prompt: str) -> bool:
    try:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if meta.get("prompt") != prompt or meta.get("style_version") != STYLE_VERSION:
            return False
        with Image.open(path) as im:
            im.load()
            return im.mode == "RGBA" and min(im.size) >= 128 and im.getchannel("A").getbbox() is not None
    except (OSError, ValueError, TypeError):
        return False


def resolve_whiteboard_ai_assets(scenes: List[Dict[str, Any]], generate_image: Callable[..., Tuple[bool, str]],
                                character_anchor: str = "", enabled: bool = True,
                                asset_dir: Path | None = None, progress_callback=None,
                                is_cancelled_callback=None, max_attempts: int = 2
                                ) -> Tuple[bool, List[Dict[str, Any]], Dict[str, Any]]:
    """Replace each ai_image item with its generated/cached local image item.

    Preserve all speech and unrelated artwork. No silent fallback to stock art.
    A backend is invoked only for a cache miss, so Chrome is not needed for reuse.
    """
    root = Path(asset_dir) if asset_dir else ASSET_DIR
    root.mkdir(parents=True, exist_ok=True)
    prepared = deepcopy(scenes)
    requests = [(idx, item) for idx, scene in enumerate(prepared)
                for item in (scene.get("whiteboard_items") or [])
                if isinstance(item, dict) and (item.get("type") == "ai_image"
                    or (item.get("type") == "image" and item.get("ai_generated") and item.get("generation_prompt")))]
    stats: Dict[str, Any] = {"requested": len(requests), "generated": 0, "cache_hits": 0, "assets": []}
    if requests and not enabled:
        return False, prepared, dict(stats, error="Kịch bản cần hình mới. Hãy bật AI tạo minh họa hoặc dùng hình đã có trong kho.")
    for index, (scene_index, item) in enumerate(requests, 1):
        if is_cancelled_callback and is_cancelled_callback():
            return False, prepared, dict(stats, error="Đã bỏ qua theo yêu cầu người dùng")
        subject = str(item.get("prompt") or item.get("generation_prompt") or "").strip()
        if not subject:
            return False, prepared, dict(stats, error=f"Cảnh {scene_index + 1} thiếu mô tả hình cần AI tạo.")
        prompt = build_whiteboard_image_prompt(subject, character_anchor)
        key = asset_identity(prompt)
        final = root / "ai" / f"ai_{key}.png"
        final.parent.mkdir(parents=True, exist_ok=True)
        if valid_cached_asset(final, prompt):
            stats["cache_hits"] += 1
        else:
            raw = final.with_name(f"{final.stem}.source.png")
            last_error = "AI chưa tạo được hình."
            for attempt in range(1, max(1, max_attempts) + 1):
                if is_cancelled_callback and is_cancelled_callback():
                    return False, prepared, dict(stats, error="Đã bỏ qua theo yêu cầu người dùng")
                if progress_callback:
                    progress_callback(20 + (index - 1) / max(1, len(requests)) * 15,
                                      f"AI đang tạo minh họa {index}/{len(requests)} cho cảnh {scene_index + 1} (lần {attempt})...")
                try:
                    ok, response = generate_image(prompt=prompt, output_path=str(raw),
                                                  scene_num=scene_index + 1, total_scenes=len(prepared),
                                                  attempt_num=attempt)
                    if not ok:
                        last_error = str(response)
                        continue
                    if is_cancelled_callback and is_cancelled_callback():
                        return False, prepared, dict(stats, error="Đã bỏ qua theo yêu cầu người dùng")
                    prepare_generated_illustration(raw, final)
                    final.with_suffix(".json").write_text(json.dumps({
                        "style_version": STYLE_VERSION, "prompt": prompt, "subject": subject,
                        "provider": "google_flow", "asset": final.name}, ensure_ascii=False, indent=2), encoding="utf-8")
                    stats["generated"] += 1
                    break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
            else:
                return False, prepared, dict(stats, error=f"Không tạo được minh họa cho cảnh {scene_index + 1}: {last_error}")
        item["type"] = "image"
        item["asset"] = final.relative_to(root).as_posix()
        item["ai_generated"] = True
        item["generation_prompt"] = subject
        stats["assets"].append(item["asset"])
    if progress_callback and requests:
        progress_callback(35, f"Đã có minh họa: {stats['generated']} ảnh mới, {stats['cache_hits']} ảnh lấy lại từ kho.")
    return True, prepared, stats
