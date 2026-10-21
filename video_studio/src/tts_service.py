# Chức năng: Gọi CLI edge-tts qua subprocess để sinh giọng đọc tiếng Việt chất lượng cao.
# Lý do tạo: Tránh các lỗi encoding websocket và xung đột asyncio event loop trong môi trường Streamlit.
# Trích dẫn: Sử dụng CLI chính thức của thư viện edge-tts với file tạm UTF-8 và cơ chế voice fallback.

import os
import re
import sys
import tempfile
import subprocess
import time
from typing import List, Tuple, Dict, Any, Optional, Callable
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.config import TTS_VOICE_DEFAULT, TTS_VOICE_ZH_DEFAULT

try:
    from src.voice_clone_service import generate_cloned_tts
except Exception:
    generate_cloned_tts = None


# Đảm bảo in log trên Windows không bị UnicodeEncodeError
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

# Bản đồ giọng đọc dự phòng khi giọng chính gặp lỗi NoAudioReceived hoặc nghẽn mạng
VOICE_FALLBACK_MAP = {
    "vi-VN-HoaiMyNeural": "vi-VN-NamMinhNeural",
    "vi-VN-NamMinhNeural": "vi-VN-HoaiMyNeural",
    "en-US-EmmaNeural": "en-US-JennyNeural",
    "en-US-JennyNeural": "en-US-GuyNeural",
    "en-US-GuyNeural": "en-US-JennyNeural",
    "zh-CN-XiaoxiaoNeural": "zh-CN-YunxiNeural",
    "zh-CN-YunxiNeural": "zh-CN-XiaoxiaoNeural",
}


def sanitize_tts_text(text: str) -> str:
    """
    Làm sạch văn bản kịch bản trước khi đưa vào TTS:
    - Loại bỏ các thẻ chỉ dẫn đạo diễn trong ngoặc: [nhạc nền...], (tiếng thở dài...)
    - Loại bỏ các ký hiệu markdown: **, *, #, __, `
    - Chuẩn hóa khoảng trắng và dấu câu
    """
    if not text:
        return ""
    
    clean = str(text)
    
    # 1. Loại bỏ các chỉ dẫn kịch bản trong ngoặc vuông [âm thanh], [nhạc nền], [SFX]
    clean = re.sub(r'\[.*?\]', ' ', clean)
    
    # 2. Loại bỏ các chỉ dẫn trong ngoặc đơn nếu có dạng gợi ý đạo diễn (ví dụ: (cười), (thì thầm), (giọng trầm))
    clean = re.sub(r'\((?:cười|khóc|thì thầm|giọng trầm|tiếng cười|tiếng nói|nhạc|thở dài|ngạc nhiên|pause|dừng|im lặng).*?\)', ' ', clean, flags=re.IGNORECASE)
    
    # 3. Loại bỏ ký tự markdown
    clean = re.sub(r'[*#_`~]', '', clean)
    
    # 4. Loại bỏ các URL nếu có
    clean = re.sub(r'https?://\S+', '', clean)
    
    # 5. Chuẩn hóa khoảng trắng
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Nếu sau khi lọc mà văn bản bị rỗng hoặc không còn chữ nào, giữ lại văn bản gốc đã gọt bỏ ký tự đặc biệt
    if not clean or not re.search(r'[\w\d]', clean, flags=re.UNICODE):
        clean = re.sub(r'[[\](){}*#_`~]', '', str(text)).strip()
        
    return clean


