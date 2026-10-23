"""Thư viện video: danh sách video đã tạo + tiêu đề/hashtag/mô tả chuẩn chính sách AI (YouTube, TikTok) + xóa an toàn."""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from src.publishing_package_service import (
        BANNED_TRENDING_HASHTAGS,
        PLATFORM_FIELD_LIMITS,
        filter_relevant_hashtags,
    )
except ModuleNotFoundError:  # chạy từ thư mục gốc repo
    from video_studio.src.publishing_package_service import (
        BANNED_TRENDING_HASHTAGS,
        PLATFORM_FIELD_LIMITS,
        filter_relevant_hashtags,
    )

STUDIO_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = STUDIO_DIR / "output"
CONFIG_PATH = STUDIO_DIR / "library_config.json"

DEFAULT_DESCRIPTION_HEADER = (
    "📩 Liên hệ mua trọn bộ PIPELINE tạo video AI (MuseAI + Google Flow + Gemini Pro): "
    "[ĐIỀN ZALO / EMAIL CỦA BẠN]"
)

SIDECAR_SUFFIX = ".publish.json"
DELETABLE_SUFFIXES = (".mp4", ".json", SIDECAR_SUFFIX, ".srt", ".ass", ".vtt", ".png", ".jpg")
EDITABLE_FIELDS = ("title", "description_body", "hashtags_youtube", "hashtags_tiktok", "tiktok_caption")
MAX_TAGS = 5
CHANNEL_TAGS = {"whiteboard": "#giaotieplade", "other": "#hochoidoday"}
HASHTAG_POLICY_VERSION = 3
TITLE_STOPWORDS = {"tại", "sao", "vì", "là", "của", "và", "các", "những", "một", "có", "không", "cho", "với", "the", "a", "an", "of", "to", "is"}


# ------------------------------------------------------------------------------
# CẤU HÌNH
# ------------------------------------------------------------------------------
def load_library_config(path: Optional[str] = None) -> Dict[str, Any]:
    cfg = {"description_header": DEFAULT_DESCRIPTION_HEADER}
    p = Path(path) if path else CONFIG_PATH
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("description_header"), str):
                cfg["description_header"] = data["description_header"]
        except (OSError, ValueError):
            pass
    return cfg


def save_library_config(cfg: Dict[str, Any], path: Optional[str] = None) -> None:
    p = Path(path) if path else CONFIG_PATH
    p.write_text(json.dumps({"description_header": str(cfg.get("description_header", ""))}, ensure_ascii=False, indent=2),
                 encoding="utf-8")


# ------------------------------------------------------------------------------
# TẠO METADATA
# ------------------------------------------------------------------------------
def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("<", "").replace(">", "")).strip()


def _clip_title(text: str, limit: int = 100) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:!?-")
    return cut or text[:limit]


