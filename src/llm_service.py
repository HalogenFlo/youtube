# Chức năng: Giao tiếp với Ollama local LLM để tạo mới và viết lại kịch bản dưới dạng JSON.
# Lý do tạo: Tự động hoá việc soạn thảo kịch bản và sinh prompts cho việc tạo hình ảnh/video.
# Trích dẫn: Tuân thủ quy định API của Ollama và cấu trúc kịch bản phân cảnh trong PLAN.md.

import json
import re
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
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
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


def _fallback_video_metadata(topic: str, language: str = "vi") -> Dict[str, Any]:
    """Tạo metadata an toàn khi Ollama tạm thời không phản hồi."""
    clean_topic = re.sub(r"\s*\((Phần|Part)\s+\d+.*?\)\s*$", "", topic, flags=re.IGNORECASE).strip()
    clean_topic = re.sub(r"\s+", " ", clean_topic).strip(" .,:;-_")
    if language == "vi":
        title = f"{clean_topic}: Điều bất ngờ bạn chưa biết"
        description = f"Khám phá kiến thức ngắn gọn, dễ hiểu và thú vị về {clean_topic}."
        base_tags = ["#kienthuc", "#kienthucmoingay", "#shorts", "#videoAI", "#khampha"]
    else:
        title = f"{clean_topic}: What You Didn't Know"
        description = f"A short, clear and surprising explanation of {clean_topic}."
        base_tags = ["#knowledge", "#learnontiktok", "#shorts", "#AIvideo", "#facts"]

    words = re.findall(r"[^\W\d_]+", clean_topic, flags=re.UNICODE)[:3]
    topic_tag = "#" + "".join(words) if words else ""
    hashtags = ([topic_tag] if topic_tag else []) + base_tags
    return {
        "title": title[:100],
        "description": description,
        "hashtags": hashtags[:8],
    }


def generate_video_metadata(
    topic: str,
    scenes: List[Dict[str, Any]],
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT,
) -> Tuple[bool, Dict[str, Any]]:
    """Sinh tiêu đề, mô tả và hashtag sẵn sàng để đăng cùng video."""
    narration = " ".join(str(scene.get("narration", "")) for scene in scenes)
    lang_name = "tiếng Việt" if language == "vi" else "English"
    system_prompt = (
        "Bạn là chuyên gia metadata cho video kiến thức ngắn. "
        "Chỉ trả về JSON gồm title, description và hashtags. "
        f"Tiêu đề và mô tả viết bằng {lang_name}; title tối đa 100 ký tự, hấp dẫn nhưng không giật tít sai. "
        "hashtags là mảng 5-8 chuỗi, mỗi chuỗi bắt đầu bằng #, không dấu cách."
    )
    prompt = (
        f"Chủ đề: {topic}\n"
        f"Nội dung lời thoại: {narration[:3500]}\n"
        "Tạo metadata đúng trọng tâm nội dung video."
    )
    success, data = call_ollama(prompt, system_prompt, model)
    if success and isinstance(data, dict):
        title = str(data.get("title", "")).strip()
        description = str(data.get("description", "")).strip()
        raw_tags = data.get("hashtags", [])
        if isinstance(raw_tags, str):
            raw_tags = raw_tags.replace(",", " ").split()
        hashtags = []
        for tag in raw_tags if isinstance(raw_tags, list) else []:
            normalized = "#" + re.sub(r"[^\w\u00C0-\u024F]", "", str(tag).lstrip("#"))
            if len(normalized) > 1 and normalized not in hashtags:
                hashtags.append(normalized)
        if title and hashtags:
            return True, {
                "title": title[:100],
                "description": description,
                "hashtags": hashtags[:8],
            }

    return True, _fallback_video_metadata(topic, language)

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

