"""Hàng đợi bền vững, State Machine 15 trạng thái và Worker nền cho xưởng sản xuất video AI."""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.batch_producer import (
    get_job_checkpoint_path,
    invalidate_dependent_stages,
    load_job_checkpoint,
    produce_single_video_pipeline,
     safe_log,
    save_job_checkpoint,
    split_prompt_to_video_topics,
)
from src.config import (
    DEFAULT_IMAGE_STYLE,
    OUTPUT_DIR,
    TEMP_DIR,
    TTS_VOICE_DEFAULT,
    TTS_VOICE_ZH_DEFAULT,
)
from src.flow_browser_service import get_flow_controller, get_flow_readiness
from src.publishing_package_service import verify_package_ready_for_platform_publish
from src.story_contract_models import PublishingPackage, compute_file_sha256
from src.studio_skill_registry import record_skill_outcome


STATE_PATH = Path(TEMP_DIR) / "video_factory_state.json"
FACTORY_WORK_DIR = Path(TEMP_DIR) / "autonomous_factory"
_LOCK = threading.RLock()
_WAKE_EVENT = threading.Event()
_WORKER_THREAD: threading.Thread | None = None

# Tập hợp đầy đủ các trạng thái của State Machine sản xuất video
VALID_JOB_STATES = {
    "queued",
    "researching",
    "scripting",
    "storyboarding",
    "generating_assets",
    "rendering",
    "qa_running",
    "needs_revision",
    "needs_review",
    "ready_for_review",
    "approved",
    "publishing",
    "published",
    "failed",
    "cancelled",
    # Hai trạng thái tổng quát giữ tương thích ngược với bộ kiểm thử và UI cũ
    "running",
    "completed",
}

ACTIVE_PROCESSING_STATES = {
    "running",
    "researching",
    "scripting",
    "storyboarding",
    "generating_assets",
    "rendering",
    "qa_running",
    "needs_revision",
    "publishing",
}

REVIEW_OR_DONE_STATES = {
    "completed",
    "needs_review",
    "ready_for_review",
    "approved",
    "published",
}

STAGE_LABELS_VI = {
    "queued": "Đang chờ hàng đợi",
    "researching": "Nghiên cứu chủ đề",
    "scripting": "Biên soạn kịch bản",
    "content_review": "Biên tập nội dung",
    "storyboarding": "Phân cảnh & Đạo diễn",
    "pre_production_check": "Tiền kiểm xuất bản",
    "tts": "Sinh giọng đọc AI",
    "generating_assets": "Sinh hình ảnh & bối cảnh",
    "rendering": "Biên tập & Render video",
    "qa_running": "Kiểm định QA độc lập",
    "needs_revision": "Cần chỉnh sửa lại",
    "needs_review": "Cần người dùng xem lại",
    "ready_for_review": "Sẵn sàng xem trước & duyệt",
    "approved": "Đã duyệt xuất bản",
    "publishing": "Đang xuất bản lên kênh",
    "published": "Đã xuất bản thành công",
    "completed": "Hoàn tất",
    "failed": "Gặp lỗi cần xử lý",
    "cancelled": "Đã hủy theo yêu cầu",
    "running": "Đang xử lý",
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_state() -> Dict[str, Any]:
    return {"version": 2, "paused": False, "jobs": []}


def _load_unlocked() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return _default_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data.get("jobs"), list):
            return _default_state()
        return data
    except (OSError, json.JSONDecodeError):
        return _default_state()


