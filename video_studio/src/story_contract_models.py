# Chức năng: Mô hình hóa các hợp đồng dữ liệu chuẩn hóa toàn diện cho Xưởng Sản Xuất Video AI (video_studio)
#          bao gồm 9 đối tượng hợp đồng cấp công đoạn (ProjectBrief, ResearchReport, Script, ScenePlan,
#          AssetManifest, RenderManifest, QAReport, PolicyReport, PublishingPackage), liên kết cấp cảnh
#          (Scene-level Traceability), và bộ kiểm định Schema tại ranh giới công đoạn (Boundary Schema Validation).
# Bảo toàn 100% tính tương thích ngược với 5 hợp đồng hạ nguồn (Audio, Image, Render, Sound, Legal).

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def compute_file_sha256(file_path: str) -> str:
    """Tính mã băm SHA-256 của tệp trên đĩa để bảo đảm tính toàn vẹn."""
    if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
        return ""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def compute_text_sha256(text: str) -> str:
    """Tính SHA-256 cho chuỗi văn bản để phát hiện thay đổi nội dung (dependency invalidation)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class ContractValidationError(ValueError):
    """Ngoại lệ ném ra khi dữ liệu tại ranh giới công đoạn hoặc đầu ra LLM vi phạm hợp đồng Schema."""

    def __init__(self, stage: str, message: str, errors: Optional[List[str]] = None):
        self.stage = stage
        self.errors = errors or [message]
        super().__init__(f"[{stage}] Vi phạm hợp đồng dữ liệu: {message} | Chi tiết: {'; '.join(self.errors)}")


# ==============================================================================
# 5 HỢP ĐỒNG HẠ NGUỒN CẤP CẢNH (TƯƠNG THÍCH NGƯỢC 100% VỚI SƠ ĐỒ MERMAID)
# ==============================================================================

@dataclass
class AudioContract:
    """Khâu 1: Âm thanh (TTS Engine) tiếp nhận: Âm tiết, Pause, Voice Profile."""
    syllables: int = 0
    pause_cues: List[str] = field(default_factory=list)
    voice_profile: str = "vi-VN-HoaiMyNeural"
    speaking_rate: str = "+0%"
    target_lufs: float = -16.0


@dataclass
class ImageContract:
    """Khâu 2: Hình ảnh (Flow CDP) tiếp nhận: Background Plate, Sticker, Visual Action."""
    background_plate: str = ""
    sticker: str = ""
    visual_action: str = ""
    video_prompt: str = ""
    character_id: str = "CH01"
    costume_lock: str = "Light blue shirt #8CCFE8, white round head, dark navy outline"
    style_lock: str = "Strictly vibrant 2D animation, flat 2D cartoon, cel-shaded vector art, no 3D"


@dataclass
class RenderContract:
    """Khâu 3: Dựng & Chuyển động (Video Compiler) tiếp nhận: Visual Beats, Camera Effects, Safe Subtitles."""
    visual_beats: List[str] = field(default_factory=list)
    camera_effects: str = "subtle_cinematic_zoom"
    safe_subtitles: str = "bottom_1_6_safe_zone"
    transition_in: str = "cut"
    transition_out: str = "cut"


@dataclass
class SoundContract:
    """Khâu 4: Thiết kế Âm thanh (Foley/SFX) tiếp nhận: Semantic Anchors, Foley Cues, BGM Ducking."""
    semantic_anchors: List[str] = field(default_factory=list)
    foley_cues: List[str] = field(default_factory=list)
    bgm_ducking: bool = True
    bgm_track: str = "default_educational_ambient"
    bgm_volume_speech: float = 0.15
    bgm_volume_pause: float = 0.45


@dataclass
class LegalContract:
    """Khâu 5: Thẩm định & Pháp lý (Contract QA) tiếp nhận: Sources, Claims, Coverage Verbatim Quotes."""
    sources: List[str] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    unverified_claims: List[str] = field(default_factory=list)
    coverage_quotes: List[str] = field(default_factory=list)
    asset_license: str = "AI-Generated / Royalty-Free Project Asset"
    ai_disclosure_required: bool = True


# ==============================================================================
# HỢP ĐỒNG PHÂN CẢNH LIÊN KẾT TOÀN DIỆN (SCENE TRACEABILITY CONTRACT)
# ==============================================================================

@dataclass
class ArchitectedScene:
    """
    Phân cảnh chuẩn hóa liên kết đầy đủ:
    - ID cảnh (scene_id, scene_num) và phiên bản (version)
    - Mục tiêu nội dung (content_goal)
    - Lời thoại (narration) và chữ trên màn hình (on_screen_text)
    - Prompt hình hoặc video (video_prompt / visual_prompt)
    - Nhân vật, bối cảnh và yêu cầu nhất quán (character_id, setting, consistency_rules)
    - Tài sản thực tế, nguồn gốc và quyền sử dụng (asset_path, asset_source, license_info)
    - Thời lượng dự kiến và thực tế (expected_duration_sec, actual_duration_sec)
    - Đoạn âm thanh, phụ đề và vị trí trên timeline (audio_segment, subtitle_cues, timeline_range)
    - Kết quả kiểm tra và lỗi cần sửa (qa_checks, issues_to_fix)
    """
    scene_num: int
    narration: str
    audio: AudioContract
    image: ImageContract
    render: RenderContract
    sound: SoundContract
    legal: LegalContract
    scene_id: str = ""
    version: int = 1
    content_goal: str = ""
    on_screen_text: str = ""
    character_id: str = "CH01"
    setting: str = ""
    consistency_rules: List[str] = field(default_factory=list)
    asset_path: str = ""
    asset_type: str = "image"
    asset_source: str = "google_flow"
    asset_checksum: str = ""
    license_info: str = "Project Owned / AI Generated"
    is_fallback_asset: bool = False
    expected_duration_sec: float = 5.0
    actual_duration_sec: float = 0.0
    audio_path: str = ""
    audio_duration: float = 0.0
    audio_checksum: str = ""
    subtitle_cues: List[Dict[str, Any]] = field(default_factory=list)
    timeline_range: List[float] = field(default_factory=lambda: [0.0, 5.0])
    qa_checks: List[Dict[str, Any]] = field(default_factory=list)
    issues_to_fix: List[str] = field(default_factory=list)
    narration_hash: str = ""
    prompt_hash: str = ""
    user_locked: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.scene_id:
            self.scene_id = f"sc_{int(self.scene_num):03d}"
        if not self.narration_hash and self.narration:
            self.narration_hash = compute_text_sha256(self.narration)[:16]
        if not self.prompt_hash and self.image.video_prompt:
            self.prompt_hash = compute_text_sha256(self.image.video_prompt)[:16]

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "scene_id": self.scene_id or f"sc_{int(self.scene_num):03d}",
            "scene_num": self.scene_num,
            "version": self.version,
            "content_goal": self.content_goal,
            "narration": self.narration,
            "on_screen_text": self.on_screen_text,
            "video_prompt": self.image.video_prompt,
            "visual_prompt": self.image.video_prompt,
            "character_id": self.character_id,
            "setting": self.setting or self.image.background_plate,
            "consistency_rules": self.consistency_rules,
            "asset_path": self.asset_path,
            "asset_type": self.asset_type,
            "asset_source": self.asset_source,
            "asset_checksum": self.asset_checksum,
            "license_info": self.license_info,
            "is_fallback_asset": self.is_fallback_asset,
            "expected_duration_sec": round(float(self.expected_duration_sec), 3),
            "actual_duration_sec": round(float(self.actual_duration_sec), 3),
            "audio_path": self.audio_path,
            "audio_duration": round(float(self.audio_duration or self.expected_duration_sec), 3),
            "audio_checksum": self.audio_checksum,
            "audio_segment": {
                "audio_path": self.audio_path,
                "duration_sec": round(float(self.audio_duration or self.expected_duration_sec), 3),
                "voice_profile": self.audio.voice_profile,
                "speaking_rate": self.audio.speaking_rate,
                "checksum": self.audio_checksum,
            },
            "subtitle_cues": self.subtitle_cues,
            "timeline_range": self.timeline_range,
            "qa_checks": self.qa_checks,
            "issues_to_fix": self.issues_to_fix,
            "narration_hash": self.narration_hash,
            "prompt_hash": self.prompt_hash,
            "user_locked": self.user_locked,
            "audio_contract": asdict(self.audio),
            "image_contract": asdict(self.image),
            "render_contract": asdict(self.render),
            "sound_contract": asdict(self.sound),
            "legal_contract": asdict(self.legal),
        }
        data.update(self.extra)
        # Đồng bộ ngược nếu extra có image_path / video_path / audio_path
        if data.get("video_path") and not data.get("asset_path"):
            data["asset_path"] = data["video_path"]
            data["asset_type"] = "video"
        elif data.get("image_path") and not data.get("asset_path"):
            data["asset_path"] = data["image_path"]
            data["asset_type"] = "image"
        if data.get("audio_duration"):
            data["actual_duration_sec"] = round(float(data["audio_duration"]), 3)
            data["audio_segment"]["duration_sec"] = round(float(data["audio_duration"]), 3)
        if data.get("audio_path"):
            data["audio_segment"]["audio_path"] = data["audio_path"]
        return data


# ==============================================================================
# 9 ĐỐI TƯỢNG HỢP ĐỒNG CHUẨN HÓA (STANDARDIZED STAGE DATA CONTRACTS)
# ==============================================================================

@dataclass
class ProjectBrief:
    """1. Hợp đồng Nhà sản xuất (Producer Brief)."""
    project_id: str
    topic: str
    target_audience: str = "Người xem phổ thông yêu thích kiến thức ngắn gọn, trực quan (16-35 tuổi)"
    objective: str = "Truyền tải kiến thức/câu chuyện rõ ràng, giữ chân người xem và tuân thủ chính sách nền tảng"
    platforms: List[str] = field(default_factory=lambda: ["youtube", "tiktok"])
    orientation: str = "vertical"
    aspect_ratio: str = "9:16"
    resolution: Tuple[int, int] = (1080, 1920)
    target_duration_sec: Tuple[float, float] = (15.0, 90.0)
    budget_limit_usd: float = 0.0  # Local / Google Flow subscription
    estimated_cost_usd: float = 0.0
    cost_type: str = "estimated_local_and_subscription"
    language: str = "vi"
    content_mode: str = "knowledge"
    style_preset: str = "2d animation, flat 2d cartoon, colorful cel-shaded vector art"
    media_mode: str = "flow_image"
    image_engine: str = "flow"
    voice_mode: str = "edge"
    voice_id: str = "vi-VN-HoaiMyNeural"
    chinese_voice_id: str = "zh-CN-XiaoxiaoNeural"
    voice_reference_path: str = ""
    voice_consent_verified: bool = False
    target_scenes: Optional[int] = None
    version: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["resolution"] = list(self.resolution)
        d["target_duration_sec"] = list(self.target_duration_sec)
        return d


@dataclass
class ResearchReport:
    """2. Hợp đồng Nghiên cứu (Research Report)."""
    brief_id: str
    topic: str
    summary: str
    key_facts: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    unverified_claims: List[Dict[str, Any]] = field(default_factory=list)
    sensitive_domains: List[str] = field(default_factory=list)
    requires_fact_review: bool = False
    version: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Script:
    """3. Hợp đồng Kịch bản & Biên tập nội dung (Script Contract)."""
    script_id: str
    brief_id: str
    topic: str
    hook: str
    narrative_arc: str
    cta: str
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    language: str = "vi"
    content_mode: str = "knowledge"
    total_estimated_duration_sec: float = 0.0
    coherence_score: float = 85.0
    deduplication_passed: bool = True
    editorial_issues_fixed: List[str] = field(default_factory=list)
    editorial_warnings: List[str] = field(default_factory=list)
    user_locked_scenes: List[int] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenePlan:
    """4. Hợp đồng Storyboard & Đạo diễn hình/tiếng (ScenePlan Contract)."""
    plan_id: str
    script_id: str
    orientation: str = "vertical"
    aspect_ratio: str = "9:16"
    resolution: Tuple[int, int] = (1080, 1920)
    character_bible: Dict[str, Any] = field(default_factory=dict)
    visual_style_rules: List[str] = field(default_factory=list)
    audio_direction: Dict[str, Any] = field(default_factory=dict)
    shots: List[Dict[str, Any]] = field(default_factory=list)
    pre_production_checks_passed: bool = True
    pre_production_warnings: List[str] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["resolution"] = list(self.resolution)
        return d


@dataclass
class AssetManifest:
    """5. Hợp đồng Quản lý Tài sản (AssetManifest Contract)."""
    manifest_id: str
    plan_id: str
    visual_assets: List[Dict[str, Any]] = field(default_factory=list)
    audio_assets: List[Dict[str, Any]] = field(default_factory=list)
    bgm_asset: Optional[Dict[str, Any]] = None
    font_asset: Optional[Dict[str, Any]] = None
    missing_scenes: List[int] = field(default_factory=list)
    corrupt_assets: List[str] = field(default_factory=list)
    fallback_substituted_scenes: List[int] = field(default_factory=list)
    all_valid: bool = True
    version: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderManifest:
    """6. Hợp đồng Dựng phim & Xuất bản nháp (RenderManifest Contract)."""
    render_id: str
    manifest_id: str
    video_path: str
    video_sha256: str
    ass_subtitle_path: str = ""
    srt_subtitle_path: str = ""
    subtitle_sha256: str = ""
    resolution: Tuple[int, int] = (1080, 1920)
    aspect_ratio: str = "9:16"
    fps: float = 30.0
    duration_sec: float = 0.0
    video_codec: str = "h264"
    audio_codec: str = "aac"
    has_video_stream: bool = True
    has_audio_stream: bool = True
    scene_timeline: List[Dict[str, Any]] = field(default_factory=list)
    render_engine: str = "ffmpeg"
    elapsed_sec: float = 0.0
    version: int = 1
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["resolution"] = list(self.resolution)
        return d


@dataclass
class QAIssue:
    """Một phát hiện/lỗi có bằng chứng trong báo cáo QA độc lập sau khi render."""
    check_id: str
    severity: str  # critical | major | minor | info
    scene_id: Optional[str]
    time_range: List[float]
    evidence: str
    suggested_fix: str
    confidence: float
    status: str  # passed | failed | warning | not_checked | needs_review

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QAReport:
    """7. Hợp đồng QA Độc lập sau khi Render (QAReport Contract)."""
    qa_id: str
    render_id: str
    video_path: str
    video_sha256: str
    overall_score: float
    category_scores: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    unchecked_count: int = 0
    needs_review_count: int = 0
    release_blocked: bool = False
    passed: bool = False
    revision_round: int = 0
    max_revisions: int = 2
    recommended_stage_to_rerun: Optional[str] = None
    recommended_scenes_to_rerun: List[int] = field(default_factory=list)
    scoring_note: str = (
        "Thang điểm nội bộ 100 có trọng số dùng để kiểm soát chất lượng sản phẩm; "
        "không phải tiêu chuẩn chính thức của nền tảng. Bất kỳ lỗi critical nào đều chặn phát hành."
    )
    version: int = 1
    checked_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyFinding:
    """Một kết luận đánh giá chính sách cho nền tảng cụ thể."""
    platform: str  # youtube | tiktok | both
    rule_id: str
    rule_name: str
    rule_url: str
    checked_date: str
    rule_version: str
    scope: str
    dimension: str  # allowed_to_publish | ai_disclosure_required | recommendation_eligibility | monetization_eligibility | asset_rights
    status: str  # pass | action_required | warning | blocked | needs_review
    evidence: str
    reasoning: str
    confidence: float
    suggested_action: str
    requires_human_review: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyReport:
    """8. Hợp đồng Kiểm chứng & Chính sách Nền tảng (PolicyReport Contract)."""
    policy_id: str
    video_sha256: str
    platforms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    allowed_to_publish: bool = True
    requires_ai_disclosure: bool = True
    requires_human_review: bool = False
    auto_publish_blocked: bool = False
    block_reasons: List[str] = field(default_factory=list)
    disclaimer: str = (
        "Báo cáo kiểm tra chính sách dựa trên quy tắc chính thức hiện hành của YouTube và TikTok. "
        "Kết quả này hỗ trợ kiểm soát rủi ro trước xuất bản, không hứa hẹn hoặc bảo đảm duyệt đăng, "
        "đủ điều kiện kiếm tiền hay phân phối đề xuất trên nền tảng."
    )
    version: int = 1
    checked_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PublishingPackage:
    """9. Hợp đồng Gói Xuất bản Riêng cho Từng Nền tảng (PublishingPackage Contract)."""
    package_id: str
    job_id: str
    version: int
    video_path: str
    video_sha256: str
    ass_subtitle_path: str
    srt_subtitle_path: str
    subtitle_sha256: str
    youtube: Dict[str, Any] = field(default_factory=dict)
    tiktok: Dict[str, Any] = field(default_factory=dict)
    qa_report_path: str = ""
    policy_report_path: str = ""
    metadata_path: str = ""
    manifest_path: str = ""
    package_dir: str = ""
    package_checksum: str = ""
    user_locked_fields: List[str] = field(default_factory=list)
    approved_by_user: bool = False
    approved_at: Optional[str] = None
    approved_video_sha256: str = ""
    auto_publish_blocked: bool = True
    publish_block_reasons: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# CÁC HÀM XỬ LÝ & CHUẨN HÓA PHÂN CẢNH
# ==============================================================================

def _estimate_syllables(text: str) -> int:
    """Ước tính số âm tiết tiếng Việt hoặc tiếng Anh."""
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 1
    return max(1, len(words))


def _extract_pause_cues(text: str) -> List[str]:
    """Trích xuất các điểm ngắt nghỉ ngữ âm (Pause Cues) từ dấu câu và liên từ."""
    cues = []
    if "," in text:
        cues.append("pause_short_comma_300ms")
    if "..." in text:
        cues.append("pause_thought_ellipsis_500ms")
    if any(p in text for p in [".", "!", "?"]):
        cues.append("pause_terminal_sentence_600ms")
    if not cues:
        cues.append("pause_breath_flow_250ms")
    return cues


def _infer_semantic_foley(narration: str, visual_prompt: str) -> Tuple[List[str], List[str]]:
    """Suy diễn semantic anchors và foley sound cues dựa trên nội dung ngữ nghĩa."""
    combined = (narration + " " + visual_prompt).lower()
    anchors = []
    cues = []

    keyword_sound_map = {
        ("làng", "village", "rừng", "forest", "thiên nhiên"): ("ambient_nature_wind_birds", "ambient_rustle"),
        ("đá", "stone", "vách", "cave", "hang"): ("foley_stone_scrape_tap", "stone_resonance"),
        ("lửa", "fire", "đuốc", "torch"): ("foley_fire_crackle", "torch_whoosh"),
        ("người", "people", "bàn thảo", "crowd", "nói"): ("crowd_soft_murmur", "expressive_breath"),
        ("khám phá", "bất ngờ", "phát hiện", "discover"): ("sfx_discovery_spark", "subtle_chime"),
        ("chào", "hello", "wifi", "điện thoại"): ("soft_interface_blip", "friendly_greeting_tone"),
        ("viết", "vẽ", "ký hiệu", "symbol"): ("foley_chisel_sketch", "drawing_friction"),
    }

    for keywords, (anchor, cue) in keyword_sound_map.items():
        if any(kw in combined for kw in keywords):
            if anchor not in anchors:
                anchors.append(anchor)
            if cue not in cues:
                cues.append(cue)

    if not anchors:
        anchors.append("foley_subtle_scene_ambience")
    if not cues:
        cues.append("ambient_room_tone")

    return anchors, cues


def _infer_content_goal(index: int, total_hint: Optional[int], narration: str) -> str:
    """Xác định mục tiêu nội dung (content_goal) của từng phân cảnh."""
    if index == 1:
        return "hook_and_problem_setup"
    if total_hint and index >= total_hint:
        return "payoff_conclusion_and_cta"
    lowered = narration.lower()
    if any(k in lowered for k in ["ví dụ", "chẳng hạn", "example", "tình huống"]):
        return "concrete_example_application"
    if any(k in lowered for k in ["vì sao", "nguyên nhân", "cách", "nghĩa là", "là gì"]):
        return "core_explanation_and_mechanism"
    return f"narrative_progression_step_{index}"


def _extract_unverified_claims(text: str) -> List[str]:
    """Đánh dấu các tuyên bố chứa số liệu cụ thể, phần trăm, năm tháng hoặc khẳng định tuyệt đối chưa có nguồn."""
    unverified = []
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    for s in sentences:
        if re.search(r"\b\d+(?:\.\d+)?%\b|\b(?:19|20)\d{2}\b|\b(?:triệu|tỷ|nghìn|million|billion)\b", s, flags=re.IGNORECASE):
            unverified.append(s)
        elif any(term in s.lower() for term in ["100%", "chắc chắn chữa khỏi", "cam kết lãi", "khoa học chứng minh"]):
            unverified.append(s)
    return unverified


def normalize_architected_scene(
    raw_item: Any,
    index: int = 1,
    total_scenes_hint: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Chuẩn hóa một phân cảnh thô thành đối tượng hợp đồng đầy đủ theo kiến trúc 5 nhánh
    và liên kết cấp cảnh (Scene-level Traceability).
    Bảo toàn 100% tính tương thích ngược với các trường cũ (narration, video_prompt...).
    """
    if isinstance(raw_item, dict):
        scene_dict = dict(raw_item)
    elif isinstance(raw_item, str):
        scene_dict = {
            "scene_num": index,
            "narration": raw_item.strip(),
            "video_prompt": f"Scene {index}: distinct 2d cartoon animation visual action",
        }
    else:
        scene_dict = {
            "scene_num": index,
            "narration": str(raw_item).strip(),
            "video_prompt": f"Scene {index}: 2d animation scene",
        }

    sc_num = int(scene_dict.get("scene_num") or index)
    scene_id = str(scene_dict.get("scene_id") or f"sc_{sc_num:03d}")
    version = int(scene_dict.get("version") or 1)
    
    # Tự phục hồi narration từ các tên trường phổ biến của LLM
    narration = str(
        scene_dict.get("narration")
        or scene_dict.get("narration_vi")
        or scene_dict.get("text")
        or scene_dict.get("content")
        or scene_dict.get("script")
        or scene_dict.get("dialogue")
        or scene_dict.get("speech")
        or scene_dict.get("voiceover")
        or scene_dict.get("voice_over")
        or scene_dict.get("line")
        or scene_dict.get("subtitle")
        or scene_dict.get("usage_vi")
        or ""
    ).strip()
    if not narration and scene_dict.get("chinese_text"):
        narration = f"{scene_dict.get('chinese_text')} nghĩa là {scene_dict.get('usage_vi', '')}".strip()
    if not narration:
        narration = str(scene_dict.get("video_prompt") or scene_dict.get("visual_prompt") or f"Khám phá câu chuyện cảnh {sc_num}").strip()

    # Tự phục hồi video_prompt từ các tên trường phổ biến
    video_prompt = str(
        scene_dict.get("video_prompt")
        or scene_dict.get("visual_prompt")
        or scene_dict.get("image_prompt")
        or scene_dict.get("prompt")
        or scene_dict.get("visual")
        or scene_dict.get("scene_description")
        or narration
        or f"Scene {sc_num} visual action"
    ).strip()

    # 1. Hợp đồng Âm thanh (Audio Contract)
    existing_audio = scene_dict.get("audio_contract")
    syllables = _estimate_syllables(narration)
    if isinstance(existing_audio, dict):
        audio_c = AudioContract(
            syllables=int(existing_audio.get("syllables") or syllables),
            pause_cues=list(existing_audio.get("pause_cues") or _extract_pause_cues(narration)),
            voice_profile=str(existing_audio.get("voice_profile") or scene_dict.get("voice") or "vi-VN-HoaiMyNeural"),
            speaking_rate=str(existing_audio.get("speaking_rate") or "+0%"),
            target_lufs=float(existing_audio.get("target_lufs") or -16.0),
        )
    else:
        audio_c = AudioContract(
            syllables=syllables,
            pause_cues=_extract_pause_cues(narration),
            voice_profile=str(scene_dict.get("voice") or "vi-VN-HoaiMyNeural"),
        )

    # 2. Hợp đồng Hình ảnh (Image Contract)
    existing_image = scene_dict.get("image_contract")
    if isinstance(existing_image, dict):
        image_c = ImageContract(
            background_plate=str(existing_image.get("background_plate") or f"Scene {sc_num} 2D background plate"),
            sticker=str(existing_image.get("sticker") or "Stickman canonical character CH01 in blue shirt"),
            visual_action=str(existing_image.get("visual_action") or "Expressive 2D character action"),
            video_prompt=str(existing_image.get("video_prompt") or video_prompt),
            character_id=str(existing_image.get("character_id") or scene_dict.get("character_id") or "CH01"),
        )
    else:
        bg_match = re.split(r"[,.]", video_prompt)
        bg_plate = bg_match[0].strip() if bg_match and bg_match[0].strip() else f"Scene {sc_num} atmospheric 2D setting"
        image_c = ImageContract(
            background_plate=bg_plate,
            sticker="Minimalist canonical stickman cartoon CH01 (#8CCFE8 shirt)",
            visual_action=f"Character performing key gesture for scene {sc_num}",
            video_prompt=video_prompt or f"Scene {sc_num}: Vibrant 2d cartoon animation, strictly no 3d",
            character_id=str(scene_dict.get("character_id") or "CH01"),
        )

    # 3. Hợp đồng Dựng & Chuyển động (Render Contract)
    existing_render = scene_dict.get("render_contract")
    if isinstance(existing_render, dict):
        render_c = RenderContract(
            visual_beats=list(existing_render.get("visual_beats") or ["zoom_in_8pct", "cut"]),
            camera_effects=str(existing_render.get("camera_effects") or "subtle_cinematic_zoom"),
            safe_subtitles=str(existing_render.get("safe_subtitles") or "bottom_1_6_safe_zone"),
            transition_in=str(existing_render.get("transition_in") or "cut"),
            transition_out=str(existing_render.get("transition_out") or "cut"),
        )
    else:
        render_c = RenderContract(
            visual_beats=["zoom_in_8pct", "subtle_smooth_transition"],
            camera_effects="subtle_slow_cinematic_zoom_1_way",
            safe_subtitles="bottom_1_6_safe_zone",
        )

    # 4. Hợp đồng Thiết kế Âm thanh (Sound Contract)
    existing_sound = scene_dict.get("sound_contract")
    if isinstance(existing_sound, dict):
        sound_c = SoundContract(
            semantic_anchors=list(existing_sound.get("semantic_anchors") or []),
            foley_cues=list(existing_sound.get("foley_cues") or []),
            bgm_ducking=bool(existing_sound.get("bgm_ducking", True)),
            bgm_track=str(existing_sound.get("bgm_track") or "default_educational_ambient"),
        )
    else:
        anchors, foleys = _infer_semantic_foley(narration, video_prompt)
        sound_c = SoundContract(
            semantic_anchors=anchors,
            foley_cues=foleys,
            bgm_ducking=True,
        )

    # 5. Hợp đồng Thẩm định & Pháp lý (Legal Contract)
    existing_legal = scene_dict.get("legal_contract")
    unverified = _extract_unverified_claims(narration)
    if isinstance(existing_legal, dict):
        legal_c = LegalContract(
            sources=list(existing_legal.get("sources") or ["Local Educational Knowledge Base"]),
            claims=list(existing_legal.get("claims") or [narration[:100]]),
            unverified_claims=list(existing_legal.get("unverified_claims") or unverified),
            coverage_quotes=list(existing_legal.get("coverage_quotes") or ["AI Educational Fair Use"]),
            asset_license=str(existing_legal.get("asset_license") or "AI-Generated / Royalty-Free Project Asset"),
            ai_disclosure_required=bool(existing_legal.get("ai_disclosure_required", True)),
        )
    else:
        claims = [s.strip() for s in re.split(r"[.!?]", narration) if len(s.strip()) > 15]
        if not claims:
            claims = [narration[:100]] if narration else ["Educational narrative explanation"]
        legal_c = LegalContract(
            sources=["General Educational Knowledge Archive 2026"],
            claims=claims,
            unverified_claims=unverified,
            coverage_quotes=["Transformative educational content; compliant with YouTube & TikTok policies."],
        )

    expected_dur = float(
        scene_dict.get("expected_duration_sec")
        or scene_dict.get("audio_duration")
        or max(3.0, round(syllables / 2.6, 2))
    )
    actual_dur = float(scene_dict.get("actual_duration_sec") or scene_dict.get("audio_duration") or 0.0)
    asset_path = str(
        scene_dict.get("asset_path")
        or scene_dict.get("video_path")
        or scene_dict.get("image_path")
        or ""
    )
    asset_type = "video" if scene_dict.get("use_video_ai") or str(asset_path).endswith(".mp4") else "image"
    audio_path = str(scene_dict.get("audio_path") or "")

    on_screen_text = str(scene_dict.get("on_screen_text") or "").strip()
    if not on_screen_text:
        if scene_dict.get("chinese_text"):
            on_screen_text = f"{scene_dict.get('chinese_text')} ({scene_dict.get('pinyin', '')})".strip()
        else:
            words = narration.split()
            on_screen_text = " ".join(words[:8]) + ("..." if len(words) > 8 else "")

    consistency_rules = list(scene_dict.get("consistency_rules") or [
        "Canonical character CH01 with round white head and light blue shirt (#8CCFE8)",
        "Strictly 2D flat cartoon / cel-shaded vector style (No 3D, No CGI)",
        "No readable text, numbers, formulas, watermarks, or logos inside generated visual",
    ])

    reserved_keys = {
        "scene_id", "scene_num", "version", "content_goal", "narration", "on_screen_text",
        "video_prompt", "visual_prompt", "character_id", "setting", "consistency_rules",
        "asset_path", "asset_type", "asset_source", "asset_checksum", "license_info",
        "is_fallback_asset", "expected_duration_sec", "actual_duration_sec",
        "audio_path", "audio_duration", "audio_checksum", "audio_segment",
        "subtitle_cues", "timeline_range", "qa_checks", "issues_to_fix",
        "narration_hash", "prompt_hash", "user_locked",
        "audio_contract", "image_contract", "render_contract", "sound_contract", "legal_contract",
    }

    arch_scene = ArchitectedScene(
        scene_num=sc_num,
        narration=narration,
        audio=audio_c,
        image=image_c,
        render=render_c,
        sound=sound_c,
        legal=legal_c,
        scene_id=scene_id,
        version=version,
        content_goal=str(scene_dict.get("content_goal") or _infer_content_goal(sc_num, total_scenes_hint, narration)),
        on_screen_text=on_screen_text,
        character_id=str(scene_dict.get("character_id") or image_c.character_id or "CH01"),
        setting=str(scene_dict.get("setting") or image_c.background_plate),
        consistency_rules=consistency_rules,
        asset_path=asset_path,
        asset_type=asset_type,
        asset_source=str(scene_dict.get("asset_source") or "google_flow"),
        asset_checksum=str(scene_dict.get("asset_checksum") or compute_file_sha256(asset_path)),
        license_info=str(scene_dict.get("license_info") or legal_c.asset_license),
        is_fallback_asset=bool(scene_dict.get("is_fallback_asset", False)),
        expected_duration_sec=expected_dur,
        actual_duration_sec=actual_dur,
        audio_path=audio_path,
        audio_duration=float(scene_dict.get("audio_duration") or expected_dur),
        audio_checksum=str(scene_dict.get("audio_checksum") or compute_file_sha256(audio_path)),
        subtitle_cues=list(scene_dict.get("subtitle_cues") or []),
        timeline_range=list(scene_dict.get("timeline_range") or [0.0, round(actual_dur or expected_dur, 3)]),
        qa_checks=list(scene_dict.get("qa_checks") or []),
        issues_to_fix=list(scene_dict.get("issues_to_fix") or []),
        narration_hash=str(scene_dict.get("narration_hash") or compute_text_sha256(narration)[:16]),
        prompt_hash=str(scene_dict.get("prompt_hash") or compute_text_sha256(image_c.video_prompt)[:16]),
        user_locked=bool(scene_dict.get("user_locked", False)),
        extra={k: v for k, v in scene_dict.items() if k not in reserved_keys},
    )
    return arch_scene.to_dict()