def _run_edge_tts_direct(text: str, output_path: str, voice: str, rate: str) -> Tuple[bool, str]:
    """
    Sinh audio trực tiếp qua API edge_tts.Communicate của Python.
    Giải quyết triệt để lỗi NoAudioReceived do CLI subprocess, buffer text UTF-8 hoàn hảo.
    """
    import asyncio
    import edge_tts

    # Đảm bảo thư mục cha tồn tại
    parent_dir = os.path.dirname(output_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    formatted_rate = rate
    if not (rate.startswith('+') or rate.startswith('-')):
        formatted_rate = f"+{rate}"

    async def _async_synthesize():
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=formatted_rate)
        await communicate.save(output_path)

    try:
        # Chạy trong loop an toàn
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Nếu đang ở trong một running loop (Streamlit thread), tạo loop độc lập trong thread riêng
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                def _run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(_async_synthesize())
                    finally:
                        new_loop.close()
                pool.submit(_run_in_new_loop).result(timeout=45)
        else:
            loop.run_until_complete(_async_synthesize())

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True, output_path
        else:
            return False, "File audio sinh ra có dung lượng không hợp lệ hoặc rỗng."
    except Exception as exc:
        if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False, str(exc)


def generate_tts(
    text: str, 
    output_path: str, 
    voice: str = TTS_VOICE_DEFAULT, 
    rate: str = "+0%"
) -> Tuple[bool, str]:
    """
    Sinh file audio giọng đọc từ văn bản sử dụng API edge-tts với cơ chế phục hồi cao:
    1. Làm sạch văn bản kịch bản (loại bỏ markdown, thẻ đạo diễn).
    2. Gọi API edge_tts.Communicate trực tiếp (chống lỗi subprocess CLI NoAudioReceived).
    3. Thử lại tối đa 3 lần với exponential backoff.
    4. Tự động chuyển sang giọng phụ (fallback voice: NamMinh <-> HoaiMy) nếu giọng chính bị nghẽn mạng.
    Trả về: (True, output_path) nếu thành công, (False, error_message) nếu thất bại.
    """
    clean_text = sanitize_tts_text(text)
    if not clean_text or not clean_text.strip():
        return False, "Văn bản trống hoặc chỉ chứa ký hiệu, không thể sinh giọng đọc."

    voices_to_try = [voice]
    # Xác định giọng dự phòng nếu có
    alt_voice = VOICE_FALLBACK_MAP.get(voice)
    if not alt_voice:
        if "vi-VN" in voice:
            alt_voice = "vi-VN-NamMinhNeural" if "HoaiMy" in voice else "vi-VN-HoaiMyNeural"
        elif "en-US" in voice:
            alt_voice = "en-US-JennyNeural" if "Emma" in voice else "en-US-GuyNeural"
    if alt_voice and alt_voice not in voices_to_try:
        voices_to_try.append(alt_voice)

    last_err = ""
    for v_idx, current_voice in enumerate(voices_to_try):
        max_attempts = 3
        for attempt in range(max_attempts):
            success, result_or_err = _run_edge_tts_direct(
                text=clean_text,
                output_path=output_path,
                voice=current_voice,
                rate=rate
            )
            if success:
                if v_idx > 0:
                    try:
                        print(f"[TTS] Đã tự động phục hồi thành công bằng giọng dự phòng: {current_voice}")
                    except Exception:
                        pass
                return True, output_path
            
            last_err = result_or_err
            try:
                print(f"[TTS] Lần thử {attempt + 1}/{max_attempts} với giọng '{current_voice}' thất bại: {last_err}")
            except Exception:
                pass
            # Backoff giãn cách có tăng dần để giải tỏa nghẽn kết nối WebSocket của Microsoft
            retry_sleep = 1.0 * (attempt + 1)
            time.sleep(retry_sleep)

        if v_idx < len(voices_to_try) - 1:
            try:
                print(f"[TTS] Giọng '{current_voice}' không phản hồi, tự động chuyển sang giọng dự phòng '{voices_to_try[v_idx + 1]}'...")
            except Exception:
                pass
            time.sleep(0.5)

    # Cơ chế tự phục hồi thông minh (Smart Prefix Padding):
    # Nếu câu bị lỗi NoAudioReceived (thường do câu ngắn hoặc Bing SSML drop frame tối thiểu),
    # tự động đệm tiền tố liên từ tự nhiên để kích hoạt pipeline tổng hợp của Microsoft Bing.
    if "No audio was received" in last_err or len(clean_text) < 35:
        padding_prefixes = ["Và rồi, ", "Thế là, ", "Lúc này, "]
        for prefix in padding_prefixes:
            padded_sentence = f"{prefix}{clean_text.rstrip('.')}."
            for pad_voice in voices_to_try:
                time.sleep(1.2)
                ok_pad, res_pad = _run_edge_tts_direct(
                    text=padded_sentence,
                    output_path=output_path,
                    voice=pad_voice,
                    rate=rate,
                )
                if ok_pad and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    try:
                        print(f"[TTS] Tự phục hồi thành công bằng tiền tố ngữ cảnh: '{padded_sentence[:40]}...' ({pad_voice})")
                    except Exception:
                        pass
                    return True, output_path

    return False, f"Lỗi sinh giọng đọc edge-tts: {last_err}"


