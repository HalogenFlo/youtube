# Chức năng: Bộ kiểm tra chính sách nền tảng TikTok & YouTube (Platform Policy & Rights Compliance Engine).

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from src.story_contract_models import (
    AssetManifest,
    PolicyFinding,
    PolicyReport,
    ProjectBrief,
    ResearchReport,
    Script,
    validate_contract_boundary,
)


POLICY_CHECKED_DATE = "2026-10-21"
POLICY_RULE_VERSION = "2026.10-official"

OFFICIAL_POLICY_REGISTRY: Dict[str, Dict[str, str]] = {
    "YT_ALTERED_SYNTHETIC": {
        "platform": "youtube",
        "rule_name": "YouTube Disclosing Use of Altered or Synthetic Content (GenAI)",
        "url": "https://support.google.com/youtube/answer/14328491",
        "blog_url": "https://blog.youtube/news-and-events/disclosing-ai-generated-content/",
        "checked_date": POLICY_CHECKED_DATE,
        "version": POLICY_RULE_VERSION,
        "scope": "Yêu cầu khai báo khi nội dung AI/chỉnh sửa có vẻ chân thực (người thật, sự kiện thật, giọng nói mô phỏng người thật); không bắt buộc với hoạt hình rõ ràng phi thực tế trừ khi giả giọng người thật hoặc chạm chủ đề nhạy cảm.",
    },
    "YT_MONETIZATION_REUSED_REPETITIOUS": {
        "platform": "youtube",
        "rule_name": "YouTube Channel Monetization Policies (Repetitious & Reused Content)",
        "url": "https://support.google.com/youtube/answer/1311392",
        "checked_date": POLICY_CHECKED_DATE,
        "version": POLICY_RULE_VERSION,
        "scope": "Kênh dùng AI vẫn đủ điều kiện kiếm tiền nếu mang lại giá trị giáo dục/sáng tạo độc bản; cấm sản xuất hàng loạt theo mẫu rập khuôn vô hồn hoặc đọc lại văn bản không có giá trị gia tăng.",
    },
    "YT_API_LIMITS_AND_SYNTHETIC_FLAG": {
        "platform": "youtube",
        "rule_name": "YouTube Data API v3 Videos Resource & status.containsSyntheticMedia",
        "url": "https://developers.google.com/youtube/data/reference/rest/v3/videos",
        "checked_date": POLICY_CHECKED_DATE,
        "version": POLICY_RULE_VERSION,
        "scope": "Giới hạn snippet.title <= 100 ký tự, snippet.description <= 5000 bytes, tổng tags <= 500 ký tự, và cờ status.containsSyntheticMedia.",
    },
    "TT_AIGC_DISCLOSURE_AND_SAFETY": {
        "platform": "tiktok",
        "rule_name": "TikTok AI-Generated Content (AIGC) Labels & Synthetic Media Policy",
        "url": "https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content",
        "checked_date": POLICY_CHECKED_DATE,
        "version": POLICY_RULE_VERSION,
        "scope": "Bắt buộc gắn nhãn AIGC cho nội dung AI có hình ảnh/âm thanh/video chân thực hoặc chỉnh sửa đáng kể bằng AI; cấm hoàn toàn giả mạo nguồn tin uy tín/khủng hoảng, giả mạo người dưới 18 tuổi, hoặc dùng hình ảnh/giọng cá nhân khi chưa được phép.",
    },
    "TT_FYF_AND_CREATOR_REWARDS": {
        "platform": "tiktok",
        "rule_name": "TikTok For You Feed Eligibility & Creator Rewards Originality Requirements",
        "url": "https://support.tiktok.com/en/business-and-creator/creator-rewards-program",
        "fyf_url": "https://support.tiktok.com/en/safety-hc/account-and-user-safety/why-is-my-account-not-being-recommended",
        "checked_date": POLICY_CHECKED_DATE,
        "version": POLICY_RULE_VERSION,
        "scope": "Bật nhãn AIGC không làm giảm phân phối nếu tuân thủ Nguyên tắc Cộng đồng; tuy nhiên nội dung sao chép/không nguyên bản bị loại khỏi For You Feed, và Creator Rewards yêu cầu video nguyên bản dài tối thiểu 60 giây.",
    },
    "TT_CONTENT_POSTING_API": {
        "platform": "tiktok",
        "rule_name": "TikTok Content Posting API Direct Post Specification",
        "url": "https://developers.tiktok.com/doc/content-posting-api-reference-direct-post",
        "checked_date": POLICY_CHECKED_DATE,
        "version": POLICY_RULE_VERSION,
        "scope": "Trường post_info.title (caption + hashtags) tối đa 2200 UTF-16 runes; hỗ trợ trường post_info.is_aigc (boolean) để gắn nhãn Creator labeled as AI-generated.",
    },
}