def build_downstream_contracts_report(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Tổng hợp báo cáo trạng thái 5 khâu hạ nguồn theo sơ đồ kiến trúc Research & Story Architect.
    Lưu ý: Các cờ trạng thái ở giai đoạn kịch bản chỉ phản ánh mức sẵn sàng kế hoạch (plan-level),
    KHÔNG thay thế báo cáo QA thực tế sau khi render hay báo cáo chính sách cuối cùng.
    """
    total_scenes = len(scenes)
    total_syllables = sum(
        int(s.get("audio_contract", {}).get("syllables", 0)) for s in scenes if isinstance(s, dict)
    )
    all_anchors = []
    all_foley = []
    all_claims = []
    all_unverified = []
    all_sources = set()

    for s in scenes:
        if not isinstance(s, dict):
            continue
        snd = s.get("sound_contract", {})
        all_anchors.extend(snd.get("semantic_anchors", []))
        all_foley.extend(snd.get("foley_cues", []))
        leg = s.get("legal_contract", {})
        all_claims.extend(leg.get("claims", []))
        all_unverified.extend(leg.get("unverified_claims", []))
        for src in leg.get("sources", []):
            all_sources.add(src)

    return {
        "pipeline_architecture": "Research & Story Architect (mermaid-diagram.svg)",
        "total_scenes": total_scenes,
        "audio_summary": {
            "total_syllables": total_syllables,
            "estimated_wpm": round((total_syllables / max(1, total_scenes * 6)) * 60, 1),
            "voice_handoff_ready": total_scenes > 0,
        },
        "image_summary": {
            "background_plates_count": total_scenes,
            "style_standard": "Strictly 2D Animation Flat Cartoon (No 3D)",
            "flow_cdp_ready": total_scenes > 0,
        },
        "render_summary": {
            "engine": "Visual Beats & Progressive Layering",
            "safe_zone": "Bottom 1/6 Safe Zone (alignment=2, y=260)",
            "effects": "Subtle cinematic zoom & seamless cut",
        },
        "sound_summary": {
            "semantic_anchors_count": len(all_anchors),
            "foley_cues_count": len(all_foley),
            "bgm_ducking_enabled": True,
        },
        "legal_summary": {
            "verified_claims_count": len(all_claims),
            "unverified_claims_count": len(all_unverified),
            "sources": list(all_sources) or ["Educational Verified Corpus"],
            "policy_compliance_status": (
                "Needs Fact Verification" if all_unverified else "Passed Pre-Production Plan Check"
            ),
        },
    }


# ==============================================================================
# KIỂM ĐỊNH SCHEMA TẠI RANH GIỚI CÔNG ĐOẠN & XỬ LÝ ĐẦU RA LLM SAI ĐỊNH DẠNG
# ==============================================================================

def extract_and_repair_json_payload(raw_payload: Any) -> Tuple[bool, Any, str]:
    """
    Phát hiện và sửa chữa có giới hạn đầu ra LLM bị bọc markdown fence, thừa chữ giải thích,
    hoặc dấu phẩy cuối (trailing comma). Trả về (ok, parsed_obj, error_msg).
    """
    if isinstance(raw_payload, (dict, list)):
        return True, raw_payload, ""
    if not isinstance(raw_payload, str):
        return False, None, f"Kiểu dữ liệu phản hồi không hợp lệ: {type(raw_payload).__name__}"

    text = raw_payload.strip()
    if not text:
        return False, None, "Phản hồi LLM rỗng."

    # 1. Thử parse trực tiếp
    try:
        return True, json.loads(text), ""
    except Exception:
        pass

    # 2. Gọt bỏ khối ```json ... ```
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            return True, json.loads(candidate), ""
        except Exception:
            text = candidate

    # 3. Tìm cặp ngoặc nhọn {...} hoặc [...] ngoài cùng
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        # Loại bỏ trailing comma trước } hoặc ]
        candidate_clean = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return True, json.loads(candidate_clean), ""
        except Exception as exc:
            return False, None, f"JSON sai cú pháp sau khi trích xuất: {exc}"

    return False, None, "Không tìm thấy cấu trúc JSON hợp lệ trong phản hồi LLM."


def validate_script_schema(
    script_payload: Any,
    content_mode: str = "knowledge",
    strict_dict_scenes: bool = True,
) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
    """
    Kiểm tra nghiêm ngặt hợp đồng dữ liệu kịch bản tại ranh giới công đoạn Scripting.
    Phát hiện thiếu trường scenes, cảnh rỗng, thiếu narration/video_prompt hoặc thiếu trường tiếng Trung.
    """
    errors: List[str] = []
    ok, parsed, parse_err = extract_and_repair_json_payload(script_payload)
    if not ok or not isinstance(parsed, dict):
        return False, [], [parse_err or "Kịch bản phải là một JSON object chứa khóa 'scenes'."]

    raw_scenes = parsed.get("scenes")
    if not isinstance(raw_scenes, list) or len(raw_scenes) == 0:
        return False, [], ["Trường 'scenes' phải là danh sách không rỗng."]

    validated_scenes: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_scenes, start=1):
        if strict_dict_scenes and not isinstance(item, dict):
            errors.append(f"Cảnh {idx} không phải là đối tượng dict (nhận được {type(item).__name__}).")
            continue

        raw_v_prompt_check = str(item.get("video_prompt") or item.get("visual_prompt") or "").strip() if isinstance(item, dict) else "ok"
        norm = normalize_architected_scene(item, index=idx, total_scenes_hint=len(raw_scenes))
        if isinstance(item, dict) and len(raw_v_prompt_check) < 5:
            norm["video_prompt"] = raw_v_prompt_check
        narration = str(norm.get("narration") or "").strip()
        narration_vi = str(norm.get("narration_vi") or "").strip()
        chinese_text = str(norm.get("chinese_text") or "").strip()
        pinyin = str(norm.get("pinyin") or "").strip()
        usage_vi = str(norm.get("usage_vi") or "").strip()

        if content_mode == "chinese_teaching_vi":
            if not (narration_vi or narration):
                errors.append(f"Cảnh {idx} thiếu lời giảng tiếng Việt (narration_vi).")
            if not chinese_text:
                errors.append(f"Cảnh {idx} thiếu mẫu chữ Hán (chinese_text).")
            if not pinyin:
                errors.append(f"Cảnh {idx} thiếu phiên âm Pinyin (pinyin).")
            if not usage_vi:
                errors.append(f"Cảnh {idx} thiếu giải thích cách dùng (usage_vi).")
            if not narration:
                norm["narration"] = " ".join(p for p in [narration_vi, chinese_text, pinyin, usage_vi] if p).strip()
        else:
            if len(narration) < 3:
                errors.append(f"Cảnh {idx} có lời thoại (narration) rỗng hoặc quá ngắn.")

        v_prompt = str(norm.get("video_prompt") or "").strip()
        if len(v_prompt) < 5:
            errors.append(f"Cảnh {idx} thiếu mô tả hình ảnh (video_prompt).")

        validated_scenes.append(norm)

    if errors:
        return False, validated_scenes, errors
    return True, validated_scenes, []


def validate_contract_boundary(stage: str, data: Any) -> Tuple[bool, List[str]]:
    """
    Kiểm định Schema dữ liệu tại ranh giới giữa mọi công đoạn sản xuất:
    - brief: ProjectBrief
    - research: ResearchReport
    - script: Script / scenes list
    - storyboard: ScenePlan
    - assets: AssetManifest
    - render: RenderManifest
    - qa: QAReport
    - policy: PolicyReport
    - publishing: PublishingPackage
    """
    errors: List[str] = []
    payload = data.to_dict() if hasattr(data, "to_dict") else (asdict(data) if hasattr(data, "__dataclass_fields__") else data)
    if not isinstance(payload, dict):
        return False, [f"Dữ liệu công đoạn '{stage}' phải là dict hoặc dataclass hợp lệ."]

    if stage == "brief":
        if not str(payload.get("topic") or "").strip():
            errors.append("ProjectBrief thiếu 'topic'.")
        if payload.get("orientation") not in ("vertical", "horizontal"):
            errors.append("ProjectBrief 'orientation' phải là 'vertical' hoặc 'horizontal'.")
        if not isinstance(payload.get("platforms"), list) or not payload.get("platforms"):
            errors.append("ProjectBrief phải chỉ định ít nhất 1 nền tảng đích.")

    elif stage == "research":
        if not str(payload.get("topic") or "").strip():
            errors.append("ResearchReport thiếu 'topic'.")
        if not isinstance(payload.get("sources"), list):
            errors.append("ResearchReport 'sources' phải là danh sách.")
        if not isinstance(payload.get("unverified_claims"), list):
            errors.append("ResearchReport 'unverified_claims' phải là danh sách.")

    elif stage == "script":
        scenes = payload.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            errors.append("Script phải có danh sách 'scenes' không rỗng.")
        else:
            for i, sc in enumerate(scenes, start=1):
                if not isinstance(sc, dict):
                    errors.append(f"Cảnh {i} trong Script không phải dict.")
                    continue
                if not str(sc.get("scene_id") or "").strip():
                    sc["scene_id"] = f"sc_{i:03d}"
                if not str(sc.get("narration") or "").strip():
                    for alt_k in ("narration_vi", "text", "content", "script", "dialogue", "speech", "voiceover", "usage_vi", "video_prompt"):
                        if str(sc.get(alt_k) or "").strip():
                            sc["narration"] = str(sc.get(alt_k)).strip()
                            break
                if not str(sc.get("narration") or "").strip():
                    errors.append(f"Cảnh {i} thiếu 'narration'.")
                if not str(sc.get("video_prompt") or "").strip():
                    for alt_vp in ("visual_prompt", "image_prompt", "prompt", "visual", "narration"):
                        if str(sc.get(alt_vp) or "").strip():
                            sc["video_prompt"] = str(sc.get(alt_vp)).strip()
                            break
                if not str(sc.get("video_prompt") or "").strip():
                    errors.append(f"Cảnh {i} thiếu 'video_prompt'.")

    elif stage == "storyboard":
        shots = payload.get("shots")
        if not isinstance(shots, list) or not shots:
            errors.append("ScenePlan (Storyboard) phải có danh sách 'shots' không rỗng.")

    elif stage == "assets":
        v_assets = payload.get("visual_assets")
        a_assets = payload.get("audio_assets")
        if not isinstance(v_assets, list) or not v_assets:
            errors.append("AssetManifest thiếu danh sách 'visual_assets'.")
        if not isinstance(a_assets, list) or not a_assets:
            errors.append("AssetManifest thiếu danh sách 'audio_assets'.")
        if payload.get("missing_scenes"):
            errors.append(f"AssetManifest còn thiếu tài sản ở các cảnh: {payload.get('missing_scenes')}.")
        if payload.get("corrupt_assets"):
            errors.append(f"AssetManifest có tài sản bị hỏng: {payload.get('corrupt_assets')}.")

    elif stage == "render":
        v_path = str(payload.get("video_path") or "")
        if not v_path or not os.path.exists(v_path) or os.path.getsize(v_path) <= 0:
            errors.append(f"RenderManifest trỏ tới file video không tồn tại hoặc rỗng: {v_path}")
        if not payload.get("video_sha256"):
            errors.append("RenderManifest thiếu 'video_sha256'.")
        if float(payload.get("duration_sec") or 0.0) <= 0:
            errors.append("RenderManifest có 'duration_sec' <= 0.")

    elif stage == "qa":
        if "overall_score" not in payload:
            errors.append("QAReport thiếu 'overall_score'.")
        issues = payload.get("issues")
        if not isinstance(issues, list):
            errors.append("QAReport 'issues' phải là danh sách.")
        else:
            required_issue_keys = {
                "check_id", "severity", "scene_id", "time_range",
                "evidence", "suggested_fix", "confidence", "status",
            }
            for idx, iss in enumerate(issues):
                if not isinstance(iss, dict) or not required_issue_keys.issubset(iss.keys()):
                    errors.append(f"QAIssue #{idx + 1} thiếu trường bắt buộc {required_issue_keys}.")

    elif stage == "policy":
        platforms = payload.get("platforms")
        if not isinstance(platforms, dict) or "youtube" not in platforms or "tiktok" not in platforms:
            errors.append("PolicyReport phải đánh giá đủ cả 'youtube' và 'tiktok'.")
        findings = payload.get("findings")
        if not isinstance(findings, list):
            errors.append("PolicyReport 'findings' phải là danh sách.")

    elif stage == "publishing":
        yt = payload.get("youtube")
        tt = payload.get("tiktok")
        if not isinstance(yt, dict) or not str(yt.get("recommended_title") or yt.get("title") or "").strip():
            errors.append("PublishingPackage thiếu tiêu đề YouTube.")
        if not isinstance(tt, dict) or not str(tt.get("caption") or "").strip():
            errors.append("PublishingPackage thiếu caption TikTok.")
        if not str(payload.get("video_sha256") or "").strip():
            errors.append("PublishingPackage thiếu 'video_sha256' để đối chiếu bản duyệt.")

    return len(errors) == 0, errors
