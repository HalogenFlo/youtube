# Chức năng: Kiểm thử tự động kiến trúc 5 khâu hạ nguồn theo sơ đồ Research & Story Architect (mermaid-diagram.svg).
# Mục đích: Đảm bảo kịch bản sinh ra có đủ hợp đồng dữ liệu cho:
#          1. Âm thanh (AudioContract: syllables, pause_cues, voice_profile)
#          2. Hình ảnh (ImageContract: background_plate, sticker, visual_action)
#          3. Dựng & Chuyển động (RenderContract: visual_beats, camera_effects, safe_subtitles)
#          4. Thiết kế Âm thanh (SoundContract: semantic_anchors, foley_cues, bgm_ducking)
#          5. Thẩm định & Pháp lý (LegalContract: sources, claims, coverage_quotes)

import pytest
from src.story_contract_models import (
    AudioContract,
    ImageContract,
    RenderContract,
    SoundContract,
    LegalContract,
    ArchitectedScene,
    normalize_architected_scene,
    build_downstream_contracts_report,
)


def test_contract_dataclasses_structure():
    audio = AudioContract(syllables=15, pause_cues=["0.3s"], voice_profile="warm_inspirational")
    image = ImageContract(
        background_plate="ancient village",
        sticker="stickman CH01 pointing",
        visual_action="drawing symbols on stone",
        video_prompt="Ancient village, flat 2d cartoon",
    )
    render = RenderContract(
        visual_beats=["zoom_in_8pct", "cut"],
        camera_effects="subtle_slow_pan",
        safe_subtitles="bottom_1_6_safe_zone",
    )
    sound = SoundContract(
        semantic_anchors=["stone scraping sound", "gasp"],
        foley_cues=["gentle wind", "crowd murmur"],
        bgm_ducking=True,
    )
    legal = LegalContract(
        sources=["Linguistic History Brief 2026"],
        claims=["Early writing evolved from mnemonic stone symbols"],
        coverage_quotes=["Archeological consensus supports early ideograms"],
    )

    scene = ArchitectedScene(
        scene_num=1,
        narration="Trong một ngôi làng cổ xưa...",
        audio=audio,
        image=image,
        render=render,
        sound=sound,
        legal=legal,
    )

    assert scene.scene_num == 1
    assert scene.audio.syllables == 15
    assert scene.image.sticker == "stickman CH01 pointing"
    assert scene.render.camera_effects == "subtle_slow_pan"
    assert scene.sound.bgm_ducking is True
    assert len(scene.legal.claims) == 1


def test_normalize_architected_scene_from_plain_dict():
    raw_dict = {
        "scene_num": 2,
        "narration": "Cậu bé Linh tò mò khám phá các ký hiệu cổ xưa trên vách đá.",
        "video_prompt": "A boy exploring stone symbols, flat 2d cartoon, strictly no 3d",
    }
    normalized = normalize_architected_scene(raw_dict, index=2)

    assert normalized["scene_num"] == 2
    assert normalized["narration"] == raw_dict["narration"]
    assert "video_prompt" in normalized

    # Kiểm tra đủ 5 hợp đồng hạ nguồn theo mermaid-diagram.svg
    assert "audio_contract" in normalized
    assert "image_contract" in normalized
    assert "render_contract" in normalized
    assert "sound_contract" in normalized
    assert "legal_contract" in normalized

    audio_c = normalized["audio_contract"]
    assert audio_c["syllables"] > 0
    assert isinstance(audio_c["pause_cues"], list)
    assert audio_c["voice_profile"] != ""

    image_c = normalized["image_contract"]
    assert image_c["background_plate"] != ""
    assert image_c["visual_action"] != ""

    render_c = normalized["render_contract"]
    assert render_c["safe_subtitles"] == "bottom_1_6_safe_zone"
    assert isinstance(render_c["visual_beats"], list)

    sound_c = normalized["sound_contract"]
    assert isinstance(sound_c["semantic_anchors"], list)
    assert sound_c["bgm_ducking"] is True

    legal_c = normalized["legal_contract"]
    assert isinstance(legal_c["claims"], list)
    assert len(legal_c["claims"]) > 0


def test_normalize_architected_scene_from_string():
    raw_str = "Con người đã học cách ghi chép suy nghĩ qua các biểu tượng."
    normalized = normalize_architected_scene(raw_str, index=1)

    assert normalized["scene_num"] == 1
    assert normalized["narration"] == raw_str
    assert "audio_contract" in normalized
    assert "image_contract" in normalized
    assert "render_contract" in normalized
    assert "sound_contract" in normalized
    assert "legal_contract" in normalized


def test_downstream_contracts_report_generation():
    raw_scenes = [
        {"scene_num": 1, "narration": "Hook câu chuyện", "video_prompt": "Scene 1 2d"},
        {"scene_num": 2, "narration": "Diễn biến chính", "video_prompt": "Scene 2 2d"},
    ]
    scenes = [normalize_architected_scene(sc, i + 1) for i, sc in enumerate(raw_scenes)]
    report = build_downstream_contracts_report(scenes)

    assert report["total_scenes"] == 2
    assert "audio_summary" in report
    assert "image_summary" in report
    assert "render_summary" in report
    assert "sound_summary" in report
    assert "legal_summary" in report
    assert report["audio_summary"]["total_syllables"] > 0
    assert report["sound_summary"]["bgm_ducking_enabled"] is True
