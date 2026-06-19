# Chức năng: Transcribe giọng nói thành văn bản và lấy mốc thời gian từng từ (word-level timestamps) bằng Faster-Whisper.
# Lý do tạo: Phục vụ chuyển đổi âm thanh gốc thành văn bản để remake và tạo phụ đề karaoke ASS đồng bộ chính xác.
# Trích dẫn: Sử dụng thư viện faster-whisper.

import gc
import torch
from typing import Tuple, List, Dict, Any
from faster_whisper import WhisperModel
from src.config import WHISPER_MODEL_DEFAULT, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

def _load_model(model_size: str) -> WhisperModel:
    """
    Tải model Whisper một cách an toàn. Thử chạy trên GPU trước, 
    nếu thất bại (bao gồm lỗi thiếu DLL do lazy load) sẽ tự động fallback về CPU.
    """
    try:
        # Thử load trên GPU
        model = WhisperModel(
            model_size, 
            device=WHISPER_DEVICE, 
            compute_type=WHISPER_COMPUTE_TYPE
        )
        # Ép CTranslate2 nạp các thư viện DLL CUDA ngay lập tức bằng cách chạy thử 0.1s im lặng
        import numpy as np
        dummy_audio = np.zeros(1600, dtype=np.float32)
        # Gọi list() để chạy generator thực tế
        list(model.transcribe(dummy_audio, beam_size=1)[0])
        return model
    except Exception as e:
        print(f"Không thể khởi động Faster-Whisper trên GPU ({e}). Đang tự động fallback về CPU...")
        # Fallback về CPU
        model = WhisperModel(
            model_size, 
            device="cpu", 
            compute_type="int8"
        )
        return model

def transcribe_audio_to_text(
    audio_path: str, 
    language: str = "vi",
    model_size: str = WHISPER_MODEL_DEFAULT
) -> Tuple[bool, str]:
    """
    Chuyển đổi file âm thanh WAV thành văn bản thô (không lấy timestamps).
    Dành cho việc lấy kịch bản từ video gốc ở Luồng B.
    """
    model = None
    try:
        model = _load_model(model_size)
        segments, info = model.transcribe(audio_path, language=language, beam_size=5)
        
        # Nối tất cả các phân đoạn văn bản
        text_list = [segment.text for segment in segments]
        full_text = " ".join(text_list).strip()
        
        return True, full_text
    except Exception as e:
        return False, f"Lỗi trong quá trình transcribe: {str(e)}"
    finally:
        # Giải phóng VRAM
        if model is not None:
            del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def get_word_timestamps(
    audio_path: str, 
    language: str = "vi",
    model_size: str = WHISPER_MODEL_DEFAULT
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Phân tích file âm thanh WAV để lấy mốc thời gian chi tiết của từng từ (word-level timestamps).
    Dành cho việc tạo phụ đề karaoke.
    Trả về danh sách dạng: [{"word": "Xin", "start": 0.1, "end": 0.4}, ...]
    """
    model = None
    try:
        model = _load_model(model_size)
        # Bắt buộc đặt word_timestamps=True
        segments, info = model.transcribe(
            audio_path, 
            language=language, 
            word_timestamps=True, 
            beam_size=5
        )
        
        words_list = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    words_list.append({
                        "word": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3)
                    })
                    
        return True, words_list
    except Exception as e:
        return False, f"Lỗi trong quá trình lấy word timestamps: {str(e)}"
    finally:
        # Giải phóng VRAM
        if model is not None:
            del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def transcribe_with_segments(
    audio_path: str,
    model_size: str = WHISPER_MODEL_DEFAULT
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Transcribe âm thanh mà không truyền trước ngôn ngữ để Whisper tự phát hiện (auto-detect).
    Trả về: (success, segments_list, detected_language)
    Trong đó segments_list là list các dict: {"text": "...", "start": float, "end": float}
    """
    model = None
    try:
        model = _load_model(model_size)
        # Không truyền language để kích hoạt auto-detect
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        detected_language = info.language
        
        segments_list = []
        for segment in segments:
            segments_list.append({
                "text": segment.text.strip(),
                "start": round(segment.start, 3),
                "end": round(segment.end, 3)
            })
            
        return True, segments_list, detected_language
    except Exception as e:
        return False, [], f"Lỗi transcribe segments: {str(e)}"
    finally:
        if model is not None:
            del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

