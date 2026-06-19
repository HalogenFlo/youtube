# Chức năng: Cung cấp các pure function tương tác với FFmpeg, FFprobe để cắt xén, trích xuất, co giãn tốc độ audio và mix âm thanh thành phẩm.
# Lý do tạo: Tách biệt logic xử lý đa phương tiện (multimedia pipeline) khỏi giao diện Streamlit để tăng khả năng bảo trì và test độc lập.
# Trích dẫn: Sử dụng FFmpeg CLI qua subprocess của Python.

import os
import json
import subprocess
import time
from typing import Tuple, Dict, Any, List

def run_ffmpeg_cmd(cmd: List[str]) -> Tuple[bool, str]:
    """
    Hàm helper chạy lệnh FFmpeg/FFprobe ẩn console trên Windows và bắt lỗi.
    """
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            startupinfo=startupinfo,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr or e.stdout or str(e)
        return False, err_msg
    except FileNotFoundError:
        return False, "Không tìm thấy FFmpeg/FFprobe trên hệ thống. Vui lòng cài đặt và thêm vào PATH."
    except Exception as e:
        return False, str(e)

def get_video_info(video_path: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Sử dụng FFprobe lấy metadata của video: width, height, duration, fps.
    """
    if not os.path.exists(video_path):
        return False, {"error": f"Không tìm thấy file video: {video_path}"}
        
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate",
        "-of", "json",
        video_path
    ]
    
    success, stdout = run_ffmpeg_cmd(cmd)
    if not success:
        return False, {"error": f"Lỗi chạy ffprobe: {stdout}"}
        
    try:
        data = json.loads(stdout)
        streams = data.get("streams", [])
        if not streams:
            # Thử lấy duration từ format nếu stream video bị thiếu hoặc lỗi
            cmd_format = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]
            success_fmt, stdout_fmt = run_ffmpeg_cmd(cmd_format)
            if success_fmt:
                fmt_data = json.loads(stdout_fmt)
                duration = float(fmt_data.get("format", {}).get("duration", 0.0))
                return True, {"width": 0, "height": 0, "duration": duration, "fps": 0.0}
            return False, {"error": "Không tìm thấy stream video hợp lệ."}
            
        stream = streams[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        
        # Duration có thể nằm ở format hoặc stream
        duration_str = stream.get("duration")
        if not duration_str:
            # Lấy từ format
            cmd_fmt = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]
            success_fmt, stdout_fmt = run_ffmpeg_cmd(cmd_fmt)
            if success_fmt:
                duration_str = json.loads(stdout_fmt).get("format", {}).get("duration", "0.0")
                
        duration = float(duration_str) if duration_str else 0.0
        
        # Parse FPS
        r_frame_rate = stream.get("r_frame_rate", "0/0")
        if "/" in r_frame_rate:
            num, den = map(int, r_frame_rate.split("/"))
            fps = num / den if den > 0 else 0.0
        else:
            fps = float(r_frame_rate)
            
        return True, {
            "width": width,
            "height": height,
            "duration": duration,
            "fps": round(fps, 2)
        }
    except Exception as e:
        return False, {"error": f"Lỗi parse metadata: {str(e)}"}

def get_video_frame(video_path: str, time_sec: float, output_img_path: str) -> Tuple[bool, str]:
    """
    Chụp một khung hình của video tại giây chỉ định để làm ảnh preview.
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_sec),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2", # Chất lượng ảnh cao
        output_img_path
    ]
    
    success, err = run_ffmpeg_cmd(cmd)
    if success and os.path.exists(output_img_path):
        return True, output_img_path
    return False, f"Không thể chụp ảnh thumbnail: {err}"

def crop_and_trim_video(
    video_path: str,
    output_path: str,
    start: float,
    end: float,
    crop_x: int = 0,
    crop_y: int = 0,
    crop_w: int = 0,
    crop_h: int = 0
) -> Tuple[bool, str]:
    """
    FFmpeg cắt thời lượng (Trim) và cắt khung hình (Crop) video.
    Nếu crop_w và crop_h > 0 thì áp dụng filter crop, ngược lại chỉ trim.
    """
    if not os.path.exists(video_path):
        return False, f"Không tìm thấy file nguồn: {video_path}"
        
    duration = end - start
    
    # Xây dựng filter video
    video_filters = []
    if crop_w > 0 and crop_h > 0:
        video_filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
        
    cmd = ["ffmpeg", "-y"]
    # ss trước -i để seek nhanh
    cmd.extend(["-ss", f"{start:.3f}"])
    cmd.extend(["-t", f"{duration:.3f}"])
    cmd.extend(["-i", video_path])
    
    if video_filters:
        filter_str = ",".join(video_filters)
        cmd.extend(["-vf", filter_str])
        
    # Re-encode video sang H264 và audio sang AAC để đảm bảo tương thích tốt
    cmd.extend([
        "-c:v", "libx264",
        "-crf", "21",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ])
    
    success, err = run_ffmpeg_cmd(cmd)
    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True, output_path
    return False, f"Lỗi khi cắt/crop video: {err}"

