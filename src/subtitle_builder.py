# Chức năng: Tạo file phụ đề ASS (.ass) với hiệu ứng karaoke đồng bộ từ word-level timestamps.
# Lý do tạo: Tự động hoá việc tạo phụ đề động bắt mắt theo phong cách Shorts/TikTok.
# Trích dẫn: Tuân thủ đặc tả định dạng phụ đề ASS (Advanced SubStation Alpha).

import os
from typing import List, Dict, Any, Tuple

def format_time(seconds: float) -> str:
    """
    Chuyển đổi giây (float) thành định dạng thời gian ASS: H:MM:SS.cs
    Ví dụ: 85.24 -> 0:01:25.24
    """
    # Tránh giá trị âm
    secs = max(0.0, seconds)
    hours = int(secs // 3600)
    minutes = int((secs % 3600) // 60)
    remaining_secs = secs % 60
    centiseconds = int(round((remaining_secs - int(remaining_secs)) * 100))
    
    # Nếu làm tròn lên 100 centiseconds
    if centiseconds == 100:
        remaining_secs += 1
        centiseconds = 0
        if remaining_secs >= 60:
            minutes += 1
            remaining_secs -= 60
            if minutes >= 60:
                hours += 1
                minutes -= 60

    return f"{hours}:{minutes:02d}:{int(remaining_secs):02d}.{centiseconds:02d}"

def clean_word(word: str) -> str:
    """Lọc các ký tự có thể làm hỏng thẻ điều khiển ASS."""
    return word.replace("{", "").replace("}", "").replace("\\", "")

def group_words_into_lines(
    words: List[Dict[str, Any]], 
    max_words: int = 4
) -> List[List[Dict[str, Any]]]:
    """
    Gom nhóm danh sách các từ thành từng dòng phụ đề dựa trên:
    - Giới hạn số từ trên một dòng (max_words).
    - Khoảng lặng lớn giữa các từ (> 0.8 giây).
    - Dấu câu ngắt câu (. ? ! ;).
    """
    if not words:
        return []
        
    lines: List[List[Dict[str, Any]]] = []
    current_line: List[Dict[str, Any]] = []
    
    for i, w in enumerate(words):
        current_line.append(w)
        
        # Kiểm tra điều kiện ngắt dòng
        should_split = False
        
        # 1. Đạt số từ tối đa
        if len(current_line) >= max_words:
            should_split = True
            
        # 2. Có dấu câu ngắt ở từ hiện tại
        elif w["word"].endswith((".", "?", "!", ";", ":")):
            should_split = True
            
        # 3. Khoảng lặng với từ tiếp theo lớn (> 0.8s)
        elif i < len(words) - 1:
            next_w = words[i + 1]
            if next_w["start"] - w["end"] > 0.8:
                should_split = True
                
        if should_split:
            lines.append(current_line)
            current_line = []
            
    if current_line:
        lines.append(current_line)
        
    return lines

def build_ass_subtitle(
    words: List[Dict[str, Any]], 
    output_path: str, 
    orientation: str = "vertical"
) -> Tuple[bool, str]:
    """
    Tạo file phụ đề ASS karaoke từ danh sách các từ.
    Hỗ trợ tuỳ chỉnh kích thước và vị trí theo hướng video (dọc/ngang).
    """
    try:
        # Đảm bảo thư mục cha tồn tại
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        # Cấu hình hiển thị theo hướng video
        if orientation == "vertical":
            # Video dọc (ví dụ 1080x1920)
            play_res_x = 1080
            play_res_y = 1920
            font_size = 72
            # Đặt phụ đề ở giữa màn hình (tránh nút UI của TikTok/Shorts ở dưới)
            vertical_margin = 960  # Căn giữa theo chiều dọc
            alignment = 5          # Alignment 5: Căn giữa chính giữa màn hình
            max_words_per_line = 4
        else:
            # Video ngang (ví dụ 1920x1080)
            play_res_x = 1920
            play_res_y = 1080
            font_size = 54
            vertical_margin = 150  # Cách đáy 150px
            alignment = 2          # Alignment 2: Căn giữa ở đáy
            max_words_per_line = 7

        # Khởi tạo nội dung file ASS
        # Style định nghĩa:
        # PrimaryColor: Trắng (&H00FFFFFF) - chữ chưa đọc
        # SecondaryColor: Vàng neon (&H0000FFFF) - màu karaoke khi chạy qua
        # OutlineColor: Đen (&H00000000) - viền đen dày nổi bật
        # BackColor: Đen trong suốt (&H80000000) - bóng đổ
        ass_content = [
            "[Script Info]",
            "Title: Automated Karaoke Subtitles",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,Montserrat,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,{alignment},50,50,{vertical_margin},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        # Gom nhóm từ thành dòng
        lines = group_words_into_lines(words, max_words=max_words_per_line)
        
        for line in lines:
            if not line:
                continue
                
            line_start = line[0]["start"]
            line_end = line[-1]["end"]
            
            # Tạo chuỗi karaoke dạng ASS
            karaoke_text = ""
            
            for i, w in enumerate(line):
                w_word = clean_word(w["word"])
                
                # Từ đầu tiên
                if i == 0:
                    # Tính thời gian sáng của từ đầu tiên tính bằng centisecond
                    duration = int(round((w["end"] - line_start) * 100))
                    karaoke_text += f"{{\\k{duration}}}{w_word}"
                # Các từ tiếp theo
                else:
                    prev_w = line[i - 1]
                    # Tính khoảng thời gian từ lúc từ trước kết thúc đến lúc từ này kết thúc
                    # Công thức này bao hàm cả khoảng lặng giữa 2 từ
                    duration = int(round((w["end"] - prev_w["end"]) * 100))
                    karaoke_text += f"{{\\k{duration}}} {w_word}"
            
            # Format thời gian
            start_str = format_time(line_start)
            end_str = format_time(line_end)
            
            # Ghi dòng dialogue
            ass_content.append(
                f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{karaoke_text}"
            )
            
        # Ghi file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content))
            
        return True, output_path
        
    except Exception as e:
        return False, f"Lỗi tạo file phụ đề ASS: {str(e)}"
