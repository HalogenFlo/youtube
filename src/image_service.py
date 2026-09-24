# Chức năng: Khởi tạo Stable Diffusion Pipeline và sinh hình ảnh chất lượng cao cho kịch bản.
# Lý do tạo: Phục vụ Chế độ Nhanh (Ảnh AI + Ken Burns) giúp tiết kiệm thời gian sản xuất video.
# Trích dẫn: Sử dụng thư viện diffusers của Hugging Face.

import os
import gc
import torch
from typing import Tuple, List, Dict, Any
from src.config import SD_MODEL_DEFAULT, SD_RESOLUTIONS, DEFAULT_IMAGE_STYLE


# Negative prompt tiêu chuẩn để tăng chất lượng ảnh SD 1.5
DEFAULT_NEGATIVE_PROMPT = (
    "ugly, deformed, noisy, blurry, low contrast, low quality, distorted, "
    "out of frame, bad anatomy, bad hands, double faces, text, watermark, "
    "signature, username, bad art"
)

def _setup_pipeline(model_id: str):
    """Khởi tạo Stable Diffusion Pipeline có kiểm tra thiết bị phần cứng."""
    import torch
    if not hasattr(torch, "xpu"):
        class _DummyXPU:
            is_available = staticmethod(lambda: False)
            device_count = staticmethod(lambda: 0)
            empty_cache = staticmethod(lambda: None)
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        torch.xpu = _DummyXPU()

    try:
        from diffusers import StableDiffusionPipeline
    except Exception as e:
        raise RuntimeError(f"Lỗi nạp thư viện diffusers ({e}). Khuyên dùng chế độ Google Flow (Nano Banana Pro)!")

    print(f"Đang tải Stable Diffusion Model: {model_id}...")
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        safety_checker=None,
        requires_safety_checker=False
    )
    
    if torch.cuda.is_available():
        pipe.enable_model_cpu_offload()
        pipe.enable_vae_slicing()
    return pipe

def generate_single_image(
    prompt: str, 
    output_path: str, 
    orientation: str = "vertical", 
    style_preset: str = DEFAULT_IMAGE_STYLE,
    model_id: str = SD_MODEL_DEFAULT,
    steps: int = 25
) -> Tuple[bool, str]:
    """
    Sinh một ảnh đơn lẻ và lưu vào output_path.
    Dành cho việc tái tạo ảnh của một phân cảnh cụ thể trên UI.
    """
    pipe = None
    try:
        # Tạo thư mục cha nếu chưa có
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        # Lấy kích thước ảnh
        width, height = SD_RESOLUTIONS.get(orientation, (512, 768))
        
        # Thiết lập pipeline
        pipe = _setup_pipeline(model_id)
        
        # Kết hợp prompt với style
        full_prompt = f"{prompt}, {style_preset}"
        
        # Sinh ảnh
        print(f"Đang sinh ảnh: \"{full_prompt}\" ({width}x{height})...")
        image = pipe(
            prompt=full_prompt,
            negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            num_inference_steps=steps,
            guidance_scale=7.5,
            width=width,
            height=height
        ).images[0]
        
        # Lưu ảnh
        image.save(output_path)
        return True, output_path
        
    except Exception as e:
        return False, f"Lỗi sinh ảnh SD: {str(e)}"
    finally:
        # Giải phóng VRAM
        if pipe is not None:
            del pipe
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def generate_batch_images(
    scenes: List[Dict[str, Any]], 
    temp_dir: str,
    orientation: str = "vertical", 
    style_preset: str = DEFAULT_IMAGE_STYLE,
    model_id: str = SD_MODEL_DEFAULT,
    steps: int = 25
) -> Tuple[bool, List[str]]:
    """
    Sinh hàng loạt ảnh cho danh sách các phân cảnh để tối ưu thời gian tải model.
    Mỗi phân cảnh cần có trường 'video_prompt' và file ảnh sẽ lưu tại temp_dir.
    Trả về: (Success, list_of_image_paths)
    """
    pipe = None
    generated_paths = []
    try:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # Lấy kích thước ảnh
        width, height = SD_RESOLUTIONS.get(orientation, (512, 768))
        
        # Khởi tạo pipeline một lần duy nhất
        pipe = _setup_pipeline(model_id)
        
        for i, scene in enumerate(scenes):
            prompt = scene.get("video_prompt", "")
            full_prompt = f"{prompt}, {style_preset}"
            output_path = os.path.join(temp_dir, f"scene_{i+1:03d}.png")
            
            # Chỉ sinh nếu file chưa tồn tại hoặc được yêu cầu ghi đè
            print(f"[{i+1}/{len(scenes)}] Đang sinh ảnh: \"{full_prompt}\"...")
            image = pipe(
                prompt=full_prompt,
                negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                num_inference_steps=steps,
                guidance_scale=7.5,
                width=width,
                height=height
            ).images[0]
            
            image.save(output_path)
            generated_paths.append(output_path)
            
        return True, generated_paths
        
    except Exception as e:
        return False, f"Lỗi sinh ảnh loạt SD: {str(e)}"
    finally:
        # Giải phóng VRAM toàn bộ sau khi sinh xong tất cả ảnh
        if pipe is not None:
            del pipe
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
