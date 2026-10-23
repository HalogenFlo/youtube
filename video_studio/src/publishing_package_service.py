# Chức năng: Xây dựng Gói Xuất Bản Riêng cho Từng Nền Tảng (YouTube & TikTok Publishing Package).

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.llm_service import generate_video_metadata
from src.story_contract_models import (
    PolicyReport,
    ProjectBrief,
    PublishingPackage,
    QAReport,
    RenderManifest,
    ResearchReport,
    Script,
    compute_file_sha256,
    validate_contract_boundary,
)


PLATFORM_FIELD_LIMITS: Dict[str, Any] = {
    "youtube": {
        "source_url": "https://developers.google.com/youtube/data/reference/rest/v3/videos",
        "checked_date": "2026-10-21",
        "title_max_chars": 100,
        "description_max_utf8_bytes": 5000,
        "tags_total_max_chars": 500,
        "forbidden_chars": ["<", ">"],
    },
    "tiktok": {
        "source_url": "https://developers.tiktok.com/doc/content-posting-api-reference-direct-post",
        "checked_date": "2026-10-21",
        "caption_max_utf16_runes": 2200,
        "default_max_hashtags": 5,
    },
}

BANNED_TRENDING_HASHTAGS = {
    "#fyp", "#foryou", "#foryoupage", "#viral", "#trending",
    "#xuhuong", "#xuhuongtiktok", "#fypシ", "#shorts",
}


def _utf16_rune_len(text: str) -> int:
    return len((text or "").encode("utf-16-le")) // 2


def _sanitize_youtube_text(text: str) -> str:
    return (text or "").replace("<", "‹").replace(">", "›").strip()


def _format_chapter_time(seconds: float) -> str:
    secs = max(0, int(round(seconds)))
    mins = secs // 60
    rem = secs % 60
    return f"{mins:02d}:{rem:02d}"


