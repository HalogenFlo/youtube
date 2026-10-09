"""Hàng đợi bền vững và worker nền cho xưởng video tự động."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.batch_producer import produce_single_video_pipeline, split_prompt_to_video_topics
from src.config import DEFAULT_IMAGE_STYLE, OUTPUT_DIR, TEMP_DIR, TTS_VOICE_DEFAULT, TTS_VOICE_ZH_DEFAULT
from src.flow_browser_service import get_flow_controller, get_flow_readiness
from src.studio_skill_registry import record_skill_outcome


STATE_PATH = Path(TEMP_DIR) / "video_factory_state.json"
FACTORY_WORK_DIR = Path(TEMP_DIR) / "autonomous_factory"
_LOCK = threading.RLock()
_WAKE_EVENT = threading.Event()
_WORKER_THREAD: threading.Thread | None = None


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_state() -> Dict[str, Any]:
    return {"version": 1, "paused": False, "jobs": []}


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
        for attempt in range(10):
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
    """Đưa việc bị ngắt do đóng ứng dụng trở lại hàng chờ."""
    with _LOCK:
        state = _load_unlocked()
        changed = False
        for job in state["jobs"]:
            if job.get("status") == "running":
                job.update(status="queued", progress=0, message="Đã khôi phục sau khi ứng dụng khởi động lại")
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
    target_scenes: int = 5,
    voice_mode: str = "edge",
    voice_reference_path: str = "",
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
                "progress": 0,
                "message": "Đang chờ vào dây chuyền",
                "attempts": 0,
                "created_at": _now(),
                "updated_at": _now(),
                "settings": {
                    "language": language,
                    "voice": voice,
                    "style_preset": style_preset,
                    "orientation": orientation,
                    "image_engine": image_engine,
                    "media_mode": media_mode,
                    "target_scenes": max(1, int(target_scenes)),
                    "voice_mode": voice_mode,
                    "voice_reference_path": voice_reference_path,
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
            if job.get("status") == "failed":
                job.update(status="queued", progress=0, message="Đã đưa lại vào hàng chờ", updated_at=_now())
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
        state["jobs"] = [job for job in state["jobs"] if job.get("status") not in {"completed", "failed"}]
        removed = before - len(state["jobs"])
        if removed:
            _save_unlocked(state)
        return removed


def clear_failed_jobs() -> int:
    """Xóa lịch sử lỗi nhưng giữ nguyên video đã hoàn tất."""
    with _LOCK:
        state = _load_unlocked()
        before = len(state["jobs"])
        state["jobs"] = [job for job in state["jobs"] if job.get("status") != "failed"]
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
    hoặc đã bị skip để giải phóng hàng đợi, cho phép job tiếp theo được chạy ngay lập tức.
    """
    global _CURRENT_RUNNING_JOB_ID
    recovered = 0
    with _LOCK:
        state = _load_unlocked()
        changed = False
        for job in state.get("jobs", []):
            if job.get("status") == "running":
                # Nếu không khớp với worker ID hiện tại hoặc worker thread không còn sống
                is_orphan = (_CURRENT_RUNNING_JOB_ID is None) or (job.get("id") != _CURRENT_RUNNING_JOB_ID)
                worker_dead = (_WORKER_THREAD is not None and not _WORKER_THREAD.is_alive())
                if is_orphan or worker_dead:
                    job.update(
                        status="queued",
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
    chuyển sang video tiếp theo trong hàng đợi mà không cần chờ đợi.
    """
    global _CURRENT_RUNNING_JOB_ID, _SKIP_REQUESTED_JOB_IDS
    with _LOCK:
        state = _load_unlocked()
        target_id = job_id or _CURRENT_RUNNING_JOB_ID
        running_jobs = [
            j for j in state["jobs"]
            if j.get("status") == "running" and (target_id is None or j.get("id") == target_id)
        ]
        if not running_jobs:
            running_jobs = [j for j in state["jobs"] if j.get("status") == "running"]

        if not running_jobs:
            # Ngay cả khi không thấy running job trong state, vẫn reset _CURRENT_RUNNING_JOB_ID
            _CURRENT_RUNNING_JOB_ID = None
            _WAKE_EVENT.set()
            return False

        for j in running_jobs:
            jid = j["id"]
            _SKIP_REQUESTED_JOB_IDS.add(jid)
            j.update(
                status="failed",
                progress=0,
                message="Đã bỏ qua theo yêu cầu người dùng",
                error="Đã bỏ qua theo yêu cầu người dùng",
                updated_at=_now(),
            )
        _CURRENT_RUNNING_JOB_ID = None
        _save_unlocked(state)
        _WAKE_EVENT.set()
        return True


def cancel_job(job_id: str) -> bool:
    """
    Hủy một công việc cụ thể:
    - Nếu đang chờ (queued) hoặc đã lỗi (failed): Xóa khỏi danh sách.
    - Nếu đang chạy (running): Ngắt và bỏ qua để chuyển sang việc tiếp theo ngay lập tức.
    """
    global _CURRENT_RUNNING_JOB_ID
    with _LOCK:
        state = _load_unlocked()
        target = next((j for j in state["jobs"] if j.get("id") == job_id), None)
        if not target:
            return False
        if target.get("status") in ("queued", "failed"):
            state["jobs"] = [j for j in state["jobs"] if j.get("id") != job_id]
            if _CURRENT_RUNNING_JOB_ID == job_id:
                _CURRENT_RUNNING_JOB_ID = None
            _save_unlocked(state)
            _WAKE_EVENT.set()
            return True

    return skip_current_job(job_id)


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

        # Tự động giải phóng các running job mồ côi (nếu có)
        for job in state.get("jobs", []):
            if job.get("status") == "running":
                if _CURRENT_RUNNING_JOB_ID is None or job.get("id") != _CURRENT_RUNNING_JOB_ID:
                    job.update(status="queued", progress=0, message="Đang chờ vào dây chuyền", updated_at=_now())

        # Đảm bảo chỉ sản xuất tuần tự đúng 1 video tại một thời điểm
        if any(job.get("status") == "running" for job in state["jobs"]):
            return None

        for job in state["jobs"]:
            if job.get("status") == "queued":
                _CURRENT_RUNNING_JOB_ID = job["id"]
                job.update(status="running", progress=1, message="Đang khởi động dây chuyền", updated_at=_now())
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
                    _update_job(job["id"], status="queued", progress=0, message=f"{flow_message} — xưởng đã tự tạm dừng")
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
                        if j.get("id") == current_job_id and j.get("status") != "running":
                            return True
                return False

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
                    target_scenes=int(settings.get("target_scenes", 5)),
                    voice_mode=settings.get("voice_mode", "edge"),
                    voice_reference_path=settings.get("voice_reference_path", ""),
                    job_key=job["id"],
                    studio_mode=bool(settings.get("studio_mode", True)),
                    content_mode=settings.get("content_mode", "knowledge"),
                    chinese_voice=settings.get("chinese_voice", TTS_VOICE_ZH_DEFAULT),
                    turbo_mode=bool(settings.get("turbo_mode", False)),
                    flow_workers=int(settings.get("flow_workers", 2)),
                    tts_workers=int(settings.get("tts_workers", 4)),
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
                        progress=0,
                        message="Đã bỏ qua theo yêu cầu người dùng",
                        error="Đã bỏ qua theo yêu cầu người dùng",
                    )
                    continue

                editorial_report = metadata.get("editorial_report") if isinstance(metadata, dict) else {}
                skill_ids = editorial_report.get("selected_skill_ids", []) if isinstance(editorial_report, dict) else []
                record_skill_outcome(skill_ids, success)
                if success:
                    _update_job(
                        job["id"], status="completed", progress=100, message="Video và metadata đã sẵn sàng",
                        output_path=result, metadata=metadata, completed_at=_now(), error="",
                    )
                else:
                    _update_job(job["id"], status="failed", progress=0, message=str(result), error=str(result))
            except Exception as exc:
                import traceback
                safe_log(f"[FACTORY WORKER] Ngoại lệ khi thực thi job {job.get('id')}:\n{traceback.format_exc()}")
                with _LOCK:
                    was_skipped = current_job_id in _SKIP_REQUESTED_JOB_IDS
                    _SKIP_REQUESTED_JOB_IDS.discard(current_job_id)
                if was_skipped:
                    _update_job(
                        current_job_id,
                        status="failed",
                        progress=0,
                        message="Đã bỏ qua theo yêu cầu người dùng",
                        error="Đã bỏ qua theo yêu cầu người dùng",
                    )
                    continue
                _update_job(job["id"], status="failed", progress=0, message=f"Dây chuyền gặp lỗi: {exc}", error=str(exc))
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

