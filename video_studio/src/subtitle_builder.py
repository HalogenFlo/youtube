# Chức năng: Tạo file phụ đề ASS (.ass) và SRT (.srt) với hiệu ứng karaoke đồng bộ từ word-level timestamps,
#          bảo vệ chống tràn khung hình (frame overflow) và tuân thủ vùng an toàn giao diện (Bottom 1/6 Safe Zone).
# Trích dẫn: Tuân thủ đặc tả định dạng phụ đề ASS (Advanced SubStation Alpha) và SubRip (.srt).

import os
from typing import List, Dict, Any, Tuple


def format_time(seconds: float) -> str:
    """
    Chuyển đổi giây (float) thành định dạng thời gian ASS: H:MM:SS.cs
    Ví dụ: 85.24 -> 0:01:25.24
    """
    secs = max(0.0, float(seconds))
    hours = int(secs // 3600)
    minutes = int((secs % 3600) // 60)
    remaining_secs = secs % 60
    centiseconds = int(round((remaining_secs - int(remaining_secs)) * 100))

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


def format_srt_time(seconds: float) -> str:
    """Chuyển đổi giây (float) thành định dạng thời gian SRT: HH:MM:SS,mmm."""
    secs = max(0.0, float(seconds))
    hours = int(secs // 3600)
    minutes = int((secs % 3600) // 60)
    remaining_secs = secs % 60
    millis = int(round((remaining_secs - int(remaining_secs)) * 1000))
    if millis == 1000:
        remaining_secs += 1
        millis = 0
        if remaining_secs >= 60:
            minutes += 1
            remaining_secs -= 60
            if minutes >= 60:
                hours += 1
                minutes -= 60
    return f"{hours:02d}:{minutes:02d}:{int(remaining_secs):02d},{millis:03d}"


def clean_word(word: str) -> str:
    """Lọc các ký tự có thể làm hỏng thẻ điều khiển ASS và ký tự lỗi encoding."""
    return str(word).replace("{", "").replace("}", "").replace("\\", "").replace("\ufffd", "")


def group_words_into_lines(
    words: List[Dict[str, Any]],
    max_words: int = 4,
    max_chars_per_line: int = 34,
) -> List[List[Dict[str, Any]]]:
    """
    Gom nhóm danh sách các từ thành từng dòng phụ đề dựa trên:
    - Giới hạn số từ trên một dòng (max_words).
    - Giới hạn tổng số ký tự trên một dòng (max_chars_per_line) để chống tràn khung hình.
    - Khoảng lặng lớn giữa các từ (> 0.8 giây).
    - Dấu câu ngắt câu (. ? ! ;).
    """
    if not words:
        return []

    lines: List[List[Dict[str, Any]]] = []
    current_line: List[Dict[str, Any]] = []
    current_chars = 0

    for i, w in enumerate(words):
        w_text = clean_word(w.get("word", ""))
        w_len = len(w_text)

        # Nếu thêm từ này làm vượt quá giới hạn ký tự trên 1 dòng và dòng hiện tại đã có từ -> ngắt trước
        if current_line and (current_chars + 1 + w_len > max_chars_per_line):
            lines.append(current_line)
            current_line = []
            current_chars = 0

        current_line.append(w)
        current_chars += w_len + (1 if len(current_line) > 1 else 0)

        should_split = False
        if len(current_line) >= max_words:
            should_split = True
        elif w_text.endswith((".", "?", "!", ";", ":")):
            should_split = True
        elif i < len(words) - 1:
            next_w = words[i + 1]
            if float(next_w.get("start", 0.0)) - float(w.get("end", 0.0)) > 0.8:
                should_split = True

        if should_split:
            lines.append(current_line)
            current_line = []
            current_chars = 0

    if current_line:
        lines.append(current_line)

    return lines


def build_ass_subtitle(
    words: List[Dict[str, Any]],
    output_path: str,
    orientation: str = "vertical",
) -> Tuple[bool, str]:
    """
    Tạo file phụ đề ASS karaoke từ danh sách các từ.
    Hỗ trợ tuỳ chỉnh kích thước và vị trí theo hướng video (dọc/ngang) trong vùng an toàn.
    """
    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if orientation == "vertical":
            play_res_x = 1080
            play_res_y = 1920
            font_size = 44
            vertical_margin = 260
            alignment = 2
            max_words_per_line = 5
            max_chars = 34
        else:
            play_res_x = 1920
            play_res_y = 1080
            font_size = 38
            vertical_margin = 90
            alignment = 2
            max_words_per_line = 7
            max_chars = 52

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
            f"Style: Default,Montserrat,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,{alignment},50,50,{vertical_margin},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        lines = group_words_into_lines(words, max_words=max_words_per_line, max_chars_per_line=max_chars)

        for line in lines:
            if not line:
                continue

            line_start = float(line[0]["start"])
            line_end = max(line_start + 0.1, float(line[-1]["end"]))

            karaoke_text = ""
            for i, w in enumerate(line):
                w_word = clean_word(w["word"])
                if i == 0:
                    duration = max(1, int(round((float(w["end"]) - line_start) * 100)))
                    karaoke_text += f"{{\\k{duration}}}{w_word}"
                else:
                    prev_w = line[i - 1]
                    duration = max(1, int(round((float(w["end"]) - float(prev_w["end"])) * 100)))
                    karaoke_text += f"{{\\k{duration}}} {w_word}"

            start_str = format_time(line_start)
            end_str = format_time(line_end)

            ass_content.append(
                f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{karaoke_text}"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content))

        return True, output_path

    except Exception as e:
        return False, f"Lỗi tạo file phụ đề ASS: {str(e)}"


def build_srt_subtitle(
    words: List[Dict[str, Any]],
    output_path: str,
    orientation: str = "vertical",
) -> Tuple[bool, str]:
    """Tạo file phụ đề chuẩn .srt (SubRip) phục vụ đóng gói xuất bản YouTube & TikTok."""
    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        max_words = 5 if orientation == "vertical" else 7
        max_chars = 34 if orientation == "vertical" else 52
        lines = group_words_into_lines(words, max_words=max_words, max_chars_per_line=max_chars)

        blocks: List[str] = []
        for idx, line in enumerate(lines, start=1):
            if not line:
                continue
            start_str = format_srt_time(float(line[0]["start"]))
            end_str = format_srt_time(max(float(line[0]["start"]) + 0.1, float(line[-1]["end"])))
            text_str = " ".join(clean_word(w["word"]) for w in line).strip()
            blocks.append(f"{idx}\n{start_str} --> {end_str}\n{text_str}\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(blocks))
        return True, output_path
    except Exception as exc:
        return False, f"Lỗi tạo file phụ đề SRT: {exc}"


def calculate_word_timings(
    narration: str,
    scene_start: float,
    wpm: int = 130,
) -> List[Dict[str, Any]]:
    """
    Tính toán mốc thời gian (start, end) cho từng từ dựa trên tốc độ đọc (WPM) và độ dài ký tự của từ.
    """
    words = narration.strip().split()
    if not words:
        return []

    total_duration = (len(words) / wpm) * 60.0
    word_lengths = [len(clean_word(w)) for w in words]
    total_chars = sum(word_lengths)

    if total_chars == 0:
        total_chars = len(words)
        word_lengths = [1] * len(words)

    word_timings = []
    current_start = scene_start

    for i, word in enumerate(words):
        duration = (word_lengths[i] / total_chars) * total_duration
        duration = max(0.15, duration)
        w_end = current_start + duration
        word_timings.append({
            "word": word,
            "start": current_start,
            "end": w_end,
        })
        current_start = w_end

    return word_timings


def split_translation_to_lines(translation: str, num_lines: int) -> List[str]:
    """
    Tách câu dịch tiếng Việt thành num_lines phần ngắn tương ứng với các dòng phụ đề.
    """
    from src.config import VI_SPLIT_CONJUNCTIONS

    translation = translation.strip()
    if num_lines <= 1 or not translation:
        return [translation]

    words = translation.split()
    if len(words) <= num_lines:
        return words + [""] * (num_lines - len(words))

    split_indices = []
    for i, w in enumerate(words):
        if i == len(words) - 1:
            continue
        if w.endswith((".", ",", "?", "!", ";", ":")):
            split_indices.append(i + 1)
        elif w.lower() in VI_SPLIT_CONJUNCTIONS:
            split_indices.append(i)

    if not split_indices:
        chunk_size = len(words) // num_lines
        parts = []
        for i in range(num_lines):
            if i == num_lines - 1:
                parts.append(" ".join(words[i * chunk_size:]))
            else:
                parts.append(" ".join(words[i * chunk_size:(i + 1) * chunk_size]))
        return parts

    points = [0] + sorted(list(set(split_indices))) + [len(words)]
    while len(points) - 1 < num_lines:
        max_gap_idx = 0
        max_gap = 0
        for i in range(len(points) - 1):
            gap = points[i + 1] - points[i]
            if gap > max_gap:
                max_gap = gap
                max_gap_idx = i
        mid_point = points[max_gap_idx] + max_gap // 2
        if mid_point not in points:
            points.append(mid_point)
            points.sort()
        else:
            break

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
        parts.append(" ".join(words[points[i]:points[i + 1]]))
    return parts


def build_bilingual_ass_subtitle(
    words: List[Dict[str, Any]],
    translations: List[Dict[str, Any]],
    speaker_segments: List[Dict[str, Any]],
    output_path: str,
    orientation: str = "vertical",
    show_translation: bool = True,
) -> Tuple[bool, str]:
    r"""
    Tạo file phụ đề ASS karaoke song ngữ Anh-Việt theo phong cách máy nhắc bài (Teleprompter).
    """
    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if orientation == "vertical":
            play_res_x = 1080
            play_res_y = 1920
            font_size = 44
            font_size_vi = 30
            font_size_next = 32
            x_pos = 540
            y_current = 1520
            y_vi = 1580
            y_next = 1640
            max_words_per_line = 5
            max_chars = 34
        else:
            play_res_x = 1920
            play_res_y = 1080
            font_size = 38
            font_size_vi = 26
            font_size_next = 28
            x_pos = 960
            y_current = 880
            y_vi = 930
            y_next = 980
            max_words_per_line = 7
            max_chars = 52

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

        if "Default" not in registered_speakers:
            ass_content.append(
                f"Style: Default,Montserrat,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,5,50,50,0,1"
            )

        ass_content.append(
            f"Style: Vietnamese,Montserrat,{font_size_vi},&H60FFFFFF,&H60FFFFFF,&H00000000,&H80000000,0,1,0,0,100,100,0,0,1,3,1,5,50,50,0,1"
        )
        ass_content.append(
            f"Style: NextLine,Montserrat,{font_size_next},&H80C0C0C0,&H80C0C0C0,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,5,50,50,0,1"
        )

        ass_content.extend([
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ])

        lines = group_words_into_lines(words, max_words=max_words_per_line, max_chars_per_line=max_chars)

        for idx, line in enumerate(lines):
            if not line:
                continue

            line_start = line[0]["start"]
            line_end = line[-1]["end"]
            mid_time = (line_start + line_end) / 2.0

            current_speaker = "Default"
            current_style = "Default"
            for seg in speaker_segments:
                if seg["start"] <= mid_time <= seg["end"]:
                    current_speaker = seg["speaker"]
                    current_style = speaker_styles.get(current_speaker, "Default")
                    break

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

            start_str = format_time(line_start)
            end_str = format_time(line_end)

            ass_content.append(
                f"Dialogue: 0,{start_str},{end_str},{current_style},,0,0,0,,{{\\pos({x_pos},{y_current})}}{karaoke_text}"
            )

            vi_text = ""
            if show_translation:
                matching_translation = ""
                for trans in translations:
                    if trans["start"] <= mid_time <= trans["end"]:
                        matching_translation = trans["text"]
                        break

                if matching_translation:
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
