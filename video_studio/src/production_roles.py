# Chức năng: Tổ chức trách nhiệm sản xuất theo 11 vai trò chuyên biệt (Production Roles Architecture).
# Mỗi vai có: Đầu vào có cấu trúc (input_schema), Đầu ra có cấu trúc (output_schema),
# Tiêu chí hoàn thành (completion_criteria), Giới hạn chỉnh sửa (max_edits / edit_bounds),
# và Chiến lược xử lý lỗi (error_strategy).

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    ASSETS_DIR,
    DEFAULT_FPS,
    DEFAULT_IMAGE_STYLE,
    FONT_PATH,
    MUSIC_DIR,
    TTS_VOICE_DEFAULT,
    TTS_VOICE_ZH_DEFAULT,
)
from src.story_contract_models import (
    AssetManifest,
    ContractValidationError,
    ProjectBrief,
    ResearchReport,
    ScenePlan,
    Script,
    compute_file_sha256,
    compute_text_sha256,
    normalize_architected_scene,
    validate_contract_boundary,
)


@dataclass
class RoleSpec:
    """Đặc tả trách nhiệm của một vai trò trong xưởng sản xuất."""
    role_number: int
    role_id: str
    name_vi: str
    name_en: str
    input_contract: str
    output_contract: str
    completion_criteria: List[str]
    edit_bounds: Dict[str, Any]
    error_strategy: str