def save_uploaded_video(uploaded_file, output_path: str) -> Tuple[bool, str]:
    """
    Lưu file video upload từ streamlit st.file_uploader vào ổ đĩa.
    """
    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            
        with open(output_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path
        return False, "Lưu file upload thất bại hoặc file trống."
    except Exception as e:
        return False, f"Lỗi hệ thống khi lưu file upload: {str(e)}"

def get_audio_duration(audio_path: str) -> float:
    """
    Lấy thời lượng của file audio bằng FFprobe.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    success, stdout = run_ffmpeg_cmd(cmd)
    if success:
        try:
            return float(stdout.strip())
        except ValueError:
            return 0.0
    return 0.0

def adjust_tts_speed(tts_path: str, target_duration: float, output_path: str) -> Tuple[bool, str]:
    """
    Đồng bộ tốc độ đọc của file TTS khớp với target_duration bằng filter atempo của FFmpeg.
    Chấp nhận chain filter nếu tốc độ vượt quá giới hạn [0.5, 2.0].
    """
    if not os.path.exists(tts_path):
        return False, f"Không tìm thấy file TTS: {tts_path}"
        
    tts_duration = get_audio_duration(tts_path)
    if tts_duration <= 0 or target_duration <= 0:
        # Nếu không lấy được thời lượng, copy thẳng
        cmd = ["ffmpeg", "-y", "-i", tts_path, "-acodec", "copy", output_path]
        success, _ = run_ffmpeg_cmd(cmd)
        return success, output_path
        
    tempo = tts_duration / target_duration
    
    # Giới hạn an toàn để tránh âm thanh bị méo tiếng quá nặng
    if tempo > 2.2:
        tempo = 2.2
    elif tempo < 0.45:
        tempo = 0.45
        
    # Xây dựng chuỗi chain filter atempo (mỗi filter giới hạn từ 0.5 đến 2.0)
    filters = []
    t = tempo
    while t > 2.0:
        filters.append("atempo=2.0")
        t /= 2.0
    while t < 0.5:
        filters.append("atempo=0.5")
        t /= 0.5
    if abs(t - 1.0) > 0.01:
        filters.append(f"atempo={t:.3f}")
        
    cmd = ["ffmpeg", "-y", "-i", tts_path]
    if filters:
        filter_str = ",".join(filters)
        cmd.extend(["-filter:a", filter_str])
        
    cmd.extend([
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path
    ])
    
    success, err = run_ffmpeg_cmd(cmd)
    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True, output_path
    return False, f"Lỗi điều chỉnh tốc độ đọc TTS: {err}"

def mix_dubbed_audio(
    original_audio_path: str,
    tts_segments: List[Dict[str, Any]],
    output_audio_path: str,
    bg_volume_mode: str = "Giữ nhỏ (10-15%)"
) -> Tuple[bool, str]:
    """
    Mix các đoạn TTS vào đúng timeline của video gốc, đồng thời mix với âm thanh nền gốc.
    - tts_segments: List các dict chứa {"adjusted_tts_path": str, "start": float}
    - bg_volume_mode: "Giữ nhỏ (10-15%)" hoặc "Tắt hoàn toàn"
    """
    if not tts_segments:
        return False, "Không có đoạn TTS nào để mix."
        
    bg_volume = 0.0 if bg_volume_mode == "Tắt hoàn toàn" else 0.12
    
    # Bắt đầu xây dựng lệnh FFmpeg complex filter
    cmd = ["ffmpeg", "-y"]
    
    # Input 0 là original audio
    cmd.extend(["-i", original_audio_path])
    
    # Các input tiếp theo là các file TTS đã được chỉnh speed
    for seg in tts_segments:
        cmd.extend(["-i", seg["adjusted_tts_path"]])
        
    # Tạo complex filter
    filter_parts = []
    
    # 1. Trì hoãn (delay) từng đoạn TTS vào mốc thời gian start tương ứng
    # Index file tts bắt đầu từ 1 (vì 0 là original audio)
    for idx, seg in enumerate(tts_segments):
        start_ms = int(seg["start"] * 1000)
        if start_ms < 0:
            start_ms = 0
        filter_parts.append(f"[{idx+1}:a]adelay={start_ms}|{start_ms}[a{idx+1}]")
        
    # 2. Trộn (mix) các đoạn TTS đã được delay lại với nhau trước
    tts_inputs_str = "".join([f"[a{i+1}]" for i in range(len(tts_segments))])
    filter_parts.append(f"{tts_inputs_str}amix=inputs={len(tts_segments)}:normalize=0[tts_mix]")
    
    # 3. Trộn tts_mix với âm thanh nền gốc (nếu giữ âm thanh nền)
    if bg_volume > 0:
        filter_parts.append(f"[0:a]volume={bg_volume}[bg]")
        filter_parts.append(f"[bg][tts_mix]amix=inputs=2:normalize=0[out]")
    else:
        filter_parts.append(f"[tts_mix]volume=1.0[out]")
        
    filter_complex_str = ";".join(filter_parts)
    
    cmd.extend([
        "-filter_complex", filter_complex_str,
        "-map", "[out]",
        "-acodec", "aac",
        "-b:a", "128k",
        output_audio_path
    ])
    
    success, err = run_ffmpeg_cmd(cmd)
    if success and os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0:
        return True, output_audio_path
    return False, f"Lỗi mix âm thanh lồng tiếng: {err}"

def compile_dubbed_video(
    video_path: str,
    dubbed_audio_path: str,
    subtitle_path: str,
    output_path: str,
    subtitle_mode: str = "Song ngữ gốc-dịch"
) -> Tuple[bool, str]:
    """
    Ghép video đã cắt với audio đã lồng tiếng mới, và burn phụ đề ASS lên video.
    """
    if not os.path.exists(video_path) or not os.path.exists(dubbed_audio_path):
        return False, "Không tìm thấy file video đã cắt hoặc file audio lồng tiếng để compile."
        
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", dubbed_audio_path]
    
    # Nếu có phụ đề và không chọn chế độ "Không phụ đề"
    if subtitle_path and os.path.exists(subtitle_path) and subtitle_mode != "Không phụ đề":
        # Do đường dẫn phụ đề trên Windows có ký tự ổ đĩa (C:), FFmpeg cần escape bằng cách đổi '\' thành '/'
        # và thêm dấu backslash trước dấu ':' hoặc dùng wrap đường dẫn.
        # Cách an toàn nhất: đổi đường dẫn sang định dạng tương thích filter subtitles của FFmpeg:
        escaped_sub_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
        cmd.extend(["-vf", f"subtitles='{escaped_sub_path}'"])
        
    cmd.extend([
        "-c:v", "libx264",
        "-crf", "22",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-map", "0:v",  # Lấy video từ input 0
        "-map", "1:a",  # Lấy audio từ input 1
        output_path
    ])
    
    success, err = run_ffmpeg_cmd(cmd)
    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True, output_path
    return False, f"Lỗi render video thành phẩm: {err}"

def build_dubbing_ass_subtitle(
    segments: List[Dict[str, Any]],
    output_path: str,
    mode: str = "Song ngữ gốc-dịch",
    orientation: str = "vertical"
) -> Tuple[bool, str]:
    """
    Tạo file phụ đề ASS cho video lồng tiếng.
    - Mode: "Song ngữ gốc-dịch", "Chỉ ngôn ngữ dịch", "Không phụ đề"
    """
    if mode == "Không phụ đề":
        return True, ""
        
    try:
        from src.subtitle_builder import format_time
    except ImportError:
        # Fallback hàm format_time nếu không import được
        def format_time(seconds: float) -> str:
            secs = max(0.0, seconds)
            hours = int(secs // 3600)
            minutes = int((secs % 3600) // 60)
            remaining_secs = secs % 60
            centiseconds = int(round((remaining_secs - int(remaining_secs)) * 100))
            if centiseconds == 100:
                remaining_secs += 1
                centiseconds = 0
            return f"{hours}:{minutes:02d}:{int(remaining_secs):02d}.{centiseconds:02d}"

    try:
        parent_dir = os.path.dirname(output_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            
        if orientation == "vertical":
            play_res_x = 1080
            play_res_y = 1920
            font_size = 48
            font_size_sub = 34
            vertical_margin = 1500 # Đặt ở phần dưới màn hình dọc
        else:
            play_res_x = 1920
            play_res_y = 1080
            font_size = 40
            font_size_sub = 28
            vertical_margin = 120 # Đặt cách đáy màn hình ngang
            
        ass_content = [
            "[Script Info]",
            "Title: Dubbing Subtitles",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            # Style chính: Vàng neon, căn giữa đáy
            f"Style: Main,Montserrat,{font_size},&H0000FFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,50,50,{vertical_margin},1",
            # Style phụ: Trắng, căn giữa đáy
            f"Style: Sub,Montserrat,{font_size_sub},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,50,50,{vertical_margin - font_size - 10 if orientation == 'vertical' else vertical_margin - font_size - 8},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]
        
        for idx, seg in enumerate(segments):
            start_str = format_time(seg["start"])
            end_str = format_time(seg["end"])
            
            text_main = seg.get("text", "").strip()
            text_sub = seg.get("translated_text", "").strip()
            
            # Tránh ký tự {} làm hỏng thẻ ASS
            text_main = text_main.replace("{", "").replace("}", "")
            text_sub = text_sub.replace("{", "").replace("}", "")
            
            if mode == "Song ngữ gốc-dịch":
                # Bản dịch (tiếng Việt/tiếng Anh) làm dòng chính, thoại gốc làm dòng phụ ở dưới
                combined_text = f"{text_sub}\\N{{\\rSub}}{text_main}"
                ass_content.append(
                    f"Dialogue: 0,{start_str},{end_str},Main,,0,0,0,,{combined_text}"
                )
            elif mode == "Chỉ ngôn ngữ dịch":
                ass_content.append(
                    f"Dialogue: 0,{start_str},{end_str},Main,,0,0,0,,{text_sub}"
                )
                
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content))
            
        return True, output_path
    except Exception as e:
        return False, f"Lỗi tạo file phụ đề ASS: {str(e)}"

