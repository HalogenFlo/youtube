# Chức năng: Kiểm thử cấu hình, interface và các tham số điều khiển của Chế độ Turbo Batch.
# Lý do tạo: Đảm bảo độ tin cậy và tính tương thích ngược cho cấu hình hệ thống và UI.

import pytest
from src.config import (
    TURBO_BATCH_ENABLED,
    TURBO_FLOW_QUEUE_SIZE_DEFAULT,
    TURBO_TTS_WORKERS_DEFAULT,
)
from src.batch_producer import produce_single_video_pipeline, run_batch_video_loop
from src.autonomous_factory import add_factory_jobs, get_factory_state, set_factory_paused


def test_turbo_config_constants():
    """Kiểm tra các hằng số cấu hình Turbo Batch trong config.py."""
    assert TURBO_BATCH_ENABLED is True
    assert TURBO_FLOW_QUEUE_SIZE_DEFAULT == 4
    assert TURBO_TTS_WORKERS_DEFAULT == 4


def test_batch_producer_pipeline_signature():
    """Kiểm tra produce_single_video_pipeline chấp nhận các tham số Turbo Batch."""
    import inspect
    sig = inspect.signature(produce_single_video_pipeline)
    assert "turbo_mode" in sig.parameters
    assert sig.parameters["turbo_mode"].default is False
    assert "flow_workers" in sig.parameters
    assert sig.parameters["flow_workers"].default == 4
    assert "tts_workers" in sig.parameters
    assert sig.parameters["tts_workers"].default == 4


def test_run_batch_video_loop_signature():
    """Kiểm tra run_batch_video_loop chấp nhận các tham số Turbo Batch."""
    import inspect
    sig = inspect.signature(run_batch_video_loop)
    assert "turbo_mode" in sig.parameters
    assert sig.parameters["turbo_mode"].default is False
    assert "flow_workers" in sig.parameters
    assert "tts_workers" in sig.parameters


def test_autonomous_factory_add_jobs_persists_turbo_settings(tmp_path, monkeypatch):
    """Kiểm tra add_factory_jobs lưu trữ chính xác các tham số turbo vào settings của từng job."""
    test_state_file = tmp_path / "test_factory_state.json"
    monkeypatch.setattr("src.autonomous_factory.STATE_PATH", test_state_file)
    monkeypatch.setattr("src.autonomous_factory.ensure_factory_worker", lambda: None)

    set_factory_paused(True)  # Tránh worker chạy thật trong test
    job_ids = add_factory_jobs(
        prompt="Chủ đề kiểm thử Turbo Settings",
        count=1,
        turbo_mode=True,
        flow_workers=3,
        tts_workers=2,
    )
    assert len(job_ids) == 1
    target_id = job_ids[0]

    state = get_factory_state()
    matched = [j for j in state["jobs"] if j["id"] == target_id]
    assert len(matched) == 1
    job = matched[0]
    settings = job.get("settings", {})
    assert settings.get("turbo_mode") is True
    assert settings.get("flow_workers") == 3
    assert settings.get("tts_workers") == 2