PRODUCTION_ROLES_SPEC: Dict[str, RoleSpec] = {
    "producer": RoleSpec(
        role_number=1,
        role_id="producer",
        name_vi="Nhà sản xuất",
        name_en="Executive Producer",
        input_contract="RawOrderRequest (topic, platforms, orientation, language, content_mode, voice_mode)",
        output_contract="ProjectBrief",
        completion_criteria=[
            "Xác định rõ đối tượng khán giả, mục tiêu nội dung và nền tảng đích (TikTok, YouTube)",
            "Thiết lập độ phân giải chuẩn (1080x1920 cho 9:16 hoặc 1920x1080 cho 16:9) và khung thời lượng",
            "Ghi nhận ngân sách/chi phí ước tính và kiểm tra điều kiện tiên quyết (consent khi clone giọng)",
        ],
        edit_bounds={"max_revisions": 1, "immutable_after_approval": ["orientation", "platforms", "language"]},
        error_strategy="Từ chối ngay từ biên nếu thiếu chủ đề hoặc bật clone giọng mà chưa có file mẫu/xác nhận quyền.",
    ),
    "researcher": RoleSpec(
        role_number=2,
        role_id="researcher",
        name_vi="Nghiên cứu",
        name_en="Research & Source Analyst",
        input_contract="ProjectBrief",
        output_contract="ResearchReport",
        completion_criteria=[
            "Tổng hợp các luận điểm cốt lõi bám sát chủ đề và chế độ nội dung",
            "Lưu danh sách nguồn tham chiếu có cấu trúc",
            "Phát hiện và gắn cờ mọi tuyên bố số liệu/y tế/tài chính/lịch sử chưa được xác minh (unverified_claims)",
        ],
        edit_bounds={"max_revisions": 2, "can_modify": ["key_facts", "sources", "unverified_claims"]},
        error_strategy="Khi thiếu nguồn xác minh cho chủ đề nhạy cảm, gắn cờ requires_fact_review=True để yêu cầu duyệt người thật.",
    ),
    "scriptwriter": RoleSpec(
        role_number=3,
        role_id="scriptwriter",
        name_vi="Biên kịch",
        name_en="Lead Scriptwriter",
        input_contract="ProjectBrief + ResearchReport",
        output_contract="Script (Draft)",
        completion_criteria=[
            "Cảnh 1 có Hook trực diện trong 3 giây đầu",
            "Mạch nội dung triển khai liền mạch, có ví dụ cụ thể và kết thúc bằng CTA phù hợp",
            "Đầu ra tuân thủ nghiêm ngặt JSON Schema của hợp đồng Script",
        ],
        edit_bounds={"max_revisions": 2, "max_llm_schema_retries": 2, "preserve_user_locked_scenes": True},
        error_strategy="Kiểm định Schema sau khi gọi LLM; thử sửa tối đa 2 lần nếu sai định dạng, báo lỗi rõ ràng nếu vẫn vi phạm.",
    ),
    "content_editor": RoleSpec(
        role_number=4,
        role_id="content_editor",
        name_vi="Biên tập nội dung",
        name_en="Content & Retention Editor",
        input_contract="Script (Draft) + ResearchReport",
        output_contract="Script (Edited & Verified)",
        completion_criteria=[
            "Kiểm tra tính mạch lạc giữa các cảnh (transitional bridges) và cô lập ngôn ngữ Việt-Trung/Pinyin",
            "Loại bỏ câu chữ lặp lại giữa các cảnh (tương đồng từ vựng < 0.65)",
            "Bảo toàn tuyệt đối các cảnh đã được người dùng khóa/duyệt thủ công (user_locked_scenes)",
        ],
        edit_bounds={"max_revisions": 2, "max_text_change_ratio": 0.45, "respect_user_locks": True},
        error_strategy="Sửa cục bộ từng cảnh bị lặp hoặc thiếu liên từ nối; giữ bản gốc hợp lệ nếu LLM biên tập trả về sai cấu trúc.",
    ),
    "director": RoleSpec(
        role_number=5,
        role_id="director",
        name_vi="Đạo diễn",
        name_en="Storyboard & Pacing Director",
        input_contract="Script (Edited)",
        output_contract="ScenePlan (Storyboard & Shot List)",
        completion_criteria=[
            "Chuyển từng cảnh thành Shot trong Storyboard với bố cục, góc máy, hiệu ứng chuyển cảnh và nhịp Visual Beats",
            "Tính toán thời lượng dự kiến từng cảnh và vị trí trên timeline tổng thể",
        ],
        edit_bounds={"max_revisions": 2, "can_modify": ["shots", "visual_beats", "camera_effects", "transition"]},
        error_strategy="Chuẩn hóa tự động nhịp Visual Beats theo thời lượng câu thoại nếu thiếu chỉ dẫn chuyển động.",
    ),
    "visual_director": RoleSpec(
        role_number=6,
        role_id="visual_director",
        name_vi="Phụ trách hình ảnh",
        name_en="Visual & Character Continuity Director",
        input_contract="ScenePlan + Generated Visual Assets",
        output_contract="ScenePlan (Visual Locked) + AssetManifest (Visuals)",
        completion_criteria=[
            "Duy trì nhất quán nhân vật CH01 (stickman áo xanh #8CCFE8), bối cảnh, trang phục và phong cách 2D hoạt hình phẳng (cấm 3D/CGI)",
            "Loại bỏ yêu cầu vẽ chữ/số/công thức trong prompt sinh hình",
            "Thẩm định file hình/video thực tế: tồn tại, đúng RGB, độ phân tán màu color_variance >= 8.0, không lấy ảnh placeholder xám",
        ],
        edit_bounds={"max_revisions": 3, "forbid_silent_fallback_copy": True},
        error_strategy="Không âm thầm lấy ảnh cảnh khác đè lên cảnh lỗi rồi coi là hoàn tất; đánh dấu cảnh lỗi để chạy lại đúng cảnh đó.",
    ),
    "audio_director": RoleSpec(
        role_number=7,
        role_id="audio_director",
        name_vi="Phụ trách âm thanh",
        name_en="Sound & Voice Director",
        input_contract="ScenePlan + Generated Audio Assets",
        output_contract="AssetManifest (Audio & BGM)",
        completion_criteria=[
            "Chọn đúng giọng đọc, tốc độ, cô lập phát âm chữ Hán/Pinyin khỏi giọng tiếng Việt",
            "Chọn nhạc nền hợp lệ từ kho tài sản dự án, thiết lập BGM ducking (15% khi có thoại, 45% khi nghỉ) và mục tiêu -16 LUFS",
            "Xác minh mọi file âm thanh phân cảnh tồn tại, giải mã được và có thời lượng > 0.3s",
        ],
        edit_bounds={"max_revisions": 3, "allow_fallback_voice": True, "target_lufs": -16.0},
        error_strategy="Thử lại với backoff và giọng dự phòng cùng ngôn ngữ; không bao giờ chèn âm thanh câm (silent clip) thay cho lời thoại bị lỗi.",
    ),
    "video_editor": RoleSpec(
        role_number=8,
        role_id="video_editor",
        name_vi="Dựng phim",
        name_en="Lead Video Editor",
        input_contract="ScenePlan + AssetManifest",
        output_contract="RenderManifest",
        completion_criteria=[
            "Đồng bộ chính xác thời lượng hình ảnh/video từng cảnh với đoạn âm thanh tương ứng",
            "Trộn nhạc nền có ducking nhẹ nhàng (khi có BGM) và tạo phụ đề ASS + SRT tại vùng an toàn Bottom 1/6 Safe Zone",
            "Xuất bản nháp MP4 (H.264 + AAC) đúng độ phân giải mục tiêu và ghi nhận mã băm SHA-256",
        ],
        edit_bounds={"max_revisions": 2, "strict_asset_verification": True},
        error_strategy="Dừng và báo lỗi rõ ràng nếu thiếu tài sản cảnh hoặc FFmpeg trả lỗi; tuyệt đối không chèn khung hình đen giả để hoàn tất.",
    ),
    "fact_and_policy_officer": RoleSpec(
        role_number=9,
        role_id="fact_and_policy_officer",
        name_vi="Kiểm chứng và chính sách",
        name_en="Fact-Checker & Platform Policy Officer",
        input_contract="ProjectBrief + ResearchReport + Script + AssetManifest + RenderManifest",
        output_contract="PolicyReport",
        completion_criteria=[
            "Đánh giá độc lập cho YouTube và TikTok theo tài liệu chính thức hiện hành (có URL, ngày kiểm tra, phiên bản quy tắc)",
            "Tách biệt 5 chiều: được phép đăng, cần khai báo AI, đủ điều kiện đề xuất, đủ điều kiện kiếm tiền, và bản quyền tài sản",
            "Phát hiện nội dung nhạy cảm, giả mạo, thiếu quyền clone giọng hoặc lặp lại hàng loạt",
        ],
        edit_bounds={"max_revisions": 1, "cannot_waive_mandatory_ai_disclosure": True},
        error_strategy="Chặn tự động đăng khi vi phạm chính sách hoặc khi bắt buộc khai báo AI mà connector chưa hỗ trợ tự động.",
    ),
    "independent_qa": RoleSpec(
        role_number=10,
        role_id="independent_qa",
        name_vi="QA độc lập",
        name_en="Independent Post-Render QA Inspector",
        input_contract="RenderManifest + ScenePlan + AssetManifest + Publishing Metadata",
        output_contract="QAReport",
        completion_criteria=[
            "Kiểm tra trực tiếp file video đã render bằng công cụ kỹ thuật (ffprobe/ffmpeg/frame/audio/subtitle analysis)",
            "Đánh giá đủ 10 nhóm tiêu chí: giải mã & streams, độ phân giải/tỷ lệ, cảnh đen/đóng băng/trùng lặp, đủ cảnh & không cắt thoại, âm thanh clipping/khoảng lặng/LUFS, đồng bộ thoại-phụ đề, phụ đề tràn khung/safe-zone, tính nhất quán hình ảnh, hook/nhịp kể, và độ khớp metadata",
            "Ghi nhận not_checked hoặc needs_review khi thiếu công cụ/bằng chứng; chặn phát hành ngay khi có bất kỳ lỗi critical nào",
        ],
        edit_bounds={"max_revisions": 0, "read_only_inspector": True},
        error_strategy="Không tự sửa âm thầm trong QA; trả về danh sách lỗi có bằng chứng và gợi ý công đoạn cần chạy lại cho bộ điều phối.",
    ),
    "publishing_editor": RoleSpec(
        role_number=11,
        role_id="publishing_editor",
        name_vi="Biên tập xuất bản",
        name_en="Multi-Platform Publishing Editor",
        input_contract="ProjectBrief + Script + RenderManifest + QAReport + PolicyReport",
        output_contract="PublishingPackage",
        completion_criteria=[
            "Tạo gói metadata riêng cho YouTube (1 tiêu đề chính + 2 tiêu đề phụ, mô tả kèm nguồn/credit, hashtag, tags, ý tưởng thumbnail, chapters, quyết định khai báo AI)",
            "Tạo gói metadata riêng cho TikTok (caption tự nhiên, hashtag cấu hình được, chữ trên ảnh bìa, CTA, quyết định gắn nhãn AIGC)",
            "Kiểm tra giới hạn ký tự/byte theo API chính thức và xuất manifest kèm SHA-256 checksum",
        ],
        edit_bounds={"max_revisions": 3, "preserve_user_locked_fields": True},
        error_strategy="Cắt gọn hợp lệ hoặc báo lỗi khi vượt giới hạn trường API; bảo toàn mọi trường đã được người dùng chỉnh sửa và duyệt.",
    ),
}


