# Chức năng: Khởi tạo Wan Pipeline (Wan 2.1 1.3B) để sinh video clip động theo từng phân cảnh.
# Lý do tạo: Phục vụ Chế độ Video AI, tạo ra các clip chuyển động thực tế cho video ngắn.
# Trích dẫn: Sử dụng thư viện diffusers của Hugging Face và giải phóng VRAM chủ động của Ollama.

import os
import gc
import time
import requests
from typing import Tuple, List, Dict, Any
from src.config import WAN_MODEL_DEFAULT, WAN_RESOLUTIONS, WAN_DEFAULT_FRAMES, WAN_DEFAULT_STEPS, OLLAMA_API_URL, OLLAMA_MODEL_DEFAULT

def unload_ollama_vram() -> None:
    """
    Chủ động gửi lệnh unload model Ollama để giải phóng ~5GB VRAM trước khi load Wan 2.1.
    """
    print("Đang gửi lệnh yêu cầu Ollama giải phóng VRAM...")
    try:
        # Gọi API generate với keep_alive = 0 để giải phóng model ngay lập tức
        # Ollama API URL: http://localhost:11434/api/generate
        # Thay thế endpoint /generate bằng /api/generate hoặc tương tự
        payload = {
            "model": OLLAMA_MODEL_DEFAULT,
            "prompt": "",
            "keep_alive": 0,
            "stream": False
        }
        # Thử gửi request unload tới Ollama
        requests.post(OLLAMA_API_URL, json=payload, timeout=5)
        print("Đã gửi yêu cầu giải phóng Ollama VRAM.")
    except Exception as e:
        print(f"Không thể liên hệ Ollama để unload model (Ollama có thể đã tắt hoặc chưa chạy): {e}")

def _setup_pipeline(model_id: str):
    """
    Khởi tạo WanPipeline cho sinh video có kiểm tra thiết bị phần cứng.
    Chủ động unload Ollama trước, sau đó thiết lập CPU/GPU động.
    """
    unload_ollama_vram()
    import torch
    from diffusers import WanPipeline
    
    print(f"Đang tải Wan 2.1 Video Generation Model: {model_id}...")
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    
    pipe = WanPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype
    )
    
    if torch.cuda.is_available():
        pipe.enable_model_cpu_offload()
        pipe.enable_vae_tiling()
    return pipe

def generate_single_video(
    prompt: str, 
    output_path: str, 
    orientation: str = "vertical",
    num_frames: int = WAN_DEFAULT_FRAMES,
    num_inference_steps: int = WAN_DEFAULT_STEPS,
    model_id: str = WAN_MODEL_DEFAULT
) -> Tuple[bool, str, float]:
    """
    Sinh một clip video đơn lẻ dài ~5 giây từ prompt và lưu vào output_path.
    Dành cho việc tạo lại clip cho riêng một phân cảnh cụ thể trên UI.
    Trả về Tuple[thành_công, đường_dẫn_hoặc_thông_báo_lỗi, thời_gian_chạy_giây].
    """
    pipe = None
    start_time = time.time()
    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        width, height = WAN_RESOLUTIONS.get(orientation, (480, 848))
        pipe = _setup_pipeline(model_id)
        
        print(f"Đang sinh clip video: \"{prompt}\" ({width}x{height}, {num_frames} frames, {num_inference_steps} steps)...")
        video_frames = pipe(
            prompt=prompt,
            num_frames=num_frames,
            height=height,
            width=width,
            num_inference_steps=num_inference_steps,
            guidance_scale=5.0
        ).frames[0]
        
        # Lưu clip video với tốc độ 16fps mặc định của Wan
        from diffusers.utils import export_to_video
        export_to_video(video_frames, output_path, fps=16)
        elapsed = time.time() - start_time
        return True, output_path, elapsed
        
    except Exception as e:
        elapsed = time.time() - start_time
        return False, f"Lỗi sinh video Wan 2.1: {str(e)}", elapsed
    finally:
        # Giải phóng VRAM toàn bộ
        if pipe is not None:
            del pipe
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

def generate_batch_videos(
    scenes: List[Dict[str, Any]], 
    temp_dir: str,
    orientation: str = "vertical",
    num_frames: int = WAN_DEFAULT_FRAMES,
    num_inference_steps: int = WAN_DEFAULT_STEPS,
    model_id: str = WAN_MODEL_DEFAULT
) -> Tuple[bool, Any, float]:
    """
    Sinh hàng loạt clip video cho các phân cảnh.
    Mỗi phân cảnh sẽ lưu thành scene_001.mp4, scene_002.mp4... trong temp_dir.
    Trả về Tuple[thành_công, danh_sách_đường_dẫn_hoặc_thông_báo_lỗi, thời_gian_chạy_giây].
    """
    pipe = None
    generated_paths = []
    start_time = time.time()
    try:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        width, height = WAN_RESOLUTIONS.get(orientation, (480, 848))
        pipe = _setup_pipeline(model_id)
        
        for i, scene in enumerate(scenes):
            prompt = scene.get("video_prompt", "")
            output_path = os.path.join(temp_dir, f"scene_{i+1:03d}.mp4")
            
            print(f"[{i+1}/{len(scenes)}] Đang sinh clip video: \"{prompt}\" (steps={num_inference_steps})...")
            video_frames = pipe(
                prompt=prompt,
                num_frames=num_frames,
                height=height,
                width=width,
                num_inference_steps=num_inference_steps,
                guidance_scale=5.0
            ).frames[0]
            
            from diffusers.utils import export_to_video
            export_to_video(video_frames, output_path, fps=16)
            generated_paths.append(output_path)
            
        elapsed = time.time() - start_time
        return True, generated_paths, elapsed
        
    except Exception as e:
        elapsed = time.time() - start_time
        return False, f"Lỗi sinh video loạt Wan 2.1: {str(e)}", elapsed
    finally:
        # Giải phóng VRAM toàn bộ sau khi chạy xong loạt
        if pipe is not None:
            del pipe
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
