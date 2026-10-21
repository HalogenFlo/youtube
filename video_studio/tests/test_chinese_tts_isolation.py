# Chức năng: Kiểm chứng cô lập ngôn ngữ tuyệt đối cho kịch bản học tiếng Trung.
# Lý do: Đảm bảo giọng tiếng Việt (vi-VN) tuyệt đối KHÔNG BAO GIỜ đọc chữ Hán giản thể (CJK),
#        và giọng tiếng Trung (zh-CN) phụ trách độc quyền 100% phần phát âm chữ Hán.

import pytest
import os
from unittest.mock import patch, MagicMock
from src.tts_service import clean_vietnamese_tts_text, generate_multivoice_tts, generate_scenes_tts_parallel
from src.batch_producer import normalize_chinese_teaching_scenes
from src.studio_editorial_service import _sanitize_scenes


def test_clean_vietnamese_tts_text_removes_cjk_and_pinyin():
    """Kiểm tra loại bỏ sạch sẽ cả chữ Hán lẫn phiên âm Pinyin (nǐ hǎo) khỏi lời dẫn tiếng Việt."""
    raw = "Chào bạn bằng câu '' (nǐ hǎo). Đây là cách chào hỏi thông thường trong tiếng Trung, tương đương với 'Xin chào'."
    cleaned = clean_vietnamese_tts_text(raw)
    assert "nǐ hǎo" not in cleaned
    assert "nǐ" not in cleaned
    assert "hǎo" not in cleaned
    assert "''" not in cleaned
    assert "Chào bạn" in cleaned
    assert "Đây là cách chào hỏi" in cleaned

    raw_cjk = "Từ 谢谢 (xièxie) dùng để cảm ơn trong tiếng Trung."
    cleaned_cjk = clean_vietnamese_tts_text(raw_cjk)
    assert "谢谢" not in cleaned_cjk
    assert "xièxie" not in cleaned_cjk
    assert "dùng để cảm ơn" in cleaned_cjk


def test_clean_vietnamese_tts_text_preserves_pure_vietnamese():
    """Kiểm tra văn bản tiếng Việt thuần không bị ảnh hưởng."""
    text = "Chào bạn, chúc bạn một ngày tốt lành và tràn đầy năng lượng!"
    assert clean_vietnamese_tts_text(text) == text


def test_normalize_chinese_teaching_scenes_cleans_vietnamese_parts():
    """Kiểm tra hàm chuẩn hóa kịch bản dạy tiếng Trung lọc sạch chữ Hán khỏi lời dẫn tiếng Việt."""
    scenes = [
        {
            "scene_num": 1,
            "narration_vi": "Hãy cùng khám phá từ 你好 trong tiếng Trung.",
            "chinese_text": "你好",
            "pinyin": "nǐ hǎo",
            "usage_vi": "Từ 你好 dùng khi lần đầu gặp mặt.",
        }
    ]
    normalized = normalize_chinese_teaching_scenes(scenes)
    assert len(normalized) == 1
    # narration_vi và usage_vi không còn chữ Hán
    assert "你好" not in normalized[0]["narration_vi"]
    assert "你好" not in normalized[0]["usage_vi"]
    # chinese_text vẫn giữ nguyên chữ Hán
    assert normalized[0]["chinese_text"] == "你好"
    assert normalized[0]["pinyin"] == "nǐ hǎo"


def test_sanitize_scenes_editorial_cleans_vietnamese_parts():
    """Kiểm tra _sanitize_scenes trong ban biên tập loại bỏ chữ Hán khỏi narration_vi."""
    scenes = [
        {
            "scene_num": 1,
            "narration_vi": "Chúng ta có từ 再见 nghĩa là tạm biệt.",
            "chinese_text": "再见",
            "pinyin": "zài jiàn",
            "usage_vi": "Từ 再见 dùng khi chia tay bạn bè.",
            "video_prompt": "A modern classroom setting with clean lighting.",
        }
    ]
    cleaned = _sanitize_scenes(scenes, target_scenes=1, content_mode="chinese_teaching_vi")
    assert len(cleaned) == 1
    assert "再见" not in cleaned[0]["narration_vi"]
    assert "再见" not in cleaned[0]["usage_vi"]
    assert cleaned[0]["chinese_text"] == "再见"