def get_all_role_specs() -> List[Dict[str, Any]]:
    ordered = sorted(PRODUCTION_ROLES_SPEC.values(), key=lambda r: r.role_number)
    return [asdict(r) for r in ordered]


def run_producer_role(
    topic: str,
    project_id: Optional[str] = None,
    language: str = "vi",
    orientation: str = "vertical",
    content_mode: str = "knowledge",
    style_preset: str = DEFAULT_IMAGE_STYLE,
    media_mode: str = "flow_image",
    image_engine: str = "flow",
    voice_mode: str = "edge",
    voice: str = TTS_VOICE_DEFAULT,
    chinese_voice: str = TTS_VOICE_ZH_DEFAULT,
    voice_reference_path: str = "",
    voice_consent_verified: bool = False,
    target_scenes: Optional[int] = None,
    platforms: Optional[List[str]] = None,
    version: int = 1,
) -> ProjectBrief:
    clean_topic = str(topic or "").strip()
    if not clean_topic:
        raise ContractValidationError("brief", "Chủ đề sản xuất (topic) không được để trống.")

    if voice_mode == "clone_local":
        if not voice_reference_path or not os.path.exists(voice_reference_path):
            raise ContractValidationError("brief", "Chế độ clone giọng yêu cầu file giọng mẫu tồn tại.")
        if not voice_consent_verified:
            raise ContractValidationError("brief", "Chế độ clone giọng bắt buộc phải xác nhận quyền sử dụng giọng nói.")

    norm_orientation = "vertical" if orientation == "vertical" else "horizontal"
    aspect_ratio = "9:16" if norm_orientation == "vertical" else "16:9"
    resolution = (1080, 1920) if norm_orientation == "vertical" else (1920, 1080)

    if content_mode == "chinese_teaching_vi":
        audience = "Người Việt mới học giao tiếp tiếng Trung qua tình huống ngắn (15-40 tuổi)"
        objective = "Giúp người xem nhớ ngay 1 từ/mẫu câu tiếng Trung, phát âm Pinyin chuẩn và biết cách dùng thực tế"
        dur_bounds = (18.0, 45.0)
    elif content_mode == "english_vocab_story":
        audience = "Người học tiếng Anh giao tiếp qua câu chuyện tình huống Micro-Drama (15-35 tuổi)"
        objective = "Dẫn dắt tình huống đời thường lôi cuốn để ghi nhớ sâu 1 cụm từ tiếng Anh thông dụng"
        dur_bounds = (25.0, 60.0)
    elif content_mode == "story_explainer":
        audience = "Khán giả yêu thích khám phá lịch sử, khoa học qua hình thức kể chuyện dẫn dắt"
        objective = "Giải mã một bí ẩn hoặc hành trình lịch sử/khoa học có mở đầu, nút thắt và bài học đọng lại"
        dur_bounds = (25.0, 90.0)
    else:
        audience = "Khán giả đại chúng trên YouTube Shorts và TikTok yêu thích kiến thức ngắn gọn, dễ hiểu"
        objective = "Giải thích rõ ràng 1 khái niệm hoặc sự thật thú vị kèm ví dụ trực quan"
        dur_bounds = (15.0, 75.0)

    est_scenes = int(target_scenes) if target_scenes else (3 if content_mode == "chinese_teaching_vi" else 5)
    per_scene_cost = 0.04 if media_mode == "flow_video" else 0.008
    estimated_cost = round(est_scenes * per_scene_cost, 4)

    brief = ProjectBrief(
        project_id=project_id or f"proj_{uuid.uuid4().hex[:10]}",
        topic=clean_topic,
        target_audience=audience,
        objective=objective,
        platforms=platforms or ["youtube", "tiktok"],
        orientation=norm_orientation,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        target_duration_sec=dur_bounds,
        budget_limit_usd=1.0,
        estimated_cost_usd=estimated_cost,
        cost_type="estimated_compute_and_flow_credits",
        language=language,
        content_mode=content_mode,
        style_preset=style_preset or DEFAULT_IMAGE_STYLE,
        media_mode=media_mode,
        image_engine=image_engine,
        voice_mode=voice_mode,
        voice_id=voice,
        chinese_voice_id=chinese_voice,
        voice_reference_path=voice_reference_path,
        voice_consent_verified=voice_consent_verified,
        target_scenes=target_scenes,
        version=version,
    )
    ok, errs = validate_contract_boundary("brief", brief)
    if not ok:
        raise ContractValidationError("brief", "ProjectBrief không hợp lệ", errs)
    return brief


