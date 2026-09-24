# Chức năng: Service cấp cao điều phối sinh ảnh từ Google Flow với cơ chế Fallback sang Stable Diffusion nếu Flow không khả dụng.
# Lý do tạo: Tích hợp liền mạch vào Web UI app.py, cho phép người dùng chọn nguồn sinh ảnh linh hoạt.
# Trích dẫn: Gọi FlowBrowserController từ src/flow_browser_service.py.

import os
from pathlib import Path
from typing import Tuple, List, Dict, Any
from src.flow_browser_service import get_flow_controller
from src.config import DEFAULT_IMAGE_STYLE


def generate_flow_image(
    prompt: str,
    output_path: str,
    orientation: str = "vertical",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    fallback_to_sd: bool = True
) -> Tuple[bool, str]:
    """
    Sinh 1 ảnh phân cảnh bằng Google Flow (Nano Banana Pro).
    Nếu gặp lỗi và fallback_to_sd=True, tự động chuyển sang mô hình Local Stable Diffusion.
    """
    print(f"[*] Đang yêu cầu Google Flow sinh ảnh: \"{prompt[:60]}...\"")
    controller = get_flow_controller()
    success, result_or_err = controller.generate_scene_image(
        prompt=prompt,
        output_path=output_path,
        orientation=orientation,
        style_preset=style_preset
    )

    if success:
        return True, result_or_err

    print(f"[!] Google Flow gặp sự cố: {result_or_err}")
    if fallback_to_sd:
        print("[*] Tự động Fallback sang Local Stable Diffusion 1.5...")
        try:
            from src.image_service import generate_single_image as generate_sd_single_image
            return generate_sd_single_image(
                prompt=prompt,
                output_path=output_path,
                orientation=orientation,
                style_preset=style_preset
            )
        except Exception as e:
            return False, f"Lỗi cả Google Flow và Fallback SD: {e}"
    return False, result_or_err


def generate_flow_batch(
    scenes: List[Dict[str, Any]],
    temp_dir: str,
    orientation: str = "vertical",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    fallback_to_sd: bool = True
) -> Tuple[bool, List[str]]:
    """
    Sinh hàng loạt ảnh cho các phân cảnh trong kịch bản.
    """
    image_paths = []
    for i, sc in enumerate(scenes):
        out_path = os.path.join(temp_dir, f"scene_flow_{i+1}.png")
        prompt = sc.get("video_prompt") or sc.get("narration") or "Stickman scene"
        
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