def get_selfheal_system_prompt(script_type: str) -> str:
    """Trả về prompt hệ thống định nghĩa nhiệm vụ của LLM đối với tính năng Học Tiếng Anh Self-heal."""
    type_instructions = ""
    if script_type == "meditation":
        type_instructions = (
            "- Thể loại: Thiền định, tự chữa lành (Self-heal), châm ngôn cuộc sống.\n"
            "- Cấu trúc speaker: Chỉ có 1 speaker duy nhất tên là 'Narrator'.\n"
            "- Nội dung: Những lời khuyên nhẹ nhàng, suy tư sâu sắc về cuộc sống, sự bình yên."
        )
    elif script_type == "interview":
        type_instructions = (
            "- Thể loại: Phỏng vấn, hỏi đáp học tiếng Anh giao tiếp.\n"
            "- Cấu trúc speaker: Có ít nhất 2 speaker, ví dụ 'Interviewer' và 'Guest' (hoặc 'You').\n"
            "- Nội dung: Các câu hỏi phỏng vấn phổ biến và câu trả lời tương ứng ngắn gọn, dễ học."
        )
    elif script_type == "conversation":
        type_instructions = (
            "- Thể loại: Hội thoại giao tiếp tiếng Anh hàng ngày.\n"
            "- Cấu trúc speaker: Có ít nhất 2 speaker, đối thoại qua lại tự nhiên.\n"
            "- Nội dung: Các tình huống giao tiếp thông thường trong cuộc sống, công việc."
        )
    else:  # custom
        type_instructions = (
            "- Thể loại: Tùy chỉnh theo yêu cầu của người dùng.\n"
            "- Cấu trúc speaker: Xác định linh hoạt các nhân vật dựa trên nội dung."
        )

    return (
        "Bạn là một chuyên gia biên kịch video học tiếng Anh Self-heal chuyên nghiệp.\n"
        "Nhiệm vụ của bạn là tạo ra một kịch bản hấp dẫn, phù hợp cho việc tự học và chữa lành.\n"
        f"Yêu cầu thể loại kịch bản:\n{type_instructions}\n\n"
        "Quy tắc kịch bản:\n"
        "1. Kịch bản được chia thành các phân cảnh tuần tự (mỗi phân cảnh dài khoảng 5 giây).\n"
        "2. Nền video BẮT BUỘC phải là các cảnh thiên nhiên thanh bình, êm dịu, không có text trên hình ảnh.\n"
        "3. Lời thoại 'narration' BẮT BUỘC viết bằng tiếng Anh (English).\n"
        "4. Bản dịch 'translation' BẮT BUỘC viết bằng tiếng Việt (Vietnamese) tương ứng sát nghĩa.\n"
        "5. Phải chỉ định rõ 'speaker' cho từng phân cảnh.\n\n"
        "Đầu ra BẮT BUỘC phải là một đối tượng JSON hợp lệ duy nhất có cấu trúc chính xác như sau:\n"
        "{\n"
        "  \"speakers\": [\"Speaker A\", \"Speaker B\"],\n"
        "  \"scenes\": [\n"
        "    {\n"
        "      \"scene_num\": 1,\n"
        "      \"speaker\": \"Speaker A\",\n"
        "      \"narration\": \"Hi! How are you doing today?\",\n"
        "      \"translation\": \"Xin chào! Hôm nay bạn thế nào rồi?\",\n"
        "      \"video_prompt\": \"A peaceful green forest path with sunlight filtering through leaves, gentle morning light, cinematic, 4k\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Lưu ý quan trọng:\n"
        "1. Trả về đúng định dạng JSON, không giải thích thêm trước hoặc sau khối JSON. Chỉ trả về chuỗi JSON thô.\n"
        "2. Trường 'video_prompt' mô tả chi tiết hình ảnh thiên nhiên, ánh sáng, góc máy bằng tiếng Anh."
    )

