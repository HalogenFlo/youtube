"""Registry kỹ năng biên tập & sản xuất 11 vai trò; chọn theo chủ đề và học từ kết quả job thực tế."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from src.config import TEMP_DIR


SCORE_PATH = Path(TEMP_DIR) / "studio_skill_scores.json"
_LOCK = threading.RLock()

# Danh mục kỹ năng bao phủ toàn bộ 11 vai trò sản xuất chính thức + các bí danh tương thích ngược
SKILL_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "producer_brief_architect_v2",
        "role": "producer",
        "canonical_role": "producer",
        "name": "Executive Producer & Brief Architect",
        "base_score": 91,
        "tags": ["general", "shorts", "education"],
    },
    {
        "id": "research_brief_local_v1",
        "role": "researcher",
        "canonical_role": "researcher",
        "name": "Research & Source Grounding Specialist",
        "base_score": 86,
        "tags": ["general", "shorts", "education"],
    },
    {
        "id": "shortform_writer_v2",
        "role": "scriptwriter",
        "canonical_role": "scriptwriter",
        "name": "Short-form Hook & Narrative Scriptwriter",
        "base_score": 89,
        "tags": ["general", "shorts"],
    },
    {
        "id": "retention_editor_v2",
        "role": "retention_editor",
        "canonical_role": "content_editor",
        "name": "Content Coherence & Retention Editor",
        "base_score": 90,
        "tags": ["shorts", "general"],
    },
    {
        "id": "storyboard_director_v2",
        "role": "director",
        "canonical_role": "director",
        "name": "Storyboard, Shot List & Pacing Director",
        "base_score": 90,
        "tags": ["general", "shorts"],
    },
    {
        "id": "visual_continuity_v2",
        "role": "visual_director",
        "canonical_role": "visual_director",
        "name": "2D Character & Visual Continuity Director",
        "base_score": 92,
        "tags": ["general", "shorts"],
    },
    {
        "id": "audio_foley_director_v2",
        "role": "audio_director",
        "canonical_role": "audio_director",
        "name": "Voice, Pronunciation & Soundscape Director",
        "base_score": 91,
        "tags": ["general", "shorts", "language"],
    },
    {
        "id": "timeline_video_editor_v2",
        "role": "video_editor",
        "canonical_role": "video_editor",
        "name": "Timeline Sync & Rough Cut Editor",
        "base_score": 92,
        "tags": ["general", "shorts"],
    },
    {
        "id": "education_factcheck_v1",
        "role": "fact_checker",
        "canonical_role": "fact_and_policy_officer",
        "name": "Education Fact Checker",
        "base_score": 90,
        "tags": ["education", "math", "science"],
    },
    {
        "id": "general_factcheck_v1",
        "role": "fact_checker",
        "canonical_role": "fact_and_policy_officer",
        "name": "General Fact Checker",
        "base_score": 84,
        "tags": ["general"],
    },
    {
        "id": "platform_policy_v2",
        "role": "policy_editor",
        "canonical_role": "fact_and_policy_officer",
        "name": "YouTube/TikTok Policy & Rights Officer",
        "base_score": 94,
        "tags": ["general", "shorts"],
    },
    {
        "id": "render_qa_v1",
        "role": "qa_editor",
        "canonical_role": "independent_qa",
        "name": "Independent Post-Render Video QA Inspector",
        "base_score": 93,
        "tags": ["general", "shorts"],
    },
    {
        "id": "publishing_packager_v2",
        "role": "publishing_editor",
        "canonical_role": "publishing_editor",
        "name": "Multi-Platform Publishing & Metadata Editor",
        "base_score": 92,
        "tags": ["general", "shorts"],
    },
]


def _topic_tags(topic: str) -> set[str]:
    value = str(topic or "").lower()
    tags = {"general", "shorts"}
    if any(word in value for word in ["toán", "nhị phân", "cộng", "math", "binary"]):
        tags.update({"education", "math"})
    if any(word in value for word in ["khoa học", "vũ trụ", "science", "physics"]):
        tags.update({"education", "science"})
    if any(word in value for word in ["tiếng trung", "tiếng anh", "từ vựng", "pinyin", "vocab"]):
        tags.update({"education", "language"})
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
    if not isinstance(learned, dict):
        learned = {}
    candidates: List[Dict[str, Any]] = []
    for item in SKILL_CATALOG:
        overlap = len(tags.intersection(item["tags"]))
        if overlap == 0:
            continue
        raw_stats = learned.get(item["id"], {})
        stats = raw_stats if isinstance(raw_stats, dict) else {}
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
    """Cập nhật điểm EMA từ kết quả sản xuất thật (chỉ cộng điểm khi QA thực tế sau render đạt)."""
    with _LOCK:
        scores = _load_scores()
        if not isinstance(scores, dict):
            scores = {}
        outcome = 100.0 if success else 35.0
        for skill_id in (skill_ids or []):
            base = next((item["base_score"] for item in SKILL_CATALOG if item["id"] == skill_id), 75)
            raw_current = scores.get(skill_id)
            current = raw_current if isinstance(raw_current, dict) else {"score": base, "runs": 0}
            runs = int(current.get("runs", 0)) + 1
            alpha = 0.18
            score = (1 - alpha) * float(current.get("score", base)) + alpha * outcome
            scores[skill_id] = {"score": round(score, 2), "runs": runs}
        SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCORE_PATH.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
