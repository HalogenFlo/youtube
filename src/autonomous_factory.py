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
from src.config import DEFAULT_IMAGE_STYLE, OUTPUT_DIR, TEMP_DIR, TTS_VOICE_DEFAULT
from src.flow_browser_service import get_flow_controller, get_flow_readiness


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
    temp_path = STATE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, STATE_PATH)


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
    with _LOCK:
        state = _load_unlocked()
        if state.get("paused"):
            return None
        for job in state["jobs"]:
            if job.get("status") == "queued":
                job.update(status="running", progress=1, message="Đang khởi động dây chuyền", updated_at=_now())
                job["attempts"] = int(job.get("attempts", 0)) + 1
                _save_unlocked(state)
                return deepcopy(job)
    return None


def _worker_loop() -> None:
    FACTORY_WORK_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        job = _next_job()
        if not job:
            _WAKE_EVENT.wait(timeout=3.0)
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

        def progress_callback(percent: float, message: str) -> None:
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
                progress_callback=progress_callback,
            )
            if success:
                _update_job(
                    job["id"], status="completed", progress=100, message="Video và metadata đã sẵn sàng",
                    output_path=result, metadata=metadata, completed_at=_now(),
                )
            else:
                _update_job(job["id"], status="failed", progress=0, message=str(result), error=str(result))
        except Exception as exc:
            _update_job(job["id"], status="failed", progress=0, message=f"Dây chuyền gặp lỗi: {exc}", error=str(exc))


def ensure_factory_worker() -> threading.Thread:
    global _WORKER_THREAD
    with _LOCK:
        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            return _WORKER_THREAD
        recover_interrupted_jobs()
        _WORKER_THREAD = threading.Thread(target=_worker_loop, name="video-factory-worker", daemon=True)
        _WORKER_THREAD.start()
        return _WORKER_THREAD
