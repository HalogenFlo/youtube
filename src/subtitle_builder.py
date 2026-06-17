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


def calculate_word_timings(
    narration: str, 
    scene_start: float, 
    wpm: int = 130
) -> List[Dict[str, Any]]:
    """
    Tính toán mốc thời gian (start, end) cho từng từ dựa trên tốc độ đọc (WPM) và độ dài ký tự của từ.
    Dùng cho các phân cảnh của speaker không có giọng nói.
    """
    words = narration.strip().split()
    if not words:
        return []
        
    # Tổng thời lượng dự kiến cho toàn bộ câu (giây)
    total_duration = (len(words) / wpm) * 60.0
    
    # Tính số ký tự của mỗi từ
    word_lengths = [len(clean_word(w)) for w in words]
    total_chars = sum(word_lengths)
    
    if total_chars == 0:
        total_chars = len(words)
        word_lengths = [1] * len(words)
        
    word_timings = []
    current_start = scene_start
    
    for i, word in enumerate(words):
        duration = (word_lengths[i] / total_chars) * total_duration
        duration = max(0.15, duration)  # Giới hạn thời lượng tối thiểu
        
        w_end = current_start + duration
        word_timings.append({
            "word": word,
            "start": current_start,
            "end": w_end
        })
        current_start = w_end
        
    return word_timings


def split_translation_to_lines(translation: str, num_lines: int) -> List[str]:
    """
    Tách câu dịch tiếng Việt thành num_lines phần ngắn tương ứng với các dòng phụ đề.
    Ưu tiên ngắt tại dấu câu hoặc liên từ tiếng Việt thông dụng.
    """
    from src.config import VI_SPLIT_CONJUNCTIONS
    
    translation = translation.strip()
    if num_lines <= 1 or not translation:
        return [translation]
        
    words = translation.split()
    if len(words) <= num_lines:
        return words + [""] * (num_lines - len(words))
        
    # Tìm các vị trí ngắt tự nhiên
    split_indices = []
    for i, w in enumerate(words):
        if i == len(words) - 1:
            continue
            
        # Ngắt ở dấu câu
        if w.endswith((".", ",", "?", "!", ";", ":")):
            split_indices.append(i + 1)
        # Ngắt ở liên từ
        elif w.lower() in VI_SPLIT_CONJUNCTIONS:
            split_indices.append(i)
            
    # Nếu không có điểm ngắt nào, chia đều theo số từ
    if not split_indices:
        chunk_size = len(words) // num_lines
        parts = []
        for i in range(num_lines):
            if i == num_lines - 1:
                parts.append(" ".join(words[i * chunk_size:]))
            else:
                parts.append(" ".join(words[i * chunk_size:(i + 1) * chunk_size]))
        return parts
        
    # Phân bổ các điểm ngắt đều nhất để tạo thành num_lines phần
    points = [0] + sorted(list(set(split_indices))) + [len(words)]
    
    # Bổ sung điểm chia đều nếu thiếu
    while len(points) - 1 < num_lines:
        max_gap_idx = 0
        max_gap = 0
        for i in range(len(points) - 1):
            gap = points[i+1] - points[i]
            if gap > max_gap:
                max_gap = gap
                max_gap_idx = i
        mid_point = points[max_gap_idx] + max_gap // 2
        if mid_point not in points:
            points.append(mid_point)
            points.sort()
        else:
            break
            
    # Lọc bớt điểm chia nếu thừa
    if len(points) - 1 > num_lines:
        step = (len(points) - 1) / num_lines
        new_points = [0]
        for i in range(1, num_lines):
            idx = int(round(i * step))
            new_points.append(points[idx])
        new_points.append(len(words))
        points = new_points
        
    parts = []
    for i in range(len(points) - 1):
        parts.append(" ".join(words[points[i]:points[i+1]]))
    return parts


