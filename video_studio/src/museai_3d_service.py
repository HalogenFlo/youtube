# Chức năng: Luồng kết hợp tự động hóa:
#   1. MUSEAI (https://muse.ai/) -> Viết Kịch Bản Cốt Truyện Hoạt Hình 3D có đầu có cuối
#      (Mở đầu Hook -> Diễn biến -> Cao trào -> Kết thúc), thiết kế Hồ sơ Nhân vật 3D (Character Lock)
#      và sinh Prompt 3D chuyên nghiệp cho từng khung/cảnh (thay thế hoàn toàn Ollama Local).
#   2. GOOGLE FLOW (https://flow.google.com/) -> Nhận từng Prompt 3D từ kịch bản của MuseAI,
#      tự động tạo Video Hoạt Hình 3D CGI thật (Pixar / DreamWorks / Unreal Engine 5 style) cho từng cảnh
#      (Scene 1 -> Scene N), loại bỏ hoàn toàn lệnh ép 2D stickman / hình học 2D cũ.
#   3. AUTO COMPILER (TTS + MoviePy / FFmpeg) -> Tự động lồng tiếng lời dẫn của từng cảnh,
#      đồng bộ thời lượng, thêm phụ đề đáy màn hình và ghép toàn bộ các video phân cảnh của Google Flow
#      thành 1 bộ phim 3D hoàn chỉnh lưu vào thư mục `output/`.

from __future__ import annotations

import os
import re
import sys
import json
import time
import hashlib
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable

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


def safe_log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

FLOW_CONFIG_PATH = ROOT_DIR / "flow_config.json"
MUSEAI_CONFIG_PATH = ROOT_DIR / "museai_config.json"
TEMP_DIR = ROOT_DIR / "temp" / "museai_flow_3d"
ATTEMPTS_DIR = ROOT_DIR / "temp" / "flow_attempts"
OUTPUT_DIR = ROOT_DIR / "output"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_BROWSER_LOCK = threading.Lock()


# ==============================================================================
# PHẦN 1: CHUẨN MỸ THUẬT 3D PIXAR / UNREAL ENGINE 5 CHO GOOGLE FLOW (CẤM 2D)
# ==============================================================================

PIXAR_3D_CANONICAL_GUIDANCE = (
    "Style: Masterpiece 3D feature-film animation, Pixar RenderMan and DreamWorks 3D CGI studio quality, "
    "Unreal Engine 5 Lumen global illumination, Octane 3D render, sculpted high-poly 3D character mesh "
    "with expressive facial blendshapes, realistic subsurface scattering (SSS) on skin, groomed 3D hair strands, "
    "physically based rendering (PBR) clothing and textures, volumetric lighting, shallow depth of field bokeh. "
    "STRICTLY NO 2D flat cartoon, NO 2D vector illustration, NO stickman, NO 2D geometric shapes/blocks, "
    "NO captions, subtitles, logos, or watermarks inside the video."
)

FORBIDDEN_2D_PATTERN = re.compile(
    r"\b("
    r"2d animation|flat 2d|2d cartoon|stickman|stick figure|vector art|cel-shaded|cel shaded|"
    r"geometric blocks|geometric shapes|color-coded geometric|primitive shapes|basic shapes|"
    r"flat design|cutout animation|paper cutout|strictly no 3d|no 3d|no cgi"
    r")\b",
    re.IGNORECASE,
)