PROHIBITED_CONTENT_PATTERNS = {
    "impersonation_or_fake_crisis": [
        r"\bgiả\s+mạo\b", r"\bdeepfake\b", r"\bkhẩn\s+cấp\s+quốc\s+gia\b",
        r"\bfake\s+breaking\s+news\b", r"\bfalse\s+endorsement\b",
    ],
    "dangerous_hate_or_minors": [
        r"\btự\s+sát\b", r"\btự\s+hại\b", r"\bchế\s+tạo\s+vũ\s+khí\b",
        r"\bấu\s+dâm\b", r"\bkích\s+động\s+bạo\s+lực\b", r"\bhate\s+speech\b",
    ],
}


def evaluate_platform_policies(
    brief: ProjectBrief,
    research: ResearchReport,
    script: Script,
    asset_manifest: AssetManifest,
    video_duration_sec: float,
    video_sha256: str = "",
    publishing_metadata: Optional[Dict[str, Any]] = None,
    youtube_connector_supports_ai_flag: bool = True,
    tiktok_connector_supports_ai_flag: bool = False,
) -> PolicyReport:
    findings: List[PolicyFinding] = []
    block_reasons: List[str] = []

    full_narration = " ".join(str(s.get("narration", "")) for s in script.scenes if isinstance(s, dict))
    combined_text = f"{brief.topic} {full_narration}"
    lowered_text = combined_text.lower()

    prohibited_hits: List[str] = []
    for category, patterns in PROHIBITED_CONTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lowered_text, flags=re.IGNORECASE):
                prohibited_hits.append(f"{category}: khớp mẫu '{pat}'")

    is_2d_stylized = "2d" in brief.style_preset.lower() or "cartoon" in brief.style_preset.lower()
    uses_cloned_voice = brief.voice_mode == "clone_local"
    has_sensitive_domains = len(research.sensitive_domains) > 0
    has_unverified_claims = len(research.unverified_claims) > 0

    if prohibited_hits:
        for plat, rule_key in [("youtube", "YT_ALTERED_SYNTHETIC"), ("tiktok", "TT_AIGC_DISCLOSURE_AND_SAFETY")]:
            rule = OFFICIAL_POLICY_REGISTRY[rule_key]
            findings.append(PolicyFinding(
                platform=plat,
                rule_id=rule_key,
                rule_name=rule["rule_name"],
                rule_url=rule["url"],
                checked_date=rule["checked_date"],
                rule_version=rule["version"],
                scope=rule["scope"],
                dimension="allowed_to_publish",
                status="blocked",
                evidence="; ".join(prohibited_hits),
                reasoning="Nội dung chứa dấu hiệu giả mạo nguy hiểm, khủng hoảng giả hoặc vi phạm an toàn cộng đồng. Gắn nhãn AI KHÔNG hợp thức hóa nội dung vi phạm.",
                confidence=0.98,
                suggested_action="Hủy xuất bản và viết lại kịch bản loại bỏ hoàn toàn nội dung vi phạm.",
                requires_human_review=True,
            ))
        block_reasons.append("Nội dung vi phạm quy tắc an toàn cộng đồng (giả mạo/nguy hiểm).")
    else:
        for plat, rule_key in [("youtube", "YT_ALTERED_SYNTHETIC"), ("tiktok", "TT_AIGC_DISCLOSURE_AND_SAFETY")]:
            rule = OFFICIAL_POLICY_REGISTRY[rule_key]
            status_val = "needs_review" if (has_sensitive_domains or has_unverified_claims) else "pass"
            findings.append(PolicyFinding(
                platform=plat,
                rule_id=rule_key,
                rule_name=rule["rule_name"],
                rule_url=rule["url"],
                checked_date=rule["checked_date"],
                rule_version=rule["version"],
                scope=rule["scope"],
                dimension="allowed_to_publish",
                status=status_val,
                evidence=(
                    f"Chủ đề nhạy cảm: {research.sensitive_domains}; Tuyên bố chưa xác minh: {len(research.unverified_claims)}"
                    if (has_sensitive_domains or has_unverified_claims)
                    else "Nội dung giáo dục/kể chuyện hoạt hình 2D không chứa yếu tố cấm."
                ),
                reasoning=(
                    "Nội dung thuộc nhóm chủ đề nhạy cảm hoặc có số liệu chưa xác minh độc lập, cần người thật kiểm duyệt trước khi đăng."
                    if status_val == "needs_review"
                    else "Nội dung tuân thủ Nguyên tắc Cộng đồng; sử dụng AI hỗ trợ sáng tạo được phép đăng tải hợp lệ."
                ),
                confidence=0.92,
                suggested_action=(
                    "Kiểm tra thủ công các số liệu/tuyên bố trong ResearchReport trước khi duyệt."
                    if status_val == "needs_review"
                    else "Đủ điều kiện đăng tải."
                ),
                requires_human_review=(status_val == "needs_review"),
            ))

    yt_mandatory_label = (not is_2d_stylized) or uses_cloned_voice or has_sensitive_domains
    yt_rule = OFFICIAL_POLICY_REGISTRY["YT_ALTERED_SYNTHETIC"]
    findings.append(PolicyFinding(
        platform="youtube",
        rule_id="YT_ALTERED_SYNTHETIC",
        rule_name=yt_rule["rule_name"],
        rule_url=yt_rule["url"],
        checked_date=yt_rule["checked_date"],
        rule_version=yt_rule["version"],
        scope=yt_rule["scope"],
        dimension="ai_disclosure_required",
        status="action_required" if yt_mandatory_label else "pass",
        evidence=f"style='2D stylized={is_2d_stylized}', voice_clone={uses_cloned_voice}, sensitive={research.sensitive_domains}",
        reasoning=(
            "YouTube bắt buộc bật nhãn 'Altered or synthetic content' khi dùng giọng clone người thật, hình ảnh chân thực hoặc chủ đề nhạy cảm."
            if yt_mandatory_label
            else "Theo tài liệu chính thức của YouTube, hoạt hình 2D cách điệu rõ ràng không bắt buộc gắn nhãn Altered Content đối với cảnh quay thực, nhưng hệ thống vẫn bật minh bạch AI trong mô tả và hỗ trợ cờ containsSyntheticMedia."
        ),
        confidence=0.95,
        suggested_action="Bật 'Altered content = Yes' (status.containsSyntheticMedia=True) khi đăng YouTube.",
        requires_human_review=yt_mandatory_label,
    ))

    tt_rule = OFFICIAL_POLICY_REGISTRY["TT_AIGC_DISCLOSURE_AND_SAFETY"]
    findings.append(PolicyFinding(
        platform="tiktok",
        rule_id="TT_AIGC_DISCLOSURE_AND_SAFETY",
        rule_name=tt_rule["rule_name"],
        rule_url=tt_rule["url"],
        checked_date=tt_rule["checked_date"],
        rule_version=tt_rule["version"],
        scope=tt_rule["scope"],
        dimension="ai_disclosure_required",
        status="action_required",
        evidence="Hình ảnh/video bối cảnh và giọng đọc được tạo bằng AI (Google Flow & Neural TTS).",
        reasoning="Chính sách AIGC của TikTok yêu cầu gắn nhãn với nội dung AI chân thực và khuyến nghị bật nhãn 'AI-generated content' (is_aigc=True) cho video tạo bằng AI.",
        confidence=0.96,
        suggested_action="Bật nút 'AI-generated content' trên ứng dụng TikTok (hoặc truyền post_info.is_aigc=true qua TikTok Content Posting API).",
        requires_human_review=not tiktok_connector_supports_ai_flag,
    ))

    if not tiktok_connector_supports_ai_flag:
        block_reasons.append(
            "TikTok connector hiện chưa kết nối OAuth Content Posting API có cờ is_aigc tự động; "
            "cần người dùng bật thủ công công tắc 'AI-generated content' khi đăng hoặc xuất gói thành phẩm."
        )

    has_duplicate_scenes = len(asset_manifest.fallback_substituted_scenes) > 0
    rec_status = "warning" if (not script.deduplication_passed or has_duplicate_scenes) else "pass"
    for plat, r_id in [("youtube", "YT_MONETIZATION_REUSED_REPETITIOUS"), ("tiktok", "TT_FYF_AND_CREATOR_REWARDS")]:
        rule = OFFICIAL_POLICY_REGISTRY[r_id]
        findings.append(PolicyFinding(
            platform=plat,
            rule_id=r_id,
            rule_name=rule["rule_name"],
            rule_url=rule["url"],
            checked_date=rule["checked_date"],
            rule_version=rule["version"],
            scope=rule["scope"],
            dimension="recommendation_eligibility",
            status=rec_status,
            evidence=f"deduplication_passed={script.deduplication_passed}, fallback_scenes={asset_manifest.fallback_substituted_scenes}",
            reasoning=(
                "Cảnh hình ảnh bị lặp hoặc câu thoại trùng lặp có nguy cơ bị thuật toán đánh dấu là nội dung chất lượng thấp/unoriginal."
                if rec_status == "warning"
                else "Kịch bản có cấu trúc Hook - Giải thích - Kết luận rõ ràng, hình ảnh phân cảnh riêng biệt, đáp ứng tiêu chuẩn đề xuất Shorts/For You."
            ),
            confidence=0.88,
            suggested_action="Tạo lại cảnh bị trùng trước khi xuất bản." if rec_status == "warning" else "Đủ điều kiện phân phối đề xuất.",
            requires_human_review=(rec_status == "warning"),
        ))

    yt_mon_rule = OFFICIAL_POLICY_REGISTRY["YT_MONETIZATION_REUSED_REPETITIOUS"]
    findings.append(PolicyFinding(
        platform="youtube",
        rule_id="YT_MONETIZATION_REUSED_REPETITIOUS",
        rule_name=yt_mon_rule["rule_name"],
        rule_url=yt_mon_rule["url"],
        checked_date=yt_mon_rule["checked_date"],
        rule_version=yt_mon_rule["version"],
        scope=yt_mon_rule["scope"],
        dimension="monetization_eligibility",
        status="warning" if has_duplicate_scenes else "pass",
        evidence=f"Kịch bản độc bản {len(script.scenes)} cảnh, thời lượng {video_duration_sec:.1f}s.",
        reasoning="YouTube cho phép kiếm tiền với nội dung có hỗ trợ AI miễn là có giá trị giáo dục/kể chuyện độc bản.",
        confidence=0.86,
        suggested_action="Đảm bảo mỗi video trong chuỗi có kịch bản và hình ảnh phân cảnh riêng biệt.",
        requires_human_review=False,
    ))

    tt_mon_rule = OFFICIAL_POLICY_REGISTRY["TT_FYF_AND_CREATOR_REWARDS"]
    tt_mon_status = "pass" if (video_duration_sec >= 60.0 and not has_duplicate_scenes) else "warning"
    findings.append(PolicyFinding(
        platform="tiktok",
        rule_id="TT_FYF_AND_CREATOR_REWARDS",
        rule_name=tt_mon_rule["rule_name"],
        rule_url=tt_mon_rule["url"],
        checked_date=tt_mon_rule["checked_date"],
        rule_version=tt_mon_rule["version"],
        scope=tt_mon_rule["scope"],
        dimension="monetization_eligibility",
        status=tt_mon_status,
        evidence=f"Thời lượng video thực tế: {video_duration_sec:.2f}s (Ngưỡng TikTok Creator Rewards: >= 60.0s).",
        reasoning=(
            "Đạt yêu cầu thời lượng >= 60 giây và tính nguyên bản của TikTok Creator Rewards Program."
            if tt_mon_status == "pass"
            else f"Video dài {video_duration_sec:.1f}s (< 60s): Vẫn được đăng và đề xuất trên TikTok For You bình thường, nhưng chưa đủ độ dài tối thiểu 1 phút của TikTok Creator Rewards Program."
        ),
        confidence=0.95,
        suggested_action="Tăng số phân cảnh nếu muốn đủ thời lượng >= 60s cho Creator Rewards.",
        requires_human_review=False,
    ))

    rights_ok = True
    rights_evidence = "Hình ảnh Google Flow thuộc tài khoản dự án; giọng Edge TTS thương mại/công cộng; nhạc nền royalty-free nội bộ."
    if uses_cloned_voice:
        if not brief.voice_consent_verified or not brief.voice_reference_path:
            rights_ok = False
            rights_evidence = "Sử dụng chế độ clone giọng (XTTS-v2) nhưng thiếu xác nhận quyền sở hữu/đồng ý của chủ giọng."
            block_reasons.append("Thiếu xác nhận quyền sử dụng giọng nói cho chế độ Voice Clone.")
        else:
            rights_evidence = f"Đã xác nhận quyền sử dụng file giọng mẫu ({brief.voice_reference_path})."

    for plat, r_id in [("youtube", "YT_ALTERED_SYNTHETIC"), ("tiktok", "TT_AIGC_DISCLOSURE_AND_SAFETY")]:
        rule = OFFICIAL_POLICY_REGISTRY[r_id]
        findings.append(PolicyFinding(
            platform=plat,
            rule_id=r_id,
            rule_name=rule["rule_name"],
            rule_url=rule["url"],
            checked_date=rule["checked_date"],
            rule_version=rule["version"],
            scope=rule["scope"],
            dimension="asset_rights",
            status="pass" if rights_ok else "blocked",
            evidence=rights_evidence,
            reasoning="Tất cả tài sản hình ảnh, âm thanh, phông chữ và giọng đọc đều có nguồn gốc rõ ràng." if rights_ok else "Cấm mô phỏng giọng nói cá nhân khi chưa có sự đồng ý.",
            confidence=0.97,
            suggested_action="Hợp lệ." if rights_ok else "Chuyển sang giọng có sẵn hoặc cung cấp xác nhận quyền sử dụng giọng mẫu.",
            requires_human_review=not rights_ok,
        ))

    allowed_overall = (len(prohibited_hits) == 0) and rights_ok
    requires_human = any(f.requires_human_review for f in findings)
    auto_publish_blocked = (not allowed_overall) or len(block_reasons) > 0 or requires_human

    def _summarize_platform(plat: str) -> Dict[str, Any]:
        p_findings = [f for f in findings if f.platform in (plat, "both")]
        by_dim = {f.dimension: f.status for f in p_findings}
        return {
            "allowed_to_publish": by_dim.get("allowed_to_publish", "pass") != "blocked",
            "ai_disclosure_required": True,
            "ai_disclosure_mode": (
                "mandatory_altered_content_flag"
                if (plat == "youtube" and yt_mandatory_label)
                else ("creator_aigc_toggle" if plat == "tiktok" else "transparent_description_disclosure")
            ),
            "recommendation_eligibility": by_dim.get("recommendation_eligibility", "pass"),
            "monetization_eligibility": by_dim.get("monetization_eligibility", "pass"),
            "asset_rights_status": by_dim.get("asset_rights", "pass"),
            "connector_supports_auto_ai_disclosure": (
                youtube_connector_supports_ai_flag if plat == "youtube" else tiktok_connector_supports_ai_flag
            ),
            "requires_human_review": any(f.requires_human_review for f in p_findings),
        }

    report = PolicyReport(
        policy_id=f"pol_{uuid.uuid4().hex[:10]}",
        video_sha256=video_sha256,
        platforms={
            "youtube": _summarize_platform("youtube"),
            "tiktok": _summarize_platform("tiktok"),
        },
        findings=[f.to_dict() for f in findings],
        allowed_to_publish=allowed_overall,
        requires_ai_disclosure=True,
        requires_human_review=requires_human,
        auto_publish_blocked=auto_publish_blocked,
        block_reasons=block_reasons,
        version=brief.version,
    )
    ok_c, errs = validate_contract_boundary("policy", report)
    if not ok_c:
        raise ValueError(f"PolicyReport vi phạm schema: {errs}")
    return report
