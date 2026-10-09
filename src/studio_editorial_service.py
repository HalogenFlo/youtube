"""Ban biên tập local nhiều vai chạy trên Ollama trước khi gửi cảnh sang Flow."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from src.llm_service import call_ollama
from src.config import OLLAMA_MODEL_DEFAULT
from src.studio_skill_registry import select_studio_skills


def _sanitize_scenes(
    scenes: Any, target_scenes: int, content_mode: str = "knowledge"
) -> List[Dict[str, Any]]:
    cleaned = []
    if not isinstance(scenes, list):
        scenes = [scenes] if scenes else []

    for index, raw_item in enumerate(scenes[:max(1, target_scenes)], start=1):
        if isinstance(raw_item, dict):
            scene = dict(raw_item)
        elif isinstance(raw_item, str):
            scene = {
                "scene_num": index,
                "narration": raw_item.strip(),
                "video_prompt": f"Scene {index}: distinct cinematic visual action, natural lighting",
            }
        else:
            scene = {
                "scene_num": index,
                "narration": str(raw_item).strip(),
                "video_prompt": f"Scene {index}: distinct cinematic visual action",
            }

        narration = str(scene.get("narration", "")).strip()
        narration_vi = str(scene.get("narration_vi", "")).strip()
        chinese_text = str(scene.get("chinese_text", "")).strip()
        pinyin = str(scene.get("pinyin", "")).strip()
        usage_vi = str(scene.get("usage_vi", "")).strip()
        if content_mode == "chinese_teaching_vi":
            narration_vi = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+', '', narration_vi).strip(" ,;:-_")
            usage_vi = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+', '', usage_vi).strip(" ,;:-_")
            narration = " ".join(part for part in [
                narration_vi, chinese_text, usage_vi
            ] if part).strip()
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
        cleaned_scene = {"scene_num": index, "narration": narration, "video_prompt": visual}
        if content_mode == "chinese_teaching_vi":
            cleaned_scene.update({
                "narration_vi": narration_vi,
                "chinese_text": chinese_text,
                "pinyin": pinyin,
                "usage_vi": usage_vi,
            })
        cleaned.append(cleaned_scene)
    return cleaned


def run_studio_editorial_pipeline(
    topic: str,
    script_data: Dict[str, Any],
    target_scenes: int,
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT,
    content_mode: str = "knowledge",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Một vòng bàn biên tập: fact-check, hook, clarity, visual continuity, policy."""
    original_scenes = _sanitize_scenes(script_data.get("scenes", []), target_scenes, content_mode)
    selected = select_studio_skills(topic)
    selected_ids = [item["id"] for item in selected]
    selected_names = [item["name"] for item in selected]

    chinese_rule = (
        " Với chế độ dạy tiếng Trung, bắt buộc giữ đủ narration_vi, chinese_text, pinyin, usage_vi; "
        "kiểm tra chữ Hán giản thể, thanh điệu pinyin và nghĩa tiếng Việt khớp nhau."
        if content_mode == "chinese_teaching_vi" else ""
    )
    system_prompt = (
        "Bạn là ban biên tập studio video ngắn gồm: nghiên cứu viên, kiểm chứng, biên kịch, "
        "biên tập giữ chân, đạo diễn hình ảnh và kiểm duyệt YouTube/TikTok. "
        "Hãy sửa trực tiếp kịch bản, không chỉ nhận xét. Chỉ trả JSON hợp lệ gồm scenes và report. "
        "Giữ ĐÚNG số cảnh yêu cầu. Cảnh 1 phải đi thẳng vào giá trị/hook; các cảnh giữa giải thích cụ thể; "
        "cảnh cuối kết luận. Kiến thức/toán phải chính xác. Không tạo tuyên bố chưa kiểm chứng. "
        "BẮT BUỘC: Giữ mạch truyện liền mạch (narrative_flow_coherence), các cảnh phải kết nối bằng liên từ bắc cầu tự nhiên, không ngắt quãng hay chắp vá. "
        "video_prompt phải bằng tiếng Anh và không được yêu cầu hiển thị chữ, số, công thức, biển hiệu hay phụ đề. "
        "report gồm scores (factual_accuracy, hook_strength, clarity, visual_continuity, policy_safety; 0-100), "
        f"issues_fixed, remaining_warnings và approved.{chinese_rule}"
    )
    prompt = (
        f"Chủ đề: {topic}\nNgôn ngữ lời thoại: {language}\nSố cảnh bắt buộc: {target_scenes}\n"
        f"Các kỹ năng được registry chọn: {', '.join(selected_names)}\n"
        f"Kịch bản nháp:\n{json.dumps({'scenes': original_scenes}, ensure_ascii=False)}"
    )
    success, edited = call_ollama(prompt, system_prompt, model)
    if success and isinstance(edited, dict) and isinstance(edited.get("scenes"), list):
        edited_scenes = _sanitize_scenes(edited["scenes"], target_scenes, content_mode)
        chinese_fields_ok = content_mode != "chinese_teaching_vi" or all(
            scene.get("narration_vi") and scene.get("chinese_text") and scene.get("pinyin") and scene.get("usage_vi")
            for scene in edited_scenes
        )
        scenes = edited_scenes if len(edited_scenes) == target_scenes and chinese_fields_ok else original_scenes
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