def build_bilingual_ass_subtitle(
    words: List[Dict[str, Any]],
    translations: List[Dict[str, Any]],
    speaker_segments: List[Dict[str, Any]],
    output_path: str,
    orientation: str = "vertical",
    show_translation: bool = True
) -> Tuple[bool, str]:
    r"""
    Tạo file phụ đề ASS karaoke song ngữ Anh-Việt theo phong cách máy nhắc bài (Teleprompter).
    Hiển thị dòng hiện tại dạng Karaoke ở trên, dòng dịch ở giữa, và dòng chuẩn bị mờ ở dưới.
    """
    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        if orientation == "vertical":
            play_res_x = 1080
            play_res_y = 1920
            font_size = 64
            font_size_vi = 40
            font_size_next = 48
            x_pos = 540
            y_current = 900
            y_vi = 980
            y_next = 1080
            max_words_per_line = 4
        else:
            play_res_x = 1920
            play_res_y = 1080
            font_size = 54
            font_size_vi = 36
            font_size_next = 40
            x_pos = 960
            y_current = 700
            y_vi = 775
            y_next = 870
            max_words_per_line = 7

        # Khởi tạo nội dung file ASS
        ass_content = [
            "[Script Info]",
            "Title: Bilingual Karaoke Subtitles",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        ]

        # Đăng ký Style cho từng speaker
        speaker_styles = {}
        registered_speakers = set()
        
        for seg in speaker_segments:
            spk = seg["speaker"]
            if spk not in registered_speakers:
                color = seg.get("color", "&H0000FFFF")
                style_name = f"Speaker_{spk.replace(' ', '_')}"
                speaker_styles[spk] = style_name
                ass_content.append(
                    f"Style: {style_name},Montserrat,{font_size},&H00FFFFFF,{color},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,5,50,50,0,1"
                )
                registered_speakers.add(spk)

        # Style mặc định
        if "Default" not in registered_speakers:
            ass_content.append(
                f"Style: Default,Montserrat,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,5,50,50,0,1"
            )

        # Style cho tiếng Việt
        ass_content.append(
            f"Style: Vietnamese,Montserrat,{font_size_vi},&H60FFFFFF,&H60FFFFFF,&H00000000,&H80000000,0,1,0,0,100,100,0,0,1,3,1,5,50,50,0,1"
        )
        
        # Style cho dòng chuẩn bị tiếp theo (NextLine)
        ass_content.append(
            f"Style: NextLine,Montserrat,{font_size_next},&H80C0C0C0,&H80C0C0C0,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,5,50,50,0,1"
        )

        ass_content.extend([
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ])

        # Chia nhóm từ thành dòng
        lines = group_words_into_lines(words, max_words=max_words_per_line)
        
        for idx, line in enumerate(lines):
            if not line:
                continue
                
            line_start = line[0]["start"]
            line_end = line[-1]["end"]
            mid_time = (line_start + line_end) / 2.0
            
            # 1. Xác định speaker của dòng
            current_speaker = "Default"
            current_style = "Default"
            for seg in speaker_segments:
                if seg["start"] <= mid_time <= seg["end"]:
                    current_speaker = seg["speaker"]
                    current_style = speaker_styles.get(current_speaker, "Default")
                    break
            
            # 2. Tạo karaoke text tiếng Anh
            karaoke_text = ""
            for i, w in enumerate(line):
                w_word = clean_word(w["word"])
                if i == 0:
                    duration = int(round((w["end"] - line_start) * 100))
                    karaoke_text += f"{{\\k{duration}}}{w_word}"
                else:
                    prev_w = line[i - 1]
                    duration = int(round((w["end"] - prev_w["end"]) * 100))
                    karaoke_text += f"{{\\k{duration}}} {w_word}"

            # Format thời gian
            start_str = format_time(line_start)
            end_str = format_time(line_end)

            # 3. Ghi dòng hiện tại (Tiếng Anh Karaoke) ở tọa độ y_current
            ass_content.append(
                f"Dialogue: 0,{start_str},{end_str},{current_style},,0,0,0,,{{\\pos({x_pos},{y_current})}}{karaoke_text}"
            )

            # 4. Ghi dòng dịch (tiếng Việt tĩnh) ở tọa độ y_vi (nếu có)
            vi_text = ""
            if show_translation:
                matching_translation = ""
                for trans in translations:
                    if trans["start"] <= mid_time <= trans["end"]:
                        matching_translation = trans["text"]
                        break
                
                if matching_translation:
                    # Đếm số dòng thuộc scene này để chia phần
                    scene_lines_count = 0
                    line_index_in_scene = 0
                    for temp_line in lines:
                        if not temp_line:
                            continue
                        t_mid = (temp_line[0]["start"] + temp_line[-1]["end"]) / 2.0
                        for trans in translations:
                            if trans["start"] <= t_mid <= trans["end"]:
                                if trans["text"] == matching_translation:
                                    if temp_line == line:
                                        line_index_in_scene = scene_lines_count
                                    scene_lines_count += 1
                                break
                    
                    vi_parts = split_translation_to_lines(matching_translation, scene_lines_count)
                    if line_index_in_scene < len(vi_parts):
                        vi_text = vi_parts[line_index_in_scene]

                if vi_text:
                    ass_content.append(
                        f"Dialogue: 0,{start_str},{end_str},Vietnamese,,0,0,0,,{{\\pos({x_pos},{y_vi})}}{vi_text}"
                    )

            # 5. Ghi dòng chuẩn bị tiếp theo ở tọa độ y_next
            if idx < len(lines) - 1:
                next_line = lines[idx + 1]
                if next_line:
                    next_text = " ".join([clean_word(w["word"]) for w in next_line])
                    ass_content.append(
                        f"Dialogue: 0,{start_str},{end_str},NextLine,,0,0,0,,{{\\pos({x_pos},{y_next})}}{next_text}"
                    )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content))
            
        return True, output_path
        
    except Exception as e:
        return False, f"Lỗi tạo file phụ đề ASS song ngữ: {str(e)}"

