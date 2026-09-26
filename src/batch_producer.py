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
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'), flush=True)
        except Exception:
            pass


from src.config import (
    TEMP_DIR, OUTPUT_DIR, TTS_VOICE_DEFAULT, DEFAULT_IMAGE_STYLE
)
from src.llm_service import generate_script, generate_video_metadata
from src.tts_service import generate_tts
from src.flow_image_service import generate_flow_image, generate_flow_video
from src.whisper_service import get_word_timestamps
from src.video_compiler import compile_video_pipeline
from src.voice_clone_service import generate_cloned_tts
from src.studio_editorial_service import run_studio_editorial_pipeline


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
    if len(lines) > 1:
        topics = lines[:count]
        while len(topics) < count:
            base_topic = lines[len(topics) % len(lines)]
            episode = len(topics) // len(lines) + 1
            suffix = f"Tập mở rộng {episode}" if language == "vi" else f"Extended episode {episode}"
            topics.append(f"{base_topic} ({suffix})")
        return topics
    
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


def build_exact_tts_timestamps(scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tạo timestamp từ đúng lời thoại nguồn, tránh Whisper viết sai thuật ngữ/toán học."""
    words_out: List[Dict[str, Any]] = []
    offset = 0.0
    for scene in scenes:
        narration_words = str(scene.get("narration", "")).split()
        duration = max(0.1, float(scene.get("audio_duration", 5.0)))
        if narration_words:
            usable_duration = duration * 0.94
            word_duration = usable_duration / len(narration_words)
            for index, word in enumerate(narration_words):
                words_out.append({
                    "word": word,
                    "start": offset + index * word_duration,
                    "end": offset + (index + 1) * word_duration,
                })
        offset += duration
    return words_out


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
    media_mode: str = "flow_image",
    target_scenes: int = 5,
    voice_mode: str = "edge",
    voice_reference_path: str = "",
    job_key: str = "",
    studio_mode: bool = True,
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
    safe_job_key = "".join(ch for ch in str(job_key) if ch.isalnum() or ch in "-_")
    work_name = f"job_{safe_job_key}" if safe_job_key else f"video_{video_index:02d}"
    video_work_dir = os.path.join(batch_work_dir, work_name)
    os.makedirs(video_work_dir, exist_ok=True)

    # 1. BIÊN SOẠN KỊCH BẢN
    notify(10, f"Đang yêu cầu AI biên soạn kịch bản cho chủ đề: '{topic[:40]}...'")
    success, script_data = generate_script(
        topic=topic,
        style_preset=style_preset,
        language=language,
        target_scenes=target_scenes,
    )

    if not success or "scenes" not in script_data or not script_data["scenes"]:
        err = f"Lỗi sinh kịch bản cho video {video_index}: {script_data}"
        notify(10, err)
        return False, err, run_meta

    if studio_mode:
        notify(15, "Ban biên tập local đang kiểm chứng, sửa hook và đạo diễn hình ảnh...")
        scenes, editorial_report = run_studio_editorial_pipeline(
            topic=topic, script_data=script_data,
            target_scenes=max(1, int(target_scenes)), language=language,
        )
        run_meta["editorial_report"] = editorial_report
    else:
        scenes = script_data["scenes"][:max(1, int(target_scenes))]
        run_meta["editorial_report"] = {"mode": "single_writer", "approved": True, "selected_skill_ids": []}
    num_scenes = len(scenes)
    notify(20, f"Đã lập kịch bản gồm {num_scenes} phân cảnh độc lập.")

    # 2. SINH GIỌNG ĐỌC & TÍNH TOÁN TIMING
    notify(25, "Đang sinh giọng đọc AI (TTS) cho các phân cảnh...")
    for i, sc in enumerate(scenes):
        sc_num = sc.get("scene_num", i + 1)
        audio_ext = ".wav" if voice_mode == "clone_local" else ".mp3"
        audio_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}{audio_ext}")
        if voice_mode == "clone_local":
            audio_ok, audio_result = generate_cloned_tts(
                text=sc["narration"], output_path=audio_file,
                reference_audio=voice_reference_path, language=language,
            )
        else:
            audio_ok, audio_result = generate_tts(
                text=sc["narration"], output_path=audio_file, voice=voice, rate="+0%"
            )
        if not audio_ok or not os.path.exists(audio_file):
            err = f"Lỗi giọng đọc cảnh {sc_num}: {audio_result}"
            notify(25, err)
            return False, err, run_meta
        sc["audio_path"] = audio_file
        sc["audio_duration"] = get_audio_duration(audio_file)
        notify(25 + (i + 1) / num_scenes * 15, f"Đã sinh giọng đọc phân cảnh {sc_num}/{num_scenes}")

    # 3. SINH BỐI CẢNH AI RIÊNG BIỆT CHO TỪNG PHÂN CẢNH (GOOGLE FLOW / FALLBACK)
    notify(45, "Bắt đầu sinh bối cảnh hình ảnh AI riêng biệt cho từng phân cảnh...")
    for i, sc in enumerate(scenes):
        sc_num = sc.get("scene_num", i + 1)
        prompt = sc.get("video_prompt") or sc.get("narration") or "Stickman cinematic scene"
        step_pct = 45 + (i / num_scenes) * 30
        notify(step_pct, f"Đang tạo bối cảnh phân cảnh {sc_num}/{num_scenes}...")

        vid_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}.mp4")
        img_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}_bg.png")

        # Kiểm tra xem phân cảnh đã có sẵn file hợp lệ từ lần chạy trước hay không (tái sử dụng thông minh)
        if os.path.exists(vid_file) and os.path.getsize(vid_file) > 10000:
            safe_log(f"[✓] Tái sử dụng clip video có sẵn cho cảnh {sc_num}: {vid_file}")
            sc["video_path"] = vid_file
            sc["use_video_ai"] = True
            continue

        if os.path.exists(img_file) and os.path.getsize(img_file) > 5000:
            safe_log(f"[✓] Tái sử dụng ảnh có sẵn cho cảnh {sc_num}: {img_file}")
            sc["image_path"] = img_file
            sc["use_video_ai"] = False
            continue

        media_ok = False
        try_flow_video = image_engine == "flow" and (
            media_mode == "flow_video" or (media_mode == "hybrid" and i == 0)
        )

        if try_flow_video:
            # Sinh video qua Google Flow (kiên trì chờ lấy video trực tiếp, KHÔNG fallback sang ảnh)
            notify(step_pct, f"Đang kết nối Google Flow sinh video cho cảnh {sc_num}/{num_scenes} (chế độ chờ video trực tiếp)...")

            def flow_status_cb(sec: int, text: str):
                notify(step_pct, f"Cảnh {sc_num}/{num_scenes}: Google Flow đang render clip ({sec}s)... Vui lòng đợi.")

            ok_vid, res_vid = generate_flow_video(
                prompt=prompt,
                output_path=vid_file,
                orientation=orientation,
                style_preset=style_preset,
                status_callback=flow_status_cb,
            )
            if ok_vid and os.path.exists(vid_file) and os.path.getsize(vid_file) > 0:
                sc["video_path"] = vid_file
                sc["use_video_ai"] = True
                media_ok = True
                safe_log(f"[✓] Cảnh {sc_num} hoàn tất bằng Google Flow video clip.")
            else:
                # Người dùng yêu cầu: KHÔNG fallback sang ảnh, không fallback sang SD hay khung hình rỗng!
                err_msg = f"Lỗi sinh video Flow cảnh {sc_num}: {res_vid}. Hệ thống dừng theo yêu cầu không fallback sang ảnh."
                safe_log(f"[X] {err_msg}")
                notify(step_pct, err_msg)
                return False, err_msg, run_meta

        elif image_engine == "flow":
            notify(step_pct, f"Đang tạo ảnh Flow cho cảnh {sc_num}/{num_scenes}...")
            res_img = ""
            for flow_attempt in range(1, 4):
                ok_img, res_img = generate_flow_image(
                    prompt=prompt,
                    output_path=img_file,
                    orientation=orientation,
                    style_preset=style_preset,
                )
                if ok_img and os.path.exists(img_file) and os.path.getsize(img_file) > 0:
                    sc["image_path"] = img_file
                    sc["use_video_ai"] = False
                    media_ok = True
                    safe_log(f"[✓] Cảnh {sc_num} hoàn tất bằng ảnh Google Flow + chuyển động dựng.")
                    break
                if flow_attempt < 3:
                    wait_seconds = 15 * flow_attempt
                    notify(step_pct, f"Flow chưa trả ảnh cảnh {sc_num}; tự thử lại {flow_attempt + 1}/3 sau {wait_seconds} giây...")
                    time.sleep(wait_seconds)
            if not media_ok:
                # Cơ chế Tự Phục Hồi (Self-Healing): Nếu Google Flow quá tải hoặc nghẽn mạng,
                # tự động kế thừa ảnh bối cảnh hợp lệ liền trước kết hợp Visual Beats để tiếp tục dây chuyền,
                # TUYỆT ĐỐI KHÔNG HỦY BỎ TIẾN TRÌNH, đảm bảo video luôn hoàn thành 100% kèm giọng đọc và phụ đề.
                fallback_source = None
                for prev_sc in reversed(scenes[:i]):
                    prev_img = prev_sc.get("image_path")
                    if prev_img and os.path.exists(prev_img) and os.path.getsize(prev_img) > 0:
                        fallback_source = prev_img
                        break

                if fallback_source:
                    import shutil
                    shutil.copy2(fallback_source, img_file)
                    sc["image_path"] = img_file
                    sc["use_video_ai"] = False
                    media_ok = True
                    safe_log(f"[!] Cảnh {sc_num}: Google Flow quá tải ({res_img}). Tự động phục hồi bối cảnh để tiếp tục dây chuyền xuất video.")
                    notify(step_pct, f"Cảnh {sc_num}: Google Flow quá tải. Tự động phục hồi bối cảnh để hoàn thành video...")
                else:
                    err_msg = f"Lỗi sinh ảnh Flow cảnh {sc_num}: {res_img}."
                    safe_log(f"[X] {err_msg}")
                    notify(step_pct, err_msg)
                    return False, err_msg, run_meta

        elif not media_ok:
            # Chỉ dùng SD 1.5 khi người dùng chủ động chọn engine local khác Flow
            notify(step_pct, f"Đang tạo hình ảnh phân cảnh {sc_num} bằng engine local...")
            try:
                from src.image_service import generate_single_image
                ok_sd, res_sd = generate_single_image(
                    prompt=prompt,
                    output_path=img_file,
                    orientation=orientation,
                    style_preset=style_preset
                )
                if ok_sd and os.path.exists(img_file) and os.path.getsize(img_file) > 0:
                    sc["image_path"] = img_file
                    sc["use_video_ai"] = False
                    media_ok = True
            except Exception as e_sd:
                safe_log(f"[!] Fallback SD lỗi: {e_sd}")

        # Nếu không có tài nguyên hình ảnh hợp lệ, báo lỗi rõ ràng, tuyệt đối không tạo khung hình giả
        if not media_ok:
            err = f"Lỗi sinh ảnh phân cảnh {sc_num}: Không tạo được bối cảnh hợp lệ từ engine."
            notify(step_pct, err)
            return False, err, run_meta

    # 4. PHÂN TÍCH TIMESTAMPS PHỤ ĐỀ (WHISPER)
    notify(78, "Đang tạo phụ đề chính xác từ lời thoại nguồn...")
    all_words = build_exact_tts_timestamps(scenes)

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

    run_meta["final_path"] = final_path
    run_meta["scenes"] = scenes
    run_meta["media_mode"] = media_mode
    run_meta["studio_mode"] = studio_mode
    notify(96, "Đang tạo tiêu đề, mô tả và hashtag phù hợp với nội dung...")
    _, publishing = generate_video_metadata(topic, scenes, language=language)
    run_meta["publishing"] = publishing
    metadata_path = os.path.splitext(final_path)[0] + ".json"
    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(run_meta, metadata_file, ensure_ascii=False, indent=2)
    run_meta["metadata_path"] = metadata_path
    notify(100, f"✅ Hoàn thành video {video_index}: {final_name}")
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