def strip_forbidden_2d_terms(text: str) -> str:
    """
    Xoa cac cum tu 2D kem tien to phu dinh ("no 2D cartoon, no stickman...") truoc khi chen vao prompt,
    tranh bien thanh cau mau thuan lap lai ("no cinematic 3D CGI animation" x3) lam Veo tu choi prompt.
    """
    cleaned = re.sub(r"\b(?:strictly\s+)?no\s+" + FORBIDDEN_2D_PATTERN.pattern.strip(), "", str(text or ""), flags=re.IGNORECASE)
    cleaned = FORBIDDEN_2D_PATTERN.sub("cinematic 3D CGI animation", cleaned)
    cleaned = re.sub(r"(cinematic 3D CGI animation)(?:[\s,]+cinematic 3D CGI animation)+", r"\1", cleaned)
    cleaned = re.sub(r"(?:\s*,){2,}", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,.;:-")


def clean_and_build_flow_3d_video_prompt(
    scene_prompt: str,
    character_anchor: str = "",
    environment_anchor: str = "",
    camera_directive: str = "Smooth 3D dolly tracking shot, 35mm cinema lens, shallow depth of field",
    orientation: str = "vertical",
    scene_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Xây dựng Prompt sinh Video 3D gửi sang Google Flow (Google Veo):
    - Xóa bỏ 100% lệnh ép 2D stickman cũ trong flow_browser_service.py.
    - Khóa ngoại hình nhân vật 3D (Character Anchor) và bối cảnh 3D (Environment Anchor) xuyên suốt các cảnh.
    - Đồng bộ diễn xuất biểu cảm 3D, mấp máy môi (lip-sync speaking gestures) và tương tác giữa các nhân vật khớp với lời thoại.
    - Ép Google Flow render đúng 1 video clip hoạt hình 3D CGI thật (Pixar / DreamWorks / UE5).
    """
    cleaned_action = strip_forbidden_2d_terms(scene_prompt)

    ratio_hint = (
        "vertical 9:16 portrait (1080x1920)"
        if orientation == "vertical"
        else "horizontal 16:9 widescreen (1920x1080)"
    )

    char_lock = (
        f"Canonical 3D Character (keep 100% identical in every scene): {character_anchor.strip()}. "
        if character_anchor and character_anchor.strip()
        else ""
    )
    env_lock = (
        f"3D Environment & Lighting: {environment_anchor.strip()}. "
        if environment_anchor and environment_anchor.strip()
        else ""
    )

    interaction_cue = (
        "3D Character Performance & Dialogue Sync: Expressive 3D facial animation, natural speaking lip-sync gestures, "
        "emotional eye contact, and lively body language interaction between the characters matching the scene's story beat."
    )
    if isinstance(scene_data, dict):
        d_lines = scene_data.get("dialogue_lines")
        if isinstance(d_lines, list):
            speakers = [str(item.get("character_name") or item.get("speaker") or "") for item in d_lines if isinstance(item, dict) and item.get("speaker") != "narrator"]
            if speakers:
                names_str = ", ".join(dict.fromkeys(s for s in speakers if s))
                interaction_cue = (
                    f"3D Character Performance & Dialogue Sync: Expressive 3D facial animation, natural speaking lip-sync gestures, "
                    f"and direct character interaction ({names_str}) matching the spoken dialogue of this exact scene."
                )

    return (
        "Generate exactly ONE 3D CGI ANIMATION VIDEO CLIP, not a still image, and strictly NO 2D flat cartoon or geometric shapes. "
        "Strictly mute video, no audio generation, silent video only.\n"
        f"{char_lock}{env_lock}"
        f"Scene 3D Action: {cleaned_action}. {interaction_cue}\n"
        f"{PIXAR_3D_CANONICAL_GUIDANCE}\n"
        f"Camera & Composition: {ratio_hint}, {camera_directive.strip()}, fluid 3D skeletal animation, rich volumetric lighting, no audio."
    )


def clean_and_build_flow_3d_image_prompt(
    scene_prompt: str,
    character_anchor: str = "",
    environment_anchor: str = "",
    camera_directive: str = "35mm cinema lens, shallow depth of field, cinematic composition",
    orientation: str = "vertical",
    scene_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Xây dựng Prompt sinh Hình ảnh 3D Keyframe liên tục trên Google Flow (Nano Banana 2.1 - 0 tín dụng):
    - Tự động áp dụng khóa nhân vật 7-Point Character DNA (`preserve the exact same...`) để hình ảnh nhân vật
      cố định 100% qua mọi câu thoại.
    - Mô tả rõ biểu cảm gương mặt 3D, ánh mắt, cử chỉ tay và bố cục điện ảnh có chiều sâu để khi đưa vào
      Visual Beats (zoom_in, zoom_out, pan_right) tạo hiệu ứng chuyển động mượt và cuốn hút liên tục.
    """
    try:
        from src.flow_character_vault import build_7_point_character_dna
    except ModuleNotFoundError:
        from video_studio.src.flow_character_vault import build_7_point_character_dna

    cleaned_action = strip_forbidden_2d_terms(scene_prompt)

    ratio_hint = (
        "vertical 9:16 portrait (1080x1920)"
        if orientation == "vertical"
        else "horizontal 16:9 widescreen (1920x1080)"
    )

    dna_anchor = build_7_point_character_dna(character_anchor.strip()) if (character_anchor and character_anchor.strip()) else ""
    char_lock = (
        f"Canonical 3D Character (keep 100% identical in every frame): {dna_anchor} "
        if dna_anchor
        else ""
    )
    env_lock = (
        f"3D Environment & Lighting: {environment_anchor.strip()}. "
        if environment_anchor and environment_anchor.strip()
        else ""
    )

    expression_cue = (
        "3D Keyframe Storytelling & Expression: Dynamic 3D character pose mid-action, expressive Pixar-grade eyes and facial emotion, "
        "layered foreground/midground/background depth for cinematic camera motion."
    )
    if isinstance(scene_data, dict):
        role_txt = str(scene_data.get("scene_role") or "")
        if "Climax" in role_txt:
            expression_cue = (
                "3D Keyframe Storytelling & Expression: High-drama climax moment, intense emotional 3D facial expression, "
                "dramatic rim lighting and glowing volumetric particles."
            )

    return (
        "Generate a single masterpiece 3D CGI animated movie still frame (Pixar / DreamWorks / Unreal Engine 5 feature film render), "
        "strictly NO 2D flat cartoon, NO text, NO watermarks, NO split-screen.\n"
        f"{char_lock}{env_lock}"
        f"Scene Moment: {cleaned_action}. {expression_cue}\n"
        f"{PIXAR_3D_CANONICAL_GUIDANCE}\n"
        f"Camera & Framing: {ratio_hint}, {camera_directive.strip()}, ultra-detailed 8k 3D textures, volumetric lighting."
    )


def sanitize_prompt_for_flow_retry(prompt_text: str) -> str:
    """
    Làm sạch và tinh gọn prompt khi Google Flow (Veo) từ chối sinh nội dung ở lần thử 1
    (thường do bộ lọc an toàn của Veo nhạy cảm với các từ khóa tuổi trẻ em kết hợp cảm xúc sợ hãi/nguy hiểm):
    - Thay các cụm từ '9-year-old boy', '10-year-old girl', 'child', 'kid' bằng 'stylized Pixar 3D animated character'.
    - Thay các từ cảm xúc tiêu cực/bạo lực ('terrified', 'screaming', 'attack', 'destroy', 'blood', 'dead') bằng mô tả điện ảnh 3D an toàn.
    """
    txt = str(prompt_text or "")
    age_patterns = [
        (r"\b(?:[1-9]|1[0-7])-year-old\b", "stylized"),
        (r"\b(?:spear|knife|dagger|axe|sword|club)\b", "wooden walking stick"),
        (r"\b(?:hungry|starving|rumbling stomach|pleading)\b", "curious"),
        (r"\b\d{1,2}-year-old\s+(?:boy|girl|child|kid)\b", "stylized Pixar 3D animated young explorer character"),
        (r"\b(?:young\s+)?(?:boy|girl|child|kid|children|kids)\b", "stylized Pixar 3D animated adventurer character"),
        (r"\b(?:terrified|horrified|panic|screaming|crying|bleeding|attacking|destroying|violent|deadly)\b", "expressive cinematic"),
    ]
    for pat, repl in age_patterns:
        txt = re.sub(pat, repl, txt, flags=re.IGNORECASE)
    return txt



# ==============================================================================
# PHẦN 2: PROMPT GIAO VIỆC CHO MUSEAI VIẾT KỊCH BẢN CỐT TRUYỆN 3D CÓ ĐẦU CÓ CUỐI
# ==============================================================================

def build_museai_story_script_prompt(
    topic: str = "",
    target_scenes: Optional[int] = None,
    language: str = "vi",
    orientation: str = "vertical",
    episode_num: int = 1,
    total_episodes: int = 1,
    previous_episodes_summary: str = "",
    locked_character_anchor: str = "",
    locked_environment_anchor: str = "",
    story_style: str = "cinematic_storytelling",
    visual_mode: str = "video_3d",
    previous_episode_learning: str = "",
    required_episode_topic: str = "",
    whiteboard_ai_enabled: bool = True,
) -> str:
    """
    Prompt gửi vào tab Chrome MuseAI (https://muse.ai/) để kêu MuseAI viết kịch bản
    cốt truyện hoạt hình 3D sâu sắc, logic, giàu cảm xúc + kết hợp Dẫn chuyện & Tương tác nhân vật tự nhiên
    + thiết kế Character Bible 3D để chuyển sang Google Flow render từng cảnh.
    Hỗ trợ cả Phim lẻ (1 tập), Ít tập (Mini-Series 2-3 tập) và Nhiều tập (Series dài kỳ 4-10+ tập),
    đảm bảo MỖI TẬP đều có đủ Mở đầu (Opening) -> Cao trào (Climax) -> Kết thúc (Ending/Cliffhanger).
    """
    aspect = "9:16 vertical portrait" if orientation == "vertical" else "16:9 widescreen landscape"
    lang_label = ("Vietnamese explanations with separate English pronunciation segments" if language == "vi_en"
                  else "Vietnamese (Tiếng Việt)" if language == "vi" else "English")
    ep_num = max(1, int(episode_num or 1))
    tot_eps = max(1, int(total_episodes or 1))
    style_norm = str(story_style or "cinematic_storytelling").strip().lower()
    from src.museai_story_modes import whiteboard_script_prompt, learning_series_instructions
    if visual_mode == "whiteboard":
        return whiteboard_script_prompt(topic, target_scenes, language, orientation, ep_num, tot_eps,
                                        previous_episodes_summary, locked_character_anchor,
                                        previous_episode_learning, required_episode_topic, story_style,
                                        ai_enabled=whiteboard_ai_enabled)
    learning_instructions = learning_series_instructions(ep_num, tot_eps, previous_episode_learning,
                                                        required_episode_topic)
    learning_instructions += '\nReturn publishing={"hashtags": [3 or 4 concise hashtags directly relevant to this episode]}. Avoid unrelated trends or claims of guaranteed views; the application adds the channel hashtag.\n'
    if language == "vi_en":
        from src.english_teaching import english_lesson_instructions
        learning_instructions += english_lesson_instructions()

    if target_scenes and int(target_scenes) >= 2:
        n_scenes = int(target_scenes)
        scene_count_str = f"exactly {n_scenes} sequential scenes (numbered 1 to {n_scenes})"
        scene_rule_header = f"COMPLETE STORYLINE WITH BEGINNING, CLIMAX & ENDING ({n_scenes} SCENES - CÓ ĐẦU CÓ CUỐI LIỀN MẠCH)"
    else:
        n_scenes = 6
        scene_count_str = "6 to 8 sequential scenes (numbered 1..N, dynamically matched to the story beats)"
        scene_rule_header = "COMPLETE STORYLINE WITH BEGINNING, CLIMAX & ENDING (AUTO-ALIGNED STORY SHOTS - CÓ ĐẦU CÓ CUỐI, SỐ KHUNG HÌNH KHỚP 1:1 VỚI CÂU CHUYỆN)"

    topic_line = (
        f"Story Topic / Series Concept: \"{topic.strip()}\""
        if topic and topic.strip()
        else "Story Topic / Series Concept: Brainstorm an original, emotionally gripping, cinematic Pixar-style 3D animated adventure with a clear beginning, rising conflict, dramatic climax, and meaningful ending."
    )

    if style_norm == "viral_knowledge":
        style_guidance = (
            "STORYTELLING & VOICEOVER STYLE (VIRAL KNOWLEDGE / DOCUMENTARY EXPLAINER):\n"
            "   - Write with the intellectual depth, vivid imagery, and curiosity-driven pacing of a Kurzgesagt / BBC Earth / TED-Ed masterpiece in natural, eloquent Vietnamese.\n"
            "   - Open Scene 1 with a mind-blowing hook or question that immediately sparks curiosity.\n"
            "   - Explain the real cause-and-effect progression step by step with concrete, fascinating details (never childish or superficial)."
        )
    elif style_norm == "pixar_dialogue":
        style_guidance = (
            "STORYTELLING & VOICEOVER STYLE (CINEMATIC PIXAR DRAMA & NATURAL DIALOGUE):\n"
            "   - Write with the emotional warmth, wit, and dramatic tension of a theatrical Pixar / DreamWorks feature film.\n"
            "   - Combine evocative narrator storytelling with natural, authentic first-person character dialogue."
        )
    else:
        style_guidance = (
            "STORYTELLING & VOICEOVER STYLE (CAPTIVATING CINEMATIC STORYTELLING):\n"
            "   - Write with rich, evocative, natural Vietnamese prose — poetic yet crystal clear, emotionally resonant, and logically tight from the first second to the finale.\n"
            "   - Avoid robotic, childish 7-word sentences or repetitive mechanical connectors ('Ngày xưa... Thế nhưng... Chính vì vậy...'). Let each scene flow naturally like a master storyteller."
        )

    continuity_block = ""
    if tot_eps > 1:
        if ep_num == 1:
            ep_arc_instruction = (
                f"MULTI-EPISODE SERIES MODE — EPISODE 1 OF {tot_eps} (OPENING EPISODE):\n"
                f"   - This video is Episode 1 of a {tot_eps}-episode continuous 3D animated series.\n"
                f"   - Even though it is Episode 1, this episode MUST have its own complete 3-act dramatic arc:\n"
                f"     + Act 1 (Opening Hook): Introduce the protagonist, world, and central mystery.\n"
                f"     + Act 2 (Rising Conflict & Episode 1 Climax): Deliver an exciting, high-stakes Climax for Episode 1.\n"
                f"     + Act 3 (Episode 1 Ending & Cliffhanger Hook for Episode 2): Resolve Episode 1's immediate challenge while unveiling a thrilling new discovery that hooks viewers into Episode 2!"
            )
        elif ep_num < tot_eps:
            ep_arc_instruction = (
                f"MULTI-EPISODE SERIES MODE — EPISODE {ep_num} OF {tot_eps} (CONTINUATION EPISODE):\n"
                f"   - This video is Episode {ep_num} of {tot_eps}, directly continuing the story from Episode {ep_num - 1}.\n"
                f"   - Previous Episodes Story Summary: {previous_episodes_summary or 'Continue the protagonist journey into the next stage.'}\n"
                f"   - Locked Canonical 3D Character (MUST keep 100% identical to previous episodes): {locked_character_anchor or 'Keep main character identical.'}\n"
                f"   - Locked 3D World Continuity: {locked_environment_anchor or 'Maintain world visual continuity.'}\n"
                f"   - This episode MUST have its own complete 3-act dramatic arc:\n"
                f"     + Act 1 (Opening Bridge): Pick up immediately from Episode {ep_num - 1}'s ending with a seamless continuation hook.\n"
                f"     + Act 2 (Escalating Conflict & Episode {ep_num} Climax): Face a deeper obstacle and reach a dramatic Climax specific to Episode {ep_num}.\n"
                f"     + Act 3 (Episode {ep_num} Ending & Cliffhanger for Episode {ep_num + 1}): Conclude this chapter and leave an irresistible suspense hook leading into Episode {ep_num + 1}!"
            )
        else:
            ep_arc_instruction = (
                f"MULTI-EPISODE SERIES MODE — EPISODE {ep_num} OF {tot_eps} (FINAL EPISODE / GRAND FINALE):\n"
                f"   - This video is the Final Episode ({ep_num} of {tot_eps}) of the 3D animated series.\n"
                f"   - Previous Episodes Story Summary: {previous_episodes_summary or 'Lead into the final confrontation of the series.'}\n"
                f"   - Locked Canonical 3D Character (MUST keep 100% identical to previous episodes): {locked_character_anchor or 'Keep main character identical.'}\n"
                f"   - Locked 3D World Continuity: {locked_environment_anchor or 'Maintain world visual continuity.'}\n"
                f"   - This episode MUST deliver the complete 3-act finale arc:\n"
                f"     + Act 1 (Opening Bridge): Connect directly from Episode {ep_num - 1} into the decisive moment.\n"
                f"     + Act 2 (Grand Climax): Deliver the ultimate emotional and visual Climax of the entire series.\n"
                f"     + Act 3 (Grand Finale & Complete Resolution): Resolve the overarching storyline with a heartwarming, unforgettable conclusion."
            )
        continuity_block = f"\n{ep_arc_instruction}\n"
    elif previous_episodes_summary or locked_character_anchor:
        continuity_block = (
            f"\nSTORY CONTINUITY FROM PREVIOUS EPISODE:\n"
            f"   - Previous Story Summary: {previous_episodes_summary}\n"
            f"   - Locked Canonical 3D Character: {locked_character_anchor}\n"
        )

    return f"""Act as a Master Pixar / DreamWorks 3D Animation Story Director & Screenwriter.
Do NOT generate any images, videos, or run Python code. Your ONLY task right now is to write a complete {n_scenes}-scene 3D animated short film script (Episode {ep_num} of {tot_eps}) and scene-by-scene 3D visual prompts so I can feed each scene sequentially into Google Flow to render the 3D visuals.
CRITICAL MEMORY RESET: Do NOT search your saved memory or reuse old characters/storyboards like 'Lumi' or 'Uga' from previous threads. Write a 100% fresh, intelligent, logically coherent script specifically for the topic below.

{topic_line}
Target Format: {scene_count_str} ({aspect}), natural voiceover storytelling & authentic character dialogue in {lang_label}.
{style_guidance}{continuity_block}{learning_instructions}
MANDATORY RULES:
1. {scene_rule_header}:
   - You MUST output ALL scenes in the `scenes` array (`scene_num` from 1 to {n_scenes}). Never stop at 1 scene.
   - EVERY VIDEO MUST HAVE 3 CLEAR DRAMATIC ACTS (MỞ ĐẦU - CAO TRÀO - KẾT THÚC):
     + Scene 1 (Opening Hook): Immediately hook the viewer with a compelling mystery, vivid sensory detail, or thought-provoking question.
     + Middle Scenes (Rising Action & Dramatic Climax): Build genuine cause-and-effect progression, emotional stakes, and tension leading to a powerful Climax. Use natural, varied transitions in `{lang_label}` (do NOT mechanically repeat the same formulaic starter words in every scene).
     + Final Scene (Resolution / Ending): Deliver a deeply satisfying, memorable conclusion or insight (and a cliffhanger bridge if there is a next episode).
   - PACING RULE (1 SHOT = 1 STORY BEAT, NO VIDEO LOOPING): Keep each scene's spoken script (`narration` / `dialogue_lines`) rich yet well-paced (around 20 to 32 words per scene, ~7–10 seconds of natural speech).
2. AUTHENTIC SPOKEN SCRIPT & DIALOGUE LOGIC (`dialogue_lines` — NO STAGE DIRECTIONS IN CHARACTER VOICE):
   - Combine an expressive storyteller (`"speaker": "narrator"`) and authentic character speech (`"speaker": "character_1"`, `"speaker": "character_2"`) in {lang_label} where dramatically appropriate.
   - STRICT DIALOGUE LOGIC:
     + NEVER put third-person stage directions or action descriptions inside a character's line (e.g., NEVER write `"speaker": "character_2", "text": "Uga chỉ tay, hét lên báo nguy!"` — third-person action descriptions MUST belong to `"speaker": "narrator"`!).
     + Character lines (`character_1`, `character_2`) MUST be 100% direct first-person spoken dialogue that makes complete logical sense in the story's setting (if characters are pre-verbal humans learning their very first sounds, they should only utter realistic primitive/first words or let the `narrator` eloquently narrate their realization — never have a pre-verbal caveman speak a modern sentence complaining that language doesn't exist!).
   - Set `"narration"` to the combined spoken text of that scene.
3. 100% VISUAL-AUDIO SYNCHRONIZATION & STRICT 3D CHARACTER CONSISTENCY (`character_anchor` & `video_prompt`):
   - Design canonical 3D characters in high-poly Pixar 3D CGI style in `"character_anchor"` (if `Locked Canonical 3D Character` is provided above, copy it verbatim into `"character_anchor"` so the character stays 100% identical across all episodes).
   - Every `"video_prompt"` (in English) MUST visually depict a distinct new camera angle, exact physical action, character interaction, expressive 3D facial emotion, and natural speaking lip-sync gestures that match that scene's `"dialogue_lines"` 1:1.
   - Strictly NO 2D cartoon, NO stickman, NO geometric primitives/blocks, and NO readable text/numbers/signs inside the visual scene.

OUTPUT FORMAT:
Reply with ONLY a single valid JSON code block containing a JSON object with these exact keys:
- "story_title": (string, title of the 3D story/episode in {lang_label})
- "character_anchor": (string, detailed English 3D Pixar character description locked across all scenes and episodes)
- "environment_anchor": (string, detailed English 3D world and lighting description)
- "episode_learning_summary": (string, a short specific summary of what viewers learn in the body)
- "next_episode_topic": (string, the concrete next lesson for a non-final series episode; otherwise empty)
- "scenes": (array of objects from scene_num 1 to {n_scenes}, where each object has keys: "scene_num", "scene_role", "dialogue_lines" [array of objects with "speaker" ("narrator" | "character_1" | "character_2"), "character_name", "text"], "narration", "camera_directive", "video_prompt")"""


ROLE_VOICE_MAP_VI = {
    "narrator": "vi-VN-HoaiMyNeural|story_warm",
    "character_1": "vi-VN-NamMinhNeural|char_boy_bright",
    "character_2": "vi-VN-NamMinhNeural|char_elder_deep",
    "character_female": "vi-VN-HoaiMyNeural|char_female_bright",
}

LINE_EMOTIONS = {"happy", "excited", "surprised", "angry", "sad", "thinking", "neutral"}

ROLE_VOICE_MAP_EN = {
    "narrator": "en-US-EmmaNeural",
    "character_1": "en-US-GuyNeural",
    "character_2": "en-GB-RyanNeural",
    "character_female": "en-US-JennyNeural",
}


# Nhiều giọng Edge cho từng giới: cùng tên nhân vật luôn ra cùng một giọng, tên khác nhau thường ra giọng khác nhau.
CHARACTER_VOICE_POOL_VI = {
    "character_1": ["char_boy_bright", "char_hero_deep", "char_comic"],
    "character_female": ["char_female_bright", "char_girl_cute", "char_mother_warm"],
}
CHARACTER_BASE_VOICE_VI = {
    "character_1": "vi-VN-NamMinhNeural",
    "character_female": "vi-VN-HoaiMyNeural",
}


def _pick_character_voice(role: str, character_name: str, vmap: Dict[str, str], language: str) -> str:
    name = str(character_name or "").strip().lower()
    if language != "vi" or not name:
        return vmap[role]
    pool = CHARACTER_VOICE_POOL_VI[role]
    preset = pool[sum(ord(c) for c in name) % len(pool)]
    return f"{CHARACTER_BASE_VOICE_VI[role]}|{preset}"


def _resolve_speaker_role_and_voice(
    speaker_raw: str,
    character_name: str = "",
    context_hint: str = "",
    language: str = "vi",
) -> Tuple[str, str, str]:
    """
    Chuẩn hóa vai đọc (`narrator`, `character_1`, `character_2`, `character_female`),
    tên hiển thị và `voice_spec` tương ứng để tạo sự tương phản rõ rệt giữa Người dẫn chuyện và Nhân vật.
    """
    sp = str(speaker_raw or "").strip().lower()
    cname = str(character_name or "").strip()
    ctx = f"{sp} {cname.lower()} {str(context_hint or '').lower()}"
    vmap = ROLE_VOICE_MAP_VI if language == "vi" else ROLE_VOICE_MAP_EN

    if sp in ("narrator", "dẫn chuyện", "người dẫn chuyện", "storyteller", "voiceover"):
        return "narrator", "Người dẫn chuyện", vmap["narrator"]

    if any(k in ctx for k in ("elder", "guardian", "mentor", "old", "ông lão", "cụ", "thần", "bóng hình", "trầm ấm", "vang vọng", "cổ xưa", "vang lên", "bí ẩn", "character_2", "char_2")):
        label = cname if cname and cname.lower() not in ("character_2", "char_2") else "Giọng nói cổ xưa / Hộ vệ"
        return "character_2", label, vmap["character_2"]

    if any(k in ctx for k in ("female", "girl", "fairy", "cô bé", "tinh linh", "nữ", "mẹ", "bà", "character_female")):
        label = cname if cname and cname.lower() not in ("character_female",) else "Nhân vật nữ"
        return "character_female", label, _pick_character_voice("character_female", cname, vmap, language)

    label = cname if cname and cname.lower() not in ("character_1", "char_1", "character", "protagonist") else "Nhân vật chính"
    return "character_1", label, _pick_character_voice("character_1", cname, vmap, language)


def _generate_contextual_character_interaction(
    narration_text: str,
    scene_num: int = 1,
    total_scenes: int = 4,
    scene_role: str = "",
    language: str = "vi",
) -> List[Dict[str, str]]:
    """
    Khi kịch bản đọc từ MuseAI ở một phân cảnh chỉ có lời dẫn ngôi thứ 3 (chưa tách lời thoại nhân vật),
    tự động tạo lời thoại tương tác tự nhiên của nhân vật bám sát 100% từ khóa ngữ cảnh và vị trí cảnh (1..total_scenes).
    Hỗ trợ linh hoạt kịch bản nhiều cảnh (4, 8, 12, 20 cảnh) mà không bị trùng lặp lời thoại.
    """
    low = narration_text.lower()
    role_low = str(scene_role or "").lower()
    tot = max(2, int(total_scenes or 4))
    is_last_scene = (scene_num >= tot) or ("resolution" in role_low) or ("ending" in role_low)
    is_climax_scene = (scene_num == tot - 1 and tot >= 3) or ("climax" in role_low) or ("cao trào" in role_low)

    if language != "vi":
        if scene_num == 1 or "hook" in role_low or "opening" in role_low:
            return [{"speaker": "character_1", "character_name": "Hero", "text": "Wait, look at this glowing light! Where is it leading us?"}]
        if is_last_scene:
            return [{"speaker": "character_1", "character_name": "Hero", "text": "Look! The whole world is glowing with life again!"}]
        if is_climax_scene:
            return [
                {"speaker": "character_2", "character_name": "Guardian", "text": "Protect the light with all your heart, young traveler!"},
                {"speaker": "character_1", "character_name": "Hero", "text": "I promise! I won't let the darkness win!"},
            ]
        mid_en_pool = [
            [{"speaker": "character_1", "character_name": "Hero", "text": "The ancient mechanism is moving! Stay close to me!"}],
            [
                {"speaker": "character_2", "character_name": "Guardian", "text": "Be careful, the path ahead tests your courage."},
                {"speaker": "character_1", "character_name": "Hero", "text": "I'm not afraid, we have to keep going!"},
            ],
            [{"speaker": "character_1", "character_name": "Hero", "text": "Look over there! That clue matches what we found earlier!"}],
        ]
        return mid_en_pool[(scene_num - 2) % len(mid_en_pool)]

    # Tiếng Việt: Kiểm tra theo đúng giai đoạn câu chuyện (Ending -> Climax -> Opening Hook -> Middle Scenes 2..N-2)
    if is_last_scene or "bình minh" in low or "nảy mầm" in low or "hồi sinh" in low:
        return [
            {
                "speaker": "character_1",
                "character_name": "Nhân vật chính",
                "text": "Nhìn kìa, cả thung lũng đã bừng sáng trở lại rồi! Khu rừng của chúng ta đã thực sự hồi sinh!",
            }
        ]
    if is_climax_scene:
        return [
            {
                "speaker": "character_2",
                "character_name": "Giọng nói cổ xưa",
                "text": "Hãy giữ vững lòng dũng cảm, ánh sáng luôn ở trong tim cháu!",
            },
            {
                "speaker": "character_1",
                "character_name": "Nhân vật chính",
                "text": "Cháu hiểu rồi! Cháu nhất định sẽ bảo vệ hạt giống ánh sáng này!",
            },
        ]
    if "bánh răng" in low or "cỗ máy" in low or "cánh cửa" in low or "yếu dần" in low:
        return [
            {
                "speaker": "character_1",
                "character_name": "Nhân vật chính",
                "text": "Ôi không, những bánh răng khổng lồ đang quay và hạt giống ánh sáng đang yếu dần!",
            },
            {
                "speaker": "character_2",
                "character_name": "Giọng nói cổ xưa",
                "text": "Hãy bước tới đi cậu bé dũng cảm, vận mệnh của khu rừng đang nằm trong tay cháu.",
            },
        ]
    if "la bàn" in low or "bản đồ" in low or "phát hiện" in low or "tình cờ" in low or scene_num == 1 or "hook" in role_low:
        return [
            {
                "speaker": "character_1",
                "character_name": "Nhân vật chính",
                "text": "Ơ kìa, chiếc la bàn cổ đang tự phát sáng! Nó muốn dẫn mình tới nơi nào thế nhỉ?",
            }
        ]

    # Các phân cảnh giữa (khi kịch bản có 6, 8, 12, 20 cảnh): luân phiên đối thoại đa dạng không trùng lặp
    mid_vi_pool = [
        [
            {"speaker": "character_1", "character_name": "Nhân vật chính", "text": "Lối đi phía trước đang mở ra kìa, mình phải nhanh chân lên thôi!"},
            {"speaker": "character_2", "character_name": "Người đồng hành", "text": "Cẩn thận nhé, thử thách thật sự vẫn đang ở phía trước đấy!"},
        ],
        [
            {"speaker": "character_1", "character_name": "Nhân vật chính", "text": "Dấu hiệu này chính là manh mối mà chúng ta đang tìm kiếm!"},
        ],
        [
            {"speaker": "character_2", "character_name": "Giọng nói cổ xưa", "text": "Chỉ những trái tim kiên định mới vượt qua được màn sương này."},
            {"speaker": "character_1", "character_name": "Nhân vật chính", "text": "Dù khó khăn thế nào cháu cũng không bỏ cuộc đâu!"},
        ],
        [
            {"speaker": "character_1", "character_name": "Nhân vật chính", "text": "Sắp tới nơi rồi, nguồn sáng đang ở ngay trước mắt chúng ta!"},
        ],
    ]
    return mid_vi_pool[(scene_num - 2) % len(mid_vi_pool)]


def is_third_person_stage_direction(text: str, character_name: str = "") -> bool:
    """
    Phát hiện xem một câu thoại bị gán nhầm cho nhân vật (`character_1` / `character_2`)
    thực chất có phải là câu mô tả hành động ngôi thứ 3 (stage direction) hay không:
    - Ví dụ: `"Uga chỉ tay, hét lên một tiếng báo nguy cho Lumi!"` hoặc `"Lumi mỉm cười và bước tới bên đống lửa."`
    - Nếu câu bắt đầu bằng chính tên nhân vật (hoặc 'Cậu bé', 'Cô bé', 'Nhân vật') đi kèm động từ mô tả hành động ngôi thứ 3
      mà không phải lời xưng hô trực tiếp ('Uga ơi', 'Lumi ơi', 'Lumi, ...'), trả về True để chuyển về giọng `narrator`.
    """
    t = str(text or "").strip().strip("\"'“”‘’")
    if not t:
        return False
    t_low = t.lower()
    cname = str(character_name or "").strip().lower()

    stage_verbs_vi = (
        "chỉ tay",
        "hét lên",
        "mỉm cười",
        "bước tới",
        "bước đi",
        "nhìn theo",
        "quay lại",
        "gật đầu",
        "lắc đầu",
        "chạy tới",
        "giật mình",
        "nắm chặt",
        "đứng dậy",
        "ngước nhìn",
        "cúi xuống",
        "vẫy tay",
        "ôm chầm",
        "bật khóc",
        "thở dài",
    )

    if cname and cname not in ("narrator", "người dẫn chuyện", "character_1", "character_2"):
        # Nếu câu bắt đầu bằng chính tên nhân vật đang nói (VD: "Uga chỉ tay..." khi speaker là Uga)
        # và theo sau KHÔNG phải từ gọi ("ơi", ",")
        if t_low.startswith(cname + " ") and not t_low.startswith((cname + " ơi", cname + ",")):
            return True

    for verb in stage_verbs_vi:
        if verb in t_low and not any(fp in t_low for fp in ("tôi ", "mình ", "cháu ", "ta ", "chúng ta ", "chúng mình ", "cậu ", "bạn ", "ơi")):
            return True

    return False


def build_scene_dialogue_segments(
    scene_data: Dict[str, Any],
    language: str = "vi",
    total_scenes: int = 4,
    allow_synthetic_filler: bool = True,
) -> List[Dict[str, str]]:
    """
    Chuyển đổi dữ liệu một phân cảnh (`scene_data`) thành danh sách các phân đoạn lồng tiếng đa giọng đọc
    kết hợp nhịp nhàng giữa **Người dẫn chuyện (`narrator`)** và **Tương tác nhân vật (`character_1`, `character_2`)**.
    - Tự động phát hiện và chuyển các câu mô tả hành động ngôi thứ 3 bị gán nhầm vào nhân vật (VD: 'Uga chỉ tay, hét lên...')
      về đúng giọng `narrator` ('Người dẫn chuyện').
    Mỗi phần tử trả về có dạng:
      {"speaker": ..., "character_name": ..., "text": ..., "voice_spec": ..., "rate": "+0%"}
    """
    if not isinstance(scene_data, dict):
        scene_data = {"scene_num": 1, "narration": str(scene_data or "")}

    if language == "vi_en" or scene_data.get("content_mode") == "english_teaching_vi":
        from src.english_teaching import build_english_lesson_segments
        segments = build_english_lesson_segments(scene_data, ROLE_VOICE_MAP_VI["narrator"])
        scene_data["content_mode"] = "english_teaching_vi"
        scene_data["speech_segments"] = segments
        scene_data["dialogue_lines"] = segments
        scene_data["narration"] = " ".join(seg["text"] for seg in segments)
        scene_data["dialogue_display"] = "<br>".join(
            f"{'🇻🇳 Giảng bài' if seg['language'] == 'vi' else '🇬🇧 Phát âm'}: {seg['text']}" for seg in segments)
        return segments

    scene_num = int(scene_data.get("scene_num") or 1)
    scene_role = str(scene_data.get("scene_role") or f"Scene {scene_num}")
    raw_lines = scene_data.get("dialogue_lines")
    segments: List[Dict[str, str]] = []

    # 1. Nếu MuseAI đã trả về mảng `dialogue_lines` có cấu trúc
    if isinstance(raw_lines, list) and len(raw_lines) > 0:
        for item in raw_lines:
            if not isinstance(item, dict):
                continue
            txt = str(item.get("text") or item.get("line") or item.get("narration") or "").strip().strip("\"'“”‘’")
            if not txt:
                continue
            raw_sp = str(item.get("speaker") or item.get("role") or "narrator")
            raw_cname = str(item.get("character_name") or item.get("name") or "")
            sp_role, sp_label, v_spec = _resolve_speaker_role_and_voice(
                speaker_raw=raw_sp,
                character_name=raw_cname,
                context_hint=txt,
                language=language,
            )
            # Nếu dòng thoại của nhân vật lại là mô tả hành động ngôi thứ 3 ('Uga chỉ tay, hét lên...'), chuyển về Người dẫn chuyện!
            if sp_role != "narrator" and is_third_person_stage_direction(txt, character_name=raw_cname or sp_label):
                sp_role, sp_label, v_spec = _resolve_speaker_role_and_voice("narrator", language=language)

            line_emotion = str(item.get("emotion") or "").strip().lower()
            seg_item = {
                "speaker": sp_role,
                "character_name": sp_label,
                "text": txt,
                "voice_spec": v_spec,
                "rate": "+0%",
            }
            if line_emotion in LINE_EMOTIONS:
                seg_item["emotion"] = line_emotion
                if str(v_spec).startswith("vi-") and "|" in str(v_spec):
                    seg_item["voice_spec"] = f"{v_spec}|{line_emotion}"
            segments.append(seg_item)

    # 2. Nếu chưa có `dialogue_lines`, bóc tách từ `narration` (hỗ trợ tách câu thoại trong ngoặc '...' / "..." / “...”)
    if not segments:
        narr_raw = str(scene_data.get("narration") or "").strip()
        if narr_raw:
            quote_pattern = re.compile(r"([\"'“‘][^\"'”’]{4,}[\"'”’])")
            parts = quote_pattern.split(narr_raw)
            prev_narr_context = ""
            for part in parts:
                cl_part = part.strip()
                if not cl_part:
                    continue
                if (cl_part.startswith(("\"", "'", "“", "‘")) and cl_part.endswith(("\"", "'", "”", "’"))) and len(cl_part) > 4:
                    spoken_quote = cl_part[1:-1].strip()
                    if spoken_quote:
                        sp_role, sp_label, v_spec = _resolve_speaker_role_and_voice(
                            speaker_raw="character",
                            context_hint=prev_narr_context,
                            language=language,
                        )
                        segments.append(
                            {
                                "speaker": sp_role,
                                "character_name": sp_label,
                                "text": spoken_quote,
                                "voice_spec": v_spec,
                                "rate": "+0%",
                            }
                        )
                        if allow_synthetic_filler and sp_role == "character_2" and language == "vi":
                            _, boy_label, boy_v = _resolve_speaker_role_and_voice("character_1", "Nhân vật chính", language=language)
                            segments.append(
                                {
                                    "speaker": "character_1",
                                    "character_name": boy_label,
                                    "text": "Cháu hiểu rồi! Cháu nhất định sẽ bảo vệ hạt giống ánh sáng này!",
                                    "voice_spec": boy_v,
                                    "rate": "+0%",
                                }
                            )
                else:
                    cleaned_narr = cl_part.strip(" ,;:-")
                    if cleaned_narr:
                        prev_narr_context = cleaned_narr
                        _, n_label, n_voice = _resolve_speaker_role_and_voice("narrator", language=language)
                        segments.append(
                            {
                                "speaker": "narrator",
                                "character_name": n_label,
                                "text": cleaned_narr,
                                "voice_spec": n_voice,
                                "rate": "+0%",
                            }
                        )

    # 3. Chỉ tự động thêm lời thoại mẫu khi `allow_synthetic_filler=True` và không phải cảnh đã tách nhịp
    has_narrator = any(s["speaker"] == "narrator" for s in segments)
    has_character = any(s["speaker"] != "narrator" for s in segments)
    is_expanded_shot = bool(scene_data.get("is_expanded_shot", False))

    if allow_synthetic_filler and not is_expanded_shot and segments and has_narrator and not has_character:
        base_narr_text = " ".join(s["text"] for s in segments)
        extra_char_lines = _generate_contextual_character_interaction(
            narration_text=base_narr_text,
            scene_num=scene_num,
            total_scenes=total_scenes,
            scene_role=scene_role,
            language=language,
        )
        for ex in extra_char_lines:
            sp_role, sp_label, v_spec = _resolve_speaker_role_and_voice(
                speaker_raw=ex["speaker"],
                character_name=ex.get("character_name", ""),
                language=language,
            )
            segments.append(
                {
                    "speaker": sp_role,
                    "character_name": sp_label,
                    "text": ex["text"],
                    "voice_spec": v_spec,
                    "rate": "+0%",
                }
            )
    elif allow_synthetic_filler and not is_expanded_shot and segments and has_character and not has_narrator:
        _, n_label, n_voice = _resolve_speaker_role_and_voice("narrator", language=language)
        lead_in = (
            f"Ở phân cảnh {scene_num}, câu chuyện tiếp diễn đầy bất ngờ."
            if language == "vi"
            else f"In scene {scene_num}, the story unfolds with emotion."
        )
        segments.insert(
            0,
            {
                "speaker": "narrator",
                "character_name": n_label,
                "text": lead_in,
                "voice_spec": n_voice,
                "rate": "+0%",
            },
        )

    # Cập nhật ngược vào scene_data để đồng bộ 100% giữa TTS, Phụ đề và UI
    if segments:
        scene_data["dialogue_lines"] = segments
        scene_data["narration"] = " ".join(s["text"].strip() for s in segments if s.get("text"))
        display_parts = []
        for s in segments:
            icon = "🎙️ **Dẫn chuyện:**" if s["speaker"] == "narrator" else f"🗣️ **{s['character_name']}:**"
            display_parts.append(f"{icon} *\"{s['text']}\"*")
        scene_data["dialogue_display"] = "<br>".join(display_parts)

    return segments


def _split_long_segment_into_sentence_beats(
    seg: Dict[str, Any],
    max_words: int = 26,
) -> List[Dict[str, Any]]:
    """
    Nếu 1 lượt đọc (ví dụ đoạn dẫn chuyện nhiều câu) dài hơn `max_words`,
    tự động tách theo ranh giới câu (và mệnh đề dấu phẩy nếu câu quá dài)
    để mỗi nhịp vừa khít 1 khung video (~6-9s).
    """
    text = str(seg.get("text") or "").strip()
    words = text.split()
    if len(words) <= max_words:
        return [dict(seg)]

    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    sentences: List[str] = []
    for rs in raw_sentences:
        if len(rs.split()) > max_words:
            clauses = [c.strip() for c in re.split(r"(?<=[,;:])\s+", rs) if c.strip()]
            sentences.extend(clauses if len(clauses) > 1 else [rs])
        else:
            sentences.append(rs)

    chunks: List[str] = []
    cur_parts: List[str] = []
    cur_count = 0
    for sent in sentences:
        w_cnt = len(sent.split())
        if cur_parts and (cur_count + w_cnt > max_words):
            chunks.append(" ".join(cur_parts))
            cur_parts = [sent]
            cur_count = w_cnt
        else:
            cur_parts.append(sent)
            cur_count += w_cnt
    if cur_parts:
        chunks.append(" ".join(cur_parts))

    result: List[Dict[str, Any]] = []
    for ch in chunks:
        new_seg = dict(seg)
        new_seg["text"] = ch.strip()
        result.append(new_seg)
    return result


def expand_scenes_to_match_story_beats(
    scenes: List[Dict[str, Any]],
    language: str = "vi",
    max_words_per_shot: int = 26,
) -> List[Dict[str, Any]]:
    """
    Tự động chia/cân đối số khung hình (Story Shots) khớp 1:1 với mạch câu chuyện:
    - Mỗi khung hình video Google Flow (8-10s) chỉ đảm nhận đúng 1 nhịp câu chuyện (~15-26 từ, ~6-9.5s).
    - Nếu một cảnh từ MuseAI chứa cả đoạn dẫn chuyện dài lẫn lời thoại nhân vật (khiến tổng thời lượng > 10s),
      hàm sẽ tự động tách thành các khung hình độc lập (Khung 1: Mở cảnh / Hành động ➔ Khung 2: Cận cảnh tương tác / Đối thoại)
      với `raw_video_prompt` và `camera_directive` riêng biệt để Google Flow vẽ cảnh mới, TUYỆT ĐỐI không lặp lại 1 khung hình!
    """
    if not scenes:
        return []

    orig_total = max(2, len(scenes))
    expanded_shots: List[Dict[str, Any]] = []

    for orig_idx, raw_sc in enumerate(scenes, start=1):
        sc_copy = dict(raw_sc) if isinstance(raw_sc, dict) else {"scene_num": orig_idx, "narration": str(raw_sc)}
        sc_copy["scene_num"] = int(sc_copy.get("scene_num") or orig_idx)

        # Chỉ tự động bổ sung câu tương tác nếu tổng số từ của cảnh hiện tại đang ngắn (<= max_words_per_shot)
        # hoặc nếu cảnh đã có sẵn câu thoại trong ngoặc / dialogue_lines
        existing_narr = str(sc_copy.get("narration") or "").strip()
        has_explicit_dialogue = bool(sc_copy.get("dialogue_lines")) or bool(
            re.search(r"[\"“”'‘’]([^\"“”'‘’]{4,240})[\"“”'‘’]", existing_narr)
        )
        if not has_explicit_dialogue and len(existing_narr.split()) > max_words_per_shot:
            # Cảnh dẫn chuyện dài > max_words_per_shot không có ngoặc: tách trực tiếp thành các nhịp dẫn chuyện + tương tác
            segs = build_scene_dialogue_segments(sc_copy, language=language, total_scenes=orig_total)
        else:
            segs = build_scene_dialogue_segments(sc_copy, language=language, total_scenes=orig_total)

        atomic_segs: List[Dict[str, Any]] = []
        for s in segs:
            atomic_segs.extend(_split_long_segment_into_sentence_beats(s, max_words=max_words_per_shot))

        shot_groups: List[List[Dict[str, Any]]] = []
        cur_group: List[Dict[str, Any]] = []
        cur_words = 0

        for s in atomic_segs:
            w_cnt = len(str(s.get("text") or "").split())
            if cur_group and (cur_words + w_cnt > max_words_per_shot):
                shot_groups.append(cur_group)
                cur_group = [s]
                cur_words = w_cnt
            else:
                cur_group.append(s)
                cur_words += w_cnt
        if cur_group:
            shot_groups.append(cur_group)

        if len(shot_groups) <= 1:
            expanded_shots.append(sc_copy)
            continue

        base_vp = str(sc_copy.get("raw_video_prompt") or sc_copy.get("video_prompt") or "").strip()
        base_cam = str(
            sc_copy.get("camera_directive")
            or "35mm cinema lens, smooth 3D dolly tracking shot, shallow depth of field"
        ).strip()
        base_role = str(sc_copy.get("scene_role") or f"Scene {orig_idx}").strip()
        vp_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", base_vp) if s.strip()]

        for sub_idx, grp in enumerate(shot_groups, start=1):
            sub_sc = dict(sc_copy)
            sub_sc.pop("audio_path", None)
            sub_sc.pop("audio_duration", None)
            sub_sc.pop("video_path", None)

            sub_narr = " ".join(item["text"].strip() for item in grp if item.get("text"))
            display_parts = []
            for item in grp:
                icon = "🎙️ **Dẫn chuyện:**" if item["speaker"] == "narrator" else f"🗣️ **{item['character_name']}:**"
                display_parts.append(f"{icon} *\"{item['text']}\"*")

            sub_sc["dialogue_lines"] = grp
            if sub_sc.get("content_mode") == "english_teaching_vi":
                sub_sc["speech_segments"] = grp
            sub_sc["narration"] = sub_narr
            sub_sc["dialogue_display"] = "<br>".join(display_parts)
            sub_sc["scene_role"] = f"{base_role} - Nhịp {sub_idx}/{len(shot_groups)}"
            sub_sc["is_expanded_shot"] = True

            has_char_speech = any(item.get("speaker") != "narrator" for item in grp)
            if sub_idx == 1:
                vp_core = vp_sentences[0] if vp_sentences else base_vp
                sub_sc["raw_video_prompt"] = (
                    f"{vp_core}. Cinematic establishing 3D shot {orig_idx}.{sub_idx} focusing on the environment, "
                    f"character walking movement, and initial visual discovery."
                )
                sub_sc["camera_directive"] = f"{base_cam}, wide-to-medium 3D establishing tracking shot"
            elif has_char_speech or sub_idx == 2:
                vp_core = vp_sentences[min(sub_idx - 1, len(vp_sentences) - 1)] if vp_sentences else base_vp
                sub_sc["raw_video_prompt"] = (
                    f"{vp_core}. Expressive 3D character interaction shot {orig_idx}.{sub_idx} with natural speaking "
                    f"gestures, lively hand movement, and vivid emotional reaction."
                )
                sub_sc["camera_directive"] = (
                    "50mm cinema lens, expressive 3D medium shot with natural character performance and eye contact, f/2.0 shallow depth of field bokeh"
                )
            else:
                vp_core = vp_sentences[-1] if vp_sentences else base_vp
                sub_sc["raw_video_prompt"] = (
                    f"{vp_core}. Dynamic 3D progression shot {orig_idx}.{sub_idx} from a fresh camera angle capturing "
                    f"the unfolding magical transformation and atmosphere."
                )
                sub_sc["camera_directive"] = (
                    f"40mm cinema lens, dynamic 3D orbital crane angle #{sub_idx}, rich volumetric god rays"
                )

            expanded_shots.append(sub_sc)

    for final_idx, shot in enumerate(expanded_shots, start=1):
        shot["scene_num"] = final_idx

    return expanded_shots



def _is_template_placeholder_story(data: Dict[str, Any]) -> bool:
    """Kiểm tra và loại bỏ nếu JSON là mẫu ví dụ placeholder cũ trong prompt của user."""
    title = str(data.get("story_title") or "").strip().lower()
    if title in ("tên câu chuyện 3d", "story title", "title of the 3d story"):
        return True
    scenes = data.get("scenes")
    if isinstance(scenes, list) and len(scenes) == 1 and isinstance(scenes[0], dict):
        narr = str(scenes[0].get("narration") or "").strip().lower()
        if narr.startswith("lời dẫn tiếng việt tự nhiên, cuốn hút"):
            return True
    return False


def does_script_match_user_topic(story_data: Optional[Dict[str, Any]], topic: str) -> bool:
    """
    Kiểm tra xem kịch bản đang hiển thị trên tab MuseAI có thực sự khớp với cốt truyện `topic`
    mà người dùng vừa nhập hay không. Nếu người dùng nhập một cốt truyện mới khác hẳn kịch bản cũ
    trên tab MuseAI, trả về False để bắt buộc gửi prompt mới cho MuseAI viết.
    """
    if not isinstance(story_data, dict):
        return False
    clean_topic = str(topic or "").strip().lower()
    if not clean_topic:
        return True

    stopwords = {
        "của", "trong", "một", "những", "các", "cho", "với", "khi", "được", "này",
        "cậu", "chú", "bạn", "người", "câu", "chuyện", "phim", "hoạt", "hình", "tập",
        "the", "and", "with", "from", "into", "about", "story",
    }
    words = [
        w for w in re.findall(r"\w+", clean_topic)
        if len(w) >= 3 and not w.isdigit() and w not in stopwords
    ]
    if not words:
        return True

    haystack_parts = [
        str(story_data.get("story_title") or ""),
        str(story_data.get("character_anchor") or ""),
        str(story_data.get("environment_anchor") or ""),
    ]
    for sc in story_data.get("scenes", []):
        if isinstance(sc, dict):
            haystack_parts.append(str(sc.get("narration") or ""))
            haystack_parts.append(str(sc.get("video_prompt") or ""))
    haystack = " ".join(haystack_parts).lower()

    matched = sum(1 for w in words if w in haystack)
    required = max(1, int(len(words) * 0.4))
    return matched >= required



def parse_museai_story_json(raw_text: str, visual_mode: str = "") -> Optional[Dict[str, Any]]:
    """
    Trích xuất kịch bản JSON do MuseAI vừa viết trên tab Chrome.
    Tự động bỏ qua các đoạn mẫu placeholder trong câu hỏi của user và ưu tiên khối JSON mới nhất ở cuối trang.
    """
    if not raw_text or not raw_text.strip():
        return None
    text = raw_text.strip()

    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates: List[str] = list(reversed(fenced))

    # Nếu truyền trực tiếp nội dung bên trong thẻ <pre> (không có dấu ``` bao ngoài)
    if text.startswith("{") and text.endswith("}"):
        candidates.insert(0, text)
    else:
        first_b = text.find("{")
        last_b = text.rfind("}")
        if first_b != -1 and last_b > first_b:
            candidates.append(text[first_b : last_b + 1])

    for cand in candidates:
        try:
            data = json.loads(cand)
            if not isinstance(data, dict):
                continue
            if _is_template_placeholder_story(data):
                continue
            if isinstance(data.get("scenes"), list) and len(data["scenes"]) > 0:
                char_anchor = str(data.get("character_anchor") or "").strip()
                env_anchor = str(data.get("environment_anchor") or "").strip()
                norm_scenes = []
                total_raw = len(data["scenes"])
                for idx, sc in enumerate(data["scenes"], start=1):
                    if isinstance(sc, dict):
                        narr = str(sc.get("narration") or "").strip()
                        vp = str(sc.get("video_prompt") or sc.get("raw_video_prompt") or "").strip()
                        d_lines = sc.get("dialogue_lines")
                        speech_lines = sc.get("speech_segments")
                        if (not narr and not vp and not (isinstance(d_lines, list) and len(d_lines) > 0)
                                and not (isinstance(speech_lines, list) and len(speech_lines) > 0)):
                            continue
                        c = dict(sc)
                        if data.get("content_mode") == "english_teaching_vi":
                            c["content_mode"] = "english_teaching_vi"
                        c["scene_num"] = int(c.get("scene_num") or idx)
                        c["narration"] = narr
                        c["raw_video_prompt"] = vp
                        build_scene_dialogue_segments(c, language="vi", total_scenes=total_raw,
                                                      allow_synthetic_filler=(visual_mode or data.get("visual_mode")) != "whiteboard")
                        norm_scenes.append(c)
                if norm_scenes:
                    data["scenes"] = norm_scenes
                    data["character_anchor"] = char_anchor
                    data["environment_anchor"] = env_anchor
                    return data
        except Exception:
            continue
    return None


def is_museai_script_complete(
    parsed: Optional[Dict[str, Any]],
    target_scenes: Optional[int] = 4,
    stable_ticks: int = 0,
) -> bool:
    """
    Xác định kịch bản JSON từ MuseAI đã được stream xong đầy đủ số phân cảnh hay chưa.
    Ngăn chặn triệt để lỗi mới stream xong Cảnh 1/4 đã vội vàng kết thúc.
    """
    if not parsed or not isinstance(parsed, dict):
        return False
    if _is_template_placeholder_story(parsed):
        return False
    scenes = parsed.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        return False

    expected = max(1, int(target_scenes or 4))
    actual = len(scenes)

    # Nếu người dùng yêu cầu >= 2 cảnh, tuyệt đối không bao giờ chấp nhận kịch bản chỉ có 1 cảnh
    if expected >= 2 and actual < 2:
        return False

    # Trường hợp chuẩn: Đã đủ số cảnh yêu cầu (ví dụ 4/4 cảnh) và khối code đã ổn định ít nhất 1 nhịp
    if actual >= expected and stable_ticks >= 1:
        return True

    # Trường hợp MuseAI viết ít hơn 1 cảnh so với yêu cầu nhưng đã ngừng stream hoàn toàn trong thời gian dài (>= 4 nhịp ~ 10s)
    if actual >= max(2, expected - 1) and stable_ticks >= 4:
        return True

    return False


def normalize_flow_video_url(url: str) -> str:
    """
    Chuẩn hóa URL video của Google Flow bằng cách lược bỏ query string chữ ký (?Expires=...&Signature=...)
    để đảm bảo video của Cảnh 1 không bao giờ bị nhận nhầm thành video của Cảnh 2/3/4 khi Flow làm mới token.
    """
    if not url:
        return ""
    u = str(url).strip()
    if u.startswith(("http://", "https://")) and ("flow-content.google/video/" in u or ".mp4" in u or "googlevideo.com" in u):
        return u.split("?", 1)[0]
    return u


# ==============================================================================
# PHẦN 3: BỘ ĐIỀU KHIỂN CHROME CDP KÉP (TAB 1: MUSEAI VIẾT TRUYỆN -> TAB 2: GG FLOW SINH VIDEO 3D)
# ==============================================================================

def load_hybrid_config() -> Dict[str, Any]:
    cfg = {
        "museai_url": "https://muse.ai/",
        "project_url": "https://flow.google.com",
        "tool_url": "https://flow.google.com",
        "cdp_port": 9222,
        "chrome_user_data_dir": str(ROOT_DIR / "flow_chrome_profile"),
        "profile_directory": "Default",
        "story_timeout_seconds": 180,
        "video_timeout_seconds": 600,
    }
    if FLOW_CONFIG_PATH.exists():
        try:
            flow_cfg = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(flow_cfg, dict):
                cfg.update(flow_cfg)
        except Exception:
            pass
    if MUSEAI_CONFIG_PATH.exists():
        try:
            muse_cfg = json.loads(MUSEAI_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(muse_cfg, dict):
                cfg.update(muse_cfg)
        except Exception:
            pass
    raw_ud = str(cfg.get("chrome_user_data_dir") or "").strip()
    if not raw_ud:
        cfg["chrome_user_data_dir"] = str((ROOT_DIR / "flow_chrome_profile").resolve())
    elif not os.path.isabs(raw_ud):
        cfg["chrome_user_data_dir"] = str((ROOT_DIR / raw_ud).resolve())
    raw_proj = str(cfg.get("project_url") or "https://flow.google.com").strip()
    if "/project/" in raw_proj:
        cfg["project_url"] = raw_proj.split("/tool/", 1)[0].split("/edit/", 1)[0].split("?", 1)[0].rstrip("/")
    return cfg


def is_cdp_available(port: int = 9222) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


class MuseAIFlowHybridController:
    """
    Bộ điều khiển trình duyệt Chrome CDP Port 9222 phối hợp nhịp nhàng 2 tab:
    - Tab MuseAI (`https://muse.ai/`): Chuyên viết cốt truyện 3D có đầu có cuối, khóa nhân vật 3D và chia phân cảnh.
    - Tab Google Flow (`https://flow.google.com/`): Nhận từng phân cảnh 3D từ MuseAI để render ra video clip 3D `.mp4`.
    """

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        self.cfg = cfg or load_hybrid_config()
        self.playwright = None
        self.browser: Any = None
        self.context: Any = None
        self.muse_page: Any = None
        self.flow_page: Any = None
        self.seen_video_urls: set = set()
        self.seen_video_hashes: set = set()

    def _launch_chrome_cdp(self) -> Tuple[bool, str]:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
        chrome_exe = next((p for p in candidates if os.path.exists(p)), "")
        if not chrome_exe:
            return False, "Không tìm thấy Google Chrome trên máy tính."

        port = int(self.cfg.get("cdp_port", 9222))
        user_data = self.cfg.get("chrome_user_data_dir") or str(ROOT_DIR / "flow_chrome_profile")
        os.makedirs(user_data, exist_ok=True)
        profile = self.cfg.get("profile_directory", "Default")
        museai_url = self.cfg.get("museai_url", "https://muse.ai/")
        flow_url = self.cfg.get("project_url", "https://flow.google.com")

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}",
            f"--profile-directory={profile}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            museai_url,
            flow_url,
        ]
        try:
            creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008) if os.name == "nt" else 0
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            for _ in range(30):
                time.sleep(0.5)
                if is_cdp_available(port):
                    return True, f"Đã tự mở Chrome CDP (Port {port}) với 2 tab MuseAI & Google Flow."
            return False, (
                f"Chrome đã mở nhưng cổng {port} chưa phản hồi. "
                "Hãy đóng các cửa sổ Chrome cũ hoặc chạy scripts\\launch_flow_chrome.bat."
            )
        except Exception as exc:
            return False, f"Lỗi mở Chrome: {exc}"

    def _ensure_browser_context(self) -> Tuple[bool, str]:
        from playwright.sync_api import sync_playwright

        port = int(self.cfg.get("cdp_port", 9222))
        try:
            if not self.playwright:
                self.playwright = sync_playwright().start()

            if not is_cdp_available(port):
                safe_log(f"[*] Cổng Chrome CDP {port} chưa mở. Đang tự khởi chạy Chrome...")
                launched, msg = self._launch_chrome_cdp()
                if not launched:
                    return False, msg

            if not self.browser or not self.context:
                self.browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=12000)
                self.context = self.browser.contexts[0] if self.browser.contexts else None

            if not self.context:
                return False, "Không thể lấy BrowserContext từ Chrome CDP."
            return True, "Đã kết nối Chrome CDP."
        except Exception as exc:
            self.browser = None
            self.context = None
            return False, f"Lỗi kết nối Chrome CDP: {exc}"

    # --------------------------------------------------------------------------
    # BƯỚC 1: ĐIỀU KHIỂN TAB MUSEAI ĐỂ VIẾT KỊCH BẢN CỐT TRUYỆN 3D
    # --------------------------------------------------------------------------

    def get_or_open_museai_tab(self) -> Tuple[bool, str]:
        ok, msg = self._ensure_browser_context()
        if not ok:
            return False, msg

        museai_url = self.cfg.get("museai_url", "https://muse.ai/")
        all_pages = [p for p in self.context.pages if not p.is_closed()]
        muse_pages = [
            p for p in all_pages
            if any(k in p.url.lower() for k in ("muse.ai", "miramuseai", "museaivideo"))
        ]

        if muse_pages:
            self.muse_page = muse_pages[0]
            safe_log(f"[✓] Đã tìm thấy tab MuseAI đang mở: {self.muse_page.url}")
        else:
            safe_log(f"[*] Đang mở tab mới tới MuseAI: {museai_url}")
            self.muse_page = self.context.new_page()
            try:
                self.muse_page.goto(museai_url, wait_until="domcontentloaded", timeout=40000)
                self.muse_page.wait_for_timeout(3000)
            except Exception as exc:
                safe_log(f"[WARNING] Điều hướng MuseAI mất nhiều thời gian: {exc}")

        try:
            self.muse_page.bring_to_front()
        except Exception:
            pass
        return True, f"Tab MuseAI đã sẵn sàng ({self.muse_page.url})."

    def _find_museai_input(self, page: Any):
        selectors = [
            "textarea[placeholder*='Ask' i]",
            "textarea[placeholder*='Muse' i]",
            "textarea[placeholder*='message' i]",
            "textarea[placeholder*='prompt' i]",
            "textarea[placeholder*='describe' i]",
            "textarea[placeholder*='Type' i]",
            "div[contenteditable='true'][role='textbox']",
            "div.ProseMirror[contenteditable='true']",
            "div[data-lexical-editor='true'][contenteditable='true']",
            "div[contenteditable='true']",
            "textarea",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                for idx in range(loc.count()):
                    cand = loc.nth(idx)
                    if cand.is_visible():
                        return cand
            except Exception:
                pass
        return None

    def read_latest_script_from_museai_tab(
        self,
        min_scenes: int = 2,
        orientation: str = "vertical",
        visual_mode: str = "video_3d",
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Đọc trực tiếp kịch bản JSON 3D mới nhất đang hiển thị trên tab MuseAI (thẻ <pre>)
        mà không cần gửi lại câu lệnh nếu người dùng hoặc phiên trước vừa tạo xong.
        """
        ok, msg = self.get_or_open_museai_tab()
        if not ok or not self.muse_page:
            return False, {"error": msg}

        page = self.muse_page
        try:
            pre_blocks = page.evaluate(
                """() => Array.from(document.querySelectorAll('pre'))
                    .map(el => (el.innerText || '').trim())
                    .filter(t => t.includes('"scenes"') && t.includes('"video_prompt"'))"""
            )
            for block_text in reversed(pre_blocks or []):
                parsed = parse_museai_story_json(block_text, visual_mode=visual_mode)
                if parsed and len(parsed.get("scenes", [])) >= max(1, min_scenes):
                    safe_log(
                        f"[✓] [MUSEAI] Đã đọc trực tiếp kịch bản '{parsed.get('story_title')}' "
                        f"({len(parsed['scenes'])} cảnh) từ tab MuseAI!"
                    )
                    return True, self._enrich_scenes_with_3d_prompts(parsed, orientation, visual_mode=visual_mode)
        except Exception as exc:
            return False, {"error": f"Không thể đọc kịch bản trên tab MuseAI: {exc}"}

        return False, {"error": f"Chưa tìm thấy kịch bản đủ {min_scenes} cảnh trên tab MuseAI."}

    def generate_3d_script_via_museai(
        self,
        topic: str = "",
        target_scenes: Optional[int] = None,
        language: str = "vi",
        orientation: str = "vertical",
        visual_mode: str = "video_3d",
        story_style: str = "cinematic_storytelling",
        timeout_sec: Optional[int] = None,
        reuse_existing_if_ready: bool = False,
        episode_num: int = 1,
        total_episodes: int = 1,
        previous_episodes_summary: str = "",
        locked_character_anchor: str = "",
        locked_environment_anchor: str = "",
        status_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled_callback: Optional[Callable[[], bool], None] = None,
        previous_episode_learning: str = "",
        required_episode_topic: str = "",
        whiteboard_ai_enabled: bool = True,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Mở/nhảy vào tab MuseAI trên Chrome, gửi prompt yêu cầu MuseAI viết kịch bản cốt truyện 3D
        có đầu có cuối (Mở đầu - Cao trào - Kết thúc), hỗ trợ nối tiếp cốt truyện nhiều tập,
        và tự động chia số khung hình khớp 1:1 theo nhịp câu chuyện.
        """
        with _BROWSER_LOCK:
            ok, msg = self.get_or_open_museai_tab()
            if not ok or not self.muse_page:
                return False, {"error": msg}

            page = self.muse_page
            expected_scenes = max(2, int(target_scenes)) if (target_scenes and int(target_scenes) >= 2) else 4
            base_timeout = int(timeout_sec or self.cfg.get("story_timeout_seconds", 180))
            effective_timeout = max(base_timeout, expected_scenes * 35)

            # Chỉ tái sử dụng kịch bản trên tab MuseAI nếu người dùng bật tùy chọn VÀ kịch bản đó khớp với chủ đề vừa nhập
            if reuse_existing_if_ready and int(episode_num or 1) == 1:
                ok_exist, data_exist = self.read_latest_script_from_museai_tab(
                    min_scenes=expected_scenes,
                    orientation=orientation,
                    visual_mode=visual_mode,
                )
                if ok_exist and does_script_match_user_topic(data_exist, topic):
                    return True, data_exist
                elif ok_exist:
                    safe_log(
                        f"[*] Kịch bản cũ trên tab MuseAI ('{data_exist.get('story_title')}') không khớp với cốt truyện mới "
                        f"('{topic[:50]}'). Đang mở cuộc trò chuyện mới trên MuseAI để viết đúng cốt truyện bạn vừa nhập..."
                    )

            # Thoát khỏi thread cũ ('/thread/...') về trang chủ MuseAI hoặc mở khung chat mới ('New side chat')
            # để xóa sạch kịch bản cũ và ngữ cảnh cũ trước khi gửi cốt truyện mới
            try:
                if "/thread/" in str(getattr(page, "url", "") or ""):
                    chat_home_link = page.locator("a[aria-label='Chat'][href='/']")
                    if chat_home_link.count() > 0 and chat_home_link.first.is_visible():
                        chat_home_link.first.click(force=True, timeout=2500)
                        page.wait_for_timeout(1200)
                    else:
                        page.goto("https://muse.ai/", wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(1800)
                new_chat_btns = page.locator("button[aria-label='New side chat'], button[title='New side chat']")
                if new_chat_btns.count() > 0 and new_chat_btns.first.is_visible():
                    new_chat_btns.first.click(force=True, timeout=2500)
                    page.wait_for_timeout(1200)
            except Exception:
                pass

            input_box = self._find_museai_input(page)
            if not input_box:
                safe_log("[!] Chưa thấy ô chat trên tab MuseAI. Hãy đăng nhập MuseAI trên cửa sổ Chrome (tự động đợi tối đa 90s)...")
                for _ in range(45):
                    if is_cancelled_callback and is_cancelled_callback():
                        return False, {"error": "Đã bỏ qua theo yêu cầu người dùng"}
                    page.wait_for_timeout(2000)
                    input_box = self._find_museai_input(page)
                    if input_box:
                        break

            if not input_box:
                return False, {"error": f"Không tìm thấy ô nhập chat trên tab MuseAI ({page.url})."}

            # Chỉ lấy danh sách thẻ <pre> (không lấy cả <code> con gây nhân đôi) trước khi gửi lệnh
            try:
                prev_pre_texts: List[str] = page.evaluate(
                    """() => Array.from(document.querySelectorAll('pre'))
                        .map(el => (el.innerText || '').trim())
                        .filter(t => t.includes('"scenes"') && t.includes('"video_prompt"'))"""
                )
            except Exception:
                prev_pre_texts = []

            prev_pre_count = len(prev_pre_texts)
            prev_last_pre = prev_pre_texts[-1] if prev_pre_texts else ""

            prompt = build_museai_story_script_prompt(
                topic=topic,
                target_scenes=target_scenes,
                language=language,
                orientation=orientation,
                episode_num=episode_num,
                total_episodes=total_episodes,
                previous_episodes_summary=previous_episodes_summary,
                locked_character_anchor=locked_character_anchor,
                locked_environment_anchor=locked_environment_anchor,
                story_style=story_style,
                visual_mode=visual_mode,
                previous_episode_learning=previous_episode_learning,
                required_episode_topic=required_episode_topic,
                whiteboard_ai_enabled=whiteboard_ai_enabled,
            )

            safe_log(
                f"[*] [BƯỚC 1 - MUSEAI] Đang gửi yêu cầu viết kịch bản Tập {episode_num}/{total_episodes} "
                f"cho chủ đề: '{topic or 'Tự do sáng tác'}'..."
            )
            try:
                input_box.click(force=True, timeout=5000)
                page.wait_for_timeout(200)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
            except Exception:
                pass

            filled = False
            try:
                input_box.fill(prompt)
                page.wait_for_timeout(300)
                val = input_box.evaluate("el => (el.value !== undefined ? el.value : el.innerText) || ''")
                if len(str(val).strip()) > 10:
                    filled = True
            except Exception:
                filled = False

            if not filled:
                try:
                    input_box.click(force=True, timeout=3000)
                    page.keyboard.insert_text(prompt)
                    page.wait_for_timeout(300)
                except Exception as exc:
                    return False, {"error": f"Không thể điền prompt vào MuseAI: {exc}"}

            try:
                input_box.evaluate(
                    """el => {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }"""
                )
            except Exception:
                pass

            page.wait_for_timeout(400)

            btn_selectors = [
                "button[aria-label*='Send' i]",
                "button[aria-label*='Submit' i]",
                "button[data-testid*='send' i]",
                "button[type='submit']",
                "button:has-text('Send')",
            ]
            clicked = False
            for b_sel in btn_selectors:
                try:
                    b_loc = page.locator(b_sel)
                    for idx in range(b_loc.count()):
                        btn = b_loc.nth(idx)
                        if btn.is_visible() and btn.is_enabled():
                            btn.click(force=True, timeout=3000)
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    pass

            if not clicked:
                input_box.press("Enter")

            # Đợi 2 giây SAU KHI gửi để bong bóng câu hỏi của user hiển thị xong trên trang,
            # sau đó mới đo baseline_body_len để TUYỆT ĐỐI không đọc nhầm câu hỏi của user!
            page.wait_for_timeout(2000)
            try:
                baseline_body_len = page.evaluate("() => (document.body.innerText || '').length")
            except Exception:
                baseline_body_len = 0

            safe_log(f"[*] Đã gửi lệnh lên MuseAI! Đang chờ MuseAI viết đủ {expected_scenes} phân cảnh 3D...")
            start_time = time.time()
            last_pre_len = 0
            pre_stable_ticks = 0
            last_body_len = 0
            body_stable_ticks = 0

            while time.time() - start_time < effective_timeout:
                if is_cancelled_callback and is_cancelled_callback():
                    return False, {"error": "Đã bỏ qua theo yêu cầu người dùng"}

                page.wait_for_timeout(2500)
                elapsed = time.time() - start_time

                try:
                    pre_blocks: List[str] = page.evaluate(
                        """() => Array.from(document.querySelectorAll('pre'))
                            .map(el => (el.innerText || '').trim())
                            .filter(t => t.includes('"scenes"') && t.includes('"video_prompt"'))"""
                    )

                    has_new_pre = (
                        len(pre_blocks) > prev_pre_count
                        or (len(pre_blocks) > 0 and pre_blocks[-1] != prev_last_pre)
                    )

                    if has_new_pre and pre_blocks:
                        latest_pre = pre_blocks[-1]
                        streamed_scene_count = len(re.findall(r'"scene_num"\s*:\s*\d+', latest_pre))

                        if len(latest_pre) == last_pre_len and len(latest_pre) > 100:
                            pre_stable_ticks += 1
                        else:
                            pre_stable_ticks = 0
                            last_pre_len = len(latest_pre)

                        if status_callback:
                            try:
                                status_callback(
                                    int(elapsed),
                                    f"MuseAI đang viết kịch bản 3D ({int(elapsed)}s) — "
                                    f"Đã viết {streamed_scene_count}/{max(expected_scenes, streamed_scene_count)} phân cảnh...",
                                )
                            except Exception:
                                pass

                        parsed = parse_museai_story_json(latest_pre, visual_mode=visual_mode)
                        if is_museai_script_complete(parsed, target_scenes=expected_scenes, stable_ticks=pre_stable_ticks):
                            safe_log(
                                f"[✓] [MUSEAI] Đã nhận kịch bản 3D '{parsed.get('story_title')}' "
                                f"đầy đủ {len(parsed['scenes'])}/{expected_scenes} phân cảnh từ MuseAI!"
                            )
                            return True, self._enrich_scenes_with_3d_prompts(parsed, orientation, visual_mode=visual_mode)
                    else:
                        if status_callback and int(elapsed) % 8 < 3:
                            try:
                                status_callback(
                                    int(elapsed),
                                    f"MuseAI đang suy nghĩ & biên soạn cốt truyện {expected_scenes} cảnh ({int(elapsed)}s)...",
                                )
                            except Exception:
                                pass

                    # Nhánh dự phòng nếu MuseAI trả lời JSON ngoài thẻ <pre>
                    body_text = page.evaluate("() => document.body.innerText || ''")
                    new_text = body_text[baseline_body_len:] if len(body_text) > baseline_body_len else ""
                    if len(new_text) == last_body_len and len(new_text) > 300:
                        body_stable_ticks += 1
                    else:
                        body_stable_ticks = 0
                        last_body_len = len(new_text)

                    if body_stable_ticks >= 2 and elapsed > 18.0:
                        parsed_body = parse_museai_story_json(new_text, visual_mode=visual_mode)
                        if is_museai_script_complete(parsed_body, target_scenes=expected_scenes, stable_ticks=body_stable_ticks):
                            safe_log(
                                f"[✓] [MUSEAI] Đã trích xuất kịch bản 3D đầy đủ {len(parsed_body['scenes'])} phân cảnh từ MuseAI!"
                            )
                            return True, self._enrich_scenes_with_3d_prompts(parsed_body, orientation, visual_mode=visual_mode)
                except Exception:
                    pass

            return False, {"error": f"Hết thời gian chờ ({effective_timeout}s) mà chưa nhận được kịch bản đủ {expected_scenes} cảnh từ tab MuseAI."}

    def _enrich_scenes_with_3d_prompts(
        self,
        story_data: Dict[str, Any],
        orientation: str,
        visual_mode: str = "video_3d",
    ) -> Dict[str, Any]:
        """
        Tự động cân đối/chia số khung hình khớp 1:1 với mạch câu chuyện (`expand_scenes_to_match_story_beats`),
        sau đó chuẩn hóa khóa nhân vật 3D theo công thức 7-Point Character DNA (`build_7_point_character_dna`)
        và gắn vào từng `video_prompt` / `image_prompt` trước khi gửi sang Google Flow:
        - `video_3d`: Mỗi nhịp ~42 từ (~7-9s) là 1 clip Video 3D Veo (`media_type="video"`).
        - `image_3d`: Chia nhịp dày đặc ~20 từ (~3-4s/câu) để hình ảnh 3D Nano Banana đổi liên tục theo từng câu chuyện
          kết hợp chuyển động máy quay Visual Beats (`media_type="image"`).
        - `hybrid_3d`: Mở đầu (`Opening Hook`) và Cao trào (`Climax`) dùng Video 3D Veo (`media_type="video"`),
          các nhịp dẫn dắt (`Rising Action` / `Resolution`) dùng Hình 3D liên tục (`media_type="image"`).
        """
        if visual_mode == "whiteboard":
            from src.whiteboard_video import layout_scene_items
            prepared = []
            for idx, sc in enumerate(story_data.get("scenes") or [], 1):
                if not isinstance(sc, dict):
                    continue
                scene = dict(sc, scene_num=idx, media_type="whiteboard", use_video_ai=True)
                if story_data.get("content_mode") == "english_teaching_vi":
                    scene["content_mode"] = "english_teaching_vi"
                build_scene_dialogue_segments(scene, allow_synthetic_filler=False)
                scene["whiteboard_items"] = layout_scene_items(scene)
                prepared.append(scene)
            return dict(story_data, scenes=prepared, visual_mode="whiteboard")
        try:
            from src.flow_character_vault import build_7_point_character_dna
        except ModuleNotFoundError:
            from video_studio.src.flow_character_vault import build_7_point_character_dna

        mode_norm = str(visual_mode or "video_3d").strip().lower()
        if mode_norm == "image_3d":
            max_words = 20
        elif mode_norm == "hybrid_3d":
            max_words = 28
        else:
            max_words = 42

        raw_char = str(story_data.get("character_anchor") or "").strip()
        char_anchor = build_7_point_character_dna(raw_char) if raw_char else ""
        if char_anchor:
            story_data["character_anchor"] = char_anchor
        env_anchor = str(story_data.get("environment_anchor") or "").strip()
        raw_list = story_data.get("scenes", [])
        aligned_list = expand_scenes_to_match_story_beats(raw_list, language="vi", max_words_per_shot=max_words)

        enriched_scenes = []
        tot_sc = max(2, len(aligned_list))
        for idx, sc in enumerate(aligned_list, start=1):
            sc_copy = dict(sc) if isinstance(sc, dict) else {"scene_num": idx, "narration": str(sc), "video_prompt": str(sc)}
            raw_vp = str(sc_copy.get("raw_video_prompt") or sc_copy.get("video_prompt") or "").strip()
            cam = str(sc_copy.get("camera_directive") or "35mm cinema lens, smooth 3D dolly tracking shot, shallow depth of field").strip()
            sc_copy["scene_num"] = int(sc_copy.get("scene_num") or idx)
            sc_copy["raw_video_prompt"] = raw_vp
            has_muse_lines = bool(sc_copy.get("dialogue_lines"))
            build_scene_dialogue_segments(sc_copy, language="vi", total_scenes=tot_sc, allow_synthetic_filler=(not has_muse_lines))

            role_str = str(sc_copy.get("scene_role") or "")
            if mode_norm == "image_3d":
                sc_media_type = "image"
            elif mode_norm == "hybrid_3d":
                if idx == 1 or "Opening Hook" in role_str or "Climax" in role_str:
                    sc_media_type = "video"
                else:
                    sc_media_type = "image"
            else:
                sc_media_type = "video"

            sc_copy["media_type"] = sc_media_type
            sc_copy["use_video_ai"] = (sc_media_type == "video")
            sc_copy["video_prompt"] = clean_and_build_flow_3d_video_prompt(
                scene_prompt=raw_vp,
                character_anchor=char_anchor,
                environment_anchor=env_anchor,
                camera_directive=cam,
                orientation=orientation,
                scene_data=sc_copy,
            )
            sc_copy["image_prompt"] = clean_and_build_flow_3d_image_prompt(
                scene_prompt=raw_vp,
                character_anchor=char_anchor,
                environment_anchor=env_anchor,
                camera_directive=cam,
                orientation=orientation,
                scene_data=sc_copy,
            )
            enriched_scenes.append(sc_copy)
        story_data["scenes"] = enriched_scenes
        story_data["visual_mode"] = mode_norm
        return story_data

    # --------------------------------------------------------------------------
    # BƯỚC 2: ĐIỀU KHIỂN TAB GOOGLE FLOW ĐỂ SINH VIDEO 3D TỪNG CẢNH (VEO)
    # --------------------------------------------------------------------------

    def _remember_flow_project_url(self, url: str) -> None:
        if "/project/" not in url:
            return
        project_url = url.split("/tool/", 1)[0].split("/edit/", 1)[0].split("?", 1)[0].rstrip("/")
        self.cfg["project_url"] = project_url
        try:
            if FLOW_CONFIG_PATH.exists():
                disk_cfg = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))
                disk_cfg["project_url"] = project_url
                FLOW_CONFIG_PATH.write_text(json.dumps(disk_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _exit_flow_edit_mode_if_needed(self, page: Any, project_url: str) -> None:
        """
        Khi bấm vào video Cảnh 1 để tải xuống, Google Flow chuyển URL sang `/project/<uuid>/edit/<clip_id>`
        và đổi thanh nhập thành 'Mô tả cách chỉnh sửa video này…' (Omni 1.1 Flash).
        Hàm này thoát khỏi chế độ `/edit/` để quay về trang dự án chính ('Bạn muốn tạo gì?' - Veo).
        """
        if not page:
            return
        try:
            cur_url = str(page.url or "")
            if "/edit/" not in cur_url and "/tool/" not in cur_url:
                return
            clean_proj_url = cur_url.split("/tool/", 1)[0].split("/edit/", 1)[0].split("?", 1)[0].rstrip("/")
            if "/project/" not in clean_proj_url and "/project/" in str(project_url or ""):
                clean_proj_url = str(project_url).split("/tool/", 1)[0].split("/edit/", 1)[0].split("?", 1)[0].rstrip("/")

            safe_log(f"[*] Đang thoát chế độ chỉnh sửa clip (/edit/) để quay về trang tạo cảnh mới: {clean_proj_url}")
            back_selectors = [
                "button[aria-label='Đã chỉnh sửa xong cảnh']",
                "button[aria-label*='quay lại' i]",
                "button[aria-label*='Back' i]",
                "button:has-text('arrow_back')",
            ]
            for b_sel in back_selectors:
                try:
                    btn = page.locator(b_sel)
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click(force=True, timeout=2500)
                        page.wait_for_timeout(1500)
                        if "/edit/" not in str(page.url or ""):
                            return
                except Exception:
                    pass

            if "/edit/" in str(page.url or "") or "/tool/" in str(page.url or ""):
                page.goto(clean_proj_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2500)
        except Exception as exc:
            safe_log(f"[WARNING] Không thể thoát chế độ /edit/ trên Google Flow: {exc}")

    def _ensure_direct_video_composer_mode(
        self,
        page: Any,
        orientation: str = "vertical",
        media_mode: str = "video",
    ) -> None:
        """
        Đảm bảo Google Flow luôn ở chế độ Direct Composer ('Bạn muốn tạo những gì?')
        thay vì nằm trong bảng chat Tác nhân (Agent) dễ bị tích tụ ngữ cảnh (context):
        1. Nếu bảng Tác nhân bên phải đang mở ('Bắt đầu phiên mới' / 'Mở nhật ký phiên'): bấm 'Bắt đầu phiên mới' để làm sạch session,
           sau đó bấm 'Đóng' (Close) bảng Tác nhân để chuyển về thanh Direct Composer.
        2. Đóng thông báo giới thiệu ('Đã hiểu, đóng thông báo giới thiệu' / 'Got it') nếu có.
        3. Kiểm tra nút 'Điều kiện kích hoạt cài đặt':
           - Nếu `media_mode == "image"`: bật sang chế độ 'Hình ảnh' (Nano Banana 2.1 - 0 tín dụng) + '9:16'/'16:9' + 'x1'.
           - Nếu `media_mode == "video"`: bật sang chế độ 'Video' (Veo) + '9:16'/'16:9' + 'x1'.
        """
        if not page:
            return
        try:
            # 1. Làm sạch phiên Tác nhân và đóng bảng Tác nhân bên phải nếu đang mở
            new_sess_btns = page.locator(
                "button[aria-label='Bắt đầu phiên mới'], button[aria-label*='New session' i], button[aria-label*='Start new session' i]"
            )
            if new_sess_btns.count() > 0 and new_sess_btns.first.is_visible():
                try:
                    new_sess_btns.first.click(force=True, timeout=2000)
                    page.wait_for_timeout(400)
                except Exception:
                    pass
                try:
                    close_btns = page.locator("button[aria-label='Đóng'], button[aria-label='Close']")
                    for idx_c in range(close_btns.count()):
                        cb = close_btns.nth(idx_c)
                        if cb.is_visible():
                            cb.click(force=True, timeout=2000)
                            page.wait_for_timeout(600)
                            break
                except Exception:
                    pass

            # 2. Đóng thông báo giới thiệu (onboarding tooltip) nếu có
            dismiss_btns = page.locator(
                "button[aria-label*='đóng thông báo' i], button[aria-label*='dismiss onboarding' i], button:has-text('Tôi hiểu')"
            )
            for idx_d in range(dismiss_btns.count()):
                db = dismiss_btns.nth(idx_d)
                if db.is_visible():
                    try:
                        db.click(force=True, timeout=1500)
                        page.wait_for_timeout(300)
                    except Exception:
                        pass

            # 3. Đảm bảo thanh cài đặt đang chọn đúng 'Video' hoặc 'Hình ảnh' + '9:16' (hoặc '16:9') + 'x1'
            target_ratio = "9:16" if orientation == "vertical" else "16:9"
            want_image = str(media_mode or "video").strip().lower() == "image"
            settings_pill = page.locator(
                "button[aria-label='Điều kiện kích hoạt cài đặt'], button[aria-label*='Settings trigger' i]"
            )
            if settings_pill.count() > 0 and settings_pill.first.is_visible():
                pill_text = (settings_pill.first.inner_text() or "").strip()
                pill_low = pill_text.lower()
                mode_matched = ("image" in pill_low or "banana" in pill_low or "hình ảnh" in pill_low) if want_image else ("video" in pill_low)
                need_switch = (
                    not mode_matched
                    or target_ratio.replace(":", "_") not in pill_text.replace(":", "_")
                    or "x1" not in pill_low
                )
                if need_switch:
                    settings_pill.first.click(force=True, timeout=2500)
                    page.wait_for_timeout(500)
                    for btn in page.locator("button, [role='tab'], [role='option']").all():
                        try:
                            if not btn.is_visible():
                                continue
                            t = (btn.inner_text() or "").strip()
                            t_low = t.lower()
                            if want_image and ("hình ảnh" in t_low or t.endswith("Image") or "image\n" in t_low):
                                btn.click(force=True, timeout=2000)
                                page.wait_for_timeout(400)
                                break
                            if (not want_image) and ("videocam" in t_low or t.endswith("Video")):
                                btn.click(force=True, timeout=2000)
                                page.wait_for_timeout(400)
                                break
                        except Exception:
                            pass
                    for btn in page.locator("button, [role='tab'], [role='option']").all():
                        try:
                            if not btn.is_visible():
                                continue
                            t = (btn.inner_text() or "").strip()
                            if target_ratio in t:
                                btn.click(force=True, timeout=2000)
                                page.wait_for_timeout(300)
                                break
                        except Exception:
                            pass
                    for btn in page.locator("button, [role='tab'], [role='option']").all():
                        try:
                            if not btn.is_visible():
                                continue
                            t = (btn.inner_text() or "").strip()
                            if t.lower() == "x1":
                                btn.click(force=True, timeout=2000)
                                page.wait_for_timeout(300)
                                break
                        except Exception:
                            pass
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(400)
        except Exception as exc:
            safe_log(f"[WARNING] Không thể đồng bộ chế độ Direct Composer trên Google Flow: {exc}")

    def start_fresh_google_flow_project(self, orientation: str = "vertical") -> Tuple[bool, str]:
        """
        Tạo mới hoàn toàn một Dự án / Phiên làm việc sạch trên Google Flow ('Dự án mới' / 'New project')
        cho mỗi video mới, giúp giải phóng 100% ngữ cảnh (context) cũ và lịch sử clip cũ.
        """
        with _BROWSER_LOCK:
            ok, msg = self._ensure_browser_context()
            if not ok:
                return False, msg

            all_pages = [p for p in self.context.pages if not p.is_closed()]
            flow_pages = [p for p in all_pages if "flow.google.com" in p.url]
            self.flow_page = (flow_pages or [None])[0]
            if not self.flow_page:
                self.flow_page = self.context.new_page()

            page = self.flow_page
            try:
                page.bring_to_front()
            except Exception:
                pass

            try:
                safe_log("[*] Đang mở trang chủ Google Flow để tạo Dự án mới (làm sạch 100% context)...")
                page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2800)

                if "/about" in page.url or "accounts.google.com" in page.url:
                    return False, "Tab Google Flow chưa đăng nhập tài khoản Google."

                clicked_new = False
                for label in ["Dự án mới", "New project", "Create project"]:
                    loc = page.get_by_text(label, exact=False)
                    for idx in range(loc.count()):
                        item = loc.nth(idx)
                        if item.is_visible():
                            safe_log(f"[*] Đang bấm '{label}' để tạo không gian Google Flow mới...")
                            item.click(timeout=10000)
                            clicked_new = True
                            break
                    if clicked_new:
                        break

                if clicked_new:
                    try:
                        page.wait_for_url("**/project/**", wait_until="domcontentloaded", timeout=35000)
                    except Exception:
                        pass
                    page.wait_for_timeout(3500)

                if "/project/" in page.url and "/404" not in page.url:
                    self._remember_flow_project_url(page.url)
                    self._ensure_direct_video_composer_mode(page, orientation=orientation)
                    self.seen_video_urls.clear()
                    safe_log(f"[✓] Đã khởi tạo Dự án Google Flow mới tinh: {self.cfg.get('project_url')}")
                    return True, str(self.cfg.get("project_url"))
            except Exception as exc:
                safe_log(f"[WARNING] Không thể tạo dự án mới trên Google Flow, dùng dự án hiện có: {exc}")

            return self.get_or_open_google_flow_tab()

    def _open_or_create_flow_project(self, page: Any) -> Tuple[bool, str]:
        if "/project/" in page.url and "/404" not in page.url:
            page.wait_for_timeout(3000)
            if "/404" not in page.url and "/project/" in page.url:
                self._remember_flow_project_url(page.url)
                return True, "Project Google Flow đã sẵn sàng."

        if "/404" in page.url or "flow.google.com" not in page.url:
            page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=30000)

        try:
            page.wait_for_timeout(2500)
            for label in ["Dự án mới", "New project", "Create project"]:
                candidate = page.get_by_text(label, exact=True)
                for idx in range(candidate.count()):
                    item = candidate.nth(idx)
                    if item.is_visible():
                        safe_log(f"[*] Đang bấm '{label}' để mở project trên Google Flow...")
                        item.click(timeout=10000)
                        page.wait_for_url("**/project/**", wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(4000)
                        if "/404" not in page.url and "/project/" in page.url:
                            self._remember_flow_project_url(page.url)
                            return True, "Đã tạo project Google Flow mới."
        except Exception as exc:
            safe_log(f"[WARNING] Chưa thể tự tạo project Google Flow: {exc}")

        return False, "Không tìm thấy project hợp lệ hoặc nút 'Dự án mới' trên Google Flow."

    def get_or_open_google_flow_tab(self) -> Tuple[bool, str]:
        ok, msg = self._ensure_browser_context()
        if not ok:
            return False, msg

        project_url = self.cfg.get("project_url", "https://flow.google.com")
        all_pages = [p for p in self.context.pages if not p.is_closed()]
        flow_pages = [p for p in all_pages if "flow.google.com" in p.url]
        project_pages = [p for p in flow_pages if "/project/" in p.url and "/404" not in p.url]
        dashboard_pages = [
            p for p in flow_pages
            if "/404" not in p.url and "/about" not in p.url and "accounts.google.com" not in p.url
        ]

        self.flow_page = (project_pages or dashboard_pages or flow_pages or [None])[0]
        if not self.flow_page:
            safe_log(f"[*] Chưa có tab Google Flow. Đang mở tab mới tới: {project_url}")
            self.flow_page = self.context.new_page()
            try:
                self.flow_page.goto(project_url, wait_until="domcontentloaded", timeout=30000)
                self.flow_page.wait_for_timeout(3500)
            except Exception:
                pass

        try:
            self.flow_page.bring_to_front()
        except Exception:
            pass

        if "/about" in self.flow_page.url or "accounts.google.com" in self.flow_page.url:
            return False, "Tab Google Flow chưa đăng nhập tài khoản Google. Hãy đăng nhập trên cửa sổ Chrome."

        if "/404" in self.flow_page.url or "/project/" not in self.flow_page.url:
            proj_ok, proj_msg = self._open_or_create_flow_project(self.flow_page)
            if not proj_ok:
                return False, proj_msg
        else:
            self._remember_flow_project_url(self.flow_page.url)
            self._exit_flow_edit_mode_if_needed(self.flow_page, self.cfg.get("project_url", ""))

        return True, f"Tab Google Flow đã sẵn sàng ({self.flow_page.url})."

    def _is_flow_video_response(self, res: Any) -> bool:
        try:
            status = getattr(res, "status", 0)
            if status not in (200, 206):
                return False
            r_url = str(getattr(res, "url", ""))
            headers = getattr(res, "headers", {}) or {}
            ct = str(headers.get("content-type", "")).lower()
            if "video/" in ct:
                return True
            if "flow-content.google/video/" in r_url or ".mp4" in r_url or "googlevideo.com" in r_url:
                return True
        except Exception:
            pass
        return False

    def _hover_newest_flow_video_thumbnails(
        self,
        page: Any,
        pre_existing_thumb_urls: Optional[set] = None,
    ) -> int:
        """
        Trên lưới dự án Google Flow ('Tất cả nội dung nghe nhìn'), mỗi video mới render xong ban đầu chỉ hiển thị
        dưới dạng thẻ `<img alt="Hình thu nhỏ của video đã tạo">` ở vị trí ĐẦU TIÊN (index 0, góc trên bên trái)
        và CHỈ gắn thẻ `<video src="https://flow-content.google/video/...">` khi di chuột (hover) lên nó.
        Hàm này di chuột (hover) từ thẻ mới nhất (index 0) trở đi và TUYỆT ĐỐI KHÔNG click để không bị nhảy vào '/edit/'.
        """
        if not page:
            return 0
        pre_set = pre_existing_thumb_urls or set()
        hovered = 0
        try:
            thumbs = page.locator(
                "img[alt*='Hình thu nhỏ của video'], img[alt*='video thumbnail' i], img[alt*='generated video' i]"
            ).all()
            visible_thumbs = [t for t in thumbs if t.is_visible()]
            if not visible_thumbs:
                return 0

            # Ưu tiên thẻ có URL ảnh thumbnail chưa từng xuất hiện trước khi gửi prompt, và luôn ưu tiên index 0 (mới nhất)
            priority_list = []
            for idx, th in enumerate(visible_thumbs):
                try:
                    t_src = str(th.get_attribute("src") or "")
                    norm_t = normalize_flow_video_url(t_src)
                    if idx == 0 or (norm_t and norm_t not in pre_set):
                        priority_list.append(th)
                except Exception:
                    if idx == 0:
                        priority_list.append(th)

            for th in priority_list[:3]:
                try:
                    th.hover(timeout=1500)
                    page.wait_for_timeout(1200)
                    hovered += 1
                except Exception:
                    pass
        except Exception:
            pass
        return hovered

    def _download_flow_video_bytes(self, page: Any, candidate_url: str) -> Optional[bytes]:
        if not candidate_url or not page:
            return None
        if candidate_url.startswith(("http://", "https://")):
            try:
                resp = page.request.get(candidate_url, timeout=25000)
                if resp.status in (200, 206):
                    data = resp.body()
                    if data and len(data) > 10000:
                        return data
            except Exception:
                pass

        save_js = """
        async (src) => {
            const response = await fetch(src);
            const blob = await response.blob();
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });
        }
        """
        try:
            data_url = page.evaluate(save_js, candidate_url)
            if data_url and "," in data_url:
                import base64
                data = base64.b64decode(data_url.split(",", 1)[1])
                if data and len(data) > 10000:
                    return data
        except Exception:
            pass
        return None

    def _find_google_flow_composer(self, page: Any):
        """
        Tìm chính xác ô nhập prompt trên Google Flow (div.ProseMirror[role='textbox']),
        bỏ qua textarea ẩn của reCAPTCHA và TUYỆT ĐỐI bỏ qua ô chỉnh sửa clip ('Mô tả cách chỉnh sửa video này…')
        khi trang đang nằm trong URL `/edit/` hoặc `/tool/`.
        """
        try:
            cur_url = str(getattr(page, "url", "") or "")
            if "/edit/" in cur_url or "/tool/" in cur_url:
                return None
        except Exception:
            pass
        selectors = [
            "div.ProseMirror[role='textbox']",
            "div[contenteditable='true'][role='textbox']",
            "textarea[placeholder*='create' i]",
            "textarea[placeholder*='prompt' i]",
            "textarea[placeholder*='describe' i]",
            "textarea[placeholder*='video' i]",
            "textarea[placeholder*='mô tả' i]",
            "div[contenteditable='true']",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                for idx in range(loc.count()):
                    cand = loc.nth(idx)
                    if cand.is_visible():
                        return cand
            except Exception:
                pass
        return None

    def _submit_google_flow_composer(self, page: Any, input_box: Any) -> Tuple[bool, str]:
        """
        Chỉ click đúng nút gửi 'Bắt đầu tạo' / 'Start generation' trong thanh composer của Google Flow,
        TUYỆT ĐỐI không click nhầm 'Tạo bộ sưu tập' và xác nhận ô nhập đã được gửi đi.
        """
        submit_selectors = [
            "button[type='submit'][aria-label='Bắt đầu tạo']",
            "button[aria-label='Bắt đầu tạo']",
            "button[type='submit'][aria-label='Start generation']",
            "button[aria-label='Start generation']",
            "button[type='submit'].generate-icon-button",
        ]
        for sel in submit_selectors:
            try:
                buttons = page.locator(sel)
                for idx in range(buttons.count()):
                    btn = buttons.nth(idx)
                    if not btn.is_visible() or not btn.is_enabled():
                        continue
                    btn.click(timeout=5000)
                    for _ in range(16):
                        draft = input_box.evaluate(
                            "e => typeof e.value === 'string' ? e.value : (e.innerText || e.textContent || '')"
                        )
                        if not str(draft or "").strip():
                            return True, "Đã gửi prompt lên Google Flow thành công."
                        page.wait_for_timeout(250)
                    return True, "Đã click nút Bắt đầu tạo trên Google Flow."
            except Exception:
                pass

        # Fallback bấm phím Enter trực tiếp trên composer
        try:
            input_box.press("Enter")
            page.wait_for_timeout(800)
            return True, "Đã gửi prompt bằng phím Enter trên Google Flow."
        except Exception as exc:
            return False, f"Không thể bấm gửi prompt trên Google Flow: {exc}"

    def generate_scene_3d_video_on_google_flow(
        self,
        scene_num: int,
        total_scenes: int,
        scene_data: Dict[str, Any],
        output_path: str,
        character_anchor: str = "",
        environment_anchor: str = "",
        orientation: str = "vertical",
        timeout_sec: Optional[int] = None,
        attempt_num: int = 1,
        status_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled_callback: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, str]:
        """
        Chuyển sang tab Google Flow trên Chrome, đưa tuần tự Prompt 3D của Cảnh `scene_num/total_scenes`
        vào composer, bấm 'Bắt đầu tạo' và thu hoạch file video `.mp4` độc lập về `output_path`.
        """
        with _BROWSER_LOCK:
            ok, msg = self.get_or_open_google_flow_tab()
            if not ok or not self.flow_page:
                return False, msg

            page = self.flow_page
            effective_timeout = timeout_sec or int(self.cfg.get("video_timeout_seconds", 600))
            project_url = str(self.cfg.get("project_url", "https://flow.google.com")).split("/tool/", 1)[0].split("/edit/", 1)[0].split("?", 1)[0].rstrip("/")
            self._exit_flow_edit_mode_if_needed(page, project_url)
            self._ensure_direct_video_composer_mode(page, orientation=orientation)

            raw_prompt = str(scene_data.get("raw_video_prompt") or scene_data.get("video_prompt") or "").strip()
            cam_dir = str(
                scene_data.get("camera_directive")
                or "Smooth 3D dolly tracking shot, 35mm cinema lens, shallow depth of field"
            ).strip()

            full_3d_prompt = clean_and_build_flow_3d_video_prompt(
                scene_prompt=raw_prompt,
                character_anchor=character_anchor,
                environment_anchor=environment_anchor,
                camera_directive=cam_dir,
                orientation=orientation,
                scene_data=scene_data,
            )
            if attempt_num >= 2:
                full_3d_prompt = sanitize_prompt_for_flow_retry(full_3d_prompt)
            if attempt_num >= 3:
                # Lan cuoi: prompt toi gian (chi hanh dong + phong cach) de tranh bo loc an toan / prompt qua dai cua Veo
                full_3d_prompt = sanitize_prompt_for_flow_retry(
                    f"Pixar-style 3D CGI animated short clip, {strip_forbidden_2d_terms(raw_prompt)}, "
                    f"{cam_dir}, vertical 9:16 portrait, silent, no text."
                    if orientation == "vertical"
                    else f"Pixar-style 3D CGI animated short clip, {strip_forbidden_2d_terms(raw_prompt)}, "
                    f"{cam_dir}, horizontal 16:9, silent, no text."
                )

            safe_log(
                f"[*] [BƯỚC 2 - GOOGLE FLOW Cảnh {scene_num}/{total_scenes}] "
                f"Đang đưa prompt Cảnh {scene_num} vào Google Flow: \"{raw_prompt[:70]}...\""
            )

            new_network_videos: List[str] = []
            def _on_response(res):
                try:
                    if self._is_flow_video_response(res):
                        r_url = res.url
                        norm_r = normalize_flow_video_url(r_url)
                        if (
                            r_url not in self.seen_video_urls
                            and norm_r not in self.seen_video_urls
                            and r_url not in new_network_videos
                        ):
                            new_network_videos.append(r_url)
                except Exception:
                    pass

            try:
                page.on("response", _on_response)
            except Exception:
                pass

            try:
                # Ghi nhận toàn bộ URL video và URL thumbnail hiện có trên trang (cả bản gốc và bản chuẩn hóa bỏ ?Expires=)
                # để Cảnh 2, 3, 4 tuyệt đối không lấy nhầm lại video của Cảnh 1!
                pre_existing_urls = set()
                pre_existing_thumb_urls = set()
                for th_el in page.locator(
                    "img[alt*='Hình thu nhỏ của video'], img[alt*='video thumbnail' i], img[alt*='generated video' i]"
                ).all():
                    try:
                        t_src = th_el.get_attribute("src")
                        if t_src:
                            pre_existing_thumb_urls.add(t_src)
                            pre_existing_thumb_urls.add(normalize_flow_video_url(t_src))
                    except Exception:
                        pass
                for v in page.locator("video").all():
                    try:
                        s = v.get_attribute("src") or v.evaluate("el => el.currentSrc || el.src")
                        if s:
                            pre_existing_urls.add(s)
                            pre_existing_urls.add(normalize_flow_video_url(s))
                    except Exception:
                        pass
                for s_el in page.locator("video source").all():
                    try:
                        s_src = s_el.get_attribute("src")
                        if s_src:
                            pre_existing_urls.add(s_src)
                            pre_existing_urls.add(normalize_flow_video_url(s_src))
                    except Exception:
                        pass

                # Đóng popup onboarding nếu có
                got_it = page.get_by_role("button", name="Got it, dismiss onboarding message", exact=True)
                if got_it.count() > 0 and got_it.first.is_visible():
                    got_it.first.click()
                    page.wait_for_timeout(300)

                def _count_visible_failed_cards() -> int:
                    failed_sels = [
                        "div:has-text('Không thành công')",
                        "div:has-text('Rất tiếc, không tạo được video')",
                        "div:has-text('Generation failed')",
                        "div:has-text('Failed to generate')",
                    ]
                    total_vis = 0
                    for fs in failed_sels:
                        try:
                            loc = page.locator(fs)
                            for i in range(loc.count()):
                                if loc.nth(i).is_visible():
                                    total_vis += 1
                        except Exception:
                            pass
                    return total_vis

                # Dọn dẹp card lỗi cũ (nếu có) trước khi gửi prompt mới
                if _count_visible_failed_cards() > 0:
                    try:
                        trash_btns = page.locator(
                            "button[aria-label*='Xóa' i], button[aria-label*='Delete' i], button:has-text('delete')"
                        )
                        for idx_t in range(trash_btns.count()):
                            tb = trash_btns.nth(idx_t)
                            if tb.is_visible():
                                tb.click(force=True, timeout=1500)
                                page.wait_for_timeout(400)
                    except Exception:
                        pass

                pre_existing_failed_count = _count_visible_failed_cards()

                input_box = self._find_google_flow_composer(page)
                if not input_box:
                    safe_log("[*] Đang chờ hoặc điều hướng về dự án chính của Google Flow để tìm ô nhập prompt...")
                    for _ in range(5):
                        page.wait_for_timeout(1000)
                        input_box = self._find_google_flow_composer(page)
                        if input_box:
                            break

                if not input_box:
                    page.goto(project_url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3500)
                    input_box = self._find_google_flow_composer(page)

                if not input_box:
                    page.screenshot(path=str(ATTEMPTS_DIR / f"error_no_flow_input_sc{scene_num}.png"))
                    return False, "Không tìm thấy ô nhập prompt trên tab Google Flow."

                # Xóa sạch nội dung cũ trong ô ProseMirror và điền prompt của Cảnh hiện tại
                try:
                    input_box.click(force=True, timeout=5000)
                    page.wait_for_timeout(150)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    input_box.fill("")
                except Exception:
                    pass

                filled_ok = False
                try:
                    input_box.fill(full_3d_prompt)
                    page.wait_for_timeout(300)
                    cur_txt = input_box.evaluate(
                        "e => typeof e.value === 'string' ? e.value : (e.innerText || e.textContent || '')"
                    )
                    if len(str(cur_txt or "").strip()) > 15:
                        filled_ok = True
                except Exception:
                    filled_ok = False

                if not filled_ok:
                    try:
                        input_box.click(force=True, timeout=3000)
                        page.keyboard.insert_text(full_3d_prompt)
                        page.wait_for_timeout(300)
                    except Exception as exc:
                        return False, f"Không thể điền prompt Cảnh {scene_num} vào Google Flow: {exc}"

                try:
                    input_box.evaluate(
                        """el => {
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }"""
                    )
                except Exception:
                    pass

                page.wait_for_timeout(400)
                sub_ok, sub_msg = self._submit_google_flow_composer(page, input_box)
                if not sub_ok:
                    return False, sub_msg

                page.wait_for_timeout(1200)
                for confirm_name in ["Generate", "Confirm", "Continue", "Xác nhận"]:
                    confirm_btn = page.get_by_role("button", name=confirm_name, exact=True)
                    try:
                        if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                            confirm_btn.first.click()
                            break
                    except Exception:
                        pass

                safe_log(f"[*] Đã gửi Cảnh {scene_num}/{total_scenes} lên Google Flow! Đang đợi Veo render video 3D...")
                start_time = time.time()

                while time.time() - start_time < effective_timeout:
                    if is_cancelled_callback and is_cancelled_callback():
                        return False, "Đã bỏ qua theo yêu cầu người dùng"

                    page.wait_for_timeout(2500)
                    elapsed = time.time() - start_time
                    if elapsed < 10.0:
                        continue

                    if int(elapsed) % 15 < 3:
                        msg_wait = f"[*] [Cảnh {scene_num}/{total_scenes}] Đang chờ Google Flow render video 3D ({int(elapsed)}s/{effective_timeout}s)..."
                        safe_log(msg_wait)
                        if status_callback:
                            try:
                                status_callback(int(elapsed), msg_wait)
                            except Exception:
                                pass

                    # Phát hiện sớm nếu Google Flow xuất hiện card lỗi MỚI (nhiều hơn số card lỗi cũ trên trang)
                    if elapsed > 15.0 and int(elapsed) % 6 < 3:
                        cur_failed_count = _count_visible_failed_cards()
                        if cur_failed_count > pre_existing_failed_count:
                            try:
                                trash_btn = page.locator("button[aria-label*='Xóa' i], button[aria-label*='Delete' i], button:has-text('delete')")
                                if trash_btn.count() > 0 and trash_btn.first.is_visible():
                                    trash_btn.first.click(force=True, timeout=2000)
                                    page.wait_for_timeout(500)
                            except Exception:
                                pass
                            self._exit_flow_edit_mode_if_needed(page, project_url)
                            return False, "Google Flow báo lỗi sinh nội dung: 'Không thành công / Rất tiếc, không tạo được video này'."

                    candidate_urls: List[str] = []
                    for n_url in list(new_network_videos):
                        norm_n = normalize_flow_video_url(n_url)
                        if (
                            n_url not in self.seen_video_urls
                            and norm_n not in self.seen_video_urls
                            and n_url not in pre_existing_urls
                            and norm_n not in pre_existing_urls
                        ):
                            if n_url not in candidate_urls:
                                candidate_urls.append(n_url)

                    # Di chuột (hover) lên card video mới nhất (index 0) trên lưới Google Flow để kích hoạt thẻ <video src=...>
                    # TUYỆT ĐỐI không click vào thumbnail để không bị đẩy sang trang chỉnh sửa '/edit/'!
                    if elapsed > 14.0 and int(elapsed) % 9 < 3:
                        self._hover_newest_flow_video_thumbnails(page, pre_existing_thumb_urls=pre_existing_thumb_urls)

                    # Bắt nút Download trực tiếp trên giao diện Google Flow (CÓ KIỂM TRA SHA-256 CHỐNG TRÙNG CẢNH CŨ)
                    try:
                        dl_btns = page.locator(
                            "button[aria-label*='Tải' i], button[aria-label*='Download' i], "
                            "[aria-label*='Tải video' i], button:has-text('Tải xuống'), button:has-text('Download')"
                        ).all()
                        for dl_btn in dl_btns:
                            if dl_btn.is_visible():
                                try:
                                    tmp_dl_path = output_path + ".dl_tmp"
                                    with page.expect_download(timeout=8000) as dl_info:
                                        dl_btn.click(force=True, timeout=2000)
                                    dl = dl_info.value
                                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                                    dl.save_as(tmp_dl_path)
                                    if os.path.exists(tmp_dl_path) and os.path.getsize(tmp_dl_path) > 10000:
                                        with open(tmp_dl_path, "rb") as tf:
                                            dl_bytes = tf.read()
                                        dl_hash = hashlib.sha256(dl_bytes).hexdigest()
                                        if dl_hash in self.seen_video_hashes:
                                            try:
                                                os.remove(tmp_dl_path)
                                            except Exception:
                                                pass
                                            continue
                                        os.replace(tmp_dl_path, output_path)
                                        self.seen_video_hashes.add(dl_hash)
                                        self._exit_flow_edit_mode_if_needed(page, project_url)
                                        safe_log(f"[✓] [Cảnh {scene_num}/{total_scenes}] Đã tải xong video 3D từ nút Download: {output_path}")
                                        return True, output_path
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    for v in page.locator("video").all():
                        try:
                            src = v.get_attribute("src") or v.evaluate("el => el.currentSrc || el.src")
                            if src and ("blob:" in src or "http" in src):
                                norm_src = normalize_flow_video_url(src)
                                if (
                                    src not in self.seen_video_urls
                                    and norm_src not in self.seen_video_urls
                                    and src not in pre_existing_urls
                                    and norm_src not in pre_existing_urls
                                ):
                                    if src not in candidate_urls:
                                        candidate_urls.append(src)
                        except Exception:
                            pass

                    for s in page.locator("video source").all():
                        try:
                            s_src = s.get_attribute("src")
                            if s_src and ("blob:" in s_src or "http" in s_src):
                                norm_s = normalize_flow_video_url(s_src)
                                if (
                                    s_src not in self.seen_video_urls
                                    and norm_s not in self.seen_video_urls
                                    and s_src not in pre_existing_urls
                                    and norm_s not in pre_existing_urls
                                ):
                                    if s_src not in candidate_urls:
                                        candidate_urls.append(s_src)
                        except Exception:
                            pass

                    if not candidate_urls and elapsed > 25.0:
                        for v in page.locator("video").all():
                            try:
                                src = v.get_attribute("src") or v.evaluate("el => el.currentSrc || el.src")
                                norm_src = normalize_flow_video_url(src) if src else ""
                                if (
                                    src
                                    and ("blob:" in src or "http" in src)
                                    and src not in self.seen_video_urls
                                    and norm_src not in self.seen_video_urls
                                ):
                                    if src not in candidate_urls:
                                        candidate_urls.append(src)
                            except Exception:
                                pass

                    for candidate_url in candidate_urls:
                        video_bytes = self._download_flow_video_bytes(page, candidate_url)
                        if not video_bytes or len(video_bytes) < 10000:
                            continue

                        file_hash = hashlib.sha256(video_bytes).hexdigest()
                        norm_cand = normalize_flow_video_url(candidate_url)
                        if file_hash in self.seen_video_hashes:
                            self.seen_video_urls.add(candidate_url)
                            self.seen_video_urls.add(norm_cand)
                            continue

                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        with open(output_path, "wb") as f_out:
                            f_out.write(video_bytes)
                        self.seen_video_hashes.add(file_hash)
                        self.seen_video_urls.add(candidate_url)
                        self.seen_video_urls.add(norm_cand)
                        self._exit_flow_edit_mode_if_needed(page, project_url)
                        safe_log(
                            f"[✓] [Cảnh {scene_num}/{total_scenes}] Đã lưu video 3D từ Google Flow "
                            f"({len(video_bytes)} bytes, hash {file_hash[:8]}): {output_path}"
                        )
                        return True, output_path

                return False, f"Hết thời gian chờ ({effective_timeout}s) video Cảnh {scene_num} từ Google Flow."
            finally:
                try:
                    page.remove_listener("response", _on_response)
                except Exception:
                    pass

    def generate_scene_3d_image_on_google_flow(self, *args, **kwargs) -> Tuple[bool, str]:
        return self._generate_image_on_google_flow(*args, **kwargs)

    def generate_whiteboard_illustration_on_google_flow(
        self, prompt: str, output_path: str, scene_num: int = 1, total_scenes: int = 1,
        orientation: str = "horizontal", attempt_num: int = 1, status_callback=None,
        is_cancelled_callback=None,
    ) -> Tuple[bool, str]:
        return self._generate_image_on_google_flow(
            scene_num=scene_num, total_scenes=total_scenes, scene_data={"image_prompt": prompt},
            output_path=output_path, orientation=orientation, attempt_num=attempt_num,
            status_callback=status_callback, is_cancelled_callback=is_cancelled_callback,
            image_style="whiteboard")

    def _generate_image_on_google_flow(
        self,
        scene_num: int,
        total_scenes: int,
        scene_data: Dict[str, Any],
        output_path: str,
        character_anchor: str = "",
        environment_anchor: str = "",
        orientation: str = "vertical",
        timeout_sec: Optional[int] = None,
        attempt_num: int = 1,
        status_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled_callback: Optional[Callable[[], bool]] = None,
        image_style: str = "3d",
    ) -> Tuple[bool, str]:
        """
        Đưa prompt Hình ảnh 3D của Cảnh `scene_num` (từ kịch bản MuseAI) sang tab Google Flow (chế độ `🍌 Nano Banana 2.1` - 0 tín dụng),
        render siêu tốc trong ~4–8 giây, tải file ảnh 3D (`scene_001.png ... scene_00N.png`) về ổ cứng để ghép cùng chuyển động Visual Beats.
        """
        with _BROWSER_LOCK:
            ok, msg = self.get_or_open_google_flow_tab()
            if not ok or not self.flow_page:
                return False, msg

            page = self.flow_page
            effective_timeout = int(timeout_sec or 150)
            project_url = str(self.cfg.get("project_url", "https://flow.google.com")).split("/tool/", 1)[0].split("/edit/", 1)[0].rstrip("/")

            self._exit_flow_edit_mode_if_needed(page, project_url)
            self._ensure_direct_video_composer_mode(page, orientation=orientation, media_mode="image")

            raw_prompt = str(scene_data.get("raw_video_prompt") or scene_data.get("video_prompt") or "").strip()
            cam_dir = str(scene_data.get("camera_directive") or "35mm cinema lens, shallow depth of field").strip()

            full_3d_img_prompt = str(scene_data.get("image_prompt") or "").strip()
            if image_style == "whiteboard" and not full_3d_img_prompt:
                return False, "Thiếu mô tả minh họa whiteboard."
            if image_style != "whiteboard" and (not full_3d_img_prompt or "Generate a single masterpiece 3D CGI" not in full_3d_img_prompt):
                full_3d_img_prompt = clean_and_build_flow_3d_image_prompt(
                    scene_prompt=raw_prompt,
                    character_anchor=character_anchor,
                    environment_anchor=environment_anchor,
                    camera_directive=cam_dir,
                    orientation=orientation,
                    scene_data=scene_data,
                )

            if image_style != "whiteboard" and int(attempt_num or 1) >= 2:
                full_3d_img_prompt = sanitize_prompt_for_flow_retry(full_3d_img_prompt)

            media_label = "minh họa whiteboard 2D" if image_style == "whiteboard" else "hình 3D"
            narration_preview = str(scene_data.get("narration") or "")[:90]
            safe_log(f"\n[GOOGLE FLOW IMAGE - CẢNH {scene_num}/{total_scenes}] Đang tạo {media_label}...")
            safe_log(f"  + Lời dẫn MuseAI : {narration_preview}...")

            try:
                pre_existing_img_urls = set()
                for img_el in page.locator("img").all():
                    try:
                        i_src = img_el.get_attribute("src")
                        if i_src and "flow-content.google" in i_src:
                            pre_existing_img_urls.add(i_src)
                            pre_existing_img_urls.add(normalize_flow_video_url(i_src))
                    except Exception:
                        pass

                input_box = self._find_google_flow_composer(page)
                if not input_box:
                    page.goto(project_url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    self._ensure_direct_video_composer_mode(page, orientation=orientation, media_mode="image")
                    input_box = self._find_google_flow_composer(page)

                if not input_box:
                    return False, "Không tìm thấy ô nhập prompt trên tab Google Flow."

                try:
                    input_box.click(force=True, timeout=5000)
                    page.wait_for_timeout(150)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    input_box.fill("")
                except Exception:
                    pass

                filled_ok = False
                try:
                    input_box.fill(full_3d_img_prompt)
                    page.wait_for_timeout(250)
                    cur_txt = input_box.evaluate(
                        "e => typeof e.value === 'string' ? e.value : (e.innerText || e.textContent || '')"
                    )
                    if len(str(cur_txt or "").strip()) > 15:
                        filled_ok = True
                except Exception:
                    filled_ok = False

                if not filled_ok:
                    try:
                        input_box.click(force=True, timeout=3000)
                        page.keyboard.insert_text(full_3d_img_prompt)
                        page.wait_for_timeout(250)
                    except Exception as exc:
                        return False, f"Không thể điền prompt {media_label} Cảnh {scene_num} vào Google Flow: {exc}"

                sub_ok, sub_msg = self._submit_google_flow_composer(page, input_box)
                if not sub_ok:
                    return False, sub_msg

                safe_log(f"[*] Đã gửi {media_label} Cảnh {scene_num}/{total_scenes} lên Google Flow, đang đợi tạo ảnh...")
                start_time = time.time()

                while time.time() - start_time < effective_timeout:
                    if is_cancelled_callback and is_cancelled_callback():
                        return False, "Đã bỏ qua theo yêu cầu người dùng"

                    page.wait_for_timeout(1500)
                    elapsed = time.time() - start_time
                    if elapsed < 2.5:
                        continue

                    if int(elapsed) % 9 < 2 and status_callback:
                        try:
                            status_callback(
                                int(elapsed),
                                f"[*] [{media_label} {scene_num}/{total_scenes}] Đang chờ Google Flow tạo ảnh ({int(elapsed)}s)...",
                            )
                        except Exception:
                            pass

                    candidate_imgs: List[str] = []
                    for img_el in page.locator("img").all():
                        try:
                            if not img_el.is_visible():
                                continue
                            alt_txt = str(img_el.get_attribute("alt") or "").lower()
                            if "video" in alt_txt:
                                continue
                            i_src = str(img_el.get_attribute("src") or "")
                            if not i_src or "flow-content.google" not in i_src:
                                continue
                            norm_i = normalize_flow_video_url(i_src)
                            if (
                                i_src not in pre_existing_img_urls
                                and norm_i not in pre_existing_img_urls
                                and i_src not in self.seen_video_urls
                                and norm_i not in self.seen_video_urls
                            ):
                                candidate_imgs.append(i_src)
                        except Exception:
                            pass

                    for cand_img_url in candidate_imgs:
                        img_bytes = self._download_flow_video_bytes(page, cand_img_url)
                        if not img_bytes or len(img_bytes) < 5000:
                            continue
                        img_hash = hashlib.sha256(img_bytes).hexdigest()
                        norm_c = normalize_flow_video_url(cand_img_url)
                        if img_hash in self.seen_video_hashes:
                            self.seen_video_urls.add(cand_img_url)
                            self.seen_video_urls.add(norm_c)
                            continue

                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        with open(output_path, "wb") as f_out:
                            f_out.write(img_bytes)
                        self.seen_video_hashes.add(img_hash)
                        self.seen_video_urls.add(cand_img_url)
                        self.seen_video_urls.add(norm_c)
                        safe_log(
                            f"[✓] [{media_label} {scene_num}/{total_scenes}] Đã lưu ảnh từ Google Flow "
                            f"({len(img_bytes)} bytes): {output_path}"
                        )
                        return True, output_path

                return False, f"Hết thời gian chờ ({effective_timeout}s) {media_label} Cảnh {scene_num} từ Google Flow."
            except Exception as exc:
                return False, f"Lỗi khi tạo {media_label} Cảnh {scene_num} trên Google Flow: {exc}"


# ==============================================================================
# PHẦN 4: GHÉP VIDEO HOÀN CHỈNH (LỒNG TIẾNG ĐA GIỌNG DẪN CHUYỆN + NHÂN VẬT + PHỤ ĐỀ)
# ==============================================================================

def synthesize_museai_scenes_interactive_tts(
    scenes: List[Dict[str, Any]],
    work_dir: str,
    language: str = "vi",
    vietnamese_voice: str = "",
) -> Tuple[bool, str]:
    """
    Sinh file âm thanh lồng tiếng đa giọng đọc (`scene_001.mp3 ... scene_00N.mp3`) cho từng phân cảnh:
    - Kết hợp giữa giọng **Người dẫn chuyện (`narrator`)** ấm áp truyền cảm và giọng **Các nhân vật tương tác (`character_1`, `character_2`)**
      với cao độ (pitch) và nhịp độ (rate) phân biệt rõ ràng.
    - Cập nhật `sc['narration']` khớp 100% từng từ với audio thực tế để bộ tạo phụ đề (word timestamps) đồng bộ tuyệt đối.
    """
    if not scenes:
        return True, "Không có phân cảnh nào cần lồng tiếng."

    os.makedirs(work_dir, exist_ok=True)
    try:
        from src.tts_service import generate_multivoice_tts, generate_tts, get_audio_duration
        from src.voice_casting import VoiceCaster, apply_vieneu_casting
    except ModuleNotFoundError:
        from video_studio.src.tts_service import generate_multivoice_tts, generate_tts, get_audio_duration
        from video_studio.src.voice_casting import VoiceCaster, apply_vieneu_casting

    tot_scenes = max(2, len(scenes))
    voice_caster: Optional[VoiceCaster] = None
    cast_file = Path(work_dir) / "voice_casting.json"
    saved_cast = next((sc["voice_casting"] for sc in scenes if isinstance(sc, dict) and isinstance(sc.get("voice_casting"), dict)), {})
    if cast_file.is_file():
        try:
            data = json.loads(cast_file.read_text(encoding="utf-8"))
            saved_cast = dict(data if isinstance(data, dict) else {}, **saved_cast)
        except (OSError, ValueError):
            return False, "Không đọc được bảng giọng nhân vật đã lưu. Hãy kiểm tra voice_casting.json trước khi dựng tiếp."
    for idx, sc in enumerate(scenes, start=1):
        if not isinstance(sc, dict):
            continue
        sc_num = int(sc.get("scene_num") or idx)
        audio_file = os.path.join(work_dir, f"scene_{sc_num:03d}.mp3")
        meta_file = os.path.join(work_dir, f"scene_{sc_num:03d}_tts.meta.json")

        try:
            dialogue_segs = build_scene_dialogue_segments(
                sc, language=language, total_scenes=tot_scenes,
                allow_synthetic_filler=sc.get("media_type") != "whiteboard" and not sc.get("series_bridge"))
        except ValueError as exc:
            return False, f"Cảnh {sc_num}: {exc}"
        if not dialogue_segs:
            continue

        selected_vi_voice = vietnamese_voice or sc.get("vietnamese_voice", "")
        if selected_vi_voice.startswith("vieneu-v3:"):
            # Giọng dẫn chuyện = giọng đã chọn; mỗi nhân vật 1 giọng VieNeu riêng + tốc độ theo cảm xúc câu thoại
            if voice_caster is None:
                voice_caster = VoiceCaster(selected_vi_voice, saved_cast)
            dialogue_segs = apply_vieneu_casting(dialogue_segs, voice_caster)
            sc["dialogue_lines"] = dialogue_segs
            sc["vietnamese_voice"] = selected_vi_voice
        elif selected_vi_voice:
            dialogue_segs = [dict(seg, voice_spec=selected_vi_voice)
                             if seg.get("language") == "vi" or
                             (language == "vi" and str(seg.get("voice_spec", "")).startswith("vi-"))
                             else dict(seg) for seg in dialogue_segs]
            sc["dialogue_lines"] = dialogue_segs
            sc["vietnamese_voice"] = selected_vi_voice

        multivoice_tuples: List[Tuple[str, str, str]] = [
            (seg["text"], seg["voice_spec"], seg.get("rate", "+0%"))
            for seg in dialogue_segs
            if seg.get("text")
        ]
        combined_text = sc.get("narration", "")
        # Invalidate old caches that could contain the legacy test-tone fallback.
        voices_signature = "real-speech-v2|" + "|".join(f"{v}:{rate}:{t}" for (t, v, rate) in multivoice_tuples)
        bilingual = sc.get("content_mode") == "english_teaching_vi"
        if bilingual:
            voices_signature = "bilingual-segment-timing-v1|" + voices_signature
        measured_segments = []

        # Kiểm tra cache: chỉ dùng lại nếu cả lời thoại lẫn phân vai giọng đọc không đổi
        cache_valid = (os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000
                       and os.path.exists(meta_file))
        if cache_valid and os.path.exists(meta_file):
            try:
                saved_meta = json.loads(Path(meta_file).read_text(encoding="utf-8"))
                if saved_meta.get("voices_signature") != voices_signature:
                    cache_valid = False
                elif bilingual:
                    sc["tts_segment_timings"] = saved_meta.get("tts_segment_timings") or []
            except Exception:
                cache_valid = False

        if not cache_valid:
            safe_log(
                f"[*] [TTS ĐA GIỌNG Cảnh {sc_num}/{len(scenes)}] "
                f"Đang lồng tiếng kết hợp Dẫn chuyện + Nhân vật ({len(multivoice_tuples)} lượt thoại)..."
            )
            strict_options = {"strict_language": True}
            if bilingual:
                strict_options["segment_timing_callback"] = measured_segments.extend
            ok, err_or_path = generate_multivoice_tts(multivoice_tuples, audio_file, **strict_options)
            if not ok or not os.path.exists(audio_file):
                if selected_vi_voice.startswith("vieneu-v3:"):
                    return False, f"Lỗi VieNeu Cảnh {sc_num}: {err_or_path}. Không tự đổi sang giọng khác."
                if sc.get("content_mode") == "english_teaching_vi":
                    return False, f"Lỗi giọng đọc Việt–Anh Cảnh {sc_num}: {err_or_path}. Không chuyển sang đọc cả bài bằng một ngôn ngữ."
                # Fallback an toàn nếu ghép multivoice gặp sự cố
                fallback_voice = ROLE_VOICE_MAP_VI["narrator"] if language == "vi" else ROLE_VOICE_MAP_EN["narrator"]
                ok, err_or_path = generate_tts(combined_text, audio_file, voice=fallback_voice, strict_language=True)
                if not ok or not os.path.exists(audio_file):
                    return False, f"Lỗi sinh lồng tiếng Cảnh {sc_num}: {err_or_path}"

        dur = get_audio_duration(audio_file)
        sc["audio_path"] = audio_file
        sc["audio_duration"] = dur
        if measured_segments:
            total = sum(float(s["duration"]) for s in measured_segments)
            cursor = 0.
            sc["tts_segment_timings"] = []
            for segment in measured_segments:
                length = float(segment["duration"]) / total * dur if total > 0 else 0.
                sc["tts_segment_timings"].append(dict(segment, start=cursor, end=cursor + length))
                cursor += length
        try:
            Path(meta_file).write_text(
                json.dumps(
                    {
                        "text": combined_text,
                        "voices_signature": voices_signature,
                        "dialogue_lines": dialogue_segs,
                        "duration": dur,
                        "tts_segment_timings": sc.get("tts_segment_timings") or [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    if voice_caster is not None:
        assignments = voice_caster.assignments()
        try:
            cast_file.write_text(json.dumps(assignments, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            return False, f"Không lưu được bảng giọng nhân vật: {exc}"
        for sc in scenes:
            if isinstance(sc, dict):
                sc["voice_casting"] = dict(assignments)
    return True, f"Đã hoàn thành lồng tiếng đa giọng (Dẫn chuyện + Nhân vật) cho {len(scenes)} phân cảnh."


def merge_flow_3d_scenes_into_final_movie(
    scenes: List[Dict[str, Any]],
    work_dir: str,
    final_output_path: str,
    language: str = "vi",
    orientation: str = "vertical",
    with_tts_and_subtitles: bool = True,
    tts_already_ready: bool = False,
) -> Tuple[bool, str]:
    """
    Ghép toàn bộ các file video 3D (`scene_01.mp4 ... scene_0N.mp4`) đã sinh từ Google Flow
    thành 1 bộ phim 3D hoàn chỉnh:
    - Tự động sinh lồng tiếng đa giọng đọc (kết hợp Người dẫn chuyện + Tương tác giữa các nhân vật),
      đồng bộ thời lượng video/audio và burn phụ đề đáy khớp 100% từng câu thoại.
    - Nếu chạy độc lập hoặc không bật TTS, tự động ghép nối trực tiếp bằng FFmpeg lossless.
    """
    # Every voiced production must fail explicitly if speech or subtitles fail.
    strict_completion = bool(with_tts_and_subtitles)
    if with_tts_and_subtitles:
        try:
            try:
                from src.batch_producer import build_exact_tts_timestamps
                from src.video_compiler import compile_video_pipeline
            except ModuleNotFoundError:
                from video_studio.src.batch_producer import build_exact_tts_timestamps
                from video_studio.src.video_compiler import compile_video_pipeline
            import shutil

            safe_log("[*] [BƯỚC 3 - TTS ĐA GIỌNG] Đang tạo lồng tiếng kết hợp Dẫn chuyện & Tương tác nhân vật cho từng cảnh...")
            tts_ok, tts_err = (True, "TTS đã sẵn sàng") if tts_already_ready else synthesize_museai_scenes_interactive_tts(
                scenes=scenes,
                work_dir=work_dir,
                language=language,
            )
            if tts_ok:
                if not scenes or any(not sc.get("audio_path") or not os.path.isfile(str(sc["audio_path"]))
                                     or os.path.getsize(str(sc["audio_path"])) <= 0 for sc in scenes):
                    return False, "Thiếu file lồng tiếng của phân cảnh. Video chưa được hoàn thành."
                for sc in scenes:
                    has_vid = bool(sc.get("video_path") and os.path.exists(str(sc.get("video_path"))))
                    sc["use_video_ai"] = has_vid
                words_ts = build_exact_tts_timestamps(scenes)
                safe_log("[*] [BƯỚC 4 - COMPILER] Đang ghép nối các cảnh 3D Google Flow + lồng tiếng đa vai + phụ đề...")
                # Chay compiler trong thread moi (stack sach): luong Streamlit/Playwright da sau nen moviepy
                # de bi "maximum recursion depth exceeded" va roi vao fallback giu am thanh Veo tieng Anh.
                comp_box: Dict[str, Any] = {}

                def _run_compiler() -> None:
                    try:
                        comp_box["res"] = compile_video_pipeline(
                            scenes=scenes,
                            words_timestamps=words_ts,
                            max_duration=3600.0,
                            orientation=orientation,
                        )
                    except BaseException as exc_c:
                        comp_box["res"] = (False, [], f"{type(exc_c).__name__}: {exc_c}")

                old_stack = threading.stack_size()
                try:
                    threading.stack_size(64 * 1024 * 1024)
                except (ValueError, RuntimeError):
                    pass
                comp_thread = threading.Thread(target=_run_compiler, name="museai-compiler")
                comp_thread.start()
                comp_thread.join()
                try:
                    threading.stack_size(old_stack)
                except (ValueError, RuntimeError):
                    pass
                comp_ok, compiled_list, comp_err = comp_box.get("res", (False, [], "compiler thread khong tra ket qua"))
                if comp_ok and compiled_list and os.path.exists(compiled_list[0]):
                    os.makedirs(os.path.dirname(os.path.abspath(final_output_path)), exist_ok=True)
                    shutil.copy2(compiled_list[0], final_output_path)
                    return True, final_output_path
                if strict_completion:
                    return False, f"Không thể ghép video với lồng tiếng và phụ đề: {comp_err}"
                safe_log(f"[!] Compiler phụ đề báo lỗi ({comp_err}), chuyển sang ghép nối FFmpeg trực tiếp...")
            else:
                if strict_completion:
                    return False, f"Không thể tạo giọng đọc bài học: {tts_err}"
                safe_log(f"[!] TTS báo lỗi ({tts_err}), chuyển sang ghép nối FFmpeg trực tiếp...")
        except Exception as exc:
            if strict_completion:
                return False, f"Không thể hoàn thiện video có lồng tiếng: {exc}"
            safe_log(f"[!] Không dùng bộ compiler phụ đề ({exc}), chuyển sang ghép FFmpeg trực tiếp...")

    # Ghép trực tiếp các video 3D bằng FFmpeg
    valid_paths = [
        sc.get("video_path", "")
        for sc in scenes
        if isinstance(sc, dict) and sc.get("video_path") and os.path.exists(sc["video_path"])
    ]
    if not valid_paths:
        return False, "Không có file video phân cảnh hợp lệ để ghép."

    os.makedirs(os.path.dirname(os.path.abspath(final_output_path)), exist_ok=True)
    concat_file = Path(final_output_path).with_suffix(".concat.txt")
    try:
        lines = [f"file '{os.path.abspath(p).replace(chr(92), '/')}'" for p in valid_paths]
        concat_file.write_text("\n".join(lines), encoding="utf-8")
        # Luon bo am thanh goc cua Veo (hay tu sinh giong tieng Anh); chi dung long tieng TTS da tao neu co.
        audio_paths = [
            str(sc.get("audio_path"))
            for sc in scenes
            if isinstance(sc, dict) and sc.get("video_path") and os.path.exists(str(sc.get("video_path")))
            and sc.get("audio_path") and os.path.exists(str(sc.get("audio_path")))
        ]
        audio_concat = Path(final_output_path).with_suffix(".audio.concat.txt")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
        if len(audio_paths) == len(valid_paths):
            audio_concat.write_text(
                "\n".join(f"file '{os.path.abspath(p).replace(chr(92), '/')}'" for p in audio_paths),
                encoding="utf-8",
            )
            cmd += ["-f", "concat", "-safe", "0", "-i", str(audio_concat),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-shortest"]
        else:
            cmd += ["-map", "0:v:0", "-an"]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", final_output_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 10000:
            return True, final_output_path
        return False, "FFmpeg chạy xong nhưng không tạo được video đầu ra."
    except Exception as exc:
        return False, f"Lỗi ghép video FFmpeg: {exc}"
    finally:
        for tmp_file in (concat_file, Path(final_output_path).with_suffix(".audio.concat.txt")):
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass


# ==============================================================================
# PHẦN 5: PIPELINE CHÍNH (MUSEAI VIẾT KỊCH BẢN -> GOOGLE FLOW SINH VIDEO 3D)
# ==============================================================================

def summarize_episode_for_continuity(story_data: Dict[str, Any], episode_num: int = 1) -> str:
    """
    Tạo bản tóm tắt cốt truyện (Mở đầu -> Cao trào -> Kết thúc) của tập `episode_num`
    để truyền vào tập tiếp theo, giúp duy trì mạch truyện dài xuyên suốt nhiều tập.
    """
    title = str(story_data.get("story_title") or f"Tập {episode_num}").strip()
    scenes = [sc for sc in story_data.get("scenes") or [] if not sc.get("series_bridge")]
    if not scenes:
        return f"Tập {episode_num} ({title}): Đã hoàn thành chặng hành trình thứ {episode_num}."

    first_narr = str(scenes[0].get("narration") or "").strip()
    mid_idx = max(0, len(scenes) // 2)
    climax_narr = str(scenes[mid_idx].get("narration") or "").strip() if len(scenes) > 2 else ""
    last_narr = str(scenes[-1].get("narration") or "").strip() if len(scenes) > 1 else ""

    parts = [p for p in (first_narr, climax_narr, last_narr) if p]
    joined = " -> ".join(parts)
    if len(joined) > 420:
        joined = joined[:417] + "..."
    return f"Tập {episode_num} ({title}): {joined}"


def run_museai_script_to_google_flow_3d_pipeline(
    topic: str = "",
    target_scenes: Optional[int] = None,
    language: str = "vi",
    orientation: str = "vertical",
    visual_mode: str = "video_3d",
    story_style: str = "cinematic_storytelling",
    with_tts_and_subtitles: bool = True,
    reuse_existing_script: bool = False,
    story_timeout_sec: Optional[int] = None,
    work_dir: Optional[str] = None,
    output_dir: str = str(OUTPUT_DIR),
    episode_num: int = 1,
    total_episodes: int = 1,
    previous_episodes_summary: str = "",
    locked_character_anchor: str = "",
    locked_environment_anchor: str = "",
    progress_callback: Optional[Callable[[float, str], None]] = None,
    on_script_ready_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_scene_status_callback: Optional[Callable[[int, int, str, Optional[str]], None]] = None,
    is_cancelled_callback: Optional[Callable[[], bool]] = None,
    previous_episode_learning: str = "",
    required_episode_topic: str = "",
    whiteboard_ai_enabled: bool = True,
    vietnamese_voice: str = "",
    initial_voice_casting: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Luồng tự động hóa kết hợp MuseAI + Google Flow (hỗ trợ cả 3 chế độ: `video_3d`, `image_3d`, `hybrid_3d`):
    1. Mở tab MuseAI trên Chrome -> Đọc kịch bản sẵn có hoặc kêu MuseAI viết kịch bản cốt truyện 3D
       (đầy đủ Mở đầu - Cao trào - Kết thúc, tự động chia số khung hình khớp 1:1 theo câu chuyện).
    2. Chuyển sang tab Google Flow trên cùng cửa sổ Chrome -> Lặp tuần tự đưa từng phân cảnh (Cảnh 1 -> Cảnh 2 -> ... -> Cảnh N)
       của MuseAI vào Google Flow:
       - Với cảnh `media_type == "video"`: dùng Veo sinh video clip 3D (`scene_001.mp4 ...`).
       - Với cảnh `media_type == "image"`: dùng Nano Banana 2.1 (0 tín dụng) sinh hình 3D siêu tốc (`scene_001.png ...`) kết hợp chuyển động điện ảnh Visual Beats.
    3. Tự động lồng tiếng đa giọng (Dẫn chuyện + Nhân vật) + ghép nối toàn bộ các cảnh từ Google Flow thành 1 bộ phim hoàn chỉnh.
    """
    def notify(pct: float, msg: str):
        safe_log(f"[{int(pct):3d}%] {msg}")
        if progress_callback:
            try:
                progress_callback(pct, msg)
            except Exception:
                pass

    ep_num = max(1, int(episode_num or 1))
    tot_eps = max(1, int(total_episodes or 1))
    ep_suffix = f"_tap{ep_num:02d}" if tot_eps > 1 else ""
    ep_label = f"[Tập {ep_num}/{tot_eps}] " if tot_eps > 1 else ""
    mode_norm = str(visual_mode or "video_3d").strip().lower()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    session_prefix = "muse_whiteboard" if mode_norm == "whiteboard" else "muse_flow_3d"
    session_dir = Path(work_dir) if work_dir else (TEMP_DIR / f"{session_prefix}_{timestamp}{ep_suffix}")
    session_dir.mkdir(parents=True, exist_ok=True)

    meta: Dict[str, Any] = {
        "topic": topic,
        "language": language,
        "episode_num": ep_num,
        "total_episodes": tot_eps,
        "visual_mode": mode_norm,
        "story_style": story_style,
        "whiteboard_ai_enabled": bool(whiteboard_ai_enabled),
        "vietnamese_voice": vietnamese_voice,
        "script_engine": "museai_browser_agent",
        "video_engine": ("local_whiteboard_pillow_ffmpeg" if mode_norm == "whiteboard" else
                         "google_flow_nano_banana_3d" if mode_norm == "image_3d" else "google_flow_veo_3d"),
        "timestamp": timestamp,
        "session_dir": str(session_dir),
    }

    controller = MuseAIFlowHybridController()

    # 1. TAB MUSEAI: VIẾT HOẶC ĐỌC KỊCH BẢN CỐT TRUYỆN 3D ĐỦ 3 HỒI (MỞ ĐẦU - CAO TRÀO - KẾT THÚC)
    if reuse_existing_script and ep_num == 1:
        notify(5, f"{ep_label}Đang kiểm tra và đọc kịch bản trên tab MuseAI...")
    else:
        notify(5, f"{ep_label}Đang mở MuseAI để viết kịch bản {'người que và sơ đồ' if mode_norm == 'whiteboard' else 'hoạt hình 3D'}...")

    ok_script, story_data = controller.generate_3d_script_via_museai(
        topic=topic,
        target_scenes=target_scenes,
        language=language,
        orientation=orientation,
        visual_mode=mode_norm,
        story_style=story_style,
        timeout_sec=story_timeout_sec,
        reuse_existing_if_ready=(reuse_existing_script and ep_num == 1),
        episode_num=ep_num,
        total_episodes=tot_eps,
        previous_episodes_summary=previous_episodes_summary,
        locked_character_anchor=locked_character_anchor,
        locked_environment_anchor=locked_environment_anchor,
        status_callback=lambda sec, m: notify(10, f"{ep_label}{m}"),
        is_cancelled_callback=is_cancelled_callback,
        previous_episode_learning=previous_episode_learning,
        required_episode_topic=required_episode_topic,
        whiteboard_ai_enabled=whiteboard_ai_enabled,
    )
    if not ok_script:
        err = story_data.get("error", "Lỗi khi lấy kịch bản từ MuseAI.")
        notify(5, f"❌ {ep_label}{err}")
        return False, err, meta

    if language == "vi_en":
        if mode_norm == "whiteboard":
            from src.english_teaching import prepare_whiteboard_lesson
            try:
                story_data = prepare_whiteboard_lesson(story_data)
            except ValueError as exc:
                return False, str(exc), meta
        story_data["content_mode"] = "english_teaching_vi"
        try:
            for scene in story_data.get("scenes") or []:
                build_scene_dialogue_segments(scene, language="vi_en", allow_synthetic_filler=False)
        except ValueError as exc:
            return False, str(exc), meta

    if tot_eps > 1 or previous_episode_learning:
        from src.museai_story_modes import add_learning_bridges
        try:
            story_data = add_learning_bridges(story_data, ep_num, tot_eps, language,
                                              previous_episode_learning or previous_episodes_summary)
        except ValueError as exc:
            return False, str(exc), meta
        # New bridge scenes need visual prompts too, without re-splitting existing shots.
        if mode_norm != "whiteboard":
            prepared_scenes = []
            for scene in story_data["scenes"]:
                if scene.get("series_bridge"):
                    bridge_story = dict(story_data, scenes=[scene])
                    prepared_scenes.extend(controller._enrich_scenes_with_3d_prompts(
                        bridge_story, orientation, visual_mode=mode_norm)["scenes"])
                else:
                    prepared_scenes.append(scene)
            story_data["scenes"] = [dict(sc, scene_num=i) for i, sc in enumerate(prepared_scenes, 1)]
    if mode_norm == "whiteboard":
        story_data = controller._enrich_scenes_with_3d_prompts(story_data, orientation, visual_mode="whiteboard")

    if locked_character_anchor and locked_character_anchor.strip():
        story_data["character_anchor"] = locked_character_anchor.strip()
    if locked_environment_anchor and locked_environment_anchor.strip() and not story_data.get("environment_anchor"):
        story_data["environment_anchor"] = locked_environment_anchor.strip()

    scenes = story_data.get("scenes", [])
    if initial_voice_casting:
        for scene in scenes:
            scene["voice_casting"] = dict(initial_voice_casting)
    if vietnamese_voice:
        for scene in scenes:
            scene["vietnamese_voice"] = vietnamese_voice
        story_data["vietnamese_voice"] = vietnamese_voice
    total_scenes = len(scenes)
    char_anchor = story_data.get("character_anchor", "")
    env_anchor = story_data.get("environment_anchor", "")
    story_title = story_data.get("story_title", topic[:40] if topic else "MuseAI_Flow_3D_Movie")

    if char_anchor and mode_norm != "whiteboard":
        try:
            try:
                from src.flow_character_vault import save_character_to_vault
            except ModuleNotFoundError:
                from video_studio.src.flow_character_vault import save_character_to_vault
            save_character_to_vault(
                name=f"Nhân vật phim: {story_title[:36]}",
                character_dna=char_anchor,
                environment_dna=env_anchor,
            )
        except Exception:
            pass

    script_file = session_dir / ("museai_whiteboard_script.json" if mode_norm == "whiteboard" else "museai_3d_script.json")
    script_file.write_text(json.dumps(story_data, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["story_data"] = story_data
    meta["story"] = story_data
    meta["script_file"] = str(script_file)

    if on_script_ready_callback:
        try:
            on_script_ready_callback(story_data)
        except Exception:
            pass

    if mode_norm == "whiteboard":
        from src.whiteboard_video import render_whiteboard_story_scenes
        from src.whiteboard_ai_assets import resolve_whiteboard_ai_assets
        if is_cancelled_callback and is_cancelled_callback():
            return False, "Đã bỏ qua theo yêu cầu người dùng", meta
        flow_image_state = {"started": False}

        def generate_missing_illustration(**request):
            if not flow_image_state["started"]:
                notify(20, f"{ep_label}Đang mở Google Flow để AI tạo minh họa còn thiếu...")
                ok_project, project_msg = controller.start_fresh_google_flow_project(orientation=orientation)
                if not ok_project:
                    return False, project_msg
                flow_image_state["started"] = True
            return controller.generate_whiteboard_illustration_on_google_flow(
                **request, orientation=orientation,
                status_callback=lambda seconds, message: notify(25, f"{ep_label}{message}"),
                is_cancelled_callback=is_cancelled_callback)

        assets_ok, prepared_scenes, asset_report = resolve_whiteboard_ai_assets(
            scenes, generate_missing_illustration, character_anchor=char_anchor,
            enabled=whiteboard_ai_enabled, progress_callback=notify,
            is_cancelled_callback=is_cancelled_callback)
        meta["whiteboard_ai_assets"] = asset_report
        if not assets_ok:
            return False, asset_report.get("error", "Không tạo được minh họa AI."), meta
        scenes = prepared_scenes
        story_data["scenes"] = scenes
        script_file.write_text(json.dumps(story_data, ensure_ascii=False, indent=2), encoding="utf-8")
        if with_tts_and_subtitles:
            notify(38, f"{ep_label}Đang tạo lời đọc để căn thời lượng nét vẽ...")
            ok_tts, error = synthesize_museai_scenes_interactive_tts(scenes, str(session_dir), language)
            if not ok_tts:
                return False, error, meta
        ok_render, error = render_whiteboard_story_scenes(
            scenes, str(session_dir), orientation, with_audio=with_tts_and_subtitles,
            on_scene_status_callback=on_scene_status_callback,
            progress_callback=lambda pct, msg: notify(40 + max(0, pct - 25) * .7, msg),
            is_cancelled_callback=is_cancelled_callback)
        if not ok_render:
            return False, error, meta
        if is_cancelled_callback and is_cancelled_callback():
            return False, "Đã bỏ qua theo yêu cầu người dùng", meta
        os.makedirs(output_dir, exist_ok=True)
        final_output_path = str(Path(output_dir) / f"museai_whiteboard_{timestamp}{ep_suffix}.mp4")
        notify(85, f"{ep_label}Đang ghép whiteboard, lời đọc và phụ đề...")
        ok_merge, error = merge_flow_3d_scenes_into_final_movie(
            scenes, str(session_dir), final_output_path, language, orientation,
            with_tts_and_subtitles=with_tts_and_subtitles, tts_already_ready=True)
        if not ok_merge:
            return False, error, meta
        meta.update(final_video_path=final_output_path,
                    scene_video_paths=[sc["video_path"] for sc in scenes],
                    episode_summary=summarize_episode_for_continuity(story_data, ep_num))
        Path(final_output_path).with_suffix(".json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        notify(100, f"{ep_label}Hoàn thành video người que bàn tay vẽ: {final_output_path}")
        return True, final_output_path, meta

    notify(
        20,
        f"{ep_label}Đã sẵn sàng kịch bản '{story_title}' ({total_scenes} khung cảnh khớp nhịp truyện)! "
        f"Bắt đầu đưa tuần tự từ Khung 1 đến Khung {total_scenes} sang Google Flow..."
    )

    # 2. TAB GOOGLE FLOW: TẠO DỰ ÁN MỚI SẠCH CONTEXT & ĐƯA TỪ TỪ TỪNG KHUNG CẢNH (1 -> N) VÀO GOOGLE FLOW
    scene_video_paths: List[str] = []
    max_attempts_per_scene = 3

    need_flow_generation = False
    for i, sc_item in enumerate(scenes, start=1):
        m_type = str(sc_item.get("media_type") or ("image" if mode_norm == "image_3d" else "video"))
        ext = ".png" if m_type == "image" else ".mp4"
        min_bytes = 5000 if m_type == "image" else 10000
        f_candidate = session_dir / f"scene_{i:03d}{ext}"
        if not (f_candidate.exists() and f_candidate.stat().st_size > min_bytes):
            need_flow_generation = True
            break

    if need_flow_generation:
        notify(20, f"{ep_label}Đang tạo Dự án / Phiên làm việc mới sạch context trên Google Flow...")
        controller.start_fresh_google_flow_project(orientation=orientation)

    for idx, sc in enumerate(scenes, start=1):
        if is_cancelled_callback and is_cancelled_callback():
            return False, "Đã bỏ qua theo yêu cầu người dùng", meta

        sc_media = str(sc.get("media_type") or ("image" if mode_norm == "image_3d" else "video")).lower()
        is_img_scene = (sc_media == "image")
        scene_out_file = str(session_dir / (f"scene_{idx:03d}.png" if is_img_scene else f"scene_{idx:03d}.mp4"))
        min_valid_size = 5000 if is_img_scene else 10000
        step_pct = 20 + ((idx - 1) / total_scenes) * 60
        role_label = str(sc.get("scene_role") or f"Cảnh {idx}").strip()
        media_badge = "Hình 3D Nano Banana" if is_img_scene else "Video 3D Veo"

        # Tái sử dụng nếu cảnh này đã render thành công trước đó
        if os.path.exists(scene_out_file) and os.path.getsize(scene_out_file) > min_valid_size:
            safe_log(f"[✓] Tái sử dụng {media_badge} có sẵn cho Cảnh {idx}/{total_scenes}: {scene_out_file}")
            if is_img_scene:
                sc["image_path"] = scene_out_file
                sc["use_video_ai"] = False
            else:
                sc["video_path"] = scene_out_file
                sc["use_video_ai"] = True
            scene_video_paths.append(scene_out_file)
            if on_scene_status_callback:
                try:
                    on_scene_status_callback(idx, total_scenes, "completed", scene_out_file)
                except Exception:
                    pass
            continue

        if on_scene_status_callback:
            try:
                on_scene_status_callback(idx, total_scenes, "rendering", None)
            except Exception:
                pass

        scene_ok = False
        last_err = ""
        for attempt in range(1, max_attempts_per_scene + 1):
            retry_label = f" (thử lại {attempt}/{max_attempts_per_scene})" if attempt > 1 else ""
            notify(
                step_pct,
                f"{ep_label}[Khung {idx}/{total_scenes} - {role_label}] Đang tạo {media_badge} trên Google Flow{retry_label}..."
            )
            if is_img_scene:
                ok_gen, res_gen = controller.generate_scene_3d_image_on_google_flow(
                    scene_num=idx,
                    total_scenes=total_scenes,
                    scene_data=sc,
                    output_path=scene_out_file,
                    character_anchor=char_anchor,
                    environment_anchor=env_anchor,
                    orientation=orientation,
                    attempt_num=attempt,
                    status_callback=lambda sec, m, _pct=step_pct: notify(_pct, f"{ep_label}{m}"),
                    is_cancelled_callback=is_cancelled_callback,
                )
            else:
                ok_gen, res_gen = controller.generate_scene_3d_video_on_google_flow(
                    scene_num=idx,
                    total_scenes=total_scenes,
                    scene_data=sc,
                    output_path=scene_out_file,
                    character_anchor=char_anchor,
                    environment_anchor=env_anchor,
                    orientation=orientation,
                    attempt_num=attempt,
                    status_callback=lambda sec, m, _pct=step_pct: notify(_pct, f"{ep_label}{m}"),
                    is_cancelled_callback=is_cancelled_callback,
                )
            if ok_gen and os.path.exists(scene_out_file) and os.path.getsize(scene_out_file) > min_valid_size:
                if is_img_scene:
                    sc["image_path"] = scene_out_file
                    sc["use_video_ai"] = False
                else:
                    sc["video_path"] = scene_out_file
                    sc["use_video_ai"] = True
                scene_video_paths.append(scene_out_file)
                scene_ok = True
                break
            last_err = res_gen
            if attempt < max_attempts_per_scene:
                safe_log(f"[!] Cảnh {idx} ({media_badge}) trên Google Flow gặp lỗi tạm thời ({last_err}). Đợi 4s rồi thử lại...")
                time.sleep(4)

        if not scene_ok:
            if on_scene_status_callback:
                try:
                    on_scene_status_callback(idx, total_scenes, "failed", None)
                except Exception:
                    pass
            err_msg = f"Không thể sinh {media_badge} Cảnh {idx}/{total_scenes} trên Google Flow: {last_err}"
            notify(step_pct, f"❌ {ep_label}{err_msg}")
            return False, err_msg, meta

        if on_scene_status_callback:
            try:
                on_scene_status_callback(idx, total_scenes, "completed", scene_out_file)
            except Exception:
                pass

        notify(
            20 + (idx / total_scenes) * 60,
            f"✓ {ep_label}Hoàn tất {media_badge} Khung {idx}/{total_scenes} ({role_label})!"
        )

        # Nghỉ nhịp nhàng trước khi đưa tiếp cảnh kế tiếp vào Google Flow
        if idx < total_scenes:
            time.sleep(1.5 if is_img_scene else 3.0)

    meta["scene_video_paths"] = scene_video_paths

    # 3. GHÉP TOÀN BỘ KHUNG CẢNH 3D CỦA GOOGLE FLOW + LỒNG TIẾNG LỜI THOẠI MUSEAI + CHUYỂN ĐỘNG VISUAL BEATS
    notify(85, f"{ep_label}Đã có đủ {total_scenes} khung cảnh 3D từ Google Flow! Đang ghép thành tập phim hoàn chỉnh...")
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"museai_flow_3d_{timestamp}{ep_suffix}.mp4")

    ok_merge, merge_res = merge_flow_3d_scenes_into_final_movie(
        scenes=scenes,
        work_dir=str(session_dir),
        final_output_path=final_output_path,
        language=language,
        orientation=orientation,
        with_tts_and_subtitles=with_tts_and_subtitles,
    )
    if not ok_merge:
        notify(85, f"❌ {ep_label}{merge_res}")
        return False, merge_res, meta

    meta["final_video_path"] = final_output_path
    meta["episode_summary"] = summarize_episode_for_continuity(story_data, episode_num=ep_num)
    meta_json = os.path.splitext(final_output_path)[0] + ".json"
    meta["language"] = language
    Path(meta_json).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from src.video_library import ensure_metadata_for_new_video
    except ModuleNotFoundError:
        from video_studio.src.video_library import ensure_metadata_for_new_video
    ensure_metadata_for_new_video(final_output_path)  # tự tạo title/hashtag/mô tả đăng bài cho Thư viện video

    notify(100, f"🎉 {ep_label}Hoàn thành tập phim 3D: {final_output_path}")
    return True, final_output_path, meta


def run_museai_multi_episode_series_pipeline(
    topic: str = "",
    total_episodes: int = 1,
    target_scenes: Optional[int] = None,
    language: str = "vi",
    orientation: str = "vertical",
    visual_mode: str = "video_3d",
    story_style: str = "cinematic_storytelling",
    with_tts_and_subtitles: bool = True,
    reuse_existing_script_for_ep1: bool = False,
    story_timeout_sec: Optional[int] = None,
    work_dir: Optional[str] = None,
    output_dir: str = str(OUTPUT_DIR),
    initial_previous_summary: str = "",
    initial_character_anchor: str = "",
    initial_environment_anchor: str = "",
    progress_callback: Optional[Callable[[float, str], None]] = None,
    on_script_ready_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_scene_status_callback: Optional[Callable[[int, int, str, Optional[str]], None]] = None,
    on_episode_done_callback: Optional[Callable[[int, int, str, Dict[str, Any]], None]] = None,
    is_cancelled_callback: Optional[Callable[[], bool]] = None,
    initial_episode_learning: str = "",
    initial_next_episode_topic: str = "",
    start_episode_num: int = 1,
    whiteboard_ai_enabled: bool = True,
    vietnamese_voice: str = "",
    initial_voice_casting: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Điều phối sản xuất cốt truyện dài qua nhiều tập (Ít tập: 2-3 tập / Nhiều tập: 4-10+ tập):
    - Mỗi tập đều có cấu trúc Mở đầu -> Cao trào -> Kết thúc riêng biệt và xuất ra 1 file `.mp4` hoàn chỉnh.
    - Tự động duy trì `character_anchor` (khóa ngoại hình nhân vật 3D từ Tập 1) và `previous_episodes_summary`
      (tóm tắt mạch truyện các tập trước) sang các tập tiếp theo để toàn bộ Series liền mạch 100%.
    """
    tot_eps = max(1, int(total_episodes or 1))
    base_work = Path(work_dir) if work_dir else (TEMP_DIR / f"series_3d_{time.strftime('%Y%m%d_%H%M%S')}")
    base_work.mkdir(parents=True, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    episode_video_paths: List[str] = []
    episodes_meta: List[Dict[str, Any]] = []
    accumulated_summaries: List[str] = [initial_previous_summary.strip()] if initial_previous_summary.strip() else []
    locked_char = initial_character_anchor.strip()
    locked_env = initial_environment_anchor.strip()
    voice_casting = dict(initial_voice_casting or {})
    previous_learning = initial_episode_learning.strip() or initial_previous_summary.strip()
    promised_topic = initial_next_episode_topic.strip()
    start_ep = max(1, int(start_episode_num))
    final_ep = start_ep + tot_eps - 1

    for run_index, ep in enumerate(range(start_ep, final_ep + 1), 1):
        if is_cancelled_callback and is_cancelled_callback():
            return False, episode_video_paths, {"error": "Đã bỏ qua theo yêu cầu người dùng",
                                               "completed_episodes": episodes_meta}

        ep_work_dir = str(base_work / f"episode_{ep:02d}")
        prev_sum_str = " | ".join(accumulated_summaries)

        def _ep_progress(pct: float, msg: str, _index=run_index):
            overall_pct = ((_index - 1) / tot_eps) * 100.0 + (pct / tot_eps)
            if progress_callback:
                try:
                    progress_callback(overall_pct, msg)
                except Exception:
                    pass

        ok_ep, ep_video_or_err, ep_meta = run_museai_script_to_google_flow_3d_pipeline(
            topic=topic,
            target_scenes=target_scenes,
            language=language,
            orientation=orientation,
            visual_mode=visual_mode,
            story_style=story_style,
            with_tts_and_subtitles=with_tts_and_subtitles,
            reuse_existing_script=(reuse_existing_script_for_ep1 and ep == 1),
            story_timeout_sec=story_timeout_sec,
            work_dir=ep_work_dir,
            output_dir=output_dir,
            episode_num=ep,
            total_episodes=final_ep,
            previous_episodes_summary=prev_sum_str,
            locked_character_anchor=locked_char,
            locked_environment_anchor=locked_env,
            progress_callback=_ep_progress,
            on_script_ready_callback=on_script_ready_callback,
            on_scene_status_callback=on_scene_status_callback,
            is_cancelled_callback=is_cancelled_callback,
            previous_episode_learning=previous_learning,
            required_episode_topic=promised_topic,
            whiteboard_ai_enabled=whiteboard_ai_enabled,
            vietnamese_voice=vietnamese_voice,
            initial_voice_casting=voice_casting,
        )
        if not ok_ep:
            return False, episode_video_paths, {
                "error": ep_video_or_err,
                "failed_episode": ep,
                "completed_episodes": episodes_meta,
            }

        episode_video_paths.append(ep_video_or_err)
        episodes_meta.append(ep_meta)

        story_obj = ep_meta.get("story") or ep_meta.get("story_data") or {}
        voice_casting = next((dict(sc["voice_casting"]) for sc in story_obj.get("scenes", [])
                              if isinstance(sc, dict) and isinstance(sc.get("voice_casting"), dict)), voice_casting)
        if not locked_char and story_obj.get("character_anchor"):
            locked_char = str(story_obj["character_anchor"]).strip()
        if not locked_env and story_obj.get("environment_anchor"):
            locked_env = str(story_obj["environment_anchor"]).strip()

        ep_summary = ep_meta.get("episode_summary") or summarize_episode_for_continuity(story_obj, episode_num=ep)
        accumulated_summaries.append(ep_summary)
        previous_learning = str(story_obj.get("episode_learning_summary") or ep_summary).strip()
        promised_topic = str(story_obj.get("next_episode_topic") or "").strip()

        # Lưu sổ cái bộ nhớ Series để có thể viết tiếp tập mới bất cứ lúc nào
        try:
            ledger_name = "series_memory_ledger_whiteboard.json" if visual_mode == "whiteboard" else "series_memory_ledger.json"
            ledger_path = TEMP_DIR / ledger_name
            ledger_data = {
                "topic": topic,
                "last_episode_num": ep,
                "total_episodes": final_ep,
                "visual_mode": visual_mode,
                "voice_casting": voice_casting,
                "vietnamese_voice": vietnamese_voice,
                "last_episode_learning": previous_learning,
                "next_episode_topic": promised_topic,
                "locked_character_anchor": locked_char,
                "locked_environment_anchor": locked_env,
                "previous_episodes_summary": " | ".join(accumulated_summaries),
                "episode_video_paths": episode_video_paths,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            ledger_path.write_text(json.dumps(ledger_data, ensure_ascii=False, indent=2), encoding="utf-8")
            (base_work / "series_memory_ledger.json").write_text(
                json.dumps(ledger_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        if on_episode_done_callback:
            try:
                on_episode_done_callback(ep, final_ep, ep_video_or_err, ep_meta)
            except Exception:
                pass

    return True, episode_video_paths, {
        "topic": topic,
        "total_episodes": tot_eps,
        "locked_character_anchor": locked_char,
        "locked_environment_anchor": locked_env,
        "previous_episodes_summary": " | ".join(accumulated_summaries),
        "episodes": episodes_meta,
        "voice_casting": voice_casting,
        "episode_video_paths": episode_video_paths,
    }


# Hàm tương thích ngược nếu được import với tên cũ
run_museai_3d_story_pipeline = run_museai_script_to_google_flow_3d_pipeline


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Luồng tự động: MuseAI viết kịch bản cốt truyện 3D -> Google Flow sinh video 3D từng cảnh -> Ghép phim hoàn chỉnh"
    )
    parser.add_argument("--topic", "-t", type=str, default="", help="Chủ đề/ý tưởng (để trống nếu muốn MuseAI tự nghĩ cốt truyện)")
    parser.add_argument("--scenes", "-s", type=int, default=5, help="Số phân cảnh (mặc định: 5)")
    parser.add_argument("--lang", "-l", type=str, default="vi", choices=["vi", "en"], help="Ngôn ngữ lời thoại (vi/en)")
    parser.add_argument("--orientation", "-o", type=str, default="vertical", choices=["vertical", "horizontal"], help="Khung hình 9:16 hoặc 16:9")
    parser.add_argument("--no-tts", action="store_true", help="Chỉ ghép video 3D thuần từ Google Flow, không lồng tiếng TTS")
    args = parser.parse_args()

    topic_in = args.topic.strip()
    if not topic_in and sys.stdin and sys.stdin.isatty():
        print("\n" + "=" * 72)
        print("🎬 HYBRID 3D PIPELINE: MUSEAI (VIẾT KỊCH BẢN) + GOOGLE FLOW (SINH VIDEO 3D)")
        print("=" * 72)
        try:
            topic_in = input("👉 Nhập chủ đề phim 3D (hoặc bấm Enter để MuseAI tự sáng tác cốt truyện): ").strip()
        except EOFError:
            topic_in = ""

    ok, final_or_err, _ = run_museai_script_to_google_flow_3d_pipeline(
        topic=topic_in,
        target_scenes=args.scenes,
        language=args.lang,
        orientation=args.orientation,
        with_tts_and_subtitles=not args.no_tts,
    )
    if not ok:
        print(f"\n[THẤT BẠI] {final_or_err}")
        sys.exit(1)
    print(f"\n[THÀNH CÔNG] Video 3D hoàn chỉnh đã lưu tại: {final_or_err}")
