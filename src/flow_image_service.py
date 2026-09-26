# Chức năng: Service điều phối sinh nội dung thật từ Google Flow (flow.google.com), loại bỏ hoàn toàn các hình ảnh giả/fallback thô sơ.
# Lý do tạo: Đáp ứng 100% yêu cầu người dùng: Mọi hình ảnh và video phải được tạo trực tiếp từ Google Flow trên tài khoản của user.

import os
import sys
import time
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional, Callable

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_log(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'), flush=True)
        except Exception:
            pass

from src.flow_browser_service import get_flow_controller
from src.config import DEFAULT_IMAGE_STYLE


def generate_flow_media(
    prompt: str,
    output_path: str,
    orientation: str = "vertical",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    mode: str = "video",
    timeout_sec: Optional[int] = None,
    status_callback: Optional[Callable[[int, str], None]] = None,
) -> Tuple[bool, str]:
    """
    Sinh nội dung (Video hoặc Ảnh) trực tiếp từ Google Flow theo prompt.
    Không dùng bất kỳ hình ảnh giả hay fallback thô sơ nào.
    """
    safe_log(f"[*] Đang đưa prompt lên Google Flow: \"{prompt[:60]}...\"")
    controller = get_flow_controller()

    if mode == "video":
        success, result_path = controller.generate_scene_video(
            prompt=prompt,
            output_path=output_path,
            orientation=orientation,
            timeout_sec=timeout_sec,
            status_callback=status_callback,
        )
    else:
        success, result_path = controller.generate_scene_image(
            prompt=prompt,
            output_path=output_path,
            orientation=orientation,
            style_preset=style_preset,
            timeout_sec=timeout_sec or 90,
        )

    if success and os.path.exists(output_path):
        safe_log(f"[✓] Đã tạo thành công từ Google Flow: {output_path}")
        return True, output_path

    return False, f"Google Flow không thể tạo nội dung: {result_path}"


# Tương thích ngược với các module gọi generate_flow_image
def generate_flow_image(
    prompt: str,
    output_path: str,
    orientation: str = "vertical",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    fallback_to_sd: bool = False,
    timeout_sec: Optional[int] = None,
) -> Tuple[bool, str]:
    return generate_flow_media(
        prompt=prompt,
        output_path=output_path,
        orientation=orientation,
        style_preset=style_preset,
        mode="image",
        timeout_sec=timeout_sec,
    )


def generate_flow_video(
    prompt: str,
    output_path: str,
    orientation: str = "vertical",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    timeout_sec: Optional[int] = None,
    status_callback: Optional[Callable[[int, str], None]] = None,
) -> Tuple[bool, str]:
    """Sinh clip MP4 thật từ Google Flow cho một phân cảnh (kiên trì chờ, không fallback)."""
    return generate_flow_media(
        prompt=prompt,
        output_path=output_path,
        orientation=orientation,
        style_preset=style_preset,
        mode="video",
        timeout_sec=timeout_sec,
        status_callback=status_callback,
    )


def generate_flow_batch(
    scenes: List[Dict[str, Any]],
    temp_dir: str,
    orientation: str = "vertical",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    fallback_to_sd: bool = False
) -> Tuple[bool, List[str]]:
    """Sinh hàng loạt nội dung cho các cảnh từ Google Flow."""
    image_paths = []
    for i, sc in enumerate(scenes):
        out_path = os.path.join(temp_dir, f"scene_flow_{i+1}.png")
        prompt = sc.get("video_prompt") or sc.get("narration") or "Cinematic scene"
        ok, res = generate_flow_image(
            prompt=prompt,
            output_path=out_path,
            orientation=orientation,
            style_preset=style_preset,
            fallback_to_sd=fallback_to_sd
        )
        if not ok:
            return False, [f"Lỗi ở cảnh {i+1}: {res}"]
        image_paths.append(res)
    return True, image_paths
