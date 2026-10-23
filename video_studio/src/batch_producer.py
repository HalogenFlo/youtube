# Chức năng: Động cơ điều phối sản xuất video AI 15 công đoạn (Production Pipeline & Orchestrator).
# Tích hợp:
# - 11 Vai trò sản xuất (Nhà sản xuất -> Nghiên cứu -> Biên kịch -> Biên tập -> Đạo diễn -> Hình ảnh ->
#   Âm thanh -> Dựng phim -> Kiểm chứng & Chính sách -> QA độc lập sau render -> Biên tập xuất bản).
# - Lưu Checkpoint bền vững theo từng công đoạn, hỗ trợ Resume sau khi khởi động lại.
# - Chống tạo trùng file khi Retry (Idempotent Output & Manifest).
# - Vô hiệu hóa phụ thuộc chính xác (Dependency Invalidation) khi sửa kịch bản, tài sản hoặc metadata.
# - Vòng lặp tự sửa lỗi QA hữu hạn (Bounded QA Revision Loop) và chặn thay thế tài sản lỗi âm thầm.

import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_log(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


from src.config import (
    DEFAULT_FPS,
    DEFAULT_IMAGE_STYLE,
    OUTPUT_DIR,
    TEMP_DIR,
    TTS_VOICE_DEFAULT,
    TTS_VOICE_ZH_DEFAULT,
)
from src.flow_image_service import (
    generate_flow_batch_queue,
    generate_flow_image,
    generate_flow_video,
)
from src.llm_service import generate_script, generate_video_metadata
from src.policy_engine import evaluate_platform_policies
from src.production_roles import (
    build_and_validate_asset_manifest,
    run_content_editor_role,
    run_director_visual_audio_planning_roles,
    run_producer_role,
    run_researcher_role,
)
from src.publishing_package_service import build_platform_publishing_package
from src.story_contract_models import (
    RenderManifest,
    build_downstream_contracts_report,
    compute_file_sha256,
    compute_text_sha256,
    normalize_architected_scene,
    validate_script_schema,
)
from src.studio_editorial_service import run_studio_editorial_pipeline
from src.tts_service import (
    clean_vietnamese_tts_text,
    generate_multivoice_tts,
    generate_scenes_tts_parallel,
    generate_tts,
    get_audio_duration,
)
from src.video_compiler import compile_video_pipeline
from src.html_frame_animator import generate_html_animations_parallel
from src.video_qa_service import probe_media_file, run_rendered_video_qa
from src.voice_clone_service import generate_cloned_tts
from src.whisper_service import get_word_timestamps


# Thứ tự 15 công đoạn chuẩn của xưởng sản xuất
PIPELINE_STAGES_ORDER: List[str] = [
    "brief",
    "researching",
    "scripting",
    "content_review",
    "storyboarding",
    "pre_production_check",
    "generating_assets",
    "tts",
    "rendering",
    "qa_running",
    "needs_revision",
    "policy_and_metadata",
    "ready_for_review",
    "exporting_package",
    "publishing",
]

# Bản đồ phụ thuộc xuôi (Downstream Dependency Graph): khi sửa công đoạn X, các công đoạn nào bị vô hiệu hóa
STAGE_DOWNSTREAM_DEPENDENCIES: Dict[str, List[str]] = {
    "brief": [
        "researching", "scripting", "content_review", "storyboarding",
        "pre_production_check", "generating_assets", "tts", "rendering",
        "qa_running", "policy_and_metadata", "ready_for_review", "exporting_package", "approved",
    ],
    "scripting": [
        "content_review", "storyboarding", "pre_production_check",
        "generating_assets", "tts", "rendering", "qa_running",
        "policy_and_metadata", "ready_for_review", "exporting_package", "approved",
    ],
    "scene_narration": [
        "tts", "rendering", "qa_running", "policy_and_metadata",
        "ready_for_review", "exporting_package", "approved",
    ],
    "scene_visual_prompt": [
        "generating_assets", "rendering", "qa_running",
        "ready_for_review", "exporting_package", "approved",
    ],
    "generating_assets": [
        "rendering", "qa_running", "ready_for_review", "exporting_package", "approved",
    ],
    "tts": [
        "rendering", "qa_running", "ready_for_review", "exporting_package", "approved",
    ],
    "rendering": [
        "qa_running", "ready_for_review", "exporting_package", "approved",
    ],
    "metadata": [
        "policy_and_metadata", "ready_for_review", "exporting_package", "approved",
    ],
}


CHINESE_TEACHING_TOPIC_BANK = [
    "Chào hỏi người mới gặp",
    "Giới thiệu tên và quê quán",
    "Hỏi thăm sức khỏe",
    "Cảm ơn và xin lỗi",
    "Tạm biệt và hẹn gặp lại",
    "Đếm số từ 1 đến 10",
    "Hỏi giờ và nói thời gian",
    "Nói ngày tháng và thứ trong tuần",
    "Gọi món trong nhà hàng",
    "Mua đồ và hỏi giá",
    "Mặc cả khi đi chợ",
    "Hỏi đường và chỉ đường",
    "Đi taxi và nói địa điểm đến",
    "Làm thủ tục tại khách sạn",
    "Giao tiếp tại sân bay",
    "Nói về gia đình",
    "Nói về công việc và nghề nghiệp",
    "Sở thích và hoạt động cuối tuần",
    "Thời tiết hôm nay",
    "Màu sắc và quần áo",
    "Mua thuốc tại hiệu thuốc",
    "Gọi điện thoại và nhắn tin",
    "Mời bạn đi ăn",
    "Khen ngợi và đáp lại lời khen",
    "Từ chối lịch sự",
    "Hỏi mật khẩu Wi-Fi",
    "Giao tiếp trong lớp học",
    "Phỏng vấn xin việc cơ bản",
    "Những câu dùng khi du lịch",
    "Các lỗi phát âm tiếng Trung người Việt hay gặp",
]

KNOWLEDGE_TOPIC_BANK = [
    "Những bí ẩn thú vị về vũ trụ",
    "Vì sao con người cần ngủ",
    "Cách trí nhớ hoạt động",
    "Những hiện tượng kỳ lạ dưới đại dương",
    "Vì sao bầu trời có màu xanh",
    "Cách Internet truyền dữ liệu",
    "Những phát minh thay đổi thế giới",
    "Cơ thể con người tự chữa lành như thế nào",
    "Các loài động vật có khả năng đặc biệt",
    "Những sự thật bất ngờ về Trái Đất",
]

ENGLISH_VOCAB_TOPIC_BANK = [
    "Từ vựng 'A few' (một vài) - Tình huống mượn tiền bạn thân",
    "Từ vựng 'Run out of' (hết sạch) - Tình huống hết tiền cuối tháng",
    "Từ vựng 'Look for' (tìm kiếm) - Tình huống tìm chìa khóa nhà lúc vội",
    "Từ vựng 'Give up' (bỏ cuộc) - Tình huống ngày đầu đi tập gym",
    "Từ vựng 'Show off' (khoe khoang) - Tình huống bạn bè flex đồ hiệu",
    "Từ vựng 'Hang out' (đi chơi) - Tình huống rủ đứa bạn hướng nội ra ngoài",
    "Từ vựng 'Put off' (trì hoãn) - Tình huống nước đến chân mới nhảy",
    "Từ vựng 'Turn down' (từ chối) - Tình huống từ chối lời mời ăn đám cưới",
    "Từ vựng 'Count on' (trông cậy) - Tình huống nhờ bạn gánh team bài tập",
    "Từ vựng 'Break down' (hỏng hóc/suy sụp) - Tình huống xe hỏng giữa đường mưa",
]

STORY_EXPLAINER_TOPIC_BANK = [
    "Hành trình con người thuần hóa lửa thời tiền sử",
    "Cuộc đào tẩu huyền thoại khỏi nhà tù Alcatraz",
    "Bí ẩn chiếc máy tính cổ đại Antikythera dưới đáy biển",
    "Cách người cổ đại vận chuyển đá xây dựng Kim Tự Tháp",
    "Chuyến hải trình đầu tiên vòng quanh thế giới của Magellan",
    "Hành trình một hạt mưa rơi từ mây xuống lòng đại dương",
    "Cuộc giải cứu kỳ diệu đội bóng nhí trong hang Tham Luang",
    "Bí mật bức họa Mona Lisa và nụ cười không tuổi",
]


def build_random_video_topics(count: int, content_mode: str = "knowledge") -> List[str]:
    """Chọn đủ chủ đề ngẫu nhiên theo thể loại video, ưu tiên không lặp trong cùng một lô."""
    if content_mode == "chinese_teaching_vi":
        bank = CHINESE_TEACHING_TOPIC_BANK
    elif content_mode == "english_vocab_story":
        bank = ENGLISH_VOCAB_TOPIC_BANK
    elif content_mode == "story_explainer":
        bank = STORY_EXPLAINER_TOPIC_BANK
    else:
        bank = KNOWLEDGE_TOPIC_BANK

    requested = max(1, int(count))
    picker = random.SystemRandom()
    topics: List[str] = []
    while len(topics) < requested:
        shuffled = list(bank)
        picker.shuffle(shuffled)
        topics.extend(shuffled[:requested - len(topics)])
    return topics


def split_prompt_to_video_topics(main_prompt: str, count: int, language: str = "vi") -> List[str]:
    """
    Tự động chia tách prompt người dùng thành danh sách các chủ đề video liên kết mạch truyện.
    """
    lines = [line.strip() for line in main_prompt.strip().split("\n") if line.strip()]
    if len(lines) > 1:
        topics = lines[:count]
        while len(topics) < count:
            base_topic = lines[len(topics) % len(lines)]
            episode = len(topics) // len(lines) + 1
            suffix = f"Tập {episode}" if language == "vi" else f"Episode {episode}"
            topics.append(f"{base_topic} ({suffix})")
        return topics

    base_topic = lines[0] if lines else main_prompt.strip()
    series_arcs_vi = [
        "Khởi đầu & Bí ẩn bất ngờ",
        "Diễn biến kịch tính & Thử thách đối mặt",
        "Bước ngoặt cao trào & Giải mã sự thật",
        "Hồi kết & Bài học đọng lại",
        "Góc nhìn mở rộng & Tương lai bí ẩn",
    ]
    series_arcs_en = [
        "The Beginning & Intriguing Mystery",
        "Rising Conflict & Crucial Challenges",
        "The Climax & Unveiling the Truth",
        "Resolution & Powerful Takeaways",
        "Extended Outlook & Beyond",
    ]
    arcs = series_arcs_vi if language == "vi" else series_arcs_en

    topics = []
    for i in range(count):
        if count == 1:
            topics.append(base_topic)
        else:
            arc_label = arcs[i % len(arcs)]
            if language == "vi":
                topics.append(f"{base_topic} (Phần {i+1} - Tập {i+1}: {arc_label})")
            else:
                topics.append(f"{base_topic} (Part {i+1} - Episode {i+1}: {arc_label})")
    return topics


def build_exact_tts_timestamps(scenes: List[Any]) -> List[Dict[str, Any]]:
    """
    Tạo timestamp từ lời thoại nguồn có trọng số theo độ dài từ và dấu câu ngắt nghỉ,
    tránh lệch phụ đề ở các câu dài hoặc chế độ dạy tiếng Trung.
    """
    words_out: List[Dict[str, Any]] = []
    offset = 0.0
    for scene in scenes:
        if isinstance(scene, dict):
            narration_words = str(scene.get("narration", "")).split()
            duration = max(0.1, float(scene.get("audio_duration", 5.0)))
        else:
            narration_words = str(scene).split()
            duration = 5.0

        timings = scene.get("tts_segment_timings") if isinstance(scene, dict) else None
        if (isinstance(timings, list) and timings
                and " ".join(str(s.get("text") or "") for s in timings).split() == narration_words):
            scene_cues = []
            for segment in timings:
                start = float(segment.get("start", 0.))
                length = max(.01, float(segment.get("end", start)) - start)
                local = build_exact_tts_timestamps([{"narration": segment["text"], "audio_duration": length}])
                scene_cues.extend(dict(cue, start=round(cue["start"] + offset + start, 3),
                                       end=round(cue["end"] + offset + start, 3)) for cue in local)
            words_out.extend(scene_cues)
            scene["subtitle_cues"] = scene_cues
            scene["timeline_range"] = [round(offset, 3), round(offset + duration, 3)]
            offset += duration
            continue

        if narration_words:
            usable_duration = duration * 0.96
            # Tính trọng số từng từ theo số ký tự + điểm dừng dấu câu
            weights = []
            for w in narration_words:
                base_w = max(1.0, float(len(w.strip(".,!?;:"))))
                if w.endswith((".", "!", "?", ";")):
                    base_w += 2.2
                elif w.endswith((",", ":")):
                    base_w += 1.1
                weights.append(base_w)
            total_w = sum(weights) or float(len(narration_words))

            cursor = offset
            scene_cues = []
            for idx, word in enumerate(narration_words):
                w_dur = usable_duration * (weights[idx] / total_w)
                cue = {
                    "word": word,
                    "start": round(cursor, 3),
                    "end": round(cursor + w_dur, 3),
                }
                words_out.append(cue)
                scene_cues.append(cue)
                cursor += w_dur

            if isinstance(scene, dict):
                scene["subtitle_cues"] = scene_cues
                scene["timeline_range"] = [round(offset, 3), round(offset + duration, 3)]
        offset += duration
    return words_out


def normalize_chinese_teaching_scenes(scenes: List[Any]) -> List[Dict[str, Any]]:
    """Chuẩn hóa dữ liệu bài học tiếng Trung thành lời phụ đề hoàn chỉnh cho pipeline."""
    normalized = []
    for index, original in enumerate(scenes, start=1):
        scene = dict(original) if isinstance(original, dict) else {
            "scene_num": index,
            "narration_vi": str(original),
            "chinese_text": "",
            "pinyin": "",
            "usage_vi": "",
        }
        narration_vi = clean_vietnamese_tts_text(str(scene.get("narration_vi", "")).strip())
        chinese_text = str(scene.get("chinese_text", "")).strip()
        pinyin = str(scene.get("pinyin", "")).strip()
        usage_vi = clean_vietnamese_tts_text(str(scene.get("usage_vi", "")).strip())
        scene["scene_num"] = int(scene.get("scene_num", index))
        scene["narration_vi"] = narration_vi
        scene["usage_vi"] = usage_vi
        scene["chinese_text"] = chinese_text
        scene["pinyin"] = pinyin
        scene["narration"] = " ".join(part for part in [
            narration_vi,
            chinese_text,
            pinyin,
            usage_vi,
        ] if part).strip()
        normalized.append(scene)
    return normalized


# ==============================================================================
# QUẢN LÝ CHECKPOINT VÀ VÔ HIỆU HÓA PHỤ THUỘC (CHECKPOINT & DEPENDENCY ENGINE)
# ==============================================================================

def get_job_checkpoint_path(video_work_dir: str) -> Path:
    return Path(video_work_dir) / "checkpoint.json"


def load_job_checkpoint(video_work_dir: str) -> Dict[str, Any]:
    cp_path = get_job_checkpoint_path(video_work_dir)
    if cp_path.exists():
        try:
            data = json.loads(cp_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "version": 1,
        "completed_stages": [],
        "last_completed_stage": None,
        "stage_timings": {},
        "cost_ledger": {
            "cost_type": "estimated_local_and_subscription",
            "estimated_total_usd": 0.0,
            "actual_total_usd": 0.0,
            "items": [],
        },
        "error_history": [],
        "decision_history": [],
        "user_locked_fields": [],
        "user_locked_scenes": {},
        "approved_edits": {},
        "revision_round": 0,
    }


def save_job_checkpoint(video_work_dir: str, checkpoint: Dict[str, Any]) -> None:
    os.makedirs(video_work_dir, exist_ok=True)
    cp_path = get_job_checkpoint_path(video_work_dir)
    tmp_path = cp_path.with_suffix(".json.tmp")
    checkpoint["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    tmp_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, cp_path)


def invalidate_dependent_stages(
    checkpoint: Dict[str, Any],
    modified_target: str,
    scene_num: Optional[int] = None,
    video_work_dir: Optional[str] = None,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Khi sửa kịch bản, tài sản phân cảnh hoặc metadata:
    - Vô hiệu hóa ĐÚNG các công đoạn và kết quả QA/Phê duyệt phụ thuộc ở hạ nguồn.
    - Chỉ xóa cache của phân cảnh bị ảnh hưởng (nếu chỉ định scene_num), bảo toàn các cảnh khác.
    - Ghi lịch sử quyết định vào decision_history.
    """
    affected = STAGE_DOWNSTREAM_DEPENDENCIES.get(modified_target, [])
    completed = list(checkpoint.get("completed_stages", []))
    checkpoint["completed_stages"] = [s for s in completed if s not in affected]

    if "qa_running" in affected:
        checkpoint.pop("qa_report", None)
    if "rendering" in affected:
        checkpoint.pop("render_manifest", None)
    if "policy_and_metadata" in affected:
        checkpoint.pop("policy_report", None)
    if "exporting_package" in affected:
        checkpoint.pop("publishing_package", None)
    if "approved" in affected:
        edits = checkpoint.setdefault("approved_edits", {})
        if isinstance(edits, dict):
            edits["approved_by_user"] = False
            edits["approval_invalidated_reason"] = reason or f"Thay đổi tại {modified_target}"

    # Nếu vô hiệu hóa toàn bộ công đoạn tts hoặc generating_assets (scene_num is None), xóa cache của toàn bộ cảnh chưa khóa
    if scene_num is None and video_work_dir and os.path.exists(video_work_dir):
        for fn in os.listdir(video_work_dir):
            if modified_target == "tts" and (fn.endswith(".mp3") or fn.endswith(".wav") or fn.endswith("_tts.meta.json")):
                try:
                    os.remove(os.path.join(video_work_dir, fn))
                except OSError:
                    pass
            elif modified_target == "generating_assets" and (fn.endswith("_bg.png") or fn.startswith("scene_flow_") or (fn.startswith("scene_") and fn.endswith(".mp4"))):
                try:
                    os.remove(os.path.join(video_work_dir, fn))
                except OSError:
                    pass
    # Nếu sửa riêng 1 cảnh (narration hoặc visual prompt), chỉ xóa file cache của đúng cảnh đó
    if scene_num is not None and video_work_dir and os.path.exists(video_work_dir):
        sc_idx = int(scene_num)
        if modified_target in ("scene_narration", "tts"):
            for ext in (".mp3", ".wav", "_tts.meta.json"):
                f_p = os.path.join(video_work_dir, f"scene_{sc_idx:03d}{ext}")
                if os.path.exists(f_p):
                    try:
                        os.remove(f_p)
                    except OSError:
                        pass
        if modified_target in ("scene_visual_prompt", "generating_assets"):
            for pat in (f"scene_{sc_idx:03d}.mp4", f"scene_{sc_idx:03d}_bg.png", f"scene_flow_{sc_idx}.png"):
                f_p = os.path.join(video_work_dir, pat)
                if os.path.exists(f_p):
                    try:
                        os.remove(f_p)
                    except OSError:
                        pass

    checkpoint.setdefault("decision_history", []).append({
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": "invalidate_dependencies",
        "modified_target": modified_target,
        "scene_num": scene_num,
        "invalidated_stages": affected,
        "reason": reason or f"Cập nhật {modified_target}",
    })
    return checkpoint


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
    target_scenes: Optional[int] = None,
    voice_mode: str = "edge",
    voice_reference_path: str = "",
    voice_consent_verified: bool = True,
    job_key: str = "",
    studio_mode: bool = True,
    content_mode: str = "knowledge",
    chinese_voice: str = TTS_VOICE_ZH_DEFAULT,
    turbo_mode: bool = False,
    flow_workers: int = 4,
    tts_workers: int = 4,
    previous_context: Optional[str] = None,
    max_auto_revisions: int = 2,
    strict_no_fallback: Optional[bool] = None,
    resume_from_checkpoint: bool = True,
    stage_callback: Optional[Callable[[str, float, str], None]] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    is_cancelled_callback: Optional[Callable[[], bool]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Thực thi toàn bộ dây chuyền 15 công đoạn sản xuất 1 video hoàn chỉnh:
    Brief -> Nghiên cứu -> Kịch bản -> Kiểm tra nội dung -> Storyboard -> Kiểm tra trước sản xuất ->
    Tạo tài sản -> TTS -> Dựng bản nháp -> QA video -> Sửa lỗi (nếu cần) -> Kiểm tra chính sách & metadata ->
    Sẵn sàng duyệt -> Xuất gói thành phẩm.
    """
    def _is_cancelled() -> bool:
        return bool(is_cancelled_callback and is_cancelled_callback())

    def notify(pct: float, message: str, stage: str = "running"):
        safe_log(f"   [{video_index}] [{stage}] [{int(pct)}%] {message}")
        if stage_callback:
            try:
                stage_callback(stage, pct, message)
            except Exception:
                pass
        if progress_callback:
            try:
                progress_callback(pct, message)
            except Exception:
                pass

    safe_job_key = "".join(ch for ch in str(job_key) if ch.isalnum() or ch in "-_")
    work_name = f"job_{safe_job_key}" if safe_job_key else f"video_{video_index:02d}"
    video_work_dir = os.path.join(batch_work_dir, work_name)
    os.makedirs(video_work_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    checkpoint = load_job_checkpoint(video_work_dir) if resume_from_checkpoint else load_job_checkpoint(video_work_dir)
    if not resume_from_checkpoint:
        checkpoint["completed_stages"] = []

    version = int(checkpoint.get("version") or 1)
    run_meta: Dict[str, Any] = {
        "topic": topic,
        "video_index": video_index,
        "job_key": safe_job_key,
        "version": version,
        "work_dir": video_work_dir,
    }

    if _is_cancelled():
        return False, "Đã bỏ qua theo yêu cầu người dùng", run_meta

    # Xác định chính sách chống thay thế tài sản lỗi âm thầm:
    # Khi bật studio_mode (mặc định của xưởng), nghiêm cấm thay ảnh lỗi bằng ảnh cảnh khác rồi coi là thành công!
    # Chỉ cho phép self-healing copy ở chế độ legacy (studio_mode=False) khi strict_no_fallback không được bật tường minh.
    effective_strict_no_fallback = (
        bool(strict_no_fallback) if strict_no_fallback is not None else bool(studio_mode)
    )

    stage_timings: Dict[str, float] = checkpoint.setdefault("stage_timings", {})
    completed_stages: List[str] = checkpoint.setdefault("completed_stages", [])
    decision_history: List[Dict[str, Any]] = checkpoint.setdefault("decision_history", [])
    error_history: List[Dict[str, Any]] = checkpoint.setdefault("error_history", [])

    def _record_decision(stage: str, decision: str, detail: str = ""):
        decision_history.append({
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "stage": stage,
            "decision": decision,
            "detail": detail,
        })

    def _record_error(stage: str, err_msg: str):
        error_history.append({
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "stage": stage,
            "error": err_msg,
        })

    # ==========================================================================
    # BƯỚC 1 & 2: NHÀ SẢN XUẤT (BRIEF) & NGHIÊN CỨU (RESEARCHING)
    # ==========================================================================
    t0 = time.time()
    notify(5, f"Khởi tạo ProjectBrief & Nghiên cứu chủ đề: '{topic[:45]}...'", stage="researching")
    try:
        brief = run_producer_role(
            topic=topic,
            project_id=safe_job_key or f"vid_{video_index:02d}",
            language=language,
            orientation=orientation,
            content_mode=content_mode,
            style_preset=style_preset,
            media_mode=media_mode,
            image_engine=image_engine,
            voice_mode=voice_mode,
            voice=voice,
            chinese_voice=chinese_voice,
            voice_reference_path=voice_reference_path,
            voice_consent_verified=voice_consent_verified,
            target_scenes=target_scenes,
            version=version,
        )
        research = run_researcher_role(brief)
    except Exception as exc:
        err = f"Lỗi khởi tạo Brief/Nghiên cứu: {exc}"
        _record_error("researching", err)
        save_job_checkpoint(video_work_dir, checkpoint)
        return False, err, run_meta

    stage_timings["researching"] = round(time.time() - t0, 3)
    checkpoint["brief"] = brief.to_dict()
    checkpoint["research_report"] = research.to_dict()
    checkpoint["cost_ledger"] = {
        "cost_type": brief.cost_type,
        "estimated_total_usd": brief.estimated_cost_usd,
        "actual_total_usd": 0.0,
        "currency": "USD",
        "note": "Ước tính dựa trên số phân cảnh và chế độ phương tiện (Local LLM/Edge-TTS miễn phí; Google Flow tính theo gói).",
    }
    if "researching" not in completed_stages:
        completed_stages.append("researching")
    save_job_checkpoint(video_work_dir, checkpoint)
    run_meta["brief"] = brief.to_dict()
    run_meta["research_report"] = research.to_dict()

    if _is_cancelled():
        return False, "Đã bỏ qua theo yêu cầu người dùng", run_meta

    # ==========================================================================
    # BƯỚC 3 & 4: BIÊN KỊCH (SCRIPTING) & BIÊN TẬP NỘI DUNG (CONTENT REVIEW)
    # ==========================================================================
    t0 = time.time()
    raw_locked_scenes = checkpoint.get("user_locked_scenes", {})
    locked_scenes_map: Dict[int, Dict[str, Any]] = {
        int(k): v for k, v in raw_locked_scenes.items() if isinstance(v, dict)
    } if isinstance(raw_locked_scenes, dict) else {}

    saved_scenes = checkpoint.get("scenes")
    saved_script_valid = bool(isinstance(saved_scenes, list) and saved_scenes) and validate_script_schema(
        {"scenes": saved_scenes}, content_mode=content_mode, strict_dict_scenes=False
    )[0]
    if "scripting" in completed_stages and saved_script_valid:
        scenes = checkpoint["scenes"]
        editorial_report = checkpoint.get("editorial_report", {"mode": "checkpoint_resumed", "approved": True})
        notify(18, f"Khôi phục kịch bản đã lưu từ checkpoint ({len(scenes)} phân cảnh).", stage="scripting")
    else:
        notify(10, f"Đang yêu cầu AI biên soạn kịch bản cho chủ đề: '{topic[:40]}...'", stage="scripting")
        script_data = None
        last_schema_err = ""
        for attempt in range(1, 3):
            success, raw_script = generate_script(
                topic=topic,
                style_preset=style_preset,
                language=language,
                target_scenes=target_scenes,
                content_mode=content_mode,
                previous_context=previous_context,
            )
            if not success:
                last_schema_err = str(raw_script)
                continue
            # Kiểm định Schema tại ranh giới công đoạn Scripting (cho phép chuẩn hóa cả str/dict)
            ok_schema, _, schema_errs = validate_script_schema(
                raw_script, content_mode=content_mode, strict_dict_scenes=False
            )
            if ok_schema:
                script_data = raw_script
                break
            last_schema_err = "; ".join(schema_errs)

        if not script_data or "scenes" not in script_data or not script_data["scenes"]:
            err = f"Lỗi sinh kịch bản cho video {video_index}: {last_schema_err or script_data}"
            _record_error("scripting", err)
            save_job_checkpoint(video_work_dir, checkpoint)
            notify(10, err, stage="failed")
            return False, err, run_meta

        if studio_mode:
            notify(15, "Ban biên tập local đang kiểm chứng, sửa hook và đạo diễn hình ảnh...", stage="scripting")
            scenes, editorial_report = run_studio_editorial_pipeline(
                topic=topic,
                script_data=script_data,
                target_scenes=int(target_scenes) if target_scenes is not None else None,
                language=language,
                content_mode=content_mode,
                locked_scenes=locked_scenes_map,
                style_preset=style_preset,
            )
        else:
            scenes = script_data["scenes"] if target_scenes is None else script_data["scenes"][:max(1, int(target_scenes))]
            if content_mode == "chinese_teaching_vi":
                scenes = normalize_chinese_teaching_scenes(scenes)
            editorial_report = {"mode": "single_writer", "approved": True, "selected_skill_ids": []}

        # Bảo toàn các cảnh đã được user khóa nếu studio_mode=False
        normalized_scenes: List[Dict[str, Any]] = []
        for idx, sc in enumerate(scenes, start=1):
            if idx in locked_scenes_map:
                norm_sc = normalize_architected_scene(locked_scenes_map[idx], index=idx, total_scenes_hint=len(scenes))
                norm_sc["user_locked"] = True
            else:
                norm_sc = normalize_architected_scene(sc, index=idx, total_scenes_hint=len(scenes))
            normalized_scenes.append(norm_sc)
        scenes = normalized_scenes

        if "scripting" not in completed_stages:
            completed_stages.append("scripting")

    run_meta["editorial_report"] = editorial_report if isinstance(editorial_report, dict) else {}
    script_contract = run_content_editor_role(
        brief=brief,
        research=research,
        scenes=scenes,
        editorial_report=run_meta["editorial_report"],
        user_locked_scenes=list(locked_scenes_map.keys()),
    )
    scenes = script_contract.scenes
    num_scenes = len(scenes)
    research = run_researcher_role(brief, existing_scenes=scenes)
    run_meta["research_report"] = research.to_dict()
    run_meta["script_contract"] = script_contract.to_dict()
    downstream_report = build_downstream_contracts_report(scenes)
    run_meta["downstream_contracts"] = downstream_report

    stage_timings["scripting"] = round(time.time() - t0, 3)
    checkpoint["scenes"] = scenes
    checkpoint["script"] = script_contract.to_dict()
    checkpoint["editorial_report"] = run_meta["editorial_report"]
    checkpoint["research_report"] = research.to_dict()
    if "content_review" not in completed_stages:
        completed_stages.append("content_review")
    save_job_checkpoint(video_work_dir, checkpoint)

    notify(20, f"Đã lập kịch bản gồm {num_scenes} phân cảnh độc lập (chuẩn hóa 5 hợp đồng hạ nguồn).", stage="storyboarding")
    if _is_cancelled():
        return False, "Đã bỏ qua theo yêu cầu người dùng", run_meta

    # ==========================================================================
    # BƯỚC 5 & 6: ĐẠO DIỄN STORYBOARD & KIỂM TRA TRƯỚC SẢN XUẤT
    # ==========================================================================
    t0 = time.time()
    scene_plan = run_director_visual_audio_planning_roles(brief=brief, script=script_contract)
    stage_timings["storyboarding"] = round(time.time() - t0, 3)
    checkpoint["scene_plan"] = scene_plan.to_dict()
    for st_name in ("storyboarding", "pre_production_check"):
        if st_name not in completed_stages:
            completed_stages.append(st_name)
    save_job_checkpoint(video_work_dir, checkpoint)
    run_meta["scene_plan"] = scene_plan.to_dict()

    # ==========================================================================
    # HÀM CON THỰC THI TTS, TẠO TÀI SẢN VÀ RENDER (DÙNG CHO CẢ LẦN CHẠY ĐẦU & VÒNG TỰ SỬA QA)
    # ==========================================================================
    def _execute_tts_stage(target_scene_indices: Optional[List[int]] = None) -> Tuple[bool, str]:
        t_tts = time.time()
        if turbo_mode and target_scene_indices is None:
            notify(25, f"Đang sinh giọng đọc AI (TTS) song song ({tts_workers} workers) cho {num_scenes} phân cảnh...", stage="tts")

            def _tts_parallel_cb(cur: int, tot: int, msg: str):
                notify(25 + (cur / max(1, tot)) * 15, msg, stage="tts")

            audio_ok, audio_result = generate_scenes_tts_parallel(
                scenes=scenes,
                video_work_dir=video_work_dir,
                voice=voice,
                voice_mode=voice_mode,
                content_mode=content_mode,
                chinese_voice=chinese_voice,
                voice_reference_path=voice_reference_path,
                max_workers=tts_workers,
                progress_callback=_tts_parallel_cb,
                language=language,
            )
            if not audio_ok:
                return False, f"Lỗi giọng đọc song song: {audio_result}"
            notify(40, f"Đã sinh giọng đọc AI song song cho toàn bộ {num_scenes} phân cảnh.", stage="tts")
        else:
            notify(25, "Đang sinh giọng đọc AI (TTS) cho các phân cảnh...", stage="tts")
            for i, sc in enumerate(scenes):
                if _is_cancelled():
                    return False, "Đã bỏ qua theo yêu cầu người dùng"
                sc_num = sc.get("scene_num", i + 1)
                if target_scene_indices is not None and sc_num not in target_scene_indices:
                    continue

                audio_ext = ".wav" if voice_mode == "clone_local" and content_mode != "chinese_teaching_vi" else ".mp3"
                audio_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}{audio_ext}")
                meta_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}_tts.meta.json")

                cache_ok = (
                    target_scene_indices is None
                    and os.path.exists(audio_file)
                    and os.path.getsize(audio_file) > 1000
                )
                if cache_ok and os.path.exists(meta_file):
                    try:
                        saved_m = json.loads(Path(meta_file).read_text(encoding="utf-8"))
                        if saved_m.get("text") and saved_m.get("text") != str(sc.get("narration", "")):
                            cache_ok = False
                    except Exception:
                        pass

                if cache_ok:
                    safe_log(f"[✓] Tái sử dụng file âm thanh có sẵn cho cảnh {sc_num}: {audio_file}")
                    sc["audio_path"] = audio_file
                    sc["audio_duration"] = get_audio_duration(audio_file)
                    notify(25 + (i + 1) / num_scenes * 15, f"Đã có giọng đọc phân cảnh {sc_num}/{num_scenes}", stage="tts")
                    continue

                if content_mode == "chinese_teaching_vi":
                    clean_narr_vi = clean_vietnamese_tts_text(str(sc.get("narration_vi", "")))
                    clean_use_vi = clean_vietnamese_tts_text(str(sc.get("usage_vi", "")))
                    chinese_text = str(sc.get("chinese_text", "")).strip()
                    audio_ok, audio_result = generate_multivoice_tts(
                        [
                            (clean_narr_vi, voice, "+0%"),
                            (chinese_text, chinese_voice, "-5%"),
                            (chinese_text, chinese_voice, "-18%"),
                            (clean_use_vi, voice, "+0%"),
                        ],
                        audio_file,
                    )
                elif voice_mode == "clone_local":
                    audio_ok, audio_result = generate_cloned_tts(
                        text=sc["narration"],
                        output_path=audio_file,
                        reference_audio=voice_reference_path,
                        language=language,
                    )
                else:
                    audio_ok, audio_result = generate_tts(
                        text=sc["narration"], output_path=audio_file, voice=voice, rate="+0%"
                    )
                if not audio_ok or not os.path.exists(audio_file):
                    return False, f"Lỗi giọng đọc cảnh {sc_num}: {audio_result}"
                sc["audio_path"] = audio_file
                sc["audio_duration"] = get_audio_duration(audio_file)
                try:
                    Path(meta_file).write_text(
                        json.dumps({"text": sc.get("narration", ""), "voice": voice, "duration": sc["audio_duration"]}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                notify(25 + (i + 1) / num_scenes * 15, f"Đã sinh giọng đọc phân cảnh {sc_num}/{num_scenes}", stage="tts")

        stage_timings["tts"] = round(stage_timings.get("tts", 0.0) + (time.time() - t_tts), 3)
        return True, ""

    def _execute_visual_assets_stage(target_scene_indices: Optional[List[int]] = None) -> Tuple[bool, str]:
        t_vis = time.time()
        if (image_engine in ("html_frames", "cartoon_2d") or media_mode in ("html_animation", "cartoon_2d", "html_frames")) and target_scene_indices is None:
            use_chromium = (image_engine == "html_frames" or media_mode in ("html_animation", "html_frames"))
            engine_label = "HTML5 Canvas Multi-Frame (Chromium + FFmpeg)" if use_chromium else "Hoạt hình 2D Vector Đa luồng"
            notify(45, f"Bắt đầu dựng hoạt hình nhiều frame ({engine_label}, {flow_workers} luồng) cho {num_scenes} phân cảnh...", stage="generating_assets")

            def _html_anim_cb(cur: int, tot: int, msg: str):
                notify(45 + (cur / max(1, tot)) * 30, msg, stage="generating_assets")

            ok_anim, _, err_anim = generate_html_animations_parallel(
                scenes=scenes,
                work_dir=video_work_dir,
                orientation=orientation,
                max_workers=flow_workers,
                use_headless_chromium=use_chromium,
                cancel_check=_is_cancelled,
                progress_callback=_html_anim_cb,
            )
            if not ok_anim:
                return False, f"Lỗi dựng hoạt hình đa frame: {err_anim}"
            stage_timings["generating_assets"] = round(stage_timings.get("generating_assets", 0.0) + (time.time() - t_vis), 3)
            notify(75, f"Đã hoàn thành dựng hoạt hình nhiều frame cho toàn bộ {num_scenes} phân cảnh.", stage="generating_assets")
            return True, ""
        elif turbo_mode and image_engine == "flow" and media_mode == "flow_image" and target_scene_indices is None:
            notify(45, f"Bắt đầu sinh bối cảnh hình ảnh AI dạng Turbo Batch ({flow_workers} workers) cho {num_scenes} phân cảnh...", stage="generating_assets")

            def _flow_batch_cb(cur: int, *args: Any):
                tot = args[0] if len(args) >= 2 else num_scenes
                msg = str(args[-1]) if args else ""
                notify(45 + (cur / max(1, tot)) * 30, msg, stage="generating_assets")

            flow_batch_ok, _, task_reports = generate_flow_batch_queue(
                scenes=scenes,
                temp_dir=video_work_dir,
                output_dir=video_work_dir,
                max_workers=flow_workers,
                orientation=orientation,
                style_preset=style_preset,
                enable_self_healing=not effective_strict_no_fallback,
                status_callback=_flow_batch_cb,
                is_cancelled_callback=is_cancelled_callback,
            )
            if isinstance(task_reports, list):
                for sc_item, rep in zip(scenes, task_reports):
                    if isinstance(sc_item, dict) and isinstance(rep, dict) and rep.get("status") == "fallback":
                        sc_item["is_fallback_asset"] = True
            if not flow_batch_ok:
                if _is_cancelled():
                    return False, "Đã bỏ qua theo yêu cầu người dùng"
                return False, "Lỗi sinh ảnh Turbo Batch: Không thể tạo đủ ảnh hợp lệ cho các phân cảnh."
            notify(75, f"Đã hoàn thành sinh bối cảnh Turbo Batch cho toàn bộ {num_scenes} phân cảnh.", stage="generating_assets")
        else:
            notify(45, "Bắt đầu sinh bối cảnh hình ảnh AI riêng biệt cho từng phân cảnh...", stage="generating_assets")
            for i, sc in enumerate(scenes):
                if _is_cancelled():
                    return False, "Đã bỏ qua theo yêu cầu người dùng"
                sc_num = sc.get("scene_num", i + 1)
                if target_scene_indices is not None and sc_num not in target_scene_indices:
                    continue

                prompt = sc.get("video_prompt") or sc.get("narration") or "Stickman cinematic scene"
                step_pct = 45 + (i / num_scenes) * 30
                notify(step_pct, f"Đang tạo bối cảnh phân cảnh {sc_num}/{num_scenes}...", stage="generating_assets")

                vid_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}.mp4")
                img_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}_bg.png")
                prompt_meta_file = os.path.join(video_work_dir, f"scene_{sc_num:03d}_visual.meta.json")

                prompt_changed = False
                if os.path.exists(prompt_meta_file):
                    try:
                        saved_pm = json.loads(Path(prompt_meta_file).read_text(encoding="utf-8"))
                        if saved_pm.get("prompt") and saved_pm.get("prompt") != prompt:
                            prompt_changed = True
                    except Exception:
                        pass

                if target_scene_indices is None and not prompt_changed:
                    if os.path.exists(vid_file) and os.path.getsize(vid_file) > 10000 and (media_mode != "flow_video" or sc.get("cinematic_shots")):
                        safe_log(f"[✓] Tái sử dụng clip video có sẵn cho cảnh {sc_num}: {vid_file}")
                        sc["video_path"] = vid_file
                        sc["use_video_ai"] = True
                        continue

                    if media_mode != "flow_video" and os.path.exists(img_file) and os.path.getsize(img_file) > 5000 and not sc.get("is_fallback_asset"):
                        safe_log(f"[✓] Tái sử dụng ảnh có sẵn cho cảnh {sc_num}: {img_file}")
                        sc["image_path"] = img_file
                        sc["use_video_ai"] = False
                        continue

                media_ok = False
                try_flow_video = image_engine == "flow" and (
                    media_mode == "flow_video" or (media_mode == "hybrid" and i == 0)
                )

                if try_flow_video:
                    max_vid_attempts = 2
                    res_vid = ""
                    for vid_attempt in range(1, max_vid_attempts + 1):
                        if _is_cancelled():
                            return False, "Đã bỏ qua theo yêu cầu người dùng"

                        retry_note = f" (lần thử {vid_attempt}/{max_vid_attempts})" if vid_attempt > 1 else ""
                        notify(step_pct, f"Đang kết nối Google Flow sinh video cho cảnh {sc_num}/{num_scenes}{retry_note}...", stage="generating_assets")

                        def flow_status_cb(sec: int, text: str):
                            notify(step_pct, f"Cảnh {sc_num}/{num_scenes}{retry_note}: {text} ({sec}s)", stage="generating_assets")

                        from src.cinematic_video import generate_cinematic_scene
                        ok_vid, res_vid = generate_cinematic_scene(
                            scene=sc,
                            previous=scenes[i-1] if i else None,
                            generate_clip=generate_flow_video,
                            output_path=vid_file,
                            orientation=orientation,
                            style_preset=style_preset,
                            status_callback=flow_status_cb,
                            is_cancelled_callback=is_cancelled_callback,
                        )
                        if _is_cancelled():
                            return False, "Đã bỏ qua theo yêu cầu người dùng"
                        if ok_vid and os.path.exists(vid_file) and os.path.getsize(vid_file) > 0:
                            sc["video_path"] = vid_file
                            sc["use_video_ai"] = True
                            sc["is_fallback_asset"] = False
                            media_ok = True
                            break
                        if vid_attempt < max_vid_attempts:
                            time.sleep(3)

                    if not media_ok:
                        err_msg = f"Lỗi sinh video Flow cảnh {sc_num}: {res_vid}. Hệ thống dừng theo yêu cầu không fallback sang ảnh."
                        notify(step_pct, err_msg, stage="failed")
                        return False, err_msg

                elif image_engine == "flow":
                    notify(step_pct, f"Đang tạo ảnh Flow cho cảnh {sc_num}/{num_scenes}...", stage="generating_assets")
                    res_img = ""
                    for flow_attempt in range(1, 4):
                        if _is_cancelled():
                            return False, "Đã bỏ qua theo yêu cầu người dùng"
                        ok_img, res_img = generate_flow_image(
                            prompt=prompt,
                            output_path=img_file,
                            orientation=orientation,
                            style_preset=style_preset,
                            is_cancelled_callback=is_cancelled_callback,
                        )
                        if ok_img and os.path.exists(img_file) and os.path.getsize(img_file) > 0:
                            sc["image_path"] = img_file
                            sc["use_video_ai"] = False
                            sc["is_fallback_asset"] = False
                            media_ok = True
                            break
                        if flow_attempt < 3:
                            wait_seconds = 15 * flow_attempt
                            notify(step_pct, f"Flow chưa trả ảnh cảnh {sc_num}; tự thử lại {flow_attempt + 1}/3 sau {wait_seconds} giây...", stage="generating_assets")
                            for _ in range(wait_seconds):
                                if _is_cancelled():
                                    return False, "Đã bỏ qua theo yêu cầu người dùng"
                                time.sleep(1.0)

                    if not media_ok:
                        if not effective_strict_no_fallback:
                            # Chế độ tương thích ngược cho bài kiểm thử legacy (studio_mode=False):
                            # Ghi nhận rõ cờ is_fallback_asset=True để không âm thầm gian lận trạng thái.
                            fallback_source = None
                            for prev_sc in reversed(scenes[:i]):
                                prev_img = prev_sc.get("image_path")
                                if prev_img and os.path.exists(prev_img) and os.path.getsize(prev_img) > 0:
                                    fallback_source = prev_img
                                    break
                            if fallback_source:
                                shutil.copy2(fallback_source, img_file)
                                sc["image_path"] = img_file
                                sc["use_video_ai"] = False
                                sc["is_fallback_asset"] = True
                                media_ok = True
                                _record_decision(
                                    "generating_assets",
                                    "legacy_fallback_copy_flagged",
                                    f"Cảnh {sc_num} dùng ảnh tạm từ cảnh trước và được gắn cờ is_fallback_asset=True.",
                                )
                        if not media_ok:
                            err_msg = (
                                f"Lỗi sinh ảnh Flow cảnh {sc_num}: {res_img}. "
                                "Hệ thống từ chối thay tài sản lỗi bằng ảnh cảnh khác để bảo đảm chất lượng thật."
                            )
                            notify(step_pct, err_msg, stage="failed")
                            return False, err_msg

                elif not media_ok:
                    notify(step_pct, f"Đang tạo hình ảnh phân cảnh {sc_num} bằng engine local...", stage="generating_assets")
                    try:
                        from src.image_service import generate_single_image
                        ok_sd, res_sd = generate_single_image(
                            prompt=prompt,
                            output_path=img_file,
                            orientation=orientation,
                            style_preset=style_preset,
                        )
                        if ok_sd and os.path.exists(img_file) and os.path.getsize(img_file) > 0:
                            sc["image_path"] = img_file
                            sc["use_video_ai"] = False
                            sc["is_fallback_asset"] = False
                            media_ok = True
                    except Exception as e_sd:
                        safe_log(f"[!] Engine local SD lỗi: {e_sd}")

                if not media_ok:
                    err = f"Lỗi sinh ảnh phân cảnh {sc_num}: Không tạo được bối cảnh hợp lệ từ engine."
                    notify(step_pct, err, stage="failed")
                    return False, err

                try:
                    Path(prompt_meta_file).write_text(
                        json.dumps({"prompt": prompt, "scene_num": sc_num}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

        stage_timings["generating_assets"] = round(stage_timings.get("generating_assets", 0.0) + (time.time() - t_vis), 3)
        return True, ""

    # Thực thi TTS & Sinh bối cảnh lần đầu
    ok_tts, err_tts = _execute_tts_stage()
    if not ok_tts:
        _record_error("tts", err_tts)
        save_job_checkpoint(video_work_dir, checkpoint)
        return False, err_tts, run_meta
    if "tts" not in completed_stages:
        completed_stages.append("tts")
    checkpoint["scenes"] = scenes
    save_job_checkpoint(video_work_dir, checkpoint)

    ok_vis, err_vis = _execute_visual_assets_stage()
    if not ok_vis:
        _record_error("generating_assets", err_vis)
        save_job_checkpoint(video_work_dir, checkpoint)
        return False, err_vis, run_meta
    if "generating_assets" not in completed_stages:
        completed_stages.append("generating_assets")
    checkpoint["scenes"] = scenes
    save_job_checkpoint(video_work_dir, checkpoint)

    # ==========================================================================
    # BƯỚC 8, 9 & 10: DỰNG BẢN NHÁP (RENDERING), QA ĐỘC LẬP SAU RENDER & VÒNG TỰ SỬA LỖI
    # ==========================================================================
    # Tên file đầu ra xác định (Idempotent) theo job_key + version để retry không sinh file trùng lặp
    if safe_job_key:
        final_name = f"video_job_{safe_job_key}_v{version:02d}.mp4"
    else:
        timestamp = checkpoint.get("output_timestamp") or time.strftime("%Y%m%d_%H%M%S")
        checkpoint["output_timestamp"] = timestamp
        final_name = f"video_batch_{timestamp}_v{video_index:02d}.mp4"
    final_path = os.path.join(output_dir, final_name)

    revision_round = int(checkpoint.get("revision_round") or 0)
    qa_report = None
    render_manifest = None
    asset_manifest = None

    while True:
        if _is_cancelled():
            return False, "Đã bỏ qua theo yêu cầu người dùng", run_meta

        asset_manifest = build_and_validate_asset_manifest(
            plan=scene_plan,
            scenes=scenes,
            strict_no_fallback=effective_strict_no_fallback,
        )
        checkpoint["asset_manifest"] = asset_manifest.to_dict()
        run_meta["asset_manifest"] = asset_manifest.to_dict()

        notify(78, "Đang tạo phụ đề đồng bộ từ lời thoại và thời lượng âm thanh thực tế...", stage="rendering")
        all_words = build_exact_tts_timestamps(scenes)

        t_rnd = time.time()
        notify(85, f"Đang biên tập chuyển cảnh và burn phụ đề video (vòng {revision_round + 1})...", stage="rendering")
        srt_work_path = os.path.join(video_work_dir, "subtitles.srt")
        ok_compile, compiled_videos, err_compile = compile_video_pipeline(
            scenes=scenes,
            words_timestamps=all_words,
            max_duration=120.0,
            orientation=orientation,
            target_resolution=brief.resolution,
            strict_assets=True,
            output_srt_path=srt_work_path,
            output_ass_path=os.path.join(video_work_dir, "subtitles.ass"),
        )
        stage_timings["rendering"] = round(stage_timings.get("rendering", 0.0) + (time.time() - t_rnd), 3)

        if not ok_compile or not compiled_videos:
            err_msg = f"Lỗi render: {err_compile}"
            _record_error("rendering", err_msg)
            save_job_checkpoint(video_work_dir, checkpoint)
            notify(85, f"Lỗi render video {video_index}: {err_compile}", stage="failed")
            return False, err_msg, run_meta

        src_video = compiled_videos[0]
        if os.path.abspath(src_video) != os.path.abspath(final_path):
            shutil.copy2(src_video, final_path)

        local_ass_copy = os.path.join(video_work_dir, "subtitles.ass")
        if not os.path.exists(local_ass_copy):
            from src.subtitle_builder import build_ass_subtitle
            build_ass_subtitle(all_words, local_ass_copy, orientation=orientation)

        if not os.path.exists(srt_work_path):
            from src.subtitle_builder import build_srt_subtitle
            build_srt_subtitle(all_words, srt_work_path, orientation=orientation)

        probe_info = probe_media_file(final_path)
        actual_video_dur = float(
            probe_info.get("duration_sec")
            or sum(float(s.get("audio_duration", 5.0)) for s in scenes if isinstance(s, dict))
        )
        render_manifest = RenderManifest(
            render_id=f"rnd_{brief.project_id}_v{version}_r{revision_round}",
            manifest_id=asset_manifest.manifest_id,
            video_path=final_path,
            video_sha256=compute_file_sha256(final_path),
            ass_subtitle_path=local_ass_copy,
            srt_subtitle_path=srt_work_path,
            subtitle_sha256=compute_file_sha256(local_ass_copy),
            resolution=(int(probe_info.get("width") or brief.resolution[0]), int(probe_info.get("height") or brief.resolution[1])),
            aspect_ratio=brief.aspect_ratio,
            fps=float(probe_info.get("fps") or DEFAULT_FPS),
            duration_sec=actual_video_dur,
            video_codec=str(probe_info.get("video_codec") or "h264"),
            audio_codec=str(probe_info.get("audio_codec") or "aac"),
            has_video_stream=bool(probe_info.get("has_video", True)),
            has_audio_stream=bool(probe_info.get("has_audio", True)),
            scene_timeline=[
                {
                    "scene_id": s.get("scene_id", f"sc_{idx:03d}"),
                    "scene_num": idx,
                    "timeline_range": s.get("timeline_range", [0.0, 5.0]),
                    "duration_sec": s.get("audio_duration", 5.0),
                }
                for idx, s in enumerate(scenes, start=1)
                if isinstance(s, dict)
            ],
            elapsed_sec=stage_timings["rendering"],
            version=version,
        )
        checkpoint["render_manifest"] = render_manifest.to_dict()
        run_meta["render_manifest"] = render_manifest.to_dict()
        if "rendering" not in completed_stages:
            completed_stages.append("rendering")

        # Chạy QA Độc lập sau khi render trên file video thực tế
        t_qa = time.time()
        notify(91, f"Đang chạy QA độc lập kiểm tra file video đã render (vòng {revision_round + 1})...", stage="qa_running")
        qa_report = run_rendered_video_qa(
            video_path=final_path,
            scenes=scenes,
            ass_subtitle_path=local_ass_copy,
            orientation=orientation,
            target_resolution=brief.resolution,
            render_id=render_manifest.render_id,
            revision_round=revision_round,
            max_revisions=max_auto_revisions,
            strict_no_fallback=effective_strict_no_fallback,
        )
        stage_timings["qa_running"] = round(stage_timings.get("qa_running", 0.0) + (time.time() - t_qa), 3)
        checkpoint["qa_report"] = qa_report.to_dict()
        run_meta["qa_report"] = qa_report.to_dict()

        if qa_report.passed or revision_round >= max_auto_revisions:
            break

        # Nếu QA phát hiện lỗi kỹ thuật có thể tự sửa và còn trong giới hạn max_auto_revisions
        rec_stage = qa_report.recommended_stage_to_rerun
        rec_scenes = qa_report.recommended_scenes_to_rerun
        if not rec_stage:
            break

        revision_round += 1
        checkpoint["revision_round"] = revision_round
        notify(
            82,
            f"QA phát hiện lỗi tại '{rec_stage}' (cảnh {rec_scenes or 'toàn bộ'}). Đang tự động sửa vòng {revision_round}/{max_auto_revisions}...",
            stage="needs_revision",
        )
        _record_decision(
            "needs_revision",
            f"auto_revision_round_{revision_round}",
            f"Chạy lại {rec_stage} cho các cảnh {rec_scenes}",
        )

        if rec_stage == "tts":
            invalidate_dependent_stages(checkpoint, "tts", scene_num=rec_scenes[0] if len(rec_scenes) == 1 else None, video_work_dir=video_work_dir)
            ok_r_tts, _ = _execute_tts_stage(target_scene_indices=rec_scenes or None)
            if not ok_r_tts:
                break
        elif rec_stage == "generating_assets":
            invalidate_dependent_stages(checkpoint, "generating_assets", scene_num=rec_scenes[0] if len(rec_scenes) == 1 else None, video_work_dir=video_work_dir)
            ok_r_vis, _ = _execute_visual_assets_stage(target_scene_indices=rec_scenes or None)
            if not ok_r_vis:
                break
        else:
            # Lỗi ở phụ đề hoặc render -> vòng lặp tiếp theo sẽ tự động build lại phụ đề và render lại
            invalidate_dependent_stages(checkpoint, "rendering", video_work_dir=video_work_dir)

    if "qa_running" not in completed_stages:
        completed_stages.append("qa_running")

    # ==========================================================================
    # BƯỚC 11 & 12: KIỂM TRA CHÍNH SÁCH (POLICY) & GÓI XUẤT BẢN RIÊNG CHO YOUTUBE / TIKTOK
    # ==========================================================================
    t_pol = time.time()
    notify(95, "Đang kiểm tra chính sách TikTok/YouTube và đóng gói xuất bản...", stage="policy_and_metadata")
    policy_report = evaluate_platform_policies(
        brief=brief,
        research=research,
        script=script_contract,
        asset_manifest=asset_manifest,
        video_duration_sec=render_manifest.duration_sec,
        video_sha256=render_manifest.video_sha256,
    )
    checkpoint["policy_report"] = policy_report.to_dict()
    run_meta["policy_report"] = policy_report.to_dict()

    package_dir = os.path.join(output_dir, "packages", f"{safe_job_key or f'video_{video_index:02d}'}_v{version:02d}")
    publishing_package = build_platform_publishing_package(
        brief=brief,
        research=research,
        script=script_contract,
        render_manifest=render_manifest,
        qa_report=qa_report,
        policy_report=policy_report,
        package_output_dir=package_dir,
        existing_user_edits=checkpoint.get("approved_edits", {}),
    )
    stage_timings["policy_and_metadata"] = round(time.time() - t_pol, 3)

    checkpoint["publishing_package"] = publishing_package.to_dict()
    for st_done in ("policy_and_metadata", "exporting_package"):
        if st_done not in completed_stages:
            completed_stages.append(st_done)

    # Xác định trạng thái vòng đời sau QA & Policy:
    # - Nếu QA bị chặn (release_blocked) hoặc Policy cần người duyệt sau khi hết vòng tự sửa -> needs_review
    # - Nếu đạt kỹ thuật -> ready_for_review (chờ người dùng xem preview & bấm Duyệt)
    if qa_report.release_blocked:
        lifecycle_state = "needs_review"
    elif policy_report.requires_human_review:
        lifecycle_state = "needs_review"
    else:
        lifecycle_state = "ready_for_review"

    checkpoint["lifecycle_state"] = lifecycle_state
    save_job_checkpoint(video_work_dir, checkpoint)

    # Tương thích ngược với cấu trúc run_meta["publishing"] cũ và lưu file .json cạnh file MP4
    with open(publishing_package.metadata_path, "r", encoding="utf-8") as mf:
        publishing_compat_dict = json.load(mf)

    run_meta["final_path"] = final_path
    run_meta["scenes"] = scenes
    run_meta["media_mode"] = media_mode
    run_meta["studio_mode"] = studio_mode
    run_meta["content_mode"] = content_mode
    run_meta["lifecycle_state"] = lifecycle_state
    run_meta["publishing"] = publishing_compat_dict
    run_meta["publishing_package"] = publishing_package.to_dict()
    run_meta["stage_timings"] = stage_timings
    run_meta["cost_ledger"] = checkpoint.get("cost_ledger", {})
    run_meta["decision_history"] = decision_history
    run_meta["error_history"] = error_history

    metadata_path = os.path.splitext(final_path)[0] + ".json"
    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(run_meta, metadata_file, ensure_ascii=False, indent=2)
    run_meta["metadata_path"] = metadata_path

    notify(100, f"✅ Hoàn thành sản xuất & đóng gói video {video_index}: {final_name} ({lifecycle_state})", stage=lifecycle_state)
    return True, final_path, run_meta


def run_batch_video_loop(
    prompt: str,
    count: int = 1,
    language: str = "vi",
    voice: str = TTS_VOICE_DEFAULT,
    style_preset: str = DEFAULT_IMAGE_STYLE,
    orientation: str = "vertical",
    image_engine: str = "flow",
    media_mode: str = "flow_image",
    turbo_mode: bool = True,
    flow_workers: int = 4,
    tts_workers: int = 4,
    batch_workers: int = 1,
    progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    VÒNG LẶP SẢN XUẤT HÀNG LOẠT (BATCH GENERATION LOOP).
    """
    safe_log("=" * 65)
    safe_log(f"🚀 BẮT ĐẦU VÒNG LẶP SẢN XUẤT HÀNG LOẠT ({count} VIDEO) [Turbo={turbo_mode}]")
    safe_log(f"   Prompt gốc: \"{prompt[:60]}...\"")
    safe_log(f"   Engine sinh bối cảnh: {image_engine.upper()}")
    safe_log("=" * 65)

    topics = split_prompt_to_video_topics(prompt, count, language=language)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    batch_work_dir = os.path.join(TEMP_DIR, f"batch_{timestamp}")
    os.makedirs(batch_work_dir, exist_ok=True)

    successful_videos = []
    meta_reports = []
    last_video_context = ""

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
            media_mode=media_mode,
            turbo_mode=turbo_mode,
            flow_workers=flow_workers,
            tts_workers=tts_workers,
            previous_context=last_video_context if last_video_context else None,
            progress_callback=single_video_callback,
        )

        if success:
            successful_videos.append(path_or_err)
            meta["status"] = "success"
            meta_reports.append(meta)
            safe_log(f"   ✓ Video {video_num}/{count} hoàn tất: {path_or_err}")

            sc_list = meta.get("scenes", [])
            if sc_list:
                first_narr = sc_list[0].get("narration", "")[:50]
                last_narr = sc_list[-1].get("narration", "")[:80]
                last_video_context = f"Tập {video_num} mở đầu: '{first_narr}...' và kết thúc: '{last_narr}'"
        else:
            meta["status"] = "failed"
            meta["error"] = path_or_err
            meta_reports.append(meta)
            safe_log(f"   ✗ Video {video_num}/{count} gặp lỗi: {path_or_err}")

    safe_log("\n" + "=" * 65)
    safe_log(f"🏁 KẾT THÚC BATCH LOOP: ĐÃ TẠO THÀNH CÔNG {len(successful_videos)}/{count} VIDEO!")
    safe_log("=" * 65)

    return successful_videos, meta_reports