@patch("src.tts_service.generate_tts")
@patch("moviepy.editor.AudioFileClip")
@patch("moviepy.editor.concatenate_audioclips")
def test_generate_multivoice_tts_isolates_cjk_to_chinese_voice(
    mock_concat, mock_clip, mock_gen_tts, tmp_path
):
    """Kiểm tra generate_multivoice_tts bảo đảm giọng vi-VN không nhận chữ Hán, giọng zh-CN chỉ nhận chữ Hán."""
    mock_gen_tts.return_value = (True, "mock.mp3")
    mock_concat_clip = MagicMock()
    mock_concat.return_value = mock_concat_clip

    output_file = str(tmp_path / "test_multivoice.mp3")

    segments = [
        ("Cụm từ 你好 mang ý nghĩa chào hỏi.", "vi-VN-HoaiMyNeural", "+0%"),
        ("你好", "zh-CN-XiaoxiaoNeural", "-5%"),
        ("你好", "zh-CN-XiaoxiaoNeural", "-15%"),
        ("Đọc là nǐ hǎo. Dùng từ 你好 khi gặp nhau.", "vi-VN-HoaiMyNeural", "+0%"),
    ]

    ok, result = generate_multivoice_tts(segments, output_file)
    assert ok is True

    # Kiểm tra tất cả các lời gọi generate_tts
    calls = mock_gen_tts.call_args_list
    assert len(calls) == 4

    # Đoạn 1 (vi-VN): Phải không còn "你好"
    call_1_text, call_1_path = calls[0][0]
    call_1_voice = calls[0][1]["voice"]
    assert "vi-VN" in call_1_voice
    assert "你好" not in call_1_text

    # Đoạn 2 (zh-CN): Phải là "你好"
    call_2_text, _ = calls[1][0]
    call_2_voice = calls[1][1]["voice"]
    assert "zh-CN" in call_2_voice
    assert call_2_text == "你好"

    # Đoạn 3 (zh-CN): Phải là "你好"
    call_3_text, _ = calls[2][0]
    call_3_voice = calls[2][1]["voice"]
    assert "zh-CN" in call_3_voice
    assert call_3_text == "你好"

    # Đoạn 4 (vi-VN): Phải không còn "你好" và không còn "nǐ hǎo"
    call_4_text, _ = calls[3][0]
    call_4_voice = calls[3][1]["voice"]
    assert "vi-VN" in call_4_voice
    assert "你好" not in call_4_text
    assert "nǐ hǎo" not in call_4_text
    assert "nǐ" not in call_4_text


@patch("src.tts_service.get_audio_duration", return_value=3.5)
@patch("src.tts_service.generate_multivoice_tts")
def test_parallel_tts_with_chinese_teaching_mode(mock_multivoice, mock_duration, tmp_path):
    """Kiểm tra generate_scenes_tts_parallel khi chạy chế độ chinese_teaching_vi chuyển đúng tham số đã làm sạch."""
    def _mock_multivoice_impl(segments, output_file):
        with open(output_file, "wb") as f:
            f.write(b"dummy mp3 audio data")
        return True, output_file

    mock_multivoice.side_effect = _mock_multivoice_impl

    scenes = [
        {
            "scene_num": 1,
            "narration_vi": "Từ 你好 rất phổ biến.",
            "chinese_text": "你好",
            "pinyin": "nǐ hǎo",
            "usage_vi": "Hãy dùng 你好 thường xuyên.",
        }
    ]

    ok, msg = generate_scenes_tts_parallel(
        scenes=scenes,
        video_work_dir=str(tmp_path),
        content_mode="chinese_teaching_vi",
        max_workers=1,
    )
    assert ok is True
    assert mock_multivoice.called

    # Kiểm tra các segment gửi tới multivoice_tts
    call_args = mock_multivoice.call_args[0]
    segments_sent = call_args[0]

    # Segment 0: narration_vi không được chứa chữ Hán
    assert "你好" not in segments_sent[0][0]
    # Segment 1 & 2: chinese_text
    assert segments_sent[1][0] == "你好"
    assert segments_sent[2][0] == "你好"
    # Segment 3: usage_vi không được chứa chữ Hán hoặc Pinyin
    assert "你好" not in segments_sent[3][0]
    assert "nǐ hǎo" not in segments_sent[3][0]
    assert "Đọc là" not in segments_sent[3][0]