def _unaccent(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _topic_hashtag(text: str) -> str:
    words = [w for w in re.findall(r"[^\W\d_]+", _unaccent(text.lower())) if w not in {_unaccent(s) for s in TITLE_STOPWORDS}]
    return "#" + "".join(w.capitalize() for w in words[:4]) if words else ""


def _title_from_filename(stem: str) -> str:
    m = re.match(r"^museai_flow_3d_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(?:_tap(\d+))?$", stem)
    if m:
        y, mo, d, hh, mi, _, tap = m.groups()
        suffix = f" - Tập {int(tap)}" if tap else ""
        return f"Video AI ngày {d}/{mo}/{y} {hh}:{mi}{suffix}"
    return _clean(stem.replace("_", " ")) or "Video AI"


def _detect_modes(meta: Dict[str, Any]) -> Tuple[bool, str]:
    story = meta.get("story_data") or meta.get("story") or {}
    story = story if isinstance(story, dict) else {}
    scenes = story.get("scenes") if isinstance(story, dict) else []
    is_english = story.get("content_mode") == "english_teaching_vi" or str(meta.get("language", "")).lower() == "vi_en" or any(
        isinstance(s, dict) and s.get("content_mode") == "english_teaching_vi" for s in (scenes or [])
    )
    mode = str(meta.get("visual_mode") or story.get("visual_mode") or "")
    if not mode and any(isinstance(s, dict) and s.get("media_type") == "whiteboard" for s in (scenes or [])):
        mode = "whiteboard"
    return is_english, mode


def channel_hashtags(tags: List[str], channel_tag: str, max_count: int = MAX_TAGS) -> List[str]:
    """Reserve a slot for the correct channel; never mix the two channel identities."""
    channel_names = {tag.casefold() for tag in CHANNEL_TAGS.values()}
    candidates = filter_relevant_hashtags(tags, topic="", max_count=max(len(tags), max_count)) if tags else []
    chosen = [channel_tag]
    seen = channel_names.copy()
    for tag in candidates:
        if tag.casefold() not in seen and len(tag) <= 64:
            chosen.append(tag)
            seen.add(tag.casefold())
    return chosen[:max_count]


def _caption_body(text: str) -> str:
    return re.sub(r"(?<!\w)#[\w]+", "", str(text)).strip()


def compose_tiktok_caption(body: str, tags: List[str]) -> str:
    """Keep channel/topic tags intact while fitting the configured UTF-16 limit."""
    tail = " ".join(tags)
    limit = PLATFORM_FIELD_LIMITS["tiktok"]["caption_max_utf16_runes"]
    budget = max(0, limit - len(("\n" + tail).encode("utf-16-le")) // 2)
    body = _caption_body(body).encode("utf-16-le")[:budget * 2].decode("utf-16-le", errors="ignore").rstrip()
    return "\n".join(part for part in (body, tail) if part)


def build_video_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo tiêu đề, hashtag, mô tả (phần thân), caption TikTok + nhắc bật nhãn AI từ metadata của pipeline."""
    meta = meta if isinstance(meta, dict) else {}
    story = meta.get("story_data") or meta.get("story") or {}
    story = story if isinstance(story, dict) else {}
    is_english, visual_mode = _detect_modes(meta)
    lang_en = str(meta.get("language", "")).lower() == "en"

    title = _clip_title(story.get("story_title") or meta.get("title") or meta.get("topic") or "Video AI")
    topic = _clean(meta.get("topic") or story.get("story_title") or title)

    publishing = story.get("publishing") or {}
    publishing = publishing if isinstance(publishing, dict) else {}
    raw_tags = publishing.get("hashtags") or meta.get("hashtags") or []
    source_tags = [t for t in raw_tags if isinstance(t, str)] if isinstance(raw_tags, list) else []
    # Prefer MuseAI's complete search phrases over a mechanically shortened title.
    candidates = list(source_tags) if source_tags else [_topic_hashtag(topic)]
    if is_english:
        candidates += ["#HocTiengAnh", "#TiengAnhGiaoTiep"]
    elif visual_mode == "whiteboard":
        candidates += ["#KienThuc", "#HocMoiNgay"]
    else:
        candidates += ["#HoatHinh3D", "#KeChuyen"]
    channel_tag = CHANNEL_TAGS["whiteboard" if visual_mode == "whiteboard" else "other"]
    tags = channel_hashtags([c for c in candidates if c], channel_tag)

    scenes = [s for s in (story.get("scenes") or []) if isinstance(s, dict)]
    body = _clean(meta.get("episode_summary") or " ".join(_clean(s.get("narration")) for s in scenes[:2])) or title
    body = body[:600].rstrip()

    if lang_en:
        disclosure = "AI Transparency: visuals and voiceover in this video were created with AI assistance."
    else:
        disclosure = "Minh bạch AI: Hình ảnh minh họa và giọng đọc trong video được hỗ trợ tạo bởi AI."

    tt_body = "\n".join([title, body[:160]])
    tt_caption = compose_tiktok_caption(tt_body, tags)

    return {
        "title": title,
        "description_body": body,
        "hashtags_youtube": tags,
        "hashtags_tiktok": tags[:PLATFORM_FIELD_LIMITS["tiktok"]["default_max_hashtags"]],
        "tiktok_caption": tt_caption,
        "tiktok_caption_body": tt_body,
        "channel_hashtag": channel_tag,
        "hashtag_policy_version": HASHTAG_POLICY_VERSION,
        "ai_disclosure": disclosure,
        "requires_ai_label": None,
        "ai_label_review_required": True,
        "platform_steps": [
            "YouTube Studio → mục AI use / Nội dung bị thay đổi: khai báo khi có người, sự kiện, cảnh hoặc âm thanh AI trông/nghe như thật; hoạt hình phi thực tế không mặc nhiên bắt buộc.",
            "TikTok → Tùy chọn khác → Nội dung do AI tạo: bắt buộc với hình, âm thanh hoặc video AI chân thực; TikTok khuyến khích minh bạch cả nội dung AI khác.",
        ],
        "compliance_notes": [
            "Dùng tối đa 5 hashtag theo lựa chọn của ứng dụng: hashtag kênh + chủ đề + nhóm nội dung. Đây không phải giới hạn chung của YouTube.",
            "Ứng dụng tránh thẻ xu hướng chung không liên quan; #shorts không phải thẻ bị nền tảng cấm.",
            "Tiêu đề phản ánh đúng nội dung video, không gây hiểu lầm.",
            "Hashtag và dòng minh bạch AI không thay thao tác khai báo trong nền tảng khi nội dung thuộc diện bắt buộc; không bảo đảm lượt xem hoặc việc duyệt video.",
        ],
        "user_edited_fields": [],
    }


def compose_description(header: str, metadata: Dict[str, Any]) -> str:
    """Fit header, body and disclosure within UTF-8 bytes, keeping the channel tags."""
    limit = PLATFORM_FIELD_LIMITS["youtube"]["description_max_utf8_bytes"]
    def clip(text: str, budget: int) -> str:
        return _clean(text).encode("utf-8")[:max(0, budget)].decode("utf-8", errors="ignore").rstrip()

    channel = metadata.get("channel_hashtag")
    raw_tags = metadata.get("hashtags_youtube") or []
    tags = " ".join(channel_hashtags(raw_tags, channel) if channel else [str(t)[:64] for t in raw_tags[:MAX_TAGS]])
    disclosure = clip(metadata.get("ai_disclosure", ""), 1000)
    footer = "\n\n".join(p for p in (disclosure, tags) if p)
    header = clip(header, min(2000, limit - len(footer.encode("utf-8")) - 4))
    reserved = len("\n\n".join(p for p in (header, footer) if p).encode("utf-8"))
    body = clip(metadata.get("description_body", ""), limit - reserved - (2 if reserved else 0))
    return "\n\n".join(p for p in (header, body, footer) if p)


# ------------------------------------------------------------------------------
# ĐỌC / GHI / XÓA
# ------------------------------------------------------------------------------
def _sidecar(video_path: str) -> Path:
    return Path(video_path).with_suffix("").with_name(Path(video_path).stem + SIDECAR_SUFFIX)


def _source_meta(video_path: str) -> Dict[str, Any]:
    p = Path(video_path)
    src = p.with_suffix(".json")
    data: Dict[str, Any] = {}
    if src.exists():
        try:
            loaded = json.loads(src.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            data = {}
    if data.get("scenes") and not (data.get("story_data") or data.get("story")):
        data = dict(data, story_data=dict(data))
    if not data.get("visual_mode") and p.stem.startswith("museai_whiteboard_"):
        data["visual_mode"] = "whiteboard"
    if not (data.get("story_data") or data.get("story") or data.get("title")):
        data.setdefault("story_data", {})["story_title"] = _title_from_filename(p.stem)
    return data


def _load_sidecar(video_path: str) -> Optional[Dict[str, Any]]:
    sc = _sidecar(video_path)
    if sc.exists():
        try:
            data = json.loads(sc.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("title"):
                return data
        except (OSError, ValueError):
            return None
    return None


def metadata_for(video_path: str) -> Dict[str, Any]:
    """Metadata hiện có (sidecar nếu đã lưu, nếu chưa thì tạo tạm trong bộ nhớ, không ghi file)."""
    generated = build_video_metadata(_source_meta(video_path))
    existing = _load_sidecar(video_path)
    if not existing:
        return generated
    result = dict(generated, **existing)
    channel = generated["channel_hashtag"]
    for key in ("hashtags_youtube", "hashtags_tiktok"):
        tags = existing.get(key, []) if key in existing.get("user_edited_fields", []) or existing.get("hashtag_policy_version") == HASHTAG_POLICY_VERSION else generated[key]
        result[key] = channel_hashtags(tags, channel)
    result.update(channel_hashtag=channel, hashtag_policy_version=HASHTAG_POLICY_VERSION,
                  requires_ai_label=None, ai_label_review_required=True,
                  platform_steps=generated["platform_steps"], compliance_notes=generated["compliance_notes"])
    result["tiktok_caption_body"] = existing.get("tiktok_caption_body", _caption_body(existing.get("tiktok_caption", generated["tiktok_caption_body"])))
    result["tiktok_caption"] = compose_tiktok_caption(result["tiktok_caption_body"], result["hashtags_tiktok"])
    return result


def ensure_metadata(video_path: str) -> Dict[str, Any]:
    existing = _load_sidecar(video_path)
    meta = metadata_for(video_path)
    if existing != meta:
        _sidecar(video_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def update_metadata(video_path: str, edits: Dict[str, Any]) -> Dict[str, Any]:
    meta = ensure_metadata(video_path)
    edited = set(meta.get("user_edited_fields") or [])
    topic = _clean(meta.get("title"))
    for key in EDITABLE_FIELDS:
        if key not in edits:
            continue
        value = edits[key]
        if key == "title":
            value = _clip_title(value) or meta["title"]
        elif key in ("hashtags_youtube", "hashtags_tiktok"):
            limit = PLATFORM_FIELD_LIMITS["tiktok"]["default_max_hashtags"] if key == "hashtags_tiktok" else MAX_TAGS
            value = channel_hashtags(list(value), meta["channel_hashtag"], max_count=limit)
        elif key == "tiktok_caption":
            value = _caption_body(str(value).replace("\r", ""))
            meta["tiktok_caption_body"] = value
        else:
            value = _clean(value)
        meta[key] = value
        edited.add(key)
    meta["user_edited_fields"] = sorted(edited)
    meta["tiktok_caption"] = compose_tiktok_caption(meta["tiktok_caption_body"], meta["hashtags_tiktok"])
    _sidecar(video_path).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def scan_library(output_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not root.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for f in root.iterdir():
        if f.is_file() and f.suffix.lower() == ".mp4":
            st = f.stat()
            items.append({
                "name": f.name,
                "path": str(f),
                "size_mb": round(st.st_size / (1024 * 1024), 2),
                "mtime": st.st_mtime,
                "created": time.strftime("%d/%m/%Y %H:%M", time.localtime(st.st_mtime)),
                "metadata": metadata_for(str(f)),
            })
    items.sort(key=lambda i: i["mtime"], reverse=True)
    return items


def delete_video(video_path: str, library_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Xóa video + các file đi kèm cùng tên (json, publish.json, srt, ass, ảnh bìa). Chỉ trong thư viện, không xóa file ngoài."""
    root = Path(library_dir or DEFAULT_OUTPUT_DIR).resolve()
    target = Path(video_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return False, "Từ chối xóa: file nằm ngoài thư mục thư viện."
    if target.parent != root or target.suffix.lower() != ".mp4":
        return False, "Từ chối xóa: chỉ xóa video .mp4 trực tiếp trong thư viện."
    if not target.is_file():
        return False, "Không tìm thấy video."
    removed = 0
    for suffix in DELETABLE_SUFFIXES:
        f = root / f"{target.stem}{suffix}"
        if f.is_file():
            try:
                f.unlink()
                removed += 1
            except OSError as exc:
                return False, f"Không xóa được {f.name}: {exc}"
    return True, f"Đã xóa {removed} file của '{target.name}'."


def ensure_metadata_for_new_video(video_path: str) -> None:
    """Gọi sau khi pipeline xuất video xong: tự tạo metadata đăng bài."""
    try:
        if os.path.exists(video_path):
            ensure_metadata(video_path)
    except OSError:
        pass