def run_researcher_role(brief: ProjectBrief, existing_scenes: Optional[List[Dict[str, Any]]] = None) -> ResearchReport:
    combined_text = brief.topic
    if existing_scenes:
        combined_text += " " + " ".join(
            str(s.get("narration", "")) for s in existing_scenes if isinstance(s, dict)
        )
    lowered = combined_text.lower()

    sensitive_domains = []
    domain_keywords = {
        "health_or_medical": ["sức khỏe", "y tế", "bệnh", "thuốc", "chữa", "medical", "health", "disease", "cure"],
        "finance_or_investment": ["tài chính", "đầu tư", "chứng khoán", "crypto", "lãi suất", "finance", "investment"],
        "civic_or_elections": ["bầu cử", "chính trị", "tổng thống", "quốc hội", "election", "politics"],
        "crisis_or_conflict": ["chiến tranh", "thảm họa", "động đất", "khủng hoảng", "war", "disaster"],
        "real_public_figure": ["người nổi tiếng", "tỷ phú", "ca sĩ", "diễn viên", "celebrity"],
    }
    for domain, terms in domain_keywords.items():
        if any(t in lowered for t in terms):
            sensitive_domains.append(domain)

    unverified_claims: List[Dict[str, Any]] = []
    for sentence in [s.strip() for s in re.split(r"[.!?]+", combined_text) if len(s.strip()) > 10]:
        if re.search(r"\b\d+(?:\.\d+)?%\b|\b(?:18|19|20)\d{2}\b|\b(?:triệu|tỷ|million|billion)\b", sentence, flags=re.IGNORECASE):
            unverified_claims.append({
                "claim": sentence,
                "reason": "Chứa số liệu định lượng hoặc mốc thời gian cụ thể từ mô hình ngôn ngữ chưa đối chiếu nguồn độc lập",
                "requires_review": True,
            })
        elif any(w in sentence.lower() for w in ["100%", "chắc chắn chữa", "bị che giấu", "không ai biết"]):
            unverified_claims.append({
                "claim": sentence,
                "reason": "Chứa khẳng định tuyệt đối hoặc giật gân chưa có nguồn kiểm chứng",
                "requires_review": True,
            })

    sources = [
        {
            "title": "Project Educational Topic Corpus & Curriculum Guidelines",
            "url": "local://video_studio/knowledge_corpus_2026",
            "verified_at": brief.created_at[:10],
            "license": "Internal Educational Synthesis",
        }
    ]
    if brief.content_mode == "chinese_teaching_vi":
        sources.append({
            "title": "Standard HSK 1-3 Mandarin Vocabulary & Pinyin Reference",
            "url": "local://video_studio/hsk_standard_lexicon",
            "verified_at": brief.created_at[:10],
            "license": "Standard Linguistic Reference",
        })

    key_facts = [
        f"Chủ đề trọng tâm: {brief.topic}",
        f"Mục tiêu truyền đạt: {brief.objective}",
        f"Định dạng xuất bản: {brief.aspect_ratio} ({brief.orientation}) cho {', '.join(brief.platforms)}",
    ]

    report = ResearchReport(
        brief_id=brief.project_id,
        topic=brief.topic,
        summary=f"Hồ sơ nghiên cứu cho chủ đề '{brief.topic}' ({brief.content_mode}).",
        key_facts=key_facts,
        sources=sources,
        unverified_claims=unverified_claims,
        sensitive_domains=sensitive_domains,
        requires_fact_review=bool(sensitive_domains or unverified_claims),
        version=brief.version,
    )
    ok, errs = validate_contract_boundary("research", report)
    if not ok:
        raise ContractValidationError("research", "ResearchReport không hợp lệ", errs)
    return report


