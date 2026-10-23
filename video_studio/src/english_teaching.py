"""Strict Vietnamese teaching / English pronunciation segments for MuseAI lessons.

Explicit language labels keep English examples out of the Vietnamese voice and
preserve the same order in speech, subtitles, and saved script metadata.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List

LESSON_MODE = "english_teaching_vi"


def english_lesson_instructions(whiteboard: bool = False) -> str:
    guidance = """
ENGLISH LESSON FOR VIETNAMESE LEARNERS — STRICT LANGUAGE ROUTING:
- Return content_mode="english_teaching_vi" at the top level.
- Explanations, translations, instructions and episode summaries are in Vietnamese.
- English vocabulary, sample sentences and pronunciation examples are spoken ONLY by the English voice.
- Every scene MUST have speech_segments, an ordered array of objects with language="vi" or "en", text, speaker="narrator".
- Keep each segment monolingual. Put an English example in its own en segment even in the middle of an explanation.
- Example structure: vi explanation -> en sample -> vi meaning and usage -> en practice sample (only if useful).
- Do not put English examples in vi segments. Use Vietnamese descriptions to introduce the next sample.
- Do not put IPA, phonetic spellings or stage directions in spoken text; these may be displayed as whiteboard text.
- Set narration to the exact concatenation of speech_segments texts in order; do not invent additional dialogue.
- Do not substitute an all-English lesson or read English examples with a Vietnamese voice.
- For recap/preview, keep the prose Vietnamese; mark any unavoidable English example explicitly as [en]example[/en].
"""
    if whiteboard:
        guidance += """
WHITEBOARD ENGLISH LESSON — CONTEXT BEFORE PHRASES:
- Build a connected mini-situation, not a list of translations or disconnected flashcards.
- Before teaching a phrase, introduce where the learner is, whom they are speaking to,
  what they need, or a relatable difficulty. Use a warm Vietnamese hook, then a clear goal.
- Every body scene containing an en speech segment MUST also return lesson_context:
  1–2 short Vietnamese sentences establishing that scene's situation BEFORE its phrases.
- lesson_context is SPOKEN, not a production note. It must contain no English examples.
  The application prepends it as a vi speech segment; do NOT repeat it in speech_segments.
- Continue speech_segments with vi communicative need/question -> en useful phrase ->
  vi meaning and when to use it -> en learner practice if useful. Keep scene transitions natural.
- First context example: "Bạn đang đi chợ ở nước ngoài và muốn mua trái cây.
  Người bán đang chờ, nhưng bạn chưa biết mở lời thế nào."
  Then vi "Muốn xin hai quả táo một cách lịch sự, bạn có thể nói:" ->
  en "I'd like two apples, please." -> vi meaning/usage.
- Later contexts should move the situation forward, without repeating the opening hook.
- Show the context with the FIRST drawing(s), followed by the phrase text. Match every
  person/object to what is being discussed; do not reveal a full answer before the setup.
- Count the context in the scene's spoken duration. Keep the context and phrase on the same
  frame when a scene limit is given; do not sacrifice the setup to satisfy the scene count.
