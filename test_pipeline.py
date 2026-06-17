# Chức năng: Kiểm thử tích hợp toàn bộ pipeline từ đầu vào kịch bản đến video đầu ra.
# Lý do tạo: Xác minh tính đúng đắn của các module AI và FFmpeg trước khi chạy giao diện Streamlit.
# Trích dẫn: Dựa trên kế hoạch kiểm thử tự động trong PLAN.md.

import os
import sys
import torch

# Ép console Windows sử dụng UTF-8 để in emoji và tiếng Việt không bị lỗi encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Thêm thư mục hiện tại vào sys.path để import các module trong src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import TEMP_DIR, OUTPUT_DIR, FONT_PATH
from src.llm_service import generate_script
from src.tts_service import generate_tts
from src.image_service import generate_single_image
from src.whisper_service import get_word_timestamps
from src.video_compiler import compile_video_pipeline

def run_integration_test():
    print("=" * 60)
    print("🚀 BẮT ĐẦU KIỂM THỬ TÍCH HỢP HỆ THỐNG VIDEO PIPELINE")
    print("=" * 60)
    
    # 0. Kiểm tra GPU CUDA
    print("\n[Bước 0] Kiểm tra tài nguyên GPU...")
    if torch.cuda.is_available():
        print(f"✓ Tìm thấy GPU: {torch.cuda.get_device_name(0)}")
        print(f"✓ VRAM khả dụng: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
    else:
        print("⚠ KHÔNG tìm thấy GPU CUDA. Các tác vụ sinh ảnh/video sẽ chạy trên CPU hoặc có thể bị lỗi.")

    # 1. Kiểm tra Font chữ
    print("\n[Bước 1] Kiểm tra file Font chữ...")
    if os.path.exists(FONT_PATH):
        print(f"✓ Font chữ tồn tại tại: {FONT_PATH}")
    else:
        print(f"✗ Thiếu font chữ tại {FONT_PATH}. Vui lòng chạy lệnh download font trước.")
        return False

    # 2. Kiểm thử Ollama LLM
    print("\n[Bước 2] Gọi Ollama để sinh kịch bản thử nghiệm...")
    topic = "3 sự thật thú vị về Trái Đất"
    print(f"Chủ đề thử nghiệm: \"{topic}\"")
    success, data = generate_script(topic, style_preset="anime style, colorful")
    
    if not success:
        print(f"✗ Thất bại khi gọi Ollama: {data}")
        print("Mẹo: Đảm bảo Ollama đã được bật (ollama serve) và đã pull model qwen2.5:7b-instruct.")
        return False
        
    print("✓ Ollama phản hồi thành công!")
    scenes = data.get("scenes", [])
    if not scenes:
        print("✗ Kịch bản trống hoặc sai cấu trúc JSON.")
        return False
        
    print(f"✓ Đã tạo kịch bản gồm {len(scenes)} phân cảnh.")
    
    # Giới hạn chỉ test 2 phân cảnh đầu tiên để tiết kiệm thời gian và tài nguyên
    test_scenes = scenes[:2]
    print(f"Đang tiến hành test thử nghiệm với 2 phân cảnh đầu:")

    # Khởi tạo các đường dẫn tài nguyên cho phân cảnh test
    for i, scene in enumerate(test_scenes):
        scene["audio_path"] = os.path.join(TEMP_DIR, f"test_scene_{i+1:03d}.mp3")
        scene["image_path"] = os.path.join(TEMP_DIR, f"test_scene_{i+1:03d}.png")
        scene["use_video_ai"] = False # Dùng ảnh cho nhanh
        print(f"  Cảnh {i+1}: - Lời thoại: {scene['narration']}")
        print(f"            - Prompt: {scene['video_prompt']}")

    # 3. Kiểm thử Edge-TTS
    print("\n[Bước 3] Sinh giọng đọc tiếng Việt bằng edge-tts...")
    for i, scene in enumerate(test_scenes):
        audio_success, audio_path = generate_tts(
            text=scene["narration"],
            output_path=scene["audio_path"]
        )
        if not audio_success:
            print(f"✗ Thất bại khi sinh giọng đọc Cảnh {i+1}: {audio_path}")
            return False
        # Đọc thời lượng
        try:
            from mutagen.mp3 import MP3
            audio = MP3(audio_path)
            scene["audio_duration"] = audio.info.length
        except Exception:
            # Fallback nếu thiếu mutagen
            scene["audio_duration"] = 5.0
            
        print(f"✓ Đã sinh audio cho Cảnh {i+1} ({scene['audio_duration']:.2f}s): {audio_path}")

    # 4. Kiểm thử Stable Diffusion 1.5
    print("\n[Bước 4] Sinh hình ảnh bằng Stable Diffusion (dreamshaper-8)...")
    print("Lưu ý: Lần chạy đầu tiên sẽ tải model từ Hugging Face (~2 GB), vui lòng kiên nhẫn...")
    for i, scene in enumerate(test_scenes):
        img_success, img_path = generate_single_image(
            prompt=scene["video_prompt"],
            output_path=scene["image_path"],
            orientation="vertical",
            style_preset="anime, detailed, 4k",
            steps=2 # Tốc độ cao trên CPU để kiểm thử tích hợp nhanh
        )
        if not img_success:
            print(f"✗ Thất bại khi sinh ảnh Cảnh {i+1}: {img_path}")
            return False
        print(f"✓ Đã sinh ảnh cho Cảnh {i+1}: {img_path}")

    # 5. Kiểm thử Faster-Whisper
    print("\n[Bước 5] Phân tích âm thanh để lấy timestamps bằng Whisper...")
    print("Lưu ý: Lần chạy đầu tiên sẽ tải model Whisper small (~1 GB) về máy...")
    all_words = []
    cumulative_time = 0.0
    
    for i, scene in enumerate(test_scenes):
        w_success, words = get_word_timestamps(scene["audio_path"])
        if not w_success:
            print(f"✗ Thất bại khi phân tích âm thanh Cảnh {i+1}: {words}")
            return False
            
        for w in words:
            shifted_word = {
                "word": w["word"],
                "start": w["start"] + cumulative_time,
                "end": w["end"] + cumulative_time
            }
            all_words.append(shifted_word)
            
        cumulative_time += scene["audio_duration"]
        print(f"✓ Đã lấy timestamps cho Cảnh {i+1} (Tìm thấy {len(words)} từ).")

    # 6. Kiểm thử Video Compiler (MoviePy + FFmpeg Subtitle Burn)
    print("\n[Bước 6] Tiến hành kết nối video và burn phụ đề...")
    compile_success, final_videos, compile_err = compile_video_pipeline(
        scenes=test_scenes,
        words_timestamps=all_words,
        max_duration=30.0, # Test 30s
        orientation="vertical"
    )
    
    if not compile_success:
        print(f"✗ Thất bại ở bước ghép video và burn phụ đề: {compile_err}")
        return False
        
    print("\n" + "=" * 60)
    print("🎉 KIỂM THỬ THÀNH CÔNG RỰC RỠ!")
    print("=" * 60)
    print(f"Video thành phẩm đã được lưu tại:")
    for video in final_videos:
        print(f"👉 {video}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
