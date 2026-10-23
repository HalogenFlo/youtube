"""Ban biên tập local nhiều vai chạy trên Ollama và bộ quy tắc xác định trước khi gửi cảnh sang Flow."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.llm_service import call_ollama
from src.config import OLLAMA_MODEL_DEFAULT
from src.studio_skill_registry import select_studio_skills
from src.story_contract_models import (
    normalize_architected_scene,
    build_downstream_contracts_report,
    extract_and_repair_json_payload,
)
from src.production_roles import get_all_role_specs


def _sanitize_scenes(
    scenes: Any,
    target_scenes: Optional[int] = None,
    content_mode: str = "knowledge",
    locked_scenes: Optional[Dict[int, Dict[str, Any]]] = None,
    style_preset: str = "",
) -> List[Dict[str, Any]]:
    cleaned = []
    if not isinstance(scenes, list):
        scenes = [scenes] if scenes else []

    scenes_slice = scenes[:max(1, int(target_scenes))] if target_scenes is not None else scenes
    total_hint = len(scenes_slice)
    locked_map = locked_scenes or {}

    for index, raw_item in enumerate(scenes_slice, start=1):
        # Nếu cảnh này đã được người dùng duyệt/khóa thủ công, giữ nguyên không cho tự động ghi đè
        if index in locked_map:
            locked_scene = normalize_architected_scene(locked_map[index], index=index, total_scenes_hint=total_hint)
            locked_scene["user_locked"] = True
            cleaned.append(locked_scene)
            continue

        arch_scene = normalize_architected_scene(raw_item, index=index, total_scenes_hint=total_hint)
        scene = arch_scene.to_dict() if hasattr(arch_scene, "to_dict") else dict(arch_scene)

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
        visual = re.sub(
            r"No readable text,? numbers,? formulas,? captions,? logos,? signs,? or watermarks in the image\.?”?",
            "",
            visual,
            flags=re.IGNORECASE,
        ).strip()
        forbidden_visual_pattern = re.compile(
            r"formula|equation|write|writing|written|whiteboard|chalkboard|caption|subtitle",
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
        cinematic_3d = "3d" in style_preset.lower() and "no 3d" not in style_preset.lower()
        visual = visual if cinematic_3d else re.sub(
            r"\b(3d|cgi|photorealistic|claymation|realistic 3d|3d render|unreal engine|octane render)\b",
            "2D animation, flat 2d cartoon",
            visual,
            flags=re.IGNORECASE,
        )
        no_text_rule = " Strictly 2D animation, flat cartoon, cel-shaded vector art, strictly no 3d. No readable text, numbers, formulas, captions, logos, signs, or watermarks in the image."
        if cinematic_3d:
            no_text_rule = f" {style_preset}. No readable text or watermarks."
        if no_text_rule.strip().lower() not in visual.lower():
            visual = f"{visual}{no_text_rule}".strip()

        scene["narration"] = narration
        scene["video_prompt"] = visual
        scene["visual_prompt"] = visual
        if isinstance(scene.get("image_contract"), dict):
            scene["image_contract"]["video_prompt"] = visual
        if content_mode == "chinese_teaching_vi":
            scene.update({
                "narration_vi": narration_vi,
                "chinese_text": chinese_text,
                "pinyin": pinyin,
                "usage_vi": usage_vi,
            })
        cleaned.append(scene)
    return cleaned


def run_studio_editorial_pipeline(
    topic: str,
    script_data: Dict[str, Any],
    target_scenes: Optional[int] = None,
    language: str = "vi",
    model: str = OLLAMA_MODEL_DEFAULT,
    content_mode: str = "knowledge",
    locked_scenes: Optional[Dict[int, Dict[str, Any]]] = None,
    max_schema_retries: int = 2,
    style_preset: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Vòng bàn biên tập trước sản xuất (Pre-Production Editorial Review):
    Thực thi phối hợp Nghiên cứu, Kiểm chứng, Biên kịch, Biên tập nội dung, Đạo diễn hình ảnh.
    Lưu ý quan trọng: Điểm số ở bước này là `editorial_plan_score` (đánh giá kịch bản trước sản xuất),
    TUYỆT ĐỐI KHÔNG phải kết luận QA của video đã render!
    """
    original_scenes = _sanitize_scenes(
        script_data.get("scenes", []) if isinstance(script_data, dict) else [],
        target_scenes,
        content_mode,
        locked_scenes=locked_scenes,
        style_preset=style_preset,
    )
    selected = select_studio_skills(topic)
    selected_ids = [item["id"] for item in selected]
    selected_names = [item["name"] for item in selected]

    chinese_rule = (
        " Với chế độ dạy tiếng Trung, bắt buộc giữ đủ narration_vi, chinese_text, pinyin, usage_vi; "
        "kiểm tra chữ Hán giản thể, thanh điệu pinyin và nghĩa tiếng Việt khớp nhau."
        if content_mode == "chinese_teaching_vi" else ""
    )
    scene_rule_system = (
        f"Giữ ĐÚNG {target_scenes} cảnh yêu cầu."
        if target_scenes is not None
        else f"Giữ trọn vẹn số cảnh tự nhiên theo mạch cốt truyện (gồm {len(original_scenes)} cảnh)."
    )
    system_prompt = (
        "Bạn là ban biên tập studio video ngắn gồm: nghiên cứu viên, kiểm chứng, biên kịch, "
        "biên tập giữ chân, đạo diễn hình ảnh và kiểm duyệt YouTube/TikTok. "
        "Hãy sửa trực tiếp kịch bản, không chỉ nhận xét. Chỉ trả JSON hợp lệ gồm scenes và report. "
        f"{scene_rule_system} Cảnh 1 phải đi thẳng vào giá trị/hook; các cảnh giữa giải thích cụ thể; "
        "cảnh cuối kết luận. Kiến thức/toán phải chính xác. Không tạo tuyên bố chưa kiểm chứng. "
        "BẮT BUỘC: Kiểm tra nhân quả xuyên cảnh: hành động cảnh trước tạo tình huống cảnh sau; "
        "giữ nhân vật, địa điểm và trạng thái đồ vật nhất quán. Mỗi cảnh phải thêm một bước tiến mới. "
        "Cắt ý lặp, mở bài lặp và triết lý chung chung. Không chữa đứt mạch bằng cách chỉ chèn liên từ. "
        "Kết thúc phải giải quyết câu hỏi hoặc mục tiêu đã đặt ở đầu. Giữ cause, consequence, state_before, state_after nếu có. "
        "video_prompt phải bằng tiếng Anh và không được yêu cầu hiển thị chữ, số, công thức, biển hiệu hay phụ đề. "
        "report gồm scores (factual_accuracy, hook_strength, clarity, visual_continuity, policy_safety; 0-100), "
        f"issues_fixed, remaining_warnings và approved.{chinese_rule}"
    )
    scene_rule_user = (
        f"Số cảnh bắt buộc: {target_scenes}\n"
        if target_scenes is not None
        else f"Số cảnh: Tự nhiên theo cốt truyện ({len(original_scenes)} phân cảnh)\n"
    )
    prompt = (
        f"Chủ đề: {topic}\nNgôn ngữ lời thoại: {language}\n{scene_rule_user}"
        f"Các kỹ năng được registry chọn: {', '.join(selected_names)}\n"
        f"Kịch bản nháp:\n{json.dumps({'scenes': original_scenes}, ensure_ascii=False)}"
    )

    edited = None
    success = False
    for attempt in range(max(1, int(max_schema_retries))):
        ok_call, raw_resp = call_ollama(prompt, system_prompt, model)
        if not ok_call:
            break
        ok_json, parsed_obj, _ = extract_and_repair_json_payload(raw_resp)
        if ok_json and isinstance(parsed_obj, dict) and isinstance(parsed_obj.get("scenes"), list) and parsed_obj["scenes"]:
            edited = parsed_obj
            success = True
            break

    if success and isinstance(edited, dict) and isinstance(edited.get("scenes"), list):
        edited_scenes = _sanitize_scenes(
            edited["scenes"], target_scenes, content_mode, locked_scenes=locked_scenes, style_preset=style_preset
        )
        chinese_fields_ok = content_mode != "chinese_teaching_vi" or all(
            scene.get("narration_vi") and scene.get("chinese_text") and scene.get("pinyin") and scene.get("usage_vi")
            for scene in edited_scenes
        )
        scenes_len_ok = (len(edited_scenes) == target_scenes) if target_scenes is not None else (len(edited_scenes) >= 1)
        narration_ok = all(str(scene.get("narration") or "").strip() for scene in edited_scenes)
        accepted_edit = scenes_len_ok and chinese_fields_ok and narration_ok
        scenes = edited_scenes if accepted_edit else original_scenes
        raw_report = edited.get("report", {}) if isinstance(edited.get("report"), dict) else {}
        llm_responded = accepted_edit
        if not accepted_edit:
            raw_report = dict(raw_report, approved=False, remaining_warnings=[
                "Bản biên tập thiếu lời thoại hoặc sai cấu trúc; giữ bản nháp gốc."
            ])
    else:
        scenes = original_scenes
        llm_responded = False
        raw_report = {
            "scores": {
                "factual_accuracy": 70,
                "hook_strength": 72,
                "clarity": 75,
                "visual_continuity": 78,
                "policy_safety": 80,
            },
            "issues_fixed": ["Áp dụng bộ lọc cấu trúc xác định, khóa nhân vật CH01 2D và quy tắc không chữ trong hình"],
            "remaining_warnings": ["Ollama editorial pass không phản hồi; dùng bản nháp đã qua chuẩn hóa quy tắc tĩnh"],
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
    if target_scenes is not None and len(scenes) != target_scenes:
        warnings.append(f"Số cảnh thực tế {len(scenes)} khác mục tiêu {target_scenes}")

    contracts_report = build_downstream_contracts_report(scenes)

    report = {
        "mode": "local_multi_role_studio",
        "evaluation_stage": "pre_production_script_review",
        "is_rendered_video_qa": False,
        "llm_editorial_verified": llm_responded,
        "selected_skills": selected,
        "selected_skill_ids": selected_ids,
        "roles_catalog": get_all_role_specs(),
        "scores": normalized_scores,
        "overall_score": overall,
        "issues_fixed": raw_report.get("issues_fixed", []),
        "remaining_warnings": warnings,
        "approved": bool(raw_report.get("approved", overall >= 78)) and overall >= 70,
        "source_grounding": "user_prompt_and_local_model",
        "downstream_contracts": contracts_report,
    }
    return scenes, report