# Ký tự phiên âm Pinyin độc quyền (tuyệt đối không thuộc bảng chữ cái tiếng Việt)
_PINYIN_EXCLUSIVE_CHARS_REGEX = r'[āēīōūǎěǐǒǔüǖǘǚǜĀĒĪŌŪǍĚǏǑǓÜǕǗǙǛ]'

# Ký tự tiếng Việt đặc thù (nếu có thì chắc chắn là tiếng Việt)
_VIETNAMESE_DISTINCT_CHARS_REGEX = r'[ăâêôơưđĂÂÊÔƠƯĐảẳẩẻểỉỏổởủửỷẢẲẨẺỂỈỎỔỞỦỬỶãẵẫẽễĩõỗỡũữỹÃẴẪẼỄĨÕỖỠŨỮỸạặậẹệịọộợụựỵẠẶẬẸỆỊỌỘỢỤỰỴ]'


def clean_vietnamese_tts_text(text: str) -> str:
    """
    Làm sạch hoàn toàn lời dẫn tiếng Việt trước khi đưa vào TTS:
    1. Loại bỏ các ký tự chữ Hán / tiếng Trung giản thể (CJK).
    2. Loại bỏ các đoạn phiên âm Pinyin trong ngoặc: (nǐ hǎo), (zǎo shàng hǎo), (ni hao)...
    3. Loại bỏ các từ chứa ký tự thanh điệu Pinyin độc quyền (ā, ǎ, ǐ, ǒ, ǔ, ü...).
    4. Loại bỏ các cặp dấu ngoặc rỗng '', "", () sót lại sau khi xóa chữ Hán.
    5. Đảm bảo 100% giọng tiếng Việt thuần túy, không bao giờ phát âm chữ Hán hay đánh vần méo mó Pinyin.
    """
    if not text:
        return ""
    
    cleaned = str(text)

    # 1. Xóa ký tự chữ Hán CJK
    cleaned = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+', '', cleaned)

    # 2. Xóa phiên âm Pinyin trong ngoặc đơn:
    # Trường hợp 2a: Ngoặc đơn chứa ký tự Pinyin độc quyền (nǐ hǎo, lǎoshī, wǒ...)
    cleaned = re.sub(rf'\s*\([^)]*{_PINYIN_EXCLUSIVE_CHARS_REGEX}[^)]*\)', '', cleaned)

    # Trường hợp 2b: Ngoặc đơn chú thích phiên âm ngắn không chứa ký tự tiếng Việt đặc thù
    def _strip_pinyin_paren(m):
        content = m.group(1).strip()
        # Nếu có ký tự tiếng Việt đặc thù (ă, â, ê, dấu hỏi, ngã, nặng, đ...) thì giữ lại
        if re.search(_VIETNAMESE_DISTINCT_CHARS_REGEX, content):
            return m.group(0)
        # Nếu chỉ gồm chữ cái Latin / pinyin không dấu hoặc dấu huyền/sắc thông thường và ngắn (< 50 ký tự)
        if len(content) <= 50 and re.match(r'^(?:pinyin:?\s*)?[a-zA-Zàáèéìíòóùú\s,\'\"\-]+$', content, flags=re.IGNORECASE):
            return ''
        return m.group(0)

    cleaned = re.sub(r'\s*\(([^)]+)\)', _strip_pinyin_paren, cleaned)

    # 3. Xóa các từ chứa ký tự Pinyin độc quyền đứng lẻ (ví dụ nǐ, hǎo, lǎo...)
    # Chỉ nhắm vào ký tự Pinyin độc quyền để TUYỆT ĐỐI không xóa nhầm từ tiếng Việt như 'Chào', 'chúc', 'ngày'
    cleaned = re.sub(rf'[\'\"“”‘’]?\b\w*{_PINYIN_EXCLUSIVE_CHARS_REGEX}\w*\b[\'\"“”‘’]?', '', cleaned)

    # 4. Xóa các dấu ngoặc kép / đơn / tròn rỗng còn sót lại sau khi gọt bỏ chữ Hán / Pinyin
    cleaned = re.sub(r'[\'\"“”‘’]\s*[\'\"“”‘’]', '', cleaned)
    cleaned = re.sub(r'\(\s*\)', '', cleaned)

    # 5. Dọn dẹp các cụm từ mồ côi thường sót lại sau khi xóa chữ Hán như: "câu ''", "từ ''", "câu.", "từ."
    cleaned = re.sub(r'\b(bằng\s+câu|từ\s+câu|bằng\s+từ)\s*([.,;!?])', r'\2', cleaned, flags=re.IGNORECASE)

    # 6. Chuẩn hóa dấu câu và khoảng trắng
    cleaned = re.sub(r'\s+([,.:;!?])', r'\1', cleaned)
    cleaned = re.sub(r'[,:;]+\s*([.!?])', r'\1', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(" ,;:-_")
    return cleaned


def generate_multivoice_tts(
    segments: List[Tuple[str, str, str]],
    output_path: str,
) -> Tuple[bool, str]:
    """Sinh từng đoạn bằng đúng giọng/ngôn ngữ rồi nối thành một file MP3."""
    from moviepy.editor import AudioFileClip, concatenate_audioclips

    parent_dir = os.path.dirname(output_path) or "."
    os.makedirs(parent_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(output_path))[0]
    temp_paths = []
    clips = []
    try:
        usable_segments = []
        for text, voice, rate in segments:
            if not text or not str(text).strip():
                continue
            clean_t = str(text).strip()
            # BẢO ĐẢM TUYỆT ĐỐI: Giọng tiếng Việt KHÔNG BAO GIỜ đọc chữ Hán giản thể
            if voice.startswith("vi-") or "vi-VN" in voice:
                clean_t = clean_vietnamese_tts_text(clean_t)
            # BẢO ĐẢM TUYỆT ĐỐI: Giọng tiếng Trung chỉ đọc chữ Hán, loại bỏ rác nếu có
            elif voice.startswith("zh-") or "zh-CN" in voice:
                # Nếu text có ký tự Hán, giữ lại chuẩn xác
                hanzi = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+', clean_t)
                if hanzi:
                    clean_t = "".join(hanzi)
            if clean_t and clean_t.strip():
                usable_segments.append((clean_t, voice, rate))

        if not usable_segments:
            return False, "Không có nội dung để sinh giọng đọc đa ngôn ngữ."
        for index, (text, voice, rate) in enumerate(usable_segments, start=1):
            segment_path = os.path.join(parent_dir, f".{stem}_segment_{index:02d}.mp3")
            temp_paths.append(segment_path)
            ok, result = generate_tts(text, segment_path, voice=voice, rate=rate)
            if not ok:
                return False, result
            clips.append(AudioFileClip(segment_path))
        combined = concatenate_audioclips(clips)
        combined.write_audiofile(output_path, codec="libmp3lame", bitrate="192k", verbose=False, logger=None)
        combined.close()
        return True, output_path
    except Exception as exc:
        return False, f"Lỗi ghép giọng Việt–Trung: {exc}"
    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        for temp_path in temp_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass


def get_audio_duration(file_path: str) -> float:
    """
    Đo thời lượng file audio chính xác bằng mutagen, wave hoặc moviepy.
    """
    if not file_path or not os.path.exists(file_path):
        return 0.0
    try:
        from mutagen.mp3 import MP3
        return float(MP3(file_path).info.length)
    except Exception:
        pass
    try:
        import wave
        with wave.open(file_path, 'r') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames / rate)
    except Exception:
        pass
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(file_path)
        dur = float(clip.duration)
        clip.close()
        return dur
    except Exception:
        return 5.0


