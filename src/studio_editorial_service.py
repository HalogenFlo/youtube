"""Ban biên tập local nhiều vai chạy trên Ollama trước khi gửi cảnh sang Flow."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from src.llm_service import call_ollama
from src.config import OLLAMA_MODEL_DEFAULT
from src.studio_skill_registry import select_studio_skills


def _sanitize_scenes(scenes: List[Dict[str, Any]], target_scenes: int) -> List[Dict[str, Any]]:
    cleaned = []
    for index, scene in enumerate(scenes[:max(1, target_scenes)], start=1):
        narration = str(scene.get("narration", "")).strip()
        visual = str(scene.get("video_prompt", "")).strip()
        # Bỏ các câu phủ định đã thêm từ vòng trước để chúng không tự kích hoạt bộ lọc.
        visual = re.sub(
            r"No readable text,? numbers,? formulas,? captions,? logos,? signs,? or watermarks in the image\.?”?",
            "",
            visual,
            flags=re.IGNORECASE,
        ).strip()
        forbidden_visual_pattern = re.compile(
            r"\d|formula|equation|write|writing|written|whiteboard|chalkboard|caption|subtitle",
            re.IGNORECASE,
        )
        if forbidden_visual_pattern.search(visual):
            safe_sentences = [
                sentence.strip() for sentence in re.split(r"[.!?]+", visual)
                if sentence.strip() and not forbidden_visual_pattern.search(sentence)
            ]
            visual = ". ".join(safe_sentences)
            if len(visual) < 35:
                visual = (
                    f"Scene {index}: a distinct conceptual educational metaphor using color-coded geometric blocks and objects, "
                    "natural light, expressive hand gestures, and the same friendly canonical stickman guide"
                )
        no_text_rule = " No readable text, numbers, formulas, captions, logos, signs, or watermarks in the image."
        if no_text_rule.strip().lower() not in visual.lower():
            visual = f"{visual}{no_text_rule}".strip()
        cleaned.append({"scene_num": index, "narration": narration, "video_prompt": visual})
    return cleaned


def run_studio_editorial_pipeline(
    topic: str,
    script_data: Dict[str, Any],
    target_scenes: int,
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Một vòng bàn biên tập: fact-check, hook, clarity, visual continuity, policy."""
    original_scenes = _sanitize_scenes(script_data.get("scenes", []), target_scenes)
    selected = select_studio_skills(topic)
    selected_ids = [item["id"] for item in selected]
    selected_names = [item["name"] for item in selected]

    system_prompt = (
        "Bạn là ban biên tập studio video ngắn gồm: nghiên cứu viên, kiểm chứng, biên kịch, "
        "biên tập giữ chân, đạo diễn hình ảnh và kiểm duyệt YouTube/TikTok. "
        "Hãy sửa trực tiếp kịch bản, không chỉ nhận xét. Chỉ trả JSON hợp lệ gồm scenes và report. "
        "Giữ ĐÚNG số cảnh yêu cầu. Cảnh 1 phải đi thẳng vào giá trị/hook; các cảnh giữa giải thích cụ thể; "
        "cảnh cuối kết luận. Kiến thức/toán phải chính xác. Không tạo tuyên bố chưa kiểm chứng. "
        "video_prompt phải bằng tiếng Anh và không được yêu cầu hiển thị chữ, số, công thức, biển hiệu hay phụ đề. "
        "report gồm scores (factual_accuracy, hook_strength, clarity, visual_continuity, policy_safety; 0-100), "
        "issues_fixed, remaining_warnings và approved."
    )
    prompt = (
        f"Chủ đề: {topic}\nNgôn ngữ lời thoại: {language}\nSố cảnh bắt buộc: {target_scenes}\n"
        f"Các kỹ năng được registry chọn: {', '.join(selected_names)}\n"
        f"Kịch bản nháp:\n{json.dumps({'scenes': original_scenes}, ensure_ascii=False)}"
    )
    success, edited = call_ollama(prompt, system_prompt, model)
    if success and isinstance(edited, dict) and isinstance(edited.get("scenes"), list):
        edited_scenes = _sanitize_scenes(edited["scenes"], target_scenes)
        scenes = edited_scenes if len(edited_scenes) == target_scenes else original_scenes
        raw_report = edited.get("report", {}) if isinstance(edited.get("report"), dict) else {}
    else:
        scenes = original_scenes
        raw_report = {
            "scores": {"factual_accuracy": 70, "hook_strength": 70, "clarity": 75, "visual_continuity": 75, "policy_safety": 80},
            "issues_fixed": ["Áp dụng bộ lọc cấu trúc và quy tắc không chữ trong hình"],
            "remaining_warnings": ["Ollama editorial pass không phản hồi; dùng bản nháp đã chuẩn hóa"],
            "approved": False,
        }

    scores = raw_report.get("scores", {}) if isinstance(raw_report.get("scores"), dict) else {}
    normalized_scores = {}
    for key in ["factual_accuracy", "hook_strength", "clarity", "visual_continuity", "policy_safety"]:
        try:
            normalized_scores[key] = max(0, min(100, int(scores.get(key, 70))))
        except Exception:
            normalized_scores[key] = 70
    overall = round(sum(normalized_scores.values()) / len(normalized_scores), 1)
    warnings = raw_report.get("remaining_warnings", [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    if len(scenes) != target_scenes:
        warnings.append(f"Số cảnh thực tế {len(scenes)} khác mục tiêu {target_scenes}")

    report = {
        "mode": "local_multi_role_studio",
        "selected_skills": selected,
        "selected_skill_ids": selected_ids,
        "scores": normalized_scores,
        "overall_score": overall,
        "issues_fixed": raw_report.get("issues_fixed", []),
        "remaining_warnings": warnings,
        "approved": bool(raw_report.get("approved", overall >= 78)) and overall >= 70,
        "source_grounding": "user_prompt_and_local_model",
    }
    return scenes, report