def build_youtube_chapters(scenes: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    if not scenes or len(scenes) < 3:
        return []
    chapters: List[Dict[str, str]] = []
    cursor = 0.0
    for idx, sc in enumerate(scenes, start=1):
        if not isinstance(sc, dict):
            continue
        t_range = sc.get("timeline_range")
        start_t = 0.0 if idx == 1 else (float(t_range[0]) if isinstance(t_range, list) and len(t_range) >= 1 else cursor)
        dur = float(sc.get("audio_duration") or sc.get("expected_duration_sec") or 5.0)
        cursor = start_t + dur

        narr = str(sc.get("narration") or "").strip()
        words = narr.split()
        label = " ".join(words[:6]).strip(" ,.;:!?") or f"Phần {idx}"
        label = _sanitize_youtube_text(label)[:55]
        chapters.append({
            "timestamp": _format_chapter_time(start_t),
            "title": label,
        })
    return chapters


def filter_relevant_hashtags(
    raw_hashtags: List[str],
    topic: str,
    max_count: int = 5,
) -> List[str]:
    cleaned: List[str] = []
    for tag in (raw_hashtags or []):
        norm = "#" + re.sub(r"[^\w\u00C0-\u024F\u1E00-\u1EFF]", "", str(tag).lstrip("#"))
        if len(norm) <= 2:
            continue
        if norm.lower() in BANNED_TRENDING_HASHTAGS:
            continue
        if norm not in cleaned:
            cleaned.append(norm)

    if not cleaned:
        topic_words = re.findall(r"[^\W\d_]+", topic, flags=re.UNICODE)
        if topic_words:
            cleaned.append("#" + "".join(w.capitalize() for w in topic_words[:3]))
        cleaned.extend(["#KienThuc", "#GiaiThich"])

    return cleaned[:max(1, int(max_count))]


def build_platform_publishing_package(
    brief: ProjectBrief,
    research: ResearchReport,
    script: Script,
    render_manifest: RenderManifest,
    qa_report: QAReport,
    policy_report: PolicyReport,
    package_output_dir: str,
    existing_user_edits: Optional[Dict[str, Any]] = None,
    max_tiktok_hashtags: int = 5,
    youtube_connector_supports_ai_flag: bool = True,
    tiktok_connector_supports_ai_flag: bool = False,
) -> PublishingPackage:
    user_edits = existing_user_edits or {}
    locked_fields = list(user_edits.get("user_locked_fields", []))

    _, raw_meta = generate_video_metadata(
        topic=brief.topic,
        scenes=script.scenes,
        language=brief.language,
    )

    clean_topic = re.sub(r"\s*\((Phần|Part)\s+\d+.*?\)\s*$", "", brief.topic, flags=re.IGNORECASE).strip()

    yt_limits = PLATFORM_FIELD_LIMITS["youtube"]
    base_title = _sanitize_youtube_text(
        user_edits.get("youtube_title")
        if "youtube_title" in locked_fields and user_edits.get("youtube_title")
        else (raw_meta.get("title") or f"Giải thích ngắn: {clean_topic}")
    )[:yt_limits["title_max_chars"]]

    if brief.language == "vi":
        alt_titles = [
            _sanitize_youtube_text(f"Sự thật thú vị về {clean_topic}")[:yt_limits["title_max_chars"]],
            _sanitize_youtube_text(f"Tìm hiểu nhanh: {clean_topic} hoạt động thế nào?")[:yt_limits["title_max_chars"]],
        ]
        ai_disclosure_text = "Minh bạch AI: Hình ảnh minh họa 2D và giọng đọc trong video được hỗ trợ tạo bởi AI."
    else:
        alt_titles = [
            _sanitize_youtube_text(f"How {clean_topic} Actually Works")[:yt_limits["title_max_chars"]],
            _sanitize_youtube_text(f"Quick Explainer: {clean_topic}")[:yt_limits["title_max_chars"]],
        ]
        ai_disclosure_text = "AI Transparency: 2D visuals and voiceover in this video were generated with AI assistance."

    if user_edits.get("youtube_alternative_titles"):
        alt_titles = [
            _sanitize_youtube_text(t)[:yt_limits["title_max_chars"]]
            for t in user_edits["youtube_alternative_titles"][:2]
        ]

    yt_hashtags = filter_relevant_hashtags(
        user_edits.get("hashtags") if "hashtags" in locked_fields else raw_meta.get("hashtags", []),
        topic=clean_topic,
        max_count=5,
    )
    chapters = build_youtube_chapters(script.scenes)
    chapters_block = ""
    if chapters:
        header_ch = "Mốc thời gian (Chapters):" if brief.language == "vi" else "Chapters:"
        chapters_block = "\n\n" + header_ch + "\n" + "\n".join(f"{c['timestamp']} {c['title']}" for c in chapters)

    sources_titles = [s.get("title", "") for s in research.sources if isinstance(s, dict) and s.get("title")]
    sources_block = (
        ("\n\nNguồn tham khảo & Credit: " if brief.language == "vi" else "\n\nSources & Credits: ")
        + "; ".join(sources_titles)
    ) if sources_titles else ""

    if "youtube_description" in locked_fields and user_edits.get("youtube_description"):
        yt_desc = _sanitize_youtube_text(user_edits["youtube_description"])
    else:
        base_desc = _sanitize_youtube_text(raw_meta.get("description") or script.hook or clean_topic)
        hashtag_str = " ".join(yt_hashtags)
        yt_desc = f"{base_desc}{chapters_block}{sources_block}\n\n{ai_disclosure_text}\n{hashtag_str}".strip()

    while len(yt_desc.encode("utf-8")) > yt_limits["description_max_utf8_bytes"]:
        yt_desc = yt_desc[:-20].rstrip()

    yt_tags: List[str] = []
    running_tags_len = 0
    for h in yt_hashtags:
        clean_tag = h.lstrip("#")
        if running_tags_len + len(clean_tag) + 2 <= yt_limits["tags_total_max_chars"]:
            yt_tags.append(clean_tag)
            running_tags_len += len(clean_tag) + 2

    yt_contains_synthetic = True
    yt_disclosure_reason = (
        "Video sử dụng hình ảnh hoạt hình 2D tạo sinh (Google Flow) và giọng đọc tổng hợp (Neural TTS). "
        "Đặt status.containsSyntheticMedia=True và ghi rõ trong mô tả để tuân thủ chính sách minh bạch AI của YouTube."
    )
    yt_manual_steps: List[str] = []
    if not youtube_connector_supports_ai_flag:
        yt_manual_steps.append(
            "Trong YouTube Studio -> Chi tiết video -> Hiện thêm -> Mục 'Nội dung đã chỉnh sửa (Altered content)': chọn 'Có (Yes)'."
        )

    youtube_spec = {
        "recommended_title": base_title,
        "alternative_titles": alt_titles,
        "description": yt_desc,
        "hashtags": yt_hashtags,
        "tags": yt_tags,
        "thumbnail_concept": {
            "visual_prompt": (
                f"2D flat cartoon thumbnail featuring canonical stickman character CH01 in light blue shirt "
                f"reacting with curiosity to {clean_topic}, high contrast focal object, clean composition, no clutter"
            ),
            "headline_overlay": clean_topic[:36],
            "aspect_ratio": brief.aspect_ratio,
        },
        "chapters": chapters,
        "contains_synthetic_media": yt_contains_synthetic,
        "ai_disclosure_reason": yt_disclosure_reason,
        "connector_supports_ai_disclosure": youtube_connector_supports_ai_flag,
        "manual_steps_required": yt_manual_steps,
        "field_validation": {
            "title_char_length": len(base_title),
            "title_limit_chars": yt_limits["title_max_chars"],
            "description_utf8_bytes": len(yt_desc.encode("utf-8")),
            "description_limit_bytes": yt_limits["description_max_utf8_bytes"],
            "tags_char_length": running_tags_len,
            "tags_limit_chars": yt_limits["tags_total_max_chars"],
            "valid": (
                0 < len(base_title) <= yt_limits["title_max_chars"]
                and len(yt_desc.encode("utf-8")) <= yt_limits["description_max_utf8_bytes"]
                and running_tags_len <= yt_limits["tags_total_max_chars"]
            ),
            "api_spec_url": yt_limits["source_url"],
        },
    }

    tt_limits = PLATFORM_FIELD_LIMITS["tiktok"]
    tt_hashtags = filter_relevant_hashtags(
        user_edits.get("tiktok_hashtags") or user_edits.get("hashtags") or raw_meta.get("hashtags", []),
        topic=clean_topic,
        max_count=max_tiktok_hashtags,
    )
    tt_cta = str(user_edits.get("tiktok_cta") or script.cta).strip()
    if "tiktok_caption" in locked_fields and user_edits.get("tiktok_caption"):
        tt_caption = str(user_edits["tiktok_caption"]).strip()
    else:
        raw_tt_cap = str(raw_meta.get("tiktok_caption") or script.hook or clean_topic).strip()
        tag_tail = " ".join(tt_hashtags)
        tt_caption = f"{raw_tt_cap}\n{tt_cta}\n{ai_disclosure_text}\n{tag_tail}".strip()

    while _utf16_rune_len(tt_caption) > tt_limits["caption_max_utf16_runes"]:
        tt_caption = tt_caption[:-20].rstrip()

    tt_manual_steps: List[str] = []
    if not tiktok_connector_supports_ai_flag:
        tt_manual_steps.append(
            "Khi đăng video trên ứng dụng TikTok / TikTok Studio -> Vào 'Tùy chọn khác (More options)' -> Bật công tắc 'Nội dung do AI tạo (AI-generated content)'."
        )

    tiktok_spec = {
        "caption": tt_caption,
        "hashtags": tt_hashtags,
        "max_hashtags_configured": max_tiktok_hashtags,
        "cover_text": clean_topic[:32],
        "video_cover_timestamp_ms": 1000,
        "cta": tt_cta,
        "is_aigc": True,
        "ai_disclosure_reason": (
            "Video sử dụng hình ảnh và âm thanh tạo bằng AI; bật nhãn 'Creator labeled as AI-generated' (is_aigc=True) "
            "theo quy định AIGC của TikTok để minh bạch với người xem."
        ),
        "connector_supports_ai_disclosure": tiktok_connector_supports_ai_flag,
        "manual_steps_required": tt_manual_steps,
        "field_validation": {
            "caption_utf16_runes": _utf16_rune_len(tt_caption),
            "caption_limit_utf16_runes": tt_limits["caption_max_utf16_runes"],
            "hashtags_count": len(tt_hashtags),
            "valid": 0 < _utf16_rune_len(tt_caption) <= tt_limits["caption_max_utf16_runes"],
            "api_spec_url": tt_limits["source_url"],
        },
    }

    os.makedirs(package_output_dir, exist_ok=True)
    pkg_video_path = os.path.join(package_output_dir, "video.mp4")
    if os.path.exists(render_manifest.video_path) and os.path.abspath(render_manifest.video_path) != os.path.abspath(pkg_video_path):
        shutil.copy2(render_manifest.video_path, pkg_video_path)
    else:
        pkg_video_path = render_manifest.video_path

    pkg_ass_path = os.path.join(package_output_dir, "subtitles.ass")
    if render_manifest.ass_subtitle_path and os.path.exists(render_manifest.ass_subtitle_path):
        if os.path.abspath(render_manifest.ass_subtitle_path) != os.path.abspath(pkg_ass_path):
            shutil.copy2(render_manifest.ass_subtitle_path, pkg_ass_path)
    else:
        pkg_ass_path = render_manifest.ass_subtitle_path

    pkg_srt_path = os.path.join(package_output_dir, "subtitles.srt")
    if render_manifest.srt_subtitle_path and os.path.exists(render_manifest.srt_subtitle_path):
        if os.path.abspath(render_manifest.srt_subtitle_path) != os.path.abspath(pkg_srt_path):
            shutil.copy2(render_manifest.srt_subtitle_path, pkg_srt_path)
    else:
        pkg_srt_path = render_manifest.srt_subtitle_path

    video_sha = compute_file_sha256(pkg_video_path)
    sub_sha = compute_file_sha256(pkg_ass_path) or compute_file_sha256(pkg_srt_path)

    qa_path = os.path.join(package_output_dir, "qa_report.json")
    Path(qa_path).write_text(json.dumps(qa_report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    policy_path = os.path.join(package_output_dir, "policy_report.json")
    Path(policy_path).write_text(json.dumps(policy_report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    meta_path = os.path.join(package_output_dir, "publishing_metadata.json")
    meta_payload = {
        "job_id": brief.project_id,
        "version": brief.version,
        "topic": brief.topic,
        "youtube": youtube_spec,
        "tiktok": tiktok_spec,
        "title": youtube_spec["recommended_title"],
        "description": youtube_spec["description"],
        "tiktok_caption": tiktok_spec["caption"],
        "hashtags": youtube_spec["hashtags"],
        "ai_disclosure": ai_disclosure_text,
        "requires_ai_label": True,
        "manual_review_required": policy_report.requires_human_review or qa_report.release_blocked,
        "risk_flags": research.sensitive_domains,
        "platforms": {
            "youtube": {
                "title": youtube_spec["recommended_title"],
                "alternative_titles": youtube_spec["alternative_titles"],
                "description": youtube_spec["description"],
                "hashtags": youtube_spec["hashtags"],
                "tags": youtube_spec["tags"],
                "chapters": youtube_spec["chapters"],
                "thumbnail_concept": youtube_spec["thumbnail_concept"],
                "set_altered_content": youtube_spec["contains_synthetic_media"],
            },
            "tiktok": {
                "caption": tiktok_spec["caption"],
                "hashtags": tiktok_spec["hashtags"],
                "cover_text": tiktok_spec["cover_text"],
                "cta": tiktok_spec["cta"],
                "enable_ai_generated_label": tiktok_spec["is_aigc"],
            },
        },
    }
    Path(meta_path).write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    publish_block_reasons: List[str] = []
    if qa_report.release_blocked:
        publish_block_reasons.append(f"QA video chưa đạt (score={qa_report.overall_score}, critical={qa_report.critical_count}).")
    if not policy_report.allowed_to_publish:
        publish_block_reasons.append("Vi phạm chính sách nền tảng (allowed_to_publish=False).")
    publish_block_reasons.extend(policy_report.block_reasons)

    approved_by_user = bool(user_edits.get("approved_by_user", False))
    approved_video_sha = str(user_edits.get("approved_video_sha256") or "")
    if not approved_by_user:
        publish_block_reasons.append("Chưa có phê duyệt phát hành từ người dùng (approved_by_user=False).")
    elif approved_video_sha and approved_video_sha != video_sha:
        publish_block_reasons.append("Mã băm SHA-256 của video hiện tại khác với bản đã được duyệt; cần duyệt lại.")

    manifest_path = os.path.join(package_output_dir, "package_manifest.json")
    manifest_payload = {
        "package_id": f"pkg_{brief.project_id}_v{brief.version}",
        "job_id": brief.project_id,
        "version": brief.version,
        "files": {
            "video_mp4": {"path": pkg_video_path, "sha256": video_sha},
            "subtitles_ass": {"path": pkg_ass_path, "sha256": compute_file_sha256(pkg_ass_path)},
            "subtitles_srt": {"path": pkg_srt_path, "sha256": compute_file_sha256(pkg_srt_path)},
            "publishing_metadata_json": {"path": meta_path, "sha256": compute_file_sha256(meta_path)},
            "qa_report_json": {"path": qa_path, "sha256": compute_file_sha256(qa_path)},
            "policy_report_json": {"path": policy_path, "sha256": compute_file_sha256(policy_path)},
        },
        "approved_by_user": approved_by_user,
        "approved_video_sha256": approved_video_sha,
        "auto_publish_blocked": len(publish_block_reasons) > 0,
        "publish_block_reasons": publish_block_reasons,
    }
    manifest_bytes = json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    package_checksum = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_payload["package_checksum"] = package_checksum
    Path(manifest_path).write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    package = PublishingPackage(
        package_id=manifest_payload["package_id"],
        job_id=brief.project_id,
        version=brief.version,
        video_path=pkg_video_path,
        video_sha256=video_sha,
        ass_subtitle_path=pkg_ass_path,
        srt_subtitle_path=pkg_srt_path,
        subtitle_sha256=sub_sha,
        youtube=youtube_spec,
        tiktok=tiktok_spec,
        qa_report_path=qa_path,
        policy_report_path=policy_path,
        metadata_path=meta_path,
        manifest_path=manifest_path,
        package_dir=package_output_dir,
        package_checksum=package_checksum,
        user_locked_fields=locked_fields,
        approved_by_user=approved_by_user,
        approved_at=user_edits.get("approved_at"),
        approved_video_sha256=approved_video_sha,
        auto_publish_blocked=len(publish_block_reasons) > 0,
        publish_block_reasons=publish_block_reasons,
    )
    ok_c, errs = validate_contract_boundary("publishing", package)
    if not ok_c:
        raise ValueError(f"PublishingPackage vi phạm schema: {errs}")
    return package


def verify_package_ready_for_platform_publish(
    package: PublishingPackage,
    platform: str,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    plat = platform.lower().strip()
    if plat not in ("youtube", "tiktok"):
        return False, [f"Nền tảng không được hỗ trợ: {platform}"]

    if not package.approved_by_user:
        reasons.append("Gói xuất bản chưa được người dùng bấm Duyệt (approved_by_user=False).")

    current_disk_sha = compute_file_sha256(package.video_path)
    if not current_disk_sha or current_disk_sha != package.video_sha256:
        reasons.append("File video MP4 trên đĩa đã bị thay đổi hoặc không khớp với checksum trong manifest.")
    if package.approved_video_sha256 and current_disk_sha != package.approved_video_sha256:
        reasons.append("Phiên bản video hiện tại không khớp với bản đã được người dùng phê duyệt (checksum mismatch).")

    plat_spec = package.youtube if plat == "youtube" else package.tiktok
    if not plat_spec.get("field_validation", {}).get("valid", False):
        reasons.append(f"Trường dữ liệu metadata của {plat} vượt giới hạn API cho phép.")

    requires_ai = bool(
        plat_spec.get("contains_synthetic_media") if plat == "youtube" else plat_spec.get("is_aigc")
    )
    connector_ok = bool(plat_spec.get("connector_supports_ai_disclosure", False))
    if requires_ai and not connector_ok:
        manual_steps = "; ".join(plat_spec.get("manual_steps_required", []))
        reasons.append(
            f"Chặn đăng tự động lên {plat.upper()}: Bắt buộc khai báo nhãn AI nhưng connector hiện tại chưa hỗ trợ bật tự động. "
            f"Bước thủ công cần thực hiện: {manual_steps}"
        )

    return len(reasons) == 0, reasons