def _save_unlocked(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_PATH.with_name(f"factory_state_{os.getpid()}_{time.time_ns()}.tmp")
    try:
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        for _ in range(10):
            try:
                os.replace(temp_path, STATE_PATH)
                return
            except OSError:
                time.sleep(0.05)
    except Exception:
        pass
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def recover_interrupted_jobs() -> None:
    """
    Đưa việc bị ngắt do đóng ứng dụng trở lại hàng chờ.
    Nếu có checkpoint trên đĩa, bảo toàn thông tin resume_from_stage để tiếp tục từ công đoạn dở dang.
    """
    with _LOCK:
        state = _load_unlocked()
        changed = False
        for job in state["jobs"]:
            if job.get("status") in ACTIVE_PROCESSING_STATES:
                job_work_dir = str(FACTORY_WORK_DIR / f"job_{job.get('id', '')}")
                cp_path = get_job_checkpoint_path(job_work_dir)
                has_cp = cp_path.exists()
                resume_stages = []
                if has_cp:
                    cp = load_job_checkpoint(job_work_dir)
                    resume_stages = cp.get("completed_stages", [])
                job.update(
                    status="queued",
                    lifecycle_state="queued",
                    progress=0,
                    has_checkpoint=has_cp,
                    completed_stages=resume_stages,
                    message=(
                        f"Đã khôi phục từ checkpoint ({', '.join(resume_stages[-2:])})"
                        if resume_stages
                        else "Đã khôi phục sau khi ứng dụng khởi động lại"
                    ),
                )
                changed = True
        if changed:
            _save_unlocked(state)


def get_factory_state() -> Dict[str, Any]:
    with _LOCK:
        return deepcopy(_load_unlocked())


def add_factory_jobs(
    prompt: str,
    count: int,
    language: str = "vi",
    voice: str = TTS_VOICE_DEFAULT,
    style_preset: str = DEFAULT_IMAGE_STYLE,
    orientation: str = "vertical",
    image_engine: str = "flow",
    media_mode: str = "flow_video",
    target_scenes: Optional[int] = None,
    voice_mode: str = "edge",
    voice_reference_path: str = "",
    voice_consent_verified: bool = True,
    studio_mode: bool = True,
    content_mode: str = "knowledge",
    chinese_voice: str = TTS_VOICE_ZH_DEFAULT,
    turbo_mode: bool = False,
    flow_workers: int = 4,
    tts_workers: int = 4,
) -> List[str]:
    topics = split_prompt_to_video_topics(prompt, count, language)
    created_ids: List[str] = []
    with _LOCK:
        state = _load_unlocked()
        next_index = max((int(job.get("video_index", 0)) for job in state["jobs"]), default=0) + 1
        for offset, topic in enumerate(topics):
            job_id = uuid.uuid4().hex[:10]
            created_ids.append(job_id)
            state["jobs"].append({
                "id": job_id,
                "video_index": next_index + offset,
                "topic": topic,
                "status": "queued",
                "lifecycle_state": "queued",
                "current_stage": "brief",
                "version": 1,
                "progress": 0,
                "message": "Đang chờ vào dây chuyền",
                "attempts": 0,
                "created_at": _now(),
                "updated_at": _now(),
                "version_history": [
                    {"version": 1, "timestamp": _now(), "action": "created", "note": "Khởi tạo lệnh sản xuất"}
                ],
                "settings": {
                    "language": language,
                    "voice": voice,
                    "style_preset": style_preset,
                    "orientation": orientation,
                    "image_engine": image_engine,
                    "media_mode": media_mode,
                    "target_scenes": int(target_scenes) if target_scenes is not None else None,
                    "voice_mode": voice_mode,
                    "voice_reference_path": voice_reference_path,
                    "voice_consent_verified": bool(voice_consent_verified),
                    "studio_mode": bool(studio_mode),
                    "content_mode": content_mode,
                    "chinese_voice": chinese_voice,
                    "turbo_mode": bool(turbo_mode),
                    "flow_workers": max(1, int(flow_workers)),
                    "tts_workers": max(1, int(tts_workers)),
                },
            })
        state["paused"] = False
        _save_unlocked(state)
    _WAKE_EVENT.set()
    ensure_factory_worker()
    return created_ids


def set_factory_paused(paused: bool) -> None:
    with _LOCK:
        state = _load_unlocked()
        state["paused"] = bool(paused)
        _save_unlocked(state)
    _WAKE_EVENT.set()


def retry_failed_jobs() -> int:
    count = 0
    with _LOCK:
        state = _load_unlocked()
        for job in state["jobs"]:
            if job.get("status") in ("failed", "cancelled"):
                job.update(
                    status="queued",
                    lifecycle_state="queued",
                    progress=0,
                    message="Đã đưa lại vào hàng chờ (tiếp tục từ checkpoint)",
                    updated_at=_now(),
                )
                count += 1
        if count:
            state["paused"] = False
            _save_unlocked(state)
    if count:
        _WAKE_EVENT.set()
        ensure_factory_worker()
    return count


def clear_finished_jobs() -> int:
    with _LOCK:
        state = _load_unlocked()
        before = len(state["jobs"])
        state["jobs"] = [
            job for job in state["jobs"]
            if job.get("status") not in {"completed", "failed", "cancelled", "published"}
        ]
        removed = before - len(state["jobs"])
        if removed:
            _save_unlocked(state)
        return removed


def delete_job(job_id: str) -> bool:
    """Xóa một công việc cụ thể khỏi danh sách theo job_id."""
    with _LOCK:
        state = _load_unlocked()
        before = len(state["jobs"])
        state["jobs"] = [j for j in state["jobs"] if j.get("id") != job_id]
        if len(state["jobs"]) < before:
            _save_unlocked(state)
            return True
        return False


def resolve_job_video_and_metadata_paths(job: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Tự động tìm kiếm và khôi phục đường dẫn thực tế của video MP4 và metadata JSON.
    Hỗ trợ chuyển đổi đường dẫn tuyệt đối cũ sang thư mục dự án hiện tại (video_studio/output/).
    """
    from src.config import OUTPUT_DIR
    job_id = str(job.get("id", ""))
    metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}

    raw_video = job.get("output_path") or metadata.get("final_path") or ""
    video_path = None
    candidates = []
    if raw_video:
        candidates.append(Path(raw_video))
        candidates.append(Path(OUTPUT_DIR) / Path(raw_video).name)
        candidates.append(Path(OUTPUT_DIR).parent / "output" / Path(raw_video).name)
        candidates.append(Path("output") / Path(raw_video).name)
    if job_id:
        candidates.append(Path(FACTORY_WORK_DIR) / f"job_{job_id}" / "final.mp4")
        candidates.append(Path(OUTPUT_DIR) / f"video_{job_id}.mp4")

    for cand in candidates:
        try:
            if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                video_path = str(cand.resolve())
                break
        except Exception:
            continue

    raw_meta = metadata.get("metadata_path") or ""
    meta_path = None
    meta_candidates = []
    if raw_meta:
        meta_candidates.append(Path(raw_meta))
        meta_candidates.append(Path(OUTPUT_DIR) / Path(raw_meta).name)
        meta_candidates.append(Path(OUTPUT_DIR).parent / "output" / Path(raw_meta).name)
    if job_id:
        meta_candidates.append(Path(FACTORY_WORK_DIR) / f"job_{job_id}" / "metadata.json")
        meta_candidates.append(Path(FACTORY_WORK_DIR) / f"job_{job_id}" / "publishing_manifest.json")

    for cand in meta_candidates:
        try:
            if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
                meta_path = str(cand.resolve())
                break
        except Exception:
            continue

    return video_path, meta_path


def clear_missing_video_jobs() -> int:
    """Dọn dẹp các công việc đã hoàn tất nhưng file video không còn tồn tại trên đĩa."""
    with _LOCK:
        state = _load_unlocked()
        before = len(state["jobs"])
        valid_jobs = []
        for job in state["jobs"]:
            if job.get("status") in ("completed", "ready_for_review", "approved", "published", "needs_review"):
                v_path, _ = resolve_job_video_and_metadata_paths(job)
                if not v_path:
                    continue
            valid_jobs.append(job)
        removed = before - len(valid_jobs)
        if removed:
            state["jobs"] = valid_jobs
            _save_unlocked(state)
        return removed


def rerun_missing_video_jobs() -> int:
    """Tự động đưa tất cả các job thành phẩm bị thiếu file video vào hàng đợi để render lại."""
    with _LOCK:
        state = _load_unlocked()
        missing_ids = []
        for job in state["jobs"]:
            if job.get("status") in ("completed", "ready_for_review", "approved", "published", "needs_review"):
                v_path, _ = resolve_job_video_and_metadata_paths(job)
                if not v_path and job.get("id"):
                    missing_ids.append(job.get("id"))

    requeued = 0
    for j_id in missing_ids:
        ok, _ = rerun_job_stage_or_scene(j_id, target_stage="rendering")
        if ok:
            requeued += 1
    return requeued


def clear_failed_jobs() -> int:
    """Xóa lịch sử lỗi nhưng giữ nguyên video đã hoàn tất."""
    with _LOCK:
        state = _load_unlocked()
        before = len(state["jobs"])
        state["jobs"] = [job for job in state["jobs"] if job.get("status") not in ("failed", "cancelled")]
        removed = before - len(state["jobs"])
        if removed:
            _save_unlocked(state)
        return removed


def cancel_queued_jobs() -> int:
    """Hủy riêng các việc chưa bắt đầu, không đụng tới video đang chạy/thành phẩm."""
    with _LOCK:
        state = _load_unlocked()
        before = len(state["jobs"])
        state["jobs"] = [job for job in state["jobs"] if job.get("status") != "queued"]
        removed = before - len(state["jobs"])
        if removed:
            _save_unlocked(state)
        return removed


_CURRENT_RUNNING_JOB_ID: Optional[str] = None
_SKIP_REQUESTED_JOB_IDS: set = set()


def recover_stale_running_jobs() -> int:
    """
    Phục hồi các job bị kẹt ở trạng thái 'running' mồ côi (không có pipeline worker active)
    để giải phóng hàng đợi, cho phép job tiếp theo được chạy ngay lập tức.
    """
    global _CURRENT_RUNNING_JOB_ID
    recovered = 0
    with _LOCK:
        state = _load_unlocked()
        changed = False
        for job in state.get("jobs", []):
            if job.get("status") in ACTIVE_PROCESSING_STATES:
                is_orphan = (_CURRENT_RUNNING_JOB_ID is None) or (job.get("id") != _CURRENT_RUNNING_JOB_ID)
                worker_dead = (_WORKER_THREAD is not None and not _WORKER_THREAD.is_alive())
                if is_orphan or worker_dead:
                    job.update(
                        status="queued",
                        lifecycle_state="queued",
                        progress=0,
                        message="Đang chờ vào dây chuyền",
                        updated_at=_now(),
                    )
                    changed = True
                    recovered += 1
        if changed:
            _CURRENT_RUNNING_JOB_ID = None
            _save_unlocked(state)
            _WAKE_EVENT.set()
    return recovered


def skip_current_job(job_id: Optional[str] = None) -> bool:
    """
    Bỏ qua video đang sản xuất hiện tại (hoặc job_id chỉ định) và lập tức
    chuyển sang video tiếp theo trong hàng đợi.
    """
    global _CURRENT_RUNNING_JOB_ID, _SKIP_REQUESTED_JOB_IDS
    with _LOCK:
        state = _load_unlocked()
        target_id = job_id or _CURRENT_RUNNING_JOB_ID
        running_jobs = [
            j for j in state["jobs"]
            if j.get("status") in ACTIVE_PROCESSING_STATES and (target_id is None or j.get("id") == target_id)
        ]
        if not running_jobs:
            running_jobs = [j for j in state["jobs"] if j.get("status") in ACTIVE_PROCESSING_STATES]

        if not running_jobs:
            _CURRENT_RUNNING_JOB_ID = None
            _WAKE_EVENT.set()
            return False

        for j in running_jobs:
            jid = j["id"]
            _SKIP_REQUESTED_JOB_IDS.add(jid)
            j.update(
                status="failed",
                lifecycle_state="cancelled",
                progress=0,
                message="Đã bỏ qua theo yêu cầu người dùng",
                error="Đã bỏ qua theo yêu cầu người dùng",
                updated_at=_now(),
            )
        _CURRENT_RUNNING_JOB_ID = None
        _save_unlocked(state)
        _WAKE_EVENT.set()
        return True


def cancel_job(job_id: str, keep_cancelled_record: bool = False) -> bool:
    """
    Hủy một công việc cụ thể:
    - Nếu keep_cancelled_record=True: Đánh dấu status='cancelled', lifecycle_state='cancelled'.
    - Nếu đang chờ (queued) hoặc đã lỗi (failed) và keep_cancelled_record=False: Xóa khỏi danh sách (tương thích ngược).
    - Nếu đang chạy (running): Ngắt tức thì.
    """
    global _CURRENT_RUNNING_JOB_ID
    with _LOCK:
        state = _load_unlocked()
        target = next((j for j in state["jobs"] if j.get("id") == job_id), None)
        if not target:
            return False
        if keep_cancelled_record:
            _SKIP_REQUESTED_JOB_IDS.add(job_id)
            target.update(
                status="cancelled",
                lifecycle_state="cancelled",
                progress=0,
                message="Đã hủy theo yêu cầu người dùng",
                updated_at=_now(),
            )
            if _CURRENT_RUNNING_JOB_ID == job_id:
                _CURRENT_RUNNING_JOB_ID = None
            _save_unlocked(state)
            _WAKE_EVENT.set()
            return True
        if target.get("status") in ("queued", "failed", "cancelled"):
            state["jobs"] = [j for j in state["jobs"] if j.get("id") != job_id]
            if _CURRENT_RUNNING_JOB_ID == job_id:
                _CURRENT_RUNNING_JOB_ID = None
            _save_unlocked(state)
            _WAKE_EVENT.set()
            return True

    return skip_current_job(job_id)


# ==============================================================================
# CÁC THAO TÁC VẬN HÀNH TRÊN GIAO DIỆN: DUYỆT, SỬA NỘI DUNG, CHẠY LẠI CẢNH/CÔNG ĐOẠN, ĐĂNG
# ==============================================================================

def approve_job_for_publishing(job_id: str, approver_note: str = "Approved by Producer/User") -> Tuple[bool, str]:
    """
    Duyệt chính thức một công việc sau khi kiểm tra Preview, QA và Policy:
    - Ghi nhận mã băm SHA-256 của video được duyệt (`approved_video_sha256`).
    - Cập nhật trạng thái sang `approved`.
    """
    with _LOCK:
        state = _load_unlocked()
        job = next((j for j in state["jobs"] if j.get("id") == job_id), None)
        if not job:
            return False, f"Không tìm thấy công việc {job_id}."

        output_path = str(job.get("output_path") or job.get("metadata", {}).get("final_path") or "")
        if not output_path or not os.path.exists(output_path):
            return False, "Không tìm thấy file video thành phẩm để phê duyệt."

        qa_rep = job.get("metadata", {}).get("qa_report", {})
        if isinstance(qa_rep, dict) and qa_rep.get("critical_count", 0) > 0:
            return False, f"Không thể duyệt khi còn {qa_rep.get('critical_count')} lỗi QA nghiêm trọng (critical)."

        video_sha = compute_file_sha256(output_path)
        now_str = _now()

        job["status"] = "completed"
        job["lifecycle_state"] = "approved"
        job["approved_by_user"] = True
        job["approved_at"] = now_str
        job["approved_video_sha256"] = video_sha
        job["message"] = f"Đã duyệt xuất bản (SHA-256: {video_sha[:10]}...)"
        job["updated_at"] = now_str
        job.setdefault("version_history", []).append({
            "version": int(job.get("version", 1)),
            "timestamp": now_str,
            "action": "approved",
            "video_sha256": video_sha,
            "note": approver_note,
        })

        # Đồng bộ vào checkpoint & package_manifest trên đĩa
        work_dir = str(FACTORY_WORK_DIR / f"job_{job_id}")
        if os.path.exists(work_dir):
            cp = load_job_checkpoint(work_dir)
            edits = cp.setdefault("approved_edits", {})
            edits["approved_by_user"] = True
            edits["approved_at"] = now_str
            edits["approved_video_sha256"] = video_sha
            save_job_checkpoint(work_dir, cp)

        pkg_dict = job.get("metadata", {}).get("publishing_package")
        if isinstance(pkg_dict, dict):
            pkg_dict["approved_by_user"] = True
            pkg_dict["approved_at"] = now_str
            pkg_dict["approved_video_sha256"] = video_sha
            manifest_p = pkg_dict.get("manifest_path")
            if manifest_p and os.path.exists(manifest_p):
                try:
                    m_data = json.loads(Path(manifest_p).read_text(encoding="utf-8"))
                    m_data["approved_by_user"] = True
                    m_data["approved_at"] = now_str
                    m_data["approved_video_sha256"] = video_sha
                    Path(manifest_p).write_text(json.dumps(m_data, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass

        _save_unlocked(state)
        return True, f"Đã phê duyệt công việc #{job.get('video_index')} (SHA-256: {video_sha[:12]})."


def update_job_metadata_or_script(
    job_id: str,
    youtube_title: Optional[str] = None,
    youtube_description: Optional[str] = None,
    tiktok_caption: Optional[str] = None,
    hashtags: Optional[List[str]] = None,
    edited_scenes: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    lock_edited_fields: bool = True,
) -> Tuple[bool, str]:
    """
    Cho phép người dùng chỉnh sửa thủ công tiêu đề, mô tả, hashtag hoặc phân cảnh:
    - Khóa các trường đã sửa (`user_locked_fields`, `user_locked_scenes`) để chạy lại tự động KHÔNG BAO GIỜ ghi đè.
    - Nếu công việc đã được duyệt (`approved`), bất kỳ chỉnh sửa nào làm thay đổi nội dung kịch bản hoặc metadata
      sẽ tự động thu hồi trạng thái `approved` và yêu cầu đánh giá/duyệt lại!
    """
    if youtube_title is None and title is not None:
        youtube_title = title
    if youtube_description is None and description is not None:
        youtube_description = description
    with _LOCK:
        state = _load_unlocked()
        job = next((j for j in state["jobs"] if j.get("id") == job_id), None)
        if not job:
            return False, f"Không tìm thấy công việc {job_id}."

        work_dir = str(FACTORY_WORK_DIR / f"job_{job_id}")
        cp = load_job_checkpoint(work_dir)
        edits = cp.setdefault("approved_edits", {})
        locked_fields: List[str] = list(edits.get("user_locked_fields", []))
        meta = job.setdefault("metadata", {}) if isinstance(job.get("metadata"), dict) else {}
        pub = meta.setdefault("publishing", {}) if isinstance(meta.get("publishing"), dict) else {}
        pkg = meta.setdefault("publishing_package", {}) if isinstance(meta.get("publishing_package"), dict) else {}

        changed_items: List[str] = []
        script_changed = False

        if youtube_title is not None and youtube_title.strip():
            edits["youtube_title"] = youtube_title.strip()[:100]
            if "youtube_title" not in locked_fields:
                locked_fields.append("youtube_title")
            pub["title"] = edits["youtube_title"]
            pub.setdefault("platforms", {}).setdefault("youtube", {})["title"] = edits["youtube_title"]
            pkg.setdefault("youtube", {})["recommended_title"] = edits["youtube_title"]
            changed_items.append("youtube_title")

        if youtube_description is not None and youtube_description.strip():
            edits["youtube_description"] = youtube_description.strip()
            if "youtube_description" not in locked_fields:
                locked_fields.append("youtube_description")
            pub["description"] = edits["youtube_description"]
            pub.setdefault("platforms", {}).setdefault("youtube", {})["description"] = edits["youtube_description"]
            pkg.setdefault("youtube", {})["description"] = edits["youtube_description"]
            changed_items.append("youtube_description")

        if tiktok_caption is not None and tiktok_caption.strip():
            edits["tiktok_caption"] = tiktok_caption.strip()[:2200]
            if "tiktok_caption" not in locked_fields:
                locked_fields.append("tiktok_caption")
            pub["tiktok_caption"] = edits["tiktok_caption"]
            pub.setdefault("platforms", {}).setdefault("tiktok", {})["caption"] = edits["tiktok_caption"]
            pkg.setdefault("tiktok", {})["caption"] = edits["tiktok_caption"]
            changed_items.append("tiktok_caption")

        if hashtags is not None:
            clean_tags = [t if str(t).startswith("#") else f"#{t}" for t in hashtags if str(t).strip()]
            edits["hashtags"] = clean_tags
            if "hashtags" not in locked_fields:
                locked_fields.append("hashtags")
            pub["hashtags"] = clean_tags
            pub.setdefault("platforms", {}).setdefault("youtube", {})["hashtags"] = clean_tags
            pub.setdefault("platforms", {}).setdefault("tiktok", {})["hashtags"] = clean_tags
            pkg.setdefault("youtube", {})["hashtags"] = clean_tags
            pkg.setdefault("tiktok", {})["hashtags"] = clean_tags
            changed_items.append("hashtags")

        edits["user_locked_fields"] = locked_fields
        cp["user_locked_fields"] = locked_fields

        if edited_scenes is not None and isinstance(edited_scenes, list):
            old_scenes = cp.get("scenes", meta.get("scenes", []))
            locked_scenes_map = cp.setdefault("user_locked_scenes", {})
            for idx, new_sc in enumerate(edited_scenes, start=1):
                if not isinstance(new_sc, dict):
                    continue
                old_sc = old_scenes[idx - 1] if idx - 1 < len(old_scenes) and isinstance(old_scenes[idx - 1], dict) else {}
                if str(new_sc.get("narration", "")) != str(old_sc.get("narration", "")):
                    invalidate_dependent_stages(cp, "scene_narration", scene_num=idx, video_work_dir=work_dir, reason=f"Người dùng sửa lời thoại cảnh {idx}")
                    script_changed = True
                if str(new_sc.get("video_prompt", "")) != str(old_sc.get("video_prompt", "")):
                    invalidate_dependent_stages(cp, "scene_visual_prompt", scene_num=idx, video_work_dir=work_dir, reason=f"Người dùng sửa prompt cảnh {idx}")
                    script_changed = True
                new_sc["user_locked"] = True
                locked_scenes_map[str(idx)] = new_sc
            cp["scenes"] = edited_scenes
            meta["scenes"] = edited_scenes
            changed_items.append("scenes")

        if changed_items and not script_changed:
            invalidate_dependent_stages(cp, "metadata", video_work_dir=work_dir, reason=f"Người dùng sửa metadata: {', '.join(changed_items)}")

        new_ver = int(job.get("version", 1)) + 1
        job["version"] = new_ver
        cp["version"] = new_ver

        # Nếu đã được duyệt trước đó, các thay đổi ảnh hưởng nội dung bắt buộc phải đánh giá/duyệt lại!
        was_approved = bool(job.get("approved_by_user")) or job.get("lifecycle_state") == "approved"
        if was_approved or script_changed:
            job["approved_by_user"] = False
            job["approved_video_sha256"] = ""
            edits["approved_by_user"] = False
            if isinstance(pkg, dict):
                pkg["approved_by_user"] = False
            job["lifecycle_state"] = "needs_revision" if script_changed else "needs_review"
            job["message"] = (
                f"Đã lưu chỉnh sửa v{new_ver} ({', '.join(changed_items)}) — cần chạy lại/duyệt lại trước khi xuất bản."
            )
        else:
            job["message"] = f"Đã lưu chỉnh sửa thủ công v{new_ver} ({', '.join(changed_items)})."

        job["updated_at"] = _now()
        job.setdefault("version_history", []).append({
            "version": new_ver,
            "timestamp": _now(),
            "action": "manual_edit",
            "fields": changed_items,
            "invalidated_approval": was_approved,
        })

        save_job_checkpoint(work_dir, cp)
        _save_unlocked(state)
        return True, job["message"]


def rerun_job_stage_or_scene(
    job_id: str,
    target_stage: str = "rendering",
    scene_num: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Vô hiệu hóa đúng công đoạn (hoặc cảnh cụ thể) và đưa công việc vào hàng đợi chạy lại chỉ phần bị ảnh hưởng.
    Không ghi đè các chỉnh sửa đã được người dùng khóa (`user_locked_fields` / `user_locked_scenes`).
    """
    with _LOCK:
        state = _load_unlocked()
        job = next((j for j in state["jobs"] if j.get("id") == job_id), None)
        if not job:
            return False, f"Không tìm thấy công việc {job_id}."

        work_dir = str(FACTORY_WORK_DIR / f"job_{job_id}")
        cp = load_job_checkpoint(work_dir)
        invalidate_dependent_stages(
            cp,
            modified_target=target_stage,
            scene_num=scene_num,
            video_work_dir=work_dir,
            reason=f"Yêu cầu chạy lại công đoạn '{target_stage}'" + (f" (cảnh {scene_num})" if scene_num else ""),
        )
        new_ver = int(job.get("version", 1)) + 1
        cp["version"] = new_ver
        save_job_checkpoint(work_dir, cp)

        job.update(
            status="queued",
            lifecycle_state="queued",
            version=new_ver,
            approved_by_user=False,
            progress=0,
            message=f"Đang chờ chạy lại '{target_stage}'" + (f" (cảnh {scene_num})" if scene_num else ""),
            updated_at=_now(),
        )
        job.setdefault("version_history", []).append({
            "version": new_ver,
            "timestamp": _now(),
            "action": "rerun_requested",
            "target_stage": target_stage,
            "scene_num": scene_num,
        })
        state["paused"] = False
        _save_unlocked(state)

    _WAKE_EVENT.set()
    ensure_factory_worker()
    return True, f"Đã đưa công việc #{job.get('video_index')} vào hàng đợi để làm lại '{target_stage}'."


def publish_approved_job(
    job_id: str,
    platform: str = "youtube",
    explicit_publish_permission: bool = False,
) -> Tuple[bool, str]:
    """
    Thực hiện kiểm tra Cổng Xuất Bản (Publication Gate) trước khi đăng:
    1. Bắt buộc có `explicit_publish_permission=True`.
    2. Bắt buộc job đã ở trạng thái `approved` (`approved_by_user=True`).
    3. Bắt buộc checksum SHA-256 của file MP4 khớp tuyệt đối với bản đã duyệt.
    4. Nếu nền tảng yêu cầu khai báo AI mà connector chưa hỗ trợ tự động (như TikTok chưa gắn OAuth),
       chặn đăng tự động và hướng dẫn bước thủ công rõ ràng!
    """
    if not explicit_publish_permission:
        return False, "Chặn đăng tự động: Chưa có xác nhận quyền đăng công khai cụ thể (explicit_publish_permission=False)."

    with _LOCK:
        state = _load_unlocked()
        job = next((j for j in state["jobs"] if j.get("id") == job_id), None)
        if not job:
            return False, f"Không tìm thấy công việc {job_id}."

        pkg_dict = job.get("metadata", {}).get("publishing_package")
        if not isinstance(pkg_dict, dict):
            return False, "Công việc chưa có gói xuất bản (PublishingPackage)."

        pkg = PublishingPackage(**{k: v for k, v in pkg_dict.items() if k in PublishingPackage.__dataclass_fields__})
        ready, reasons = verify_package_ready_for_platform_publish(pkg, platform=platform)
        if not ready:
            return False, "Chặn đăng tự động: " + " | ".join(reasons)

        job["lifecycle_state"] = "publishing"
        job["message"] = f"Đang chuẩn bị đăng lên {platform.upper()}..."
        _save_unlocked(state)

    return True, f"Gói xuất bản {pkg.package_id} đã vượt qua mọi cổng kiểm tra cho {platform.upper()}."


def _update_job(job_id: str, **changes: Any) -> None:
    with _LOCK:
        state = _load_unlocked()
        for job in state["jobs"]:
            if job.get("id") == job_id:
                job.update(changes)
                job["updated_at"] = _now()
                break
        _save_unlocked(state)


def _next_job() -> Dict[str, Any] | None:
    global _CURRENT_RUNNING_JOB_ID
    with _LOCK:
        state = _load_unlocked()
        if state.get("paused"):
            return None

        for job in state.get("jobs", []):
            if job.get("status") in ACTIVE_PROCESSING_STATES:
                if _CURRENT_RUNNING_JOB_ID is None or job.get("id") != _CURRENT_RUNNING_JOB_ID:
                    job.update(
                        status="queued",
                        lifecycle_state="queued",
                        progress=0,
                        message="Đang chờ vào dây chuyền",
                        updated_at=_now(),
                    )

        if any(job.get("status") in ACTIVE_PROCESSING_STATES for job in state["jobs"]):
            return None

        for job in state["jobs"]:
            if job.get("status") == "queued":
                _CURRENT_RUNNING_JOB_ID = job["id"]
                job.update(
                    status="running",
                    lifecycle_state="researching",
                    current_stage="brief",
                    progress=1,
                    message="Đang khởi động dây chuyền",
                    updated_at=_now(),
                )
                job["attempts"] = int(job.get("attempts", 0)) + 1
                _save_unlocked(state)
                return deepcopy(job)
    return None


def _worker_loop() -> None:
    FACTORY_WORK_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            job = _next_job()
            if not job:
                _WAKE_EVENT.wait(timeout=2.0)
                _WAKE_EVENT.clear()
                continue

            settings = job.get("settings", {})

            if settings.get("image_engine", "flow") == "flow" and get_flow_readiness() != "ready":
                _update_job(job["id"], progress=1, message="Đang tự mở lại Chrome Google Flow...")
                flow_ok, flow_message = get_flow_controller().connect()
                if not flow_ok:
                    _update_job(
                        job["id"],
                        status="queued",
                        lifecycle_state="queued",
                        progress=0,
                        message=f"{flow_message} — xưởng đã tự tạm dừng",
                    )
                    set_factory_paused(True)
                    continue

            current_job_id = job["id"]
            with _LOCK:
                _CURRENT_RUNNING_JOB_ID = current_job_id

            def is_cancelled() -> bool:
                with _LOCK:
                    if current_job_id in _SKIP_REQUESTED_JOB_IDS:
                        return True
                    st = _load_unlocked()
                    for j in st.get("jobs", []):
                        if j.get("id") == current_job_id and j.get("status") not in ACTIVE_PROCESSING_STATES:
                            return True
                return False

            def stage_callback(stage_name: str, percent: float, message: str) -> None:
                if not is_cancelled():
                    _update_job(
                        job["id"],
                        current_stage=stage_name,
                        lifecycle_state=stage_name if stage_name in VALID_JOB_STATES else "running",
                        progress=max(1, min(99, int(percent))),
                        message=message,
                    )

            def progress_callback(percent: float, message: str) -> None:
                if not is_cancelled():
                    _update_job(job["id"], progress=max(1, min(99, int(percent))), message=message)

            try:
                success, result, metadata = produce_single_video_pipeline(
                    topic=job["topic"],
                    video_index=int(job["video_index"]),
                    batch_work_dir=str(FACTORY_WORK_DIR),
                    output_dir=OUTPUT_DIR,
                    language=settings.get("language", "vi"),
                    voice=settings.get("voice", TTS_VOICE_DEFAULT),
                    style_preset=settings.get("style_preset", DEFAULT_IMAGE_STYLE),
                    orientation=settings.get("orientation", "vertical"),
                    image_engine=settings.get("image_engine", "flow"),
                    media_mode=settings.get("media_mode", "flow_image"),
                    target_scenes=int(settings["target_scenes"]) if settings.get("target_scenes") is not None else None,
                    voice_mode=settings.get("voice_mode", "edge"),
                    voice_reference_path=settings.get("voice_reference_path", ""),
                    voice_consent_verified=bool(settings.get("voice_consent_verified", True)),
                    job_key=job["id"],
                    studio_mode=bool(settings.get("studio_mode", True)),
                    content_mode=settings.get("content_mode", "knowledge"),
                    chinese_voice=settings.get("chinese_voice", TTS_VOICE_ZH_DEFAULT),
                    turbo_mode=bool(settings.get("turbo_mode", False)),
                    flow_workers=int(settings.get("flow_workers", 2)),
                    tts_workers=int(settings.get("tts_workers", 4)),
                    stage_callback=stage_callback,
                    progress_callback=progress_callback,
                    is_cancelled_callback=is_cancelled,
                )

                with _LOCK:
                    if current_job_id == _CURRENT_RUNNING_JOB_ID:
                        _CURRENT_RUNNING_JOB_ID = None
                    was_skipped = current_job_id in _SKIP_REQUESTED_JOB_IDS
                    _SKIP_REQUESTED_JOB_IDS.discard(current_job_id)

                if was_skipped:
                    _update_job(
                        current_job_id,
                        status="failed",
                        lifecycle_state="cancelled",
                        progress=0,
                        message="Đã bỏ qua theo yêu cầu người dùng",
                        error="Đã bỏ qua theo yêu cầu người dùng",
                    )
                    continue

                editorial_report = metadata.get("editorial_report") if isinstance(metadata, dict) else {}
                qa_report = metadata.get("qa_report") if isinstance(metadata, dict) else {}
                skill_ids = editorial_report.get("selected_skill_ids", []) if isinstance(editorial_report, dict) else []
                # Chỉ cộng điểm kỹ năng khi cả pipeline VÀ QA thực tế sau render đạt!
                qa_passed = bool(qa_report.get("passed", True)) if isinstance(qa_report, dict) else True
                record_skill_outcome(skill_ids, bool(success and qa_passed))

                if success:
                    final_lifecycle = (
                        metadata.get("lifecycle_state", "ready_for_review")
                        if isinstance(metadata, dict)
                        else "ready_for_review"
                    )
                    _update_job(
                        job["id"],
                        status="completed",
                        lifecycle_state=final_lifecycle,
                        current_stage=final_lifecycle,
                        progress=100,
                        message="Video và gói xuất bản đã sẵn sàng duyệt" if final_lifecycle == "ready_for_review" else "Video cần kiểm tra thủ công trước khi duyệt",
                        output_path=result,
                        metadata=metadata,
                        completed_at=_now(),
                        error="",
                    )
                else:
                    _update_job(
                        job["id"],
                        status="failed",
                        lifecycle_state="failed",
                        progress=0,
                        message=str(result),
                        error=str(result),
                    )
            except Exception as exc:
                safe_log(f"[FACTORY WORKER] Ngoại lệ khi thực thi job {job.get('id')}:\n{traceback.format_exc()}")
                with _LOCK:
                    if current_job_id == _CURRENT_RUNNING_JOB_ID:
                        _CURRENT_RUNNING_JOB_ID = None
                    was_skipped = current_job_id in _SKIP_REQUESTED_JOB_IDS
                    _SKIP_REQUESTED_JOB_IDS.discard(current_job_id)
                if was_skipped:
                    _update_job(
                        current_job_id,
                        status="failed",
                        lifecycle_state="cancelled",
                        progress=0,
                        message="Đã bỏ qua theo yêu cầu người dùng",
                        error="Đã bỏ qua theo yêu cầu người dùng",
                    )
                    continue
                _update_job(
                    job["id"],
                    status="failed",
                    lifecycle_state="failed",
                    progress=0,
                    message=f"Dây chuyền gặp lỗi: {exc}",
                    error=str(exc),
                )
        except Exception as loop_err:
            safe_log(f"[FACTORY WORKER] Ngoại lệ vòng lặp nền: {loop_err}")
            time.sleep(2.0)


def ensure_factory_worker() -> threading.Thread:
    global _WORKER_THREAD
    with _LOCK:
        recover_stale_running_jobs()
        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            _WAKE_EVENT.set()
            return _WORKER_THREAD
        recover_interrupted_jobs()
        _WORKER_THREAD = threading.Thread(target=_worker_loop, name="video-factory-worker", daemon=True)
        _WORKER_THREAD.start()
        _WAKE_EVENT.set()
        return _WORKER_THREAD


def restart_factory_worker() -> threading.Thread:
    """Ép buộc khởi động lại worker nền và dọn sạch trạng thái treo."""
    global _WORKER_THREAD, _CURRENT_RUNNING_JOB_ID
    with _LOCK:
        _CURRENT_RUNNING_JOB_ID = None
        recover_interrupted_jobs()
        recover_stale_running_jobs()
        _WORKER_THREAD = threading.Thread(target=_worker_loop, name="video-factory-worker", daemon=True)
        _WORKER_THREAD.start()
        _WAKE_EVENT.set()
        return _WORKER_THREAD


if __name__ == "__main__":
    print("[*] Khởi động autonomous factory standalone worker process...", flush=True)
    recover_stale_running_jobs()
    _worker_loop()