"""
    return guidance


def prepare_whiteboard_lesson(story: Dict[str, Any]) -> Dict[str, Any]:
    """Put MuseAI's scene-specific spoken setup before examples, once, without inventing it."""
    result = deepcopy(story)
    for index, scene in enumerate(result.get("scenes") or [], 1):
        if not isinstance(scene, dict) or scene.get("series_bridge"):
            continue
        source = scene.get("speech_segments") or []
        context_segments = [s for s in source if isinstance(s, dict) and s.get("lesson_part") == "context"]
        context = str(scene.get("lesson_context") or (context_segments[0].get("text") if context_segments else "") or "").strip()
        samples = [s for s in source if not (isinstance(s, dict) and s.get("lesson_part") == "context")]
        if context and samples and isinstance(samples[0], dict) and samples[0].get("language") == "vi" and str(samples[0].get("text") or "").strip() == context:
            samples = samples[1:]
        if any(isinstance(s, dict) and s.get("language") == "en" for s in samples) and not context:
            raise ValueError(f"Cảnh {index} thiếu lesson_context: cần MuseAI viết tình huống dẫn dắt bằng tiếng Việt trước câu mẫu. Hãy tạo lại kịch bản theo chế độ vẽ tay.")
        if not context:
            continue
        if re.search(r"\[/?en\]", context, flags=re.I):
            raise ValueError(f"Cảnh {index}: lesson_context chỉ gồm lời dẫn tiếng Việt; tách ví dụ Anh sang speech_segments.")
        scene["lesson_context"] = context
        scene["speech_segments"] = [{"language": "vi", "text": context, "lesson_part": "context"}] + samples
        scene["narration"] = " ".join(str(s.get("text") or "").strip() for s in scene["speech_segments"])
        scene.pop("tts_segment_timings", None)
        scene.pop("audio_path", None)
        scene.pop("audio_duration", None)
    return result


def tagged_language_segments(text: str) -> List[Dict[str, str]]:
    """Only explicit English tags switch voices; no unreliable ASCII guessing."""
    if re.search(r"\[/?en\]", text, flags=re.I):
        if len(re.findall(r"\[en\]", text, flags=re.I)) != len(re.findall(r"\[/en\]", text, flags=re.I)):
            raise ValueError("Thiếu thẻ đóng/mở [en] cho phần phát âm tiếng Anh.")
    chunks = re.split(r"(\[en\].*?\[/en\])", text, flags=re.I | re.S)
    segments = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        english = bool(re.fullmatch(r"\[en\].*?\[/en\]", chunk, flags=re.I | re.S))
        value = re.sub(r"^\[en\]|\[/en\]$", "", chunk, flags=re.I).strip() if english else chunk.strip()
        if value:
            segments.append({"language": "en" if english else "vi", "text": value})
    return segments


def build_english_lesson_segments(scene: Dict[str, Any], vietnamese_voice: str,
                                  english_voice: str = "en-US-JennyNeural") -> List[Dict[str, str]]:
    source = scene.get("speech_segments")
    if not isinstance(source, list) or not source:
        dialogue = scene.get("dialogue_lines")
        if isinstance(dialogue, list) and dialogue and all(isinstance(s, dict) and s.get("language") for s in dialogue):
            source = dialogue
        elif scene.get("series_bridge") or "[en]" in str(scene.get("narration") or "").lower():
            source = tagged_language_segments(str(scene.get("narration") or ""))
        else:
            raise ValueError("Bài dạy tiếng Anh cần speech_segments có language=vi/en cho từng đoạn. Hãy yêu cầu MuseAI tạo lại đúng chế độ bài học.")
    segments = []
    for item in source:
        if not isinstance(item, dict):
            raise ValueError("Đoạn giọng đọc phải gồm language và text.")
        text = str(item.get("text") or "").strip()
        lang = str(item.get("language") or "").strip().lower()
        if lang not in {"vi", "en"}:
            raise ValueError("Ngôn ngữ đoạn giọng đọc phải là vi hoặc en.")
        if not text:
            continue
        if "[en]" in text.lower() or "[/en]" in text.lower():
            raise ValueError("Hãy tách nội dung [en] thành đoạn language=en riêng.")
        segment = {"speaker": "narrator", "character_name": "Giáo viên" if lang == "vi" else "Phát âm tiếng Anh",
                   "language": lang, "text": text,
                   "voice_spec": vietnamese_voice if lang == "vi" else english_voice,
                   "rate": "+0%" if lang == "vi" else "-8%"}
        if item.get("lesson_part") == "context" and lang == "vi":
            segment["lesson_part"] = "context"
        segments.append(segment)
    if not segments:
        raise ValueError("Bài học chưa có nội dung giọng đọc.")
    return segments
