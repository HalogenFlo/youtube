# Chức năng: Động cơ sản xuất video tự động hàng loạt (Auto Batch Video Pipeline).
# Lý do tạo: Tự động hóa hoàn toàn từ Prompt -> Kịch bản -> Audio TTS -> Google Flow bối cảnh từng cảnh -> Render video theo vòng lặp.
# Trích dẫn: Tích hợp src/llm_service, src/tts_service, src/flow_image_service, src/whisper_service, src/video_compiler.

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable

# Đảm bảo UTF-8 chống lỗi hiển thị trên console Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_log(msg: str):
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass

from src.config import (
    TEMP_DIR, OUTPUT_DIR, TTS_VOICE_DEFAULT, DEFAULT_IMAGE_STYLE
)
from src.llm_service import generate_script
from src.tts_service import generate_tts
from src.flow_image_service import generate_flow_image
from src.whisper_service import get_word_timestamps
from src.video_compiler import compile_video_pipeline


def get_audio_duration(file_path: str) -> float:
    """Đo thời lượng file audio chính xác."""
    try:
        from mutagen.mp3 import MP3
        return MP3(file_path).info.length
    except Exception:
        pass
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(file_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return 5.0


def split_prompt_to_video_topics(main_prompt: str, count: int, language: str = "vi") -> List[str]:
    """
    Tự động chia tách prompt người dùng thành danh sách các chủ đề video độc lập.
    Hỗ trợ cả trường hợp người dùng nhập nhiều dòng hoặc nhập 1 chủ đề lớn cần chia N tập.
    """
    # Nếu người dùng nhập mỗi dòng một chủ đề
    lines = [line.strip() for line in main_prompt.strip().split("\n") if line.strip()]
    if len(lines) >= count and len(lines) > 1:
        return lines[:count]
    
    # Nếu chỉ có 1 chủ đề hoặc số dòng ít hơn count
    base_topic = lines[0] if lines else main_prompt.strip()
    topics = []
    for i in range(count):
        if count == 1:
            topics.append(base_topic)
        else:
            if language == "vi":
                topics.append(f"{base_topic} (Phần {i+1}: Các khía cạnh đặc sắc và bất ngờ)")
            else:
                topics.append(f"{base_topic} (Part {i+1}: Surprising Facts and Insights)")
    return topics


def produce_single_video_pipeline(
    topic: str,
    video_index: int,
    batch_work_dir: str,
    output_dir: str = OUTPUT_DIR,
    language: str = "vi",
    voice: str = TTS_VOICE_DEFAULT,
    style_preset: str = DEFAULT_IMAGE_STYLE,
    orientation: str = "vertical",
    image_engine: str = "flow",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Sản xuất 1 video hoàn chỉnh từ Topic:
    1. Sinh kịch bản phân cảnh với LLM (Ollama)
    2. Sinh audio TTS cho từng phân cảnh
    3. Sinh bối cảnh AI RIÊNG BIỆT cho từng phân cảnh qua Google Flow
    4. Trích xuất word timestamps qua Faster-Whisper
    5. Biên tập và Render video hoàn chỉnh kèm phụ đề
    """
    def notify(pct: float, message: str):
        safe_log(f"   [{video_index}] [{int(pct)}%] {message}")
        if progress_callback:
            try:
                progress_callback(pct, message)
            except Exception:
                pass

    run_meta = {"topic": topic, "video_index": video_index}
    video_work_dir = os.path.join(batch_work_dir, f"video_{video_index:02d}")
    os.makedirs(video_work_dir, exist_ok=True)

    # 1. BIÊN SOẠN KỊCH BẢN
    notify(10, f"Đang yêu cầu AI biên soạn kịch bản cho chủ đề: '{topic[:40]}...'")
    success, script_data = generate_script(
        topic=topic,
        style_preset=style_preset,
        language=language
    )

    if not success or "scenes" not in script_data or not script_data["scenes"]:
        err = f"Lỗi sinh kịch bản cho video {video_index}: {script_data}"
        notify(10, err)
        return False, err, run_meta

    scenes = script_data["scenes"]
    num_scenes = len(scenes)
    notify(20, f"Đã lập kịch bản gồm {num_scenes} phân cảnh độc lập.")

    # 2. SINH GIỌNG ĐỌC & TÍNH TOÁN TIMING
    notify(25, "Đang sinh giọng đọc AI (TTS) cho các phân cảnh...")
    for i, sc in enumerate(scenes):
        sc_num = sc.get("scene_num", i + 1)
        audio_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}.mp3")
        generate_tts(
            text=sc["narration"],
            output_path=audio_file,
            voice=voice,
            rate="+0%"
        )
        sc["audio_path"] = audio_file
        sc["audio_duration"] = get_audio_duration(audio_file)
        notify(25 + (i + 1) / num_scenes * 15, f"Đã sinh giọng đọc phân cảnh {sc_num}/{num_scenes}")

    # 3. SINH BỐI CẢNH AI RIÊNG BIỆT CHO TỪNG PHÂN CẢNH (GOOGLE FLOW)
    notify(45, "Bắt đầu sinh bối cảnh hình ảnh AI riêng biệt cho từng phân cảnh...")
    for i, sc in enumerate(scenes):
        sc_num = sc.get("scene_num", i + 1)
        img_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}_bg.png")
        sc["image_path"] = img_file
        sc["use_video_ai"] = False

        prompt = sc.get("video_prompt") or sc.get("narration") or "Stickman cinematic scene"
        step_pct = 45 + (i / num_scenes) * 30
        notify(step_pct, f"Đang vẽ bối cảnh phân cảnh {sc_num}/{num_scenes} qua Google Flow...")

        if image_engine == "flow":
            ok, res = generate_flow_image(
                prompt=prompt,
                output_path=img_file,
                orientation=orientation,
                style_preset=style_preset,
                fallback_to_sd=False
            )
        else:
            from src.image_service import generate_single_image
            ok, res = generate_single_image(
                prompt=prompt,
                output_path=img_file,
                orientation=orientation,
                style_preset=style_preset
            )

        if not ok or not os.path.exists(img_file):
            err = f"Lỗi sinh ảnh phân cảnh {sc_num} từ Google Flow: {res}"
            notify(step_pct, err)
            return False, err, run_meta

    # 4. PHÂN TÍCH TIMESTAMPS PHỤ ĐỀ (WHISPER)
    notify(78, "Đang phân tích phụ đề từng chữ (Karaoke Word Timestamps)...")
    all_words = []
    cumulative_time = 0.0

    for i, sc in enumerate(scenes):
        ok, words = get_word_timestamps(sc["audio_path"], language=language)
        if ok and words:
            for w in words:
                all_words.append({
                    "word": w["word"],
                    "start": w["start"] + cumulative_time,
                    "end": w["end"] + cumulative_time
                })
        cumulative_time += sc.get("audio_duration", 5.0)

    # 5. BIÊN TẬP VÀ RENDER VIDEO HOÀN CHỈNH
    notify(85, "Đang biên tập chuyển cảnh và burn phụ đề video...")
    ok, compiled_videos, err = compile_video_pipeline(
        scenes=scenes,
        words_timestamps=all_words,
        max_duration=120.0,
        orientation=orientation
    )

    if not ok or not compiled_videos:
        notify(85, f"Lỗi render video {video_index}: {err}")
        return False, f"Lỗi render: {err}", run_meta

    # Di chuyển file video cuối cùng vào thư mục output với tên chuẩn
    src_video = compiled_videos[0]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    final_name = f"video_batch_{timestamp}_v{video_index:02d}.mp4"
    final_path = os.path.join(output_dir, final_name)

    import shutil
    shutil.copy2(src_video, final_path)
    notify(100, f"✅ Hoàn thành xuất sắc video {video_index}: {final_name}")

    run_meta["final_path"] = final_path
    run_meta["scenes"] = scenes
    return True, final_path, run_meta


def run_batch_video_loop(
    prompt: str,
    count: int = 1,
    language: str = "vi",
    voice: str = TTS_VOICE_DEFAULT,
    style_preset: str = DEFAULT_IMAGE_STYLE,
    orientation: str = "vertical",
    image_engine: str = "flow",
    progress_callback: Optional[Callable[[int, int, float, str], None]] = None
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    VÒNG LẶP SẢN XUẤT HÀNG LOẠT (BATCH GENERATION LOOP):
    Tự động chạy liên tục từ Prompt -> Kịch bản -> Google Flow bối cảnh -> Render video.
    Trả về: (danh_sách_file_video_thành_công, danh_sách_thông_tin_meta)
    """
    safe_log("=" * 65)
    safe_log(f"🚀 BẮT ĐẦU VÒNG LẶP SẢN XUẤT HÀNG LOẠT ({count} VIDEO)")
    safe_log(f"   Prompt gốc: \"{prompt[:60]}...\"")
    safe_log(f"   Engine sinh bối cảnh: {image_engine.upper()}")
    safe_log("=" * 65)

    topics = split_prompt_to_video_topics(prompt, count, language=language)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    batch_work_dir = os.path.join(TEMP_DIR, f"batch_{timestamp}")
    os.makedirs(batch_work_dir, exist_ok=True)

    successful_videos = []
    meta_reports = []

    for idx, topic in enumerate(topics):
        video_num = idx + 1
        safe_log(f"\n▶ [{video_num}/{count}] Đang sản xuất video: '{topic}'...")

        def single_video_callback(pct: float, msg: str):
            if progress_callback:
                progress_callback(video_num, count, pct, msg)

        success, path_or_err, meta = produce_single_video_pipeline(
            topic=topic,
            video_index=video_num,
            batch_work_dir=batch_work_dir,
            output_dir=OUTPUT_DIR,
            language=language,
            voice=voice,
            style_preset=style_preset,
            orientation=orientation,
            image_engine=image_engine,
            progress_callback=single_video_callback
        )

        if success:
            successful_videos.append(path_or_err)
            meta["status"] = "success"
            meta_reports.append(meta)
            safe_log(f"   ✓ Video {video_num}/{count} hoàn tất: {path_or_err}")
        else:
            meta["status"] = "failed"
            meta["error"] = path_or_err
            meta_reports.append(meta)
            safe_log(f"   ✗ Video {video_num}/{count} gặp lỗi: {path_or_err}")

    safe_log("\n" + "=" * 65)
    safe_log(f"🏁 KẾT THÚC BATCH LOOP: ĐÃ TẠO THÀNH CÔNG {len(successful_videos)}/{count} VIDEO!")
    safe_log("=" * 65)

    return successful_videos, meta_reports
