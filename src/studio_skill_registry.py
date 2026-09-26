"""Registry kỹ năng biên tập; chọn theo vai trò và học từ kết quả job thực tế."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from src.config import TEMP_DIR


SCORE_PATH = Path(TEMP_DIR) / "studio_skill_scores.json"
_LOCK = threading.RLock()

SKILL_CATALOG: List[Dict[str, Any]] = [
    {"id": "research_brief_local_v1", "role": "researcher", "name": "Research Brief Local", "base_score": 82, "tags": ["general"]},
    {"id": "education_factcheck_v1", "role": "fact_checker", "name": "Education Fact Checker", "base_score": 90, "tags": ["education", "math", "science"]},
    {"id": "general_factcheck_v1", "role": "fact_checker", "name": "General Fact Checker", "base_score": 84, "tags": ["general"]},
    {"id": "shortform_writer_v2", "role": "scriptwriter", "name": "Short-form Scriptwriter", "base_score": 88, "tags": ["general"]},
    {"id": "retention_editor_v2", "role": "retention_editor", "name": "Retention & Hook Editor", "base_score": 90, "tags": ["shorts", "general"]},
    {"id": "visual_continuity_v2", "role": "visual_director", "name": "Visual Continuity Director", "base_score": 92, "tags": ["general"]},
    {"id": "platform_policy_v2", "role": "policy_editor", "name": "YouTube/TikTok Policy Editor", "base_score": 94, "tags": ["general"]},
    {"id": "render_qa_v1", "role": "qa_editor", "name": "Render & Subtitle QA", "base_score": 93, "tags": ["general"]},
]


def _topic_tags(topic: str) -> set[str]:
    value = topic.lower()
    tags = {"general", "shorts"}
    if any(word in value for word in ["toán", "nhị phân", "cộng", "math", "binary"]):
        tags.update({"education", "math"})
    if any(word in value for word in ["khoa học", "vũ trụ", "science", "physics"]):
        tags.update({"education", "science"})
    return tags


def _load_scores() -> Dict[str, Dict[str, float]]:
    try:
        return json.loads(SCORE_PATH.read_text(encoding="utf-8")) if SCORE_PATH.exists() else {}
    except Exception:
        return {}


def select_studio_skills(topic: str) -> List[Dict[str, Any]]:
    """Chọn kỹ năng có điểm hiệu dụng cao nhất cho từng vai trò."""
    tags = _topic_tags(topic)
    with _LOCK:
        learned = _load_scores()
    candidates: List[Dict[str, Any]] = []
    for item in SKILL_CATALOG:
        overlap = len(tags.intersection(item["tags"]))
        if overlap == 0:
            continue
        stats = learned.get(item["id"], {})
        learned_score = float(stats.get("score", item["base_score"]))
        candidate = dict(item)
        candidate["score"] = round(min(100.0, learned_score + overlap), 1)
        candidate["runs"] = int(stats.get("runs", 0))
        candidates.append(candidate)

    selected = []
    for role in {item["role"] for item in candidates}:
        role_items = [item for item in candidates if item["role"] == role]
        selected.append(max(role_items, key=lambda item: item["score"]))
    return sorted(selected, key=lambda item: item["role"])


def record_skill_outcome(skill_ids: List[str], success: bool) -> None:
    """Cập nhật điểm EMA từ kết quả sản xuất thật."""
    with _LOCK:
        scores = _load_scores()
        outcome = 100.0 if success else 35.0
        for skill_id in skill_ids:
            base = next((item["base_score"] for item in SKILL_CATALOG if item["id"] == skill_id), 75)
            current = scores.get(skill_id, {"score": base, "runs": 0})
            runs = int(current.get("runs", 0)) + 1
            alpha = 0.18
            score = (1 - alpha) * float(current.get("score", base)) + alpha * outcome
            scores[skill_id] = {"score": round(score, 2), "runs": runs}
        SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCORE_PATH.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