def generate_selfheal_script(
    topic: str,
    script_type: str = "meditation",
    target_scenes: int = 10,
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Sinh kịch bản Học Tiếng Anh Self-heal từ chủ đề/ý tưởng và thể loại kịch bản.
    """
    user_prompt = (
        f"Hãy viết kịch bản tiếng Anh Self-heal theo chủ đề/ý tưởng sau: \"{topic}\".\n"
        f"Thể loại kịch bản: {script_type}.\n"
        f"YÊU CẦU BẮT BUỘC VỀ SỐ PHÂN CẢNH: Hãy viết chính xác đúng {target_scenes} phân cảnh (scenes từ 1 đến {target_scenes}).\n"
        "Hãy thiết kế các phân cảnh tuần tự với hình ảnh thiên nhiên phù hợp nhất.\n"
        "Lưu ý quan trọng: Nếu trong chủ đề của người dùng có chứa các yêu cầu cụ thể về đóng vai (roles), nhân vật (speakers), bối cảnh cuộc thoại hoặc lời khuyên chi tiết, "
        "bạn BẮT BUỘC phải tuân thủ và triển khai đầy đủ các yêu cầu đó trong kịch bản JSON đầu ra."
    )
    system_prompt = get_selfheal_system_prompt(script_type)
    return call_ollama(user_prompt, system_prompt, model)


def feedback_script(
    current_script: List[Dict[str, Any]],
    feedback: str,
    style_preset: str = "cinematic, detailed, 4k",
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Góp ý bổ sung cho kịch bản Video Ngắn hiện tại.
    AI sẽ giữ lại cấu trúc cũ và cập nhật/chỉnh sửa các scene dựa trên phản hồi.
    """
    user_prompt = (
        "Dưới đây là kịch bản phân cảnh hiện tại dưới dạng JSON:\n"
        f"\"\"\"{json.dumps(current_script, ensure_ascii=False)}\"\"\"\n\n"
        "Yêu cầu góp ý chỉnh sửa bổ sung từ người dùng:\n"
        f"\"\"\"{feedback}\"\"\"\n\n"
        f"Phong cách hình ảnh yêu cầu cho các video prompt: \"{style_preset}\".\n"
        "Hãy cập nhật lại kịch bản JSON theo góp ý trên. Giữ nguyên định dạng và nội dung các phân cảnh không bị yêu cầu sửa đổi."
    )
    return call_ollama(user_prompt, get_system_prompt(language), model)


def feedback_selfheal_script(
    current_script: List[Dict[str, Any]],
    feedback: str,
    script_type: str = "interview",
    target_scenes: int = 10,
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Góp ý bổ sung cho kịch bản Self-heal hiện tại.
    AI sẽ giữ lại các phân cảnh cũ và chỉ cập nhật/chỉnh sửa theo phản hồi của người dùng.
    """
    user_prompt = (
        "Dưới đây là kịch bản Self-heal hiện tại dưới dạng JSON:\n"
        f"\"\"\"{json.dumps(current_script, ensure_ascii=False)}\"\"\"\n\n"
        "Yêu cầu góp ý chỉnh sửa bổ sung từ người dùng:\n"
        f"\"\"\"{feedback}\"\"\"\n\n"
        f"YÊU CẦU SỐ PHÂN CẢNH MỤC TIÊU: Kịch bản cập nhật nên có khoảng {target_scenes} phân cảnh.\n"
        "Hãy cập nhật lại kịch bản JSON theo góp ý trên. Giữ nguyên định dạng, danh sách speakers và nội dung các phân cảnh không liên quan.\n"
        "Nếu người dùng muốn mở rộng, kéo dài kịch bản để video dài hơn, hãy sinh thêm các phân cảnh mới tiếp nối một cách hợp lý."
    )
    return call_ollama(user_prompt, get_selfheal_system_prompt(script_type), model)


def get_translation_system_prompt(source_lang: str, target_lang: str) -> str:
    """Trả về prompt hệ thống cho nhiệm vụ dịch thuật thoại video."""
    return (
        f"Bạn là một chuyên gia dịch thuật phim và video chuyên nghiệp.\n"
        f"Nhiệm vụ của bạn là dịch các câu thoại từ ngôn ngữ gốc ({source_lang}) sang ngôn ngữ đích ({target_lang}).\n"
        f"Quy tắc dịch:\n"
        f"1. Dịch chính xác, tự nhiên, trôi chảy, phù hợp ngữ cảnh nói của video.\n"
        f"2. Câu dịch ngắn gọn, súc tích để khi lồng tiếng (TTS) khớp với khoảng thời gian (timing) gốc.\n"
        f"3. Đầu ra BẮT BUỘC là một mảng JSON chứa các câu đã dịch theo đúng thứ tự của mảng đầu vào.\n"
        f"Ví dụ định dạng đầu ra:\n"
        f"[\n"
        f"  \"câu dịch 1\",\n"
        f"  \"câu dịch 2\"\n"
        f"]\n"
        f"Chỉ trả về chuỗi JSON thô của mảng, không có bất kỳ giải thích nào bên ngoài."
    )


def translate_segments_batch(
    segments: List[Dict[str, Any]],
    source_lang: str,
    target_lang: str,
    model: str = OLLAMA_MODEL_DEFAULT
) -> List[Dict[str, Any]]:
    """
    Dịch hàng loạt các đoạn thoại video trong 1 lần gọi Ollama để tối ưu hiệu năng.
    Mỗi segment: {"text": "...", "start": 0.0, "end": 3.0}
    Trả về danh sách segment đã bổ sung trường "translated_text".
    """
    if not segments:
        return []
        
    texts_to_translate = [seg["text"] for seg in segments]
    
    # Map tên ngôn ngữ hiển thị
    lang_map = {
        "zh": "Tiếng Trung (Chinese)",
        "en": "Tiếng Anh (English)",
        "vi": "Tiếng Việt (Vietnamese)"
    }
    src_display = lang_map.get(source_lang, source_lang)
    tgt_display = lang_map.get(target_lang, target_lang)
    
    system_prompt = get_translation_system_prompt(src_display, tgt_display)
    user_prompt = f"Hãy dịch mảng các câu thoại sau đây:\n{json.dumps(texts_to_translate, ensure_ascii=False)}"
    
    payload = {
        "model": model,
        "prompt": f"System:\n{system_prompt}\n\nUser:\n{user_prompt}",
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.3, # Đặt nhiệt độ thấp để dịch chính xác hơn
            "num_predict": 2048
        }
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "").strip()
            translated_list = json.loads(response_text)
            
            if isinstance(translated_list, list) and len(translated_list) == len(segments):
                # Gán bản dịch vào từng segment tương ứng
                updated_segments = []
                for idx, seg in enumerate(segments):
                    updated_seg = seg.copy()
                    updated_seg["translated_text"] = str(translated_list[idx]).strip()
                    updated_segments.append(updated_seg)
                return updated_segments
            else:
                print(f"Kích thước mảng dịch không khớp: nhận được {len(translated_list)} thay vì {len(segments)}.")
        else:
            print(f"Ollama trả về mã lỗi HTTP: {response.status_code}")
    except Exception as e:
        print(f"Lỗi khi gọi batch dịch qua Ollama: {str(e)}")
        
    # Fallback: Nếu lỗi hoặc không khớp số lượng, gán translated_text = text gốc
    updated_segments = []
    for seg in segments:
        updated_seg = seg.copy()
        updated_seg["translated_text"] = seg["text"]
        updated_segments.append(updated_seg)
    return updated_segments


def get_educational_system_prompt(language: str = "vi") -> str:
    """Trả về prompt hệ thống định nghĩa nhiệm vụ tạo kịch bản bài dạy/slideshow."""
    lang_name = "tiếng Việt" if language == "vi" else "tiếng Anh (English)"
    lang_instruction = (
        "Lời thoại giảng giải bằng tiếng Việt rõ ràng, ngắn gọn và súc tích như một giảng viên công nghệ."
        if language == "vi"
        else "Educational narration text in English. Clear, educational, short, and natural."
    )
    return (
        "Bạn là một giảng viên công nghệ và chuyên gia biên soạn bài giảng điện tử chuyên nghiệp.\n"
        "Nhiệm vụ của bạn là tạo ra một kịch bản bài dạy dạng slideshow (AI Slideshow Video) sinh động, dễ hiểu.\n"
        "Kịch bản phải được chia thành các phân cảnh tuần tự liền mạch (mỗi cảnh dài khoảng 5-7 giây).\n"
        "Đầu ra BẮT BUỘC phải là một đối tượng JSON hợp lệ duy nhất có cấu trúc như sau:\n"
        "{\n"
        "  \"scenes\": [\n"
        "    {\n"
        "      \"scene_num\": 1,\n"
        "      \"narration\": \"" + lang_instruction + "\",\n"
        "      \"video_prompt\": \"English description of a technical/infographic slide. E.g., 'A modern infographic diagram showing Docker architecture with client, host and registry, clean flat vector design, high tech illustration, soft blue gradient background, 4k'\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Lưu ý quan trọng:\n"
        f"1. Lời thoại 'narration' viết hoàn toàn bằng {lang_name}.\n"
        "2. Trường 'video_prompt' viết hoàn toàn bằng tiếng Anh để dùng cho Stable Diffusion/Wan 2.1. Phải mô tả dạng hình minh họa công nghệ (tech illustration), đồ họa phẳng (flat design), sơ đồ (diagram, infographic), giao diện sạch sẽ (clean UI/UX), tránh vẽ chữ viết ngoằn ngoèo không đọc được. Không vẽ cảnh phim cinematic thông thường trừ khi chủ đề yêu cầu.\n"
        "3. Không thêm bất kỳ văn bản giải thích nào ngoài khối JSON. Chỉ trả về chuỗi JSON thô."
    )


def generate_educational_script(
    topic: str,
    style_preset: str = "modern tech illustration, flat design, clean UI, soft gradient background, 4k",
    language: str = "vi",
    target_scenes: int = 8,
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Tạo kịch bản bài dạy AI Slideshow từ một từ khóa/chủ đề.
    """
    user_prompt = (
        f"Hãy viết một kịch bản bài dạy/slideshow cho chủ đề: \"{topic}\".\n"
        f"Phong cách hình ảnh slide yêu cầu cho các video prompt: \"{style_preset}\".\n"
        f"YÊU CẦU SỐ PHÂN CẢNH: Hãy viết chính xác đúng {target_scenes} phân cảnh (scenes từ 1 đến {target_scenes}).\n"
        "Đảm bảo cấu trúc bài giảng rõ ràng:\n"
        "- Cảnh đầu: Đặt vấn đề hoặc giới thiệu lôi cuốn.\n"
        "- Các cảnh giữa: Giải thích chi tiết khái niệm, tính năng, ví dụ minh họa hoặc mẹo thực tế.\n"
        "- Cảnh cuối: Tóm tắt bài học và kêu gọi hành động (CTA).\n"
        "Hãy viết nội dung giảng giải sinh động, có cấu trúc và đúng định dạng JSON yêu cầu."
    )
    return call_ollama(user_prompt, get_educational_system_prompt(language), model)


def generate_script_from_doc(
    doc_content: str,
    style_preset: str = "modern tech illustration, flat design, clean UI, soft gradient background, 4k",
    language: str = "vi",
    target_scenes: int = 8,
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Phân tích và chuyển đổi nội dung tài liệu dán trực tiếp thành kịch bản bài dạy AI Slideshow.
    """
    user_prompt = (
        "Dưới đây là nội dung tài liệu học tập/hướng dẫn kỹ thuật:\n"
        f"\"\"\"{doc_content}\"\"\"\n\n"
        "Yêu cầu:\n"
        f"1. Hãy phân tích và chắt lọc nội dung tài liệu trên để viết thành một kịch bản bài giảng/slideshow hoàn chỉnh.\n"
        f"2. Phong cách hình ảnh slide yêu cầu cho các video prompt: \"{style_preset}\".\n"
        f"3. YÊU CẦU SỐ PHÂN CẢNH: Hãy viết chính xác đúng {target_scenes} phân cảnh (scenes từ 1 đến {target_scenes}).\n"
        "Đảm bảo các phân cảnh tóm gọn chuẩn xác các ý chính của tài liệu, truyền tải lời giảng hấp dẫn, dễ hiểu và đúng định dạng JSON yêu cầu."
    )
    return call_ollama(user_prompt, get_educational_system_prompt(language), model)


def feedback_educational_script(
    current_script: List[Dict[str, Any]],
    feedback: str,
    style_preset: str = "modern tech illustration, flat design, clean UI, soft gradient background, 4k",
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT
) -> Tuple[bool, Any]:
    """
    Góp ý chỉnh sửa kịch bản bài dạy hiện tại dựa trên góp ý của người dùng.
    AI sẽ giữ lại cấu trúc cũ và cập nhật/chỉnh sửa các phân cảnh tương ứng.
    """
    user_prompt = (
        "Dưới đây là kịch bản bài giảng/slideshow hiện tại dưới dạng JSON:\n"
        f"\"\"\"{json.dumps(current_script, ensure_ascii=False)}\"\"\"\n\n"
        "Yêu cầu góp ý chỉnh sửa bổ sung từ người dùng:\n"
        f"\"\"\"{feedback}\"\"\"\n\n"
        f"Phong cách hình ảnh slide yêu cầu cho các video prompt: \"{style_preset}\".\n"
        "Hãy cập nhật lại kịch bản JSON theo góp ý trên. Giữ nguyên định dạng và nội dung các phân cảnh không bị yêu cầu sửa đổi."
    )
    return call_ollama(user_prompt, get_educational_system_prompt(language), model)