def generate_scenes_tts_parallel(
    scenes: List[Dict[str, Any]],
    video_work_dir: str,
    voice: str = TTS_VOICE_DEFAULT,
    voice_mode: str = "edge",
    content_mode: str = "knowledge",
    chinese_voice: str = TTS_VOICE_ZH_DEFAULT,
    voice_reference_path: str = "",
    rate: str = "+0%",
    max_workers: int = 4,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    language: str = "vi",
) -> Tuple[bool, str]:
    """
    Sinh giọng đọc song song cho tất cả các phân cảnh trong kịch bản.
    Đảm bảo:
    1. Tối ưu hóa thời gian xử lý thông qua ThreadPoolExecutor (max_workers=max_workers).
    2. Bảo toàn 100% thứ tự phân cảnh (scene 1, scene 2, ... N) qua mapping future_to_index.
    3. Tái sử dụng file âm thanh có sẵn nếu đã tồn tại hợp lệ (>1000 bytes).
    4. Cập nhật sc['audio_path'] và sc['audio_duration'] in-place.
    5. Báo cáo tiến độ realtime qua progress_callback(done_count, total_scenes, message).
    """
    if not scenes:
        return True, "Không có phân cảnh nào cần xử lý."

    os.makedirs(video_work_dir, exist_ok=True)
    total_scenes = len(scenes)
    completed_count = 0
    lock = threading.Lock()

    tasks_to_run = []

    for idx, sc in enumerate(scenes):
        sc_num = (sc.get("scene_num") if isinstance(sc, dict) else None) or (idx + 1)
        audio_ext = ".wav" if voice_mode == "clone_local" and content_mode != "chinese_teaching_vi" else ".mp3"
        audio_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}{audio_ext}")

        # Kiểm tra cache tái sử dụng
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
            if isinstance(sc, dict):
                sc["audio_path"] = audio_file
                sc["audio_duration"] = get_audio_duration(audio_file)
            with lock:
                completed_count += 1
                curr_done = completed_count
            if progress_callback:
                try:
                    progress_callback(curr_done, total_scenes, f"Đã có giọng đọc phân cảnh {curr_done}/{total_scenes} (cảnh {sc_num})")
                except Exception:
                    pass
        else:
            tasks_to_run.append((idx, sc, audio_file))

    if not tasks_to_run:
        return True, "Đã có sẵn giọng đọc cho toàn bộ phân cảnh."

    def _worker(task_tuple: Tuple[int, Any, str], delay: float = 0.0) -> Tuple[int, bool, str, str, float]:
        if delay > 0:
            time.sleep(delay)
        t_idx, t_sc, t_audio_file = task_tuple
        t_sc_num = (t_sc.get("scene_num") if isinstance(t_sc, dict) else None) or (t_idx + 1)
        try:
            if content_mode == "chinese_teaching_vi":
                clean_narr_vi = clean_vietnamese_tts_text(str(t_sc.get("narration_vi", "") if isinstance(t_sc, dict) else t_sc))
                clean_use_vi = clean_vietnamese_tts_text(str(t_sc.get("usage_vi", "") if isinstance(t_sc, dict) else ""))
                chinese_text = str(t_sc.get("chinese_text", "") if isinstance(t_sc, dict) else "").strip()
                audio_ok, audio_result = generate_multivoice_tts(
                    [
                        (clean_narr_vi, voice, "+0%"),
                        (chinese_text, chinese_voice, "-5%"),
                        (chinese_text, chinese_voice, "-18%"),
                        (clean_use_vi, voice, "+0%"),
                    ],
                    t_audio_file,
                )
            elif voice_mode == "clone_local":
                clone_fn = globals().get("generate_cloned_tts")
                if clone_fn is None:
                    try:
                        from src.voice_clone_service import generate_cloned_tts as _gct
                        clone_fn = _gct
                    except Exception:
                        clone_fn = None
                if clone_fn is None:
                    return t_idx, False, "Chức năng nhân bản giọng đọc (voice clone) không khả dụng.", "", 0.0

                narr_text = t_sc.get("narration", "") if isinstance(t_sc, dict) else str(t_sc)
                audio_ok, audio_result = clone_fn(
                    text=narr_text,
                    output_path=t_audio_file,
                    reference_audio=voice_reference_path,
                    language=language,
                )
            else:
                narr_text = t_sc.get("narration", "") if isinstance(t_sc, dict) else str(t_sc)
                audio_ok, audio_result = generate_tts(
                    text=narr_text,
                    output_path=t_audio_file,
                    voice=voice,
                    rate=rate,
                )

            if not audio_ok or not os.path.exists(t_audio_file):
                err = f"Lỗi giọng đọc cảnh {t_sc_num}: {audio_result}"
                return t_idx, False, err, "", 0.0

            dur = get_audio_duration(t_audio_file)
            return t_idx, True, "", t_audio_file, dur
        except Exception as exc:
            return t_idx, False, f"Lỗi giọng đọc cảnh {t_sc_num}: {exc}", "", 0.0

    worker_count = max_workers if max_workers and max_workers > 0 else 4
    first_error = None

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_idx = {
            executor.submit(_worker, task, i * 1.2): task[0]
            for i, task in enumerate(tasks_to_run)
        }

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                res_idx, success, err_msg, out_file, duration = future.result()
            except Exception as e:
                res_idx = idx
                success = False
                err_msg = f"Lỗi giọng đọc cảnh {scenes[idx].get('scene_num') or (idx + 1)}: {e}"
                out_file = ""
                duration = 0.0

            if not success:
                if not first_error:
                    first_error = err_msg
            else:
                scenes[res_idx]["audio_path"] = out_file
                scenes[res_idx]["audio_duration"] = duration
                with lock:
                    completed_count += 1
                    curr_done = completed_count
                if progress_callback:
                    sc_num = scenes[res_idx].get("scene_num") or (res_idx + 1)
                    try:
                        progress_callback(curr_done, total_scenes, f"Đã sinh giọng đọc phân cảnh {curr_done}/{total_scenes} (cảnh {sc_num})")
                    except Exception:
                        pass

    # Nếu có phân cảnh bị lỗi do xung đột socket song song, tự động phục hồi tuần tự từng cảnh
    unresolved_tasks = [task for task in tasks_to_run if not scenes[task[0]].get("audio_path")]
    if unresolved_tasks:
        try:
            print(f"[TTS Parallel] Phát hiện {len(unresolved_tasks)} cảnh bị nghẽn mạng WebSocket song song. Đang tự phục hồi tuần tự...")
        except Exception:
            pass

        for retry_idx, retry_task in enumerate(unresolved_tasks):
            time.sleep(2.0)  # Giãn cách 2 giây để Microsoft giải phóng rate-limit WebSocket
            r_idx, r_success, r_err, r_out_file, r_dur = _worker(retry_task, delay=0.0)
            if r_success:
                scenes[r_idx]["audio_path"] = r_out_file
                scenes[r_idx]["audio_duration"] = r_dur
                completed_count += 1
                if progress_callback:
                    sc_num = scenes[r_idx].get("scene_num") or (r_idx + 1)
                    try:
                        progress_callback(completed_count, total_scenes, f"Đã phục hồi giọng đọc phân cảnh {completed_count}/{total_scenes} (cảnh {sc_num})")
                    except Exception:
                        pass
            else:
                return False, r_err

    return True, f"Hoàn thành sinh giọng đọc cho {total_scenes} phân cảnh."