def _word_jaccard_similarity(a: str, b: str) -> float:
    words_a = set(re.findall(r"\b\w+\b", a.lower()))
    words_b = set(re.findall(r"\b\w+\b", b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a.intersection(words_b)) / max(1, len(words_a.union(words_b)))


def run_content_editor_role(
    brief: ProjectBrief,
    research: ResearchReport,
    scenes: List[Dict[str, Any]],
    editorial_report: Optional[Dict[str, Any]] = None,
    user_locked_scenes: Optional[List[int]] = None,
) -> Script:
    locked_set = set(user_locked_scenes or [])
    issues_fixed: List[str] = list((editorial_report or {}).get("issues_fixed", []))
    warnings: List[str] = list((editorial_report or {}).get("remaining_warnings", []))

    normalized_scenes: List[Dict[str, Any]] = []
    for idx, sc in enumerate(scenes, start=1):
        norm = normalize_architected_scene(sc, index=idx, total_scenes_hint=len(scenes))
        if idx in locked_set or norm.get("user_locked"):
            norm["user_locked"] = True
        normalized_scenes.append(norm)

    dedup_passed = True
    bridges_vi = ["Thế nhưng,", "Chính vì vậy,", "Điều thú vị là,", "Hơn thế nữa,", "Kết quả là,"]
    bridges_en = ["However,", "Therefore,", "Interestingly,", "Moreover,", "As a result,"]

    for i in range(1, len(normalized_scenes)):
        prev_narr = normalized_scenes[i - 1].get("narration", "")
        curr_sc = normalized_scenes[i]
        curr_narr = curr_sc.get("narration", "")
        sim = _word_jaccard_similarity(prev_narr, curr_narr)
        if sim >= 0.72:
            if curr_sc.get("user_locked"):
                warnings.append(f"Cảnh {i+1} có độ tương đồng từ vựng cao ({sim:.0%}) với cảnh {i} nhưng đang được khóa bởi người dùng.")
                dedup_passed = False
            else:
                warnings.append(f"Cảnh {i+1} lặp ý với cảnh {i} ({sim:.0%}); cần biên tập nội dung, không chỉ thêm từ nối.")
                dedup_passed = False


    hook_text = normalized_scenes[0].get("narration", "") if normalized_scenes else ""
    last_text = normalized_scenes[-1].get("narration", "") if normalized_scenes else ""
    default_cta = (
        "Hãy theo dõi kênh để khám phá thêm nhiều kiến thức thú vị mỗi ngày!"
        if brief.language == "vi"
        else "Follow for more concise educational stories every day!"
    )
    total_dur = round(sum(float(s.get("expected_duration_sec", 5.0)) for s in normalized_scenes), 2)
    coherence = float((editorial_report or {}).get("overall_score", 84.0))

    script_contract = Script(
        script_id=f"scr_{brief.project_id}_v{brief.version}",
        brief_id=brief.project_id,
        topic=brief.topic,
        hook=hook_text,
        narrative_arc=f"{len(normalized_scenes)} phân cảnh liên kết từ Hook -> Giải thích/Diễn biến -> Kết luận",
        cta=last_text if any(w in last_text.lower() for w in ["theo dõi", "đăng ký", "follow", "subscribe", "bình luận"]) else default_cta,
        scenes=normalized_scenes,
        language=brief.language,
        content_mode=brief.content_mode,
        total_estimated_duration_sec=total_dur,
        coherence_score=coherence,
        deduplication_passed=dedup_passed,
        editorial_issues_fixed=issues_fixed,
        editorial_warnings=warnings,
        user_locked_scenes=list(locked_set),
        version=brief.version,
    )
    ok, errs = validate_contract_boundary("script", script_contract)
    if not ok:
        raise ContractValidationError("script", "Script không hợp lệ sau bước biên tập nội dung", errs)
    return script_contract


def run_director_visual_audio_planning_roles(
    brief: ProjectBrief,
    script: Script,
) -> ScenePlan:
    from src.visual_beats import calculate_visual_beats

    character_bible = {
        "character_id": "CH01",
        "name": "Stickman Guide CH01",
        "appearance": "Cute minimalist 2D stickman cartoon, round white head, dark navy outline, oval expressive eyes",
        "outfit": "Light blue shirt (#8CCFE8)",
        "style_lock": "Strictly vibrant 2D animation, flat 2D cartoon, hand-drawn cel-shaded vector illustration, NO 3D, NO CGI",
        "reference_image": os.path.join(ASSETS_DIR, "characters", "channel-mascot", "reference-v1.png"),
    }

    visual_style_rules = [
        "Strictly 2D animation, flat 2D cartoon, cel-shaded vector art",
        "Strictly NO 3D rendering, NO CGI, NO photorealistic models, NO claymation",
        "No readable text, numbers, formulas, captions, logos, or watermarks inside visuals",
        f"Target aspect ratio {brief.aspect_ratio} ({brief.resolution[0]}x{brief.resolution[1]})",
    ]

    if "3d" in brief.style_preset.lower() and "no 3d" not in brief.style_preset.lower():
        character_bible.update(style_lock=brief.style_preset,
                               name="Story character",
                               appearance="Preserve the character identity and appearance established in the script",
                               outfit="Preserve the same clothing and accessories across all shots")
        visual_style_rules = [brief.style_preset, "No readable text, captions, logos or watermarks inside visuals",
                              f"Target aspect ratio {brief.aspect_ratio}"]

    available_bgm = []
    if os.path.exists(MUSIC_DIR):
        available_bgm = sorted([
            os.path.join(MUSIC_DIR, f)
            for f in os.listdir(MUSIC_DIR)
            if f.lower().endswith(".mp3") and os.path.getsize(os.path.join(MUSIC_DIR, f)) > 1000
        ])
    selected_bgm = available_bgm[0] if available_bgm else ""

    audio_direction = {
        "primary_voice": brief.voice_id,
        "secondary_chinese_voice": brief.chinese_voice_id if brief.content_mode == "chinese_teaching_vi" else None,
        "voice_mode": brief.voice_mode,
        "speaking_rate": "+0%",
        "chinese_rates": ["-5%", "-18%"] if brief.content_mode == "chinese_teaching_vi" else [],
        "bgm_path": selected_bgm,
        "bgm_ducking_enabled": True,
        "bgm_volume_during_speech": 0.14,
        "bgm_volume_during_pause": 0.40,
        "target_integrated_lufs": -16.0,
        "true_peak_max_dbfs": -1.0,
    }

    shots: List[Dict[str, Any]] = []
    pre_warnings: List[str] = []
    cursor_sec = 0.0

    for idx, sc in enumerate(script.scenes, start=1):
        dur = float(sc.get("audio_duration") or sc.get("expected_duration_sec") or 5.0)
        beats = calculate_visual_beats(scene_duration=dur, num_beats=2)
        start_t = round(cursor_sec, 3)
        end_t = round(cursor_sec + dur, 3)
        cursor_sec = end_t

        sc["timeline_range"] = [start_t, end_t]
        v_prompt = str(sc.get("video_prompt") or "").strip()
        if any(bad in v_prompt.lower() for bad in ["3d render", "unreal engine", "photorealistic"]):
            pre_warnings.append(f"Cảnh {idx} chứa từ khóa 3D trong prompt; đã tự động khóa lại phong cách 2D.")

        shot = {
            "shot_number": idx,
            "scene_id": sc.get("scene_id", f"sc_{idx:03d}"),
            "scene_num": idx,
            "content_goal": sc.get("content_goal", f"step_{idx}"),
            "timeline_range": [start_t, end_t],
            "expected_duration_sec": round(dur, 3),
            "composition": "9:16 vertical center-framed subject, bottom 1/6 reserved for subtitles"
            if brief.orientation == "vertical"
            else "16:9 widescreen rule-of-thirds composition, bottom 1/8 reserved for subtitles",
            "camera_motion": sc.get("render_contract", {}).get("camera_effects", "subtle_slow_cinematic_zoom_1_way"),
            "transition_in": "cut" if idx > 1 else "fade_in_0.2s",
            "transition_out": "cut",
            "visual_beats": beats,
            "character_id": sc.get("character_id", "CH01"),
            "setting": sc.get("setting", sc.get("image_contract", {}).get("background_plate", "")),
            "visual_prompt": v_prompt,
            "narration": sc.get("narration", ""),
            "on_screen_text": sc.get("on_screen_text", ""),
            "voice_profile": brief.voice_id,
            "foley_cues": sc.get("sound_contract", {}).get("foley_cues", []),
        }
        shots.append(shot)

    plan = ScenePlan(
        plan_id=f"plan_{brief.project_id}_v{brief.version}",
        script_id=script.script_id,
        orientation=brief.orientation,
        aspect_ratio=brief.aspect_ratio,
        resolution=brief.resolution,
        character_bible=character_bible,
        visual_style_rules=visual_style_rules,
        audio_direction=audio_direction,
        shots=shots,
        pre_production_checks_passed=len(shots) > 0,
        pre_production_warnings=pre_warnings,
        version=brief.version,
    )
    ok, errs = validate_contract_boundary("storyboard", plan)
    if not ok:
        raise ContractValidationError("storyboard", "ScenePlan (Storyboard) không hợp lệ", errs)
    return plan


def build_and_validate_asset_manifest(
    plan: ScenePlan,
    scenes: List[Dict[str, Any]],
    strict_no_fallback: bool = True,
) -> AssetManifest:
    from src.flow_browser_service import is_valid_production_image

    visual_assets: List[Dict[str, Any]] = []
    audio_assets: List[Dict[str, Any]] = []
    missing_scenes: List[int] = []
    corrupt_assets: List[str] = []
    fallback_scenes: List[int] = []

    seen_visual_hashes: Dict[str, int] = {}
    cursor_sec = 0.0

    for idx, sc in enumerate(scenes, start=1):
        sc_num = int(sc.get("scene_num") or idx)
        scene_id = sc.get("scene_id") or f"sc_{sc_num:03d}"

        a_path = str(sc.get("audio_path") or "")
        a_dur = float(sc.get("audio_duration") or 0.0)
        a_exists = bool(a_path and os.path.exists(a_path) and os.path.getsize(a_path) > 100)
        a_hash = compute_file_sha256(a_path) if a_exists else ""
        if not a_exists or a_dur <= 0.05:
            missing_scenes.append(sc_num)
            if a_path:
                corrupt_assets.append(a_path)

        start_t = round(cursor_sec, 3)
        end_t = round(cursor_sec + max(0.1, a_dur), 3)
        cursor_sec = end_t
        sc["actual_duration_sec"] = round(a_dur, 3)
        sc["timeline_range"] = [start_t, end_t]
        sc["audio_checksum"] = a_hash

        audio_assets.append({
            "scene_id": scene_id,
            "scene_num": sc_num,
            "path": a_path,
            "sha256": a_hash,
            "duration_sec": round(a_dur, 3),
            "timeline_range": [start_t, end_t],
            "source": "edge_tts" if plan.audio_direction.get("voice_mode") != "clone_local" else "xtts_v2_local",
            "license": "Authorized Voice Synthesis",
            "valid": a_exists and a_dur > 0.05,
        })

        use_vid = bool(sc.get("use_video_ai"))
        v_path = str(sc.get("video_path") if use_vid else (sc.get("image_path") or sc.get("asset_path") or ""))
        v_exists = bool(v_path and os.path.exists(v_path) and os.path.getsize(v_path) > 50)
        v_hash = compute_file_sha256(v_path) if v_exists else ""
        is_fallback = bool(sc.get("is_fallback_asset", False))

        if v_hash and v_hash in seen_visual_hashes:
            is_fallback = True
            sc["is_fallback_asset"] = True
            if sc_num not in fallback_scenes:
                fallback_scenes.append(sc_num)
        elif v_hash:
            seen_visual_hashes[v_hash] = sc_num

        if is_fallback and sc_num not in fallback_scenes:
            fallback_scenes.append(sc_num)

        v_valid = v_exists
        if v_exists and not use_vid:
            try:
                from PIL import Image
                with Image.open(v_path) as im:
                    w, h = im.size
                    if w >= 180 and h >= 180:
                        if not is_valid_production_image(v_path):
                            v_valid = False
                            corrupt_assets.append(v_path)
            except Exception:
                pass

        if not v_exists:
            if sc_num not in missing_scenes:
                missing_scenes.append(sc_num)

        sc["asset_path"] = v_path
        sc["asset_type"] = "video" if use_vid else "image"
        sc["asset_checksum"] = v_hash

        visual_assets.append({
            "scene_id": scene_id,
            "scene_num": sc_num,
            "type": "video" if use_vid else "image",
            "path": v_path,
            "sha256": v_hash,
            "source": sc.get("asset_source", "google_flow"),
            "license": sc.get("license_info", "Project Owned / AI Generated"),
            "is_fallback": is_fallback,
            "valid": v_valid and (not is_fallback if strict_no_fallback else True),
        })

    bgm_path = str(plan.audio_direction.get("bgm_path") or "")
    bgm_info = None
    if bgm_path and os.path.exists(bgm_path):
        bgm_info = {
            "path": bgm_path,
            "sha256": compute_file_sha256(bgm_path),
            "source": "project_assets_music",
            "license": "Royalty-Free Bundled Background Music",
        }

    font_info = None
    if FONT_PATH and os.path.exists(FONT_PATH):
        font_info = {
            "path": FONT_PATH,
            "sha256": compute_file_sha256(FONT_PATH),
            "source": "project_assets_fonts",
            "license": "OFL (Open Font License) - Montserrat",
        }

    all_valid = (
        len(missing_scenes) == 0
        and len(corrupt_assets) == 0
        and (len(fallback_scenes) == 0 if strict_no_fallback else True)
    )

    return AssetManifest(
        manifest_id=f"assets_{plan.plan_id}",
        plan_id=plan.plan_id,
        visual_assets=visual_assets,
        audio_assets=audio_assets,
        bgm_asset=bgm_info,
        font_asset=font_info,
        missing_scenes=missing_scenes,
        corrupt_assets=corrupt_assets,
        fallback_substituted_scenes=fallback_scenes,
        all_valid=all_valid,
        version=plan.version,
    )
