# Chức năng: Giao tiếp với Ollama local LLM để tạo mới và viết lại kịch bản dưới dạng JSON.
# Lý do tạo: Tự động hoá việc soạn thảo kịch bản và sinh prompts cho việc tạo hình ảnh/video.
# Trích dẫn: Tuân thủ quy định API của Ollama và cấu trúc kịch bản phân cảnh trong PLAN.md.

import json
import requests
from typing import Tuple, Dict, Any, List
from src.config import OLLAMA_API_URL, OLLAMA_MODEL_DEFAULT

def get_system_prompt(language: str = "vi") -> str:
    """Trả về prompt hệ thống định nghĩa nhiệm vụ của LLM."""
    lang_name = "tiếng Việt" if language == "vi" else "tiếng Anh (English)"
    lang_instruction = (
        "Lời thoại đọc bằng tiếng Việt cho cảnh 1. Ngắn gọn, súc tích, tự nhiên."
        if language == "vi"
        else "Narration text in English for scene 1. Short, punchy, and natural."
    )
    return (
        "Bạn là một chuyên gia biên kịch video ngắn (Shorts, TikTok, Reels) chuyên nghiệp.\n"
        "Nhiệm vụ của bạn là tạo ra một kịch bản hấp dẫn, thu hút người xem ngay từ những giây đầu tiên.\n"
        "Kịch bản phải được chia thành các phân cảnh tuần tự liền mạch (mỗi cảnh dài khoảng 5 giây).\n"
        "Đầu ra BẮT BUỘC phải là một đối tượng JSON hợp lệ duy nhất có cấu trúc như sau:\n"
        "{\n"
        "  \"scenes\": [\n"
        "    {\n"
        "      \"scene_num\": 1,\n"
        "      \"narration\": \"" + lang_instruction + "\",\n"
        "      \"video_prompt\": \"English description of the visual scene for AI image/video generation. Include styles, lighting, camera angles, detailed details, no text on image.\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Lưu ý quan trọng:\n"
        f"1. Lời thoại 'narration' viết hoàn toàn bằng {lang_name}.\n"
        "2. Trường 'video_prompt' viết hoàn toàn bằng tiếng Anh để dùng cho Stable Diffusion/Wan 2.1. Phải mô tả chi tiết hình ảnh, màu sắc, ánh sáng, góc máy.\n"
        "3. Không thêm bất kỳ văn bản giải thích nào ngoài khối JSON. Chỉ trả về chuỗi JSON thô."
    )

def call_ollama(prompt: str, system_prompt: str, model: str = OLLAMA_MODEL_DEFAULT) -> Tuple[bool, Any]:
    """
    Gọi API Ollama để sinh văn bản.
    Sử dụng chế độ format='json' của Ollama để ép đầu ra là JSON.
    """
    payload = {
        "model": model,
        "prompt": f"System:\n{system_prompt}\n\nUser:\n{prompt}",
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 2048
        }
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "").strip()
            try:
                data = json.loads(response_text)
                return True, data
            except json.JSONDecodeError:
                return False, f"Ollama returned non-JSON content: {response_text}"
        else:
            return False, f"Ollama API error: HTTP Status {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Không thể kết nối tới Ollama. Hãy chắc chắn Ollama đang chạy tại {OLLAMA_API_URL}. Chi tiết lỗi: {e}"

def generate_script(
    topic: str, 
    style_preset: str = "cinematic, detailed, 4k", 
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Luồng A: Sinh kịch bản mới hoàn toàn từ chủ đề/ý tưởng.
    """
    user_prompt = (
        f"Hãy viết kịch bản video ngắn cho chủ đề/ý tưởng sau: \"{topic}\".\n"
        f"Phong cách hình ảnh yêu cầu cho các video prompt: \"{style_preset}\".\n"
        "Đảm bảo mạch câu chuyện liền mạch, hấp dẫn và cấu trúc đúng định dạng JSON."
    )
    return call_ollama(user_prompt, get_system_prompt(language), model)

def remake_script(
    transcript: str, 
    edit_instructions: str, 
    style_preset: str = "cinematic, detailed, 4k", 
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Luồng B: Viết lại kịch bản dựa trên transcript của video cũ và các chỉ dẫn chỉnh sửa mới.
    """
    user_prompt = (
        "Dưới đây là kịch bản/transcript của một video gốc:\n"
        f"\"\"\"{transcript}\"\"\"\n\n"
        "Yêu cầu từ người dùng để viết lại kịch bản này:\n"
        f"\"\"\"{edit_instructions}\"\"\"\n\n"
        f"Phong cách hình ảnh yêu cầu cho các video prompt: \"{style_preset}\".\n"
        "Hãy giữ lại khung sườn cốt lõi của câu chuyện nhưng biến đổi nội dung lời thoại "
        "và mô tả cảnh theo đúng yêu cầu chỉnh sửa của người dùng. Xuất ra định dạng JSON quy định."
    )
    return call_ollama(user_prompt, get_system_prompt(language), model)
