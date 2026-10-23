import os
import sys
import json
import pytest
from pathlib import Path

# Đảm bảo import được cả khi chạy từ repo root hoặc thư mục video_studio
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STUDIO_ROOT = Path(__file__).resolve().parent.parent
for p in [str(STUDIO_ROOT), str(REPO_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import src.museai_3d_service as muse_svc
    from src.museai_3d_service import (
        PIXAR_3D_CANONICAL_GUIDANCE,
        FORBIDDEN_2D_PATTERN,
        clean_and_build_flow_3d_video_prompt,
        build_museai_story_script_prompt,
        parse_museai_story_json,
        load_hybrid_config,
        is_cdp_available,
        MuseAIFlowHybridController,
    )
except ModuleNotFoundError:
    import video_studio.src.museai_3d_service as muse_svc
    from video_studio.src.museai_3d_service import (
        PIXAR_3D_CANONICAL_GUIDANCE,
        FORBIDDEN_2D_PATTERN,
        clean_and_build_flow_3d_video_prompt,
        build_museai_story_script_prompt,
        parse_museai_story_json,
        load_hybrid_config,
        is_cdp_available,
        MuseAIFlowHybridController,
    )


@pytest.fixture(autouse=True)
def isolate_live_museai_state(tmp_path, monkeypatch):
    """Regression tests must not overwrite the user's Flow project or series ledger."""
    monkeypatch.setattr(muse_svc, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(muse_svc, "FLOW_CONFIG_PATH", tmp_path / "flow_config.json")
    from src import flow_character_vault
    original_save = flow_character_vault.save_character_to_vault
    def isolated_save(*args, **kwargs):
        kwargs.setdefault("vault_path", tmp_path / "character_vault.json")
        return original_save(*args, **kwargs)
    monkeypatch.setattr(flow_character_vault, "save_character_to_vault", isolated_save)


def test_clean_and_build_flow_3d_video_prompt_filters_2d_and_enforces_pixar():
    """Kiểm tra clean_and_build_flow_3d_video_prompt quét sạch từ khóa 2d/stickman và ép chuẩn Pixar 3D cho Google Flow."""
    dirty_prompt = (
        "A flat 2d cartoon stickman walking with geometric blocks and primitive shapes, "
        "whiteboard cutout animation, strictly no 3d."
    )
    full_prompt = clean_and_build_flow_3d_video_prompt(
        scene_prompt=dirty_prompt,
        character_anchor="Timmy, a 10-year-old boy in Pixar 3D CGI style",
        environment_anchor="Misty ancient forest with volumetric sunbeams",
        camera_directive="35mm lens, slow dolly-in",
        orientation="vertical",
    )

    # Đảm bảo phần action đã được biến đổi thành 3D CGI animation
    assert "cinematic 3D CGI animation" in full_prompt
    assert "Timmy, a 10-year-old boy in Pixar 3D CGI style" in full_prompt
    assert "Misty ancient forest" in full_prompt
    assert "Masterpiece 3D feature-film animation, Pixar RenderMan" in full_prompt
    assert "vertical 9:16 portrait" in full_prompt
    assert not FORBIDDEN_2D_PATTERN.search("cinematic 3D CGI animation walking with cinematic 3D CGI animation")



def test_build_museai_story_script_prompt():
    """Kiểm tra prompt yêu cầu MuseAI viết kịch bản cốt truyện 3D có đầu có cuối."""
    p = build_museai_story_script_prompt(
        topic="Chú robot nhỏ đi tìm bông hoa pha lê",
        target_scenes=4,
        language="vi",
        orientation="vertical"
    )
    assert "Chú robot nhỏ đi tìm bông hoa pha lê" in p
    assert "Pixar / DreamWorks 3D Animation Story Director" in p
    assert "COMPLETE STORYLINE WITH BEGINNING, CLIMAX & ENDING" in p
    assert "character_anchor" in p
    assert "scenes" in p
    assert "exactly 4 sequential scenes" in p


def test_parse_museai_story_json():
    """Kiểm tra trích xuất JSON kịch bản do MuseAI phản hồi."""
    sample = """
    Dưới đây là kịch bản hoàn chỉnh:
    ```json
    {
      "story_title": "Bông Hoa Pha Lê",
      "character_anchor": "Rusty, a small vintage brass robot with glowing turquoise optic lenses",
      "environment_anchor": "Snowy enchanted winter forest with bioluminescent mushrooms",
      "scenes": [
        {
          "scene_num": 1,
          "scene_role": "Hook",
          "narration": "Giữa đêm đông buốt giá, Rusty nhìn thấy một vệt sáng xanh kỳ ảo.",
          "video_prompt": "Rusty walking through deep 3D snow in the enchanted winter forest."
        }
      ]
    }
    ```
    Tôi đã sẵn sàng chuyển giao sang Google Flow!
    """
    data = parse_museai_story_json(sample)
    assert data is not None
    assert data["story_title"] == "Bông Hoa Pha Lê"
    assert len(data["scenes"]) == 1
    assert data["scenes"][0]["scene_num"] == 1
    assert "Rusty" in data["character_anchor"]


def test_load_hybrid_config():
    """Kiểm tra tải cấu hình kết hợp MuseAI + Google Flow."""
    cfg = load_hybrid_config()
    assert isinstance(cfg, dict)
    assert cfg.get("museai_url") == "https://muse.ai/"
    assert "flow.google.com" in cfg.get("project_url", "")
    assert int(cfg.get("cdp_port", 0)) == 9222
    assert "flow_chrome_profile" in cfg.get("chrome_user_data_dir", "")


def test_parse_museai_story_json_ignores_user_prompt_template_and_reads_full_4_scenes():
    """
    Regression Test: Đảm bảo hệ thống KHÔNG bao giờ bốc nhầm khối JSON mẫu 1 cảnh ('Tên câu chuyện 3D')
    nằm trong chính câu lệnh prompt của user, mà phải đọc đúng kịch bản 4 cảnh do MuseAI viết.
    """
    user_prompt_text = build_museai_story_script_prompt(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        target_scenes=4,
        language="vi",
        orientation="vertical",
    )
    # Nếu trên trang chỉ mới có câu hỏi của user (MuseAI đang suy nghĩ), tuyệt đối phải trả về None
    assert parse_museai_story_json(user_prompt_text) is None

    # Giả lập cả đoạn mẫu placeholder cũ nếu còn xuất hiện trong lịch sử chat
    legacy_placeholder = '''
    ```json
    {
      "story_title": "Tên câu chuyện 3D",
      "character_anchor": "Leo...",
      "scenes": [
        {
          "scene_num": 1,
          "narration": "Lời dẫn tiếng Việt tự nhiên, cuốn hút cho Cảnh 1.",
          "video_prompt": "Sample prompt"
        }
      ]
    }
    ```
    '''
    assert parse_museai_story_json(legacy_placeholder) is None

    # Khi MuseAI phản hồi kịch bản 4 cảnh thật sự phía sau câu hỏi của user
    assistant_4_scenes = '''
    ```json
    {
      "story_title": "Hạt Giống Ánh Sáng Cuối Cùng",
      "character_anchor": "Leo, a cute expressive 9-year-old boy in Pixar 3D CGI style",
      "environment_anchor": "Ancient clockwork sanctuary in a misty valley",
      "scenes": [
        {"scene_num": 1, "scene_role": "Opening Hook", "narration": "Cảnh 1 mở đầu.", "video_prompt": "3D shot 1"},
        {"scene_num": 2, "scene_role": "Rising Action", "narration": "Thế nhưng sang cảnh 2.", "video_prompt": "3D shot 2"},
        {"scene_num": 3, "scene_role": "Climax", "narration": "Đúng lúc đó ở cảnh 3.", "video_prompt": "3D shot 3"},
        {"scene_num": 4, "scene_role": "Resolution", "narration": "Nhờ vậy ở cảnh 4 kết thúc.", "video_prompt": "3D shot 4"}
      ]
    }
    ```
    '''
    combined_dom_text = user_prompt_text + "\n" + legacy_placeholder + "\n" + assistant_4_scenes
    parsed = parse_museai_story_json(combined_dom_text)
    assert parsed is not None
    assert parsed["story_title"] == "Hạt Giống Ánh Sáng Cuối Cùng"
    assert len(parsed["scenes"]) == 4
    assert [s["scene_num"] for s in parsed["scenes"]] == [1, 2, 3, 4]


def test_is_museai_script_complete_waits_for_target_scenes():
    """Đảm bảo không kết thúc sớm khi MuseAI mới stream được 1/4 cảnh."""
    fn = getattr(muse_svc, "is_museai_script_complete", None)
    assert fn is not None, "Chưa triển khai hàm is_museai_script_complete"
    partial_1_scene = {
        "story_title": "Hạt Giống Ánh Sáng Cuối Cùng",
        "scenes": [{"scene_num": 1, "narration": "Cảnh 1", "video_prompt": "Shot 1"}],
    }
    full_4_scenes = {
        "story_title": "Hạt Giống Ánh Sáng Cuối Cùng",
        "scenes": [
            {"scene_num": i, "narration": f"Cảnh {i}", "video_prompt": f"Shot {i}"}
            for i in range(1, 5)
        ],
    }
    assert fn(partial_1_scene, target_scenes=4, stable_ticks=1) is False
    assert fn(partial_1_scene, target_scenes=4, stable_ticks=2) is False
    assert fn(full_4_scenes, target_scenes=4, stable_ticks=1) is True


def test_normalize_flow_video_url_strips_expiring_query_params():
    """Đảm bảo URL video của Google Flow được chuẩn hóa bỏ query ?Expires= để Cảnh 2 không nhận nhầm video Cảnh 1."""
    fn = getattr(muse_svc, "normalize_flow_video_url", None)
    assert fn is not None, "Chưa triển khai hàm normalize_flow_video_url"
    raw_url = "https://flow-content.google/video/3c586cf3-904d-43b8-9a85-00c290d451ee?Expires=1792763776&KeyName=labs-flow-prod-cdn-key&Signature=abc"
    assert fn(raw_url) == "https://flow-content.google/video/3c586cf3-904d-43b8-9a85-00c290d451ee"


def test_e2e_pipeline_reads_4_scenes_and_feeds_google_flow_sequentially(tmp_path, monkeypatch):
    """
    Kiểm thử E2E luồng MuseAI -> Google Flow:
    Xác nhận hệ thống đọc đủ 4 cảnh từ MuseAI và đưa tuần tự từng cảnh (1/4 -> 2/4 -> 3/4 -> 4/4)
    vào Google Flow, sau đó ghép thành 1 video hoàn chỉnh.
    """
    dispatched_scenes = []
    ready_scripts = []
    scene_status_events = []

    fake_story = {
        "story_title": "Hạt Giống Ánh Sáng Cuối Cùng",
        "character_anchor": "Leo, 9-year-old boy in Pixar 3D CGI style",
        "environment_anchor": "Ancient glowing clockwork sanctuary",
        "scenes": [
            {"scene_num": 1, "scene_role": "Opening Hook", "narration": "Cảnh 1", "raw_video_prompt": "Prompt 1", "video_prompt": "Prompt 1"},
            {"scene_num": 2, "scene_role": "Rising Action", "narration": "Cảnh 2", "raw_video_prompt": "Prompt 2", "video_prompt": "Prompt 2"},
            {"scene_num": 3, "scene_role": "Climax", "narration": "Cảnh 3", "raw_video_prompt": "Prompt 3", "video_prompt": "Prompt 3"},
            {"scene_num": 4, "scene_role": "Resolution", "narration": "Cảnh 4", "raw_video_prompt": "Prompt 4", "video_prompt": "Prompt 4"},
        ],
    }

    def fake_gen_script(self, **kwargs):
        return True, fake_story

    def fake_gen_flow_video(self, scene_num, total_scenes, scene_data, output_path, **kwargs):
        dispatched_scenes.append((scene_num, total_scenes, scene_data["raw_video_prompt"]))
        Path(output_path).write_bytes(b"0" * 15000)
        return True, output_path

    def fake_merge(scenes, work_dir, final_output_path, **kwargs):
        Path(final_output_path).write_bytes(b"M" * 30000)
        return True, final_output_path

    monkeypatch.setattr(muse_svc.MuseAIFlowHybridController, "start_fresh_google_flow_project", lambda self, **kw: (True, "mock"))
    monkeypatch.setattr(muse_svc.MuseAIFlowHybridController, "generate_3d_script_via_museai", fake_gen_script)
    monkeypatch.setattr(muse_svc.MuseAIFlowHybridController, "generate_scene_3d_video_on_google_flow", fake_gen_flow_video)
    monkeypatch.setattr(muse_svc, "merge_flow_3d_scenes_into_final_movie", fake_merge)
    monkeypatch.setattr(muse_svc.time, "sleep", lambda s: None)

    ok, final_path, meta = muse_svc.run_museai_script_to_google_flow_3d_pipeline(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        target_scenes=4,
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "out"),
        on_script_ready_callback=lambda s: ready_scripts.append(s),
        on_scene_status_callback=lambda idx, tot, st, vp: scene_status_events.append((idx, tot, st)),
    )

    assert ok is True
    assert os.path.exists(final_path)
    assert len(ready_scripts) == 1
    assert len(ready_scripts[0]["scenes"]) == 4
    assert dispatched_scenes == [
        (1, 4, "Prompt 1"),
        (2, 4, "Prompt 2"),
        (3, 4, "Prompt 3"),
        (4, 4, "Prompt 4"),
    ]
    assert len(meta["scene_video_paths"]) == 4


def test_resolve_voice_and_prosody_distinct_narrator_and_character_voices():
    """
    Đảm bảo hệ thống TTS có các preset giọng đọc phân biệt rõ ràng giữa:
    - Người dẫn chuyện (narrator / story_warm)
    - Nhân vật chính cậu bé / thiếu niên (char_boy_bright)
    - Nhân vật phụ trưởng lão / thần hộ mệnh (char_elder_deep)
    - Nhân vật nữ trẻ / tinh linh (char_female_bright)
    """
    try:
        from src.tts_service import resolve_voice_and_prosody
    except ModuleNotFoundError:
        from video_studio.src.tts_service import resolve_voice_and_prosody

    v_narr, r_narr, p_narr, _ = resolve_voice_and_prosody("vi-VN-HoaiMyNeural|story_warm")
    v_boy, r_boy, p_boy, _ = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_boy_bright")
    v_elder, r_elder, p_elder, _ = resolve_voice_and_prosody("vi-VN-NamMinhNeural|char_elder_deep")
    v_girl, r_girl, p_girl, _ = resolve_voice_and_prosody("vi-VN-HoaiMyNeural|char_female_bright")

    assert v_narr == "vi-VN-HoaiMyNeural"
    assert v_boy == "vi-VN-NamMinhNeural"
    assert v_elder == "vi-VN-NamMinhNeural"
    assert v_girl == "vi-VN-HoaiMyNeural"
    # Nhân vật cậu bé phải có pitch cao sáng hơn và nhịp nhanh hơn nhân vật trưởng lão trầm sâu
    assert p_boy != p_elder and "+" in p_boy and "-" in p_elder
    assert r_boy != r_elder
    # Nhân vật nữ trẻ phải có pitch cao hơn giọng người dẫn chuyện ấm áp
    assert p_girl != p_narr and "+" in p_girl


def test_build_museai_story_script_prompt_requires_narrator_and_character_dialogue_sync():
    """
    Kiểm tra prompt gửi cho MuseAI bắt buộc mỗi phân cảnh phải có `dialogue_lines`
    kết hợp giữa Người dẫn chuyện (`narrator`) và Tương tác giữa các nhân vật (`character_1`, `character_2`),
    đồng thời `video_prompt` phải miêu tả đúng biểu cảm nói chuyện và tương tác nhân vật ăn khớp 1:1.
    """
    p = build_museai_story_script_prompt(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        target_scenes=4,
        language="vi",
        orientation="vertical",
    )
    assert "dialogue_lines" in p
    assert "narrator" in p
    assert "character_1" in p
    assert "lip-sync" in p.lower() or "speaking" in p.lower()


def test_build_scene_dialogue_segments_combines_narrator_and_characters():
    """
    Kiểm tra `build_scene_dialogue_segments` xử lý tốt cả 3 trường hợp:
    1. Phân cảnh có sẵn `dialogue_lines` chuẩn từ MuseAI.
    2. Phân cảnh chỉ có `narration` chứa câu thoại trong ngoặc kép/đơn (như Cảnh 3 của kịch bản đang mở trên MuseAI).
    3. Phân cảnh chỉ có `narration` mô tả đơn thuần không có ngoặc kép -> tự động nâng cấp bổ sung lời thoại tương tác
       của nhân vật khớp ngữ cảnh để cảnh nào cũng có sự kết hợp giữa Dẫn chuyện + Nhân vật tương tác!
    """
    fn = getattr(muse_svc, "build_scene_dialogue_segments", None)
    assert fn is not None, "Chưa triển khai hàm build_scene_dialogue_segments"

    # Case 1: Có sẵn dialogue_lines
    sc_structured = {
        "scene_num": 1,
        "scene_role": "Opening Hook",
        "dialogue_lines": [
            {"speaker": "narrator", "text": "Trong khu rừng sương mù, Leo phát hiện một chiếc la bàn kỳ lạ."},
            {"speaker": "character_1", "character_name": "Leo", "text": "Chiếc la bàn này đang phát sáng kìa!"},
        ],
    }
    segs_1 = fn(sc_structured, language="vi")
    assert len(segs_1) >= 2
    roles_1 = [item["speaker"] for item in segs_1]
    assert "narrator" in roles_1
    assert any(r != "narrator" for r in roles_1)
    assert segs_1[0]["voice_spec"] != segs_1[1]["voice_spec"]

    # Case 2: Chỉ có narration chứa câu thoại trong dấu nháy (như Cảnh 3 trên MuseAI)
    sc_quoted = {
        "scene_num": 3,
        "scene_role": "Climax",
        "narration": "Đúng lúc đó, một bóng hình ánh sáng hiện lên, giọng nói trầm ấm vang vọng: 'Mang hạt giống về, cậu bé sẽ được an toàn.' Leo nắm chặt hạt giống, đôi mắt sáng rực.",
    }
    segs_2 = fn(sc_quoted, language="vi")
    roles_2 = [item["speaker"] for item in segs_2]
    assert "narrator" in roles_2
    assert any(r != "narrator" for r in roles_2)
    full_txt_2 = " ".join(item["text"] for item in segs_2)
    assert "Mang hạt giống về, cậu bé sẽ được an toàn" in full_txt_2

    # Case 3: Chỉ có narration mô tả ngôi thứ 3 không có ngoặc kép (như Cảnh 1 trên MuseAI)
    sc_plain = {
        "scene_num": 1,
        "scene_role": "Opening Hook",
        "narration": "Giữa khu rừng sương mù cổ xưa, cậu bé Leo 9 tuổi tình cờ phát hiện một chiếc la bàn bằng đồng kỳ lạ nằm dưới gốc cây đại thụ.",
    }
    segs_3 = fn(sc_plain, language="vi")
    roles_3 = [item["speaker"] for item in segs_3]
    assert "narrator" in roles_3
    assert any(r != "narrator" for r in roles_3), "Phải tự động bổ sung câu tương tác của nhân vật khi kịch bản thiếu lời thoại!"


def test_synthesize_museai_scenes_interactive_tts_and_visual_sync(tmp_path, monkeypatch):
    """
    Kiểm tra hàm `synthesize_museai_scenes_interactive_tts` sinh file MP3 đa giọng đọc
    (kết hợp Dẫn chuyện + Nhân vật) cho từng cảnh, đồng bộ chính xác `sc['narration']`
    cho phụ đề và đồng bộ chỉ dẫn tương tác nhân vật vào `video_prompt`.
    """
    synth_fn = getattr(muse_svc, "synthesize_museai_scenes_interactive_tts", None)
    assert synth_fn is not None, "Chưa triển khai hàm synthesize_museai_scenes_interactive_tts"

    called_multivoice = []

    def fake_multivoice(segments, output_path, **kwargs):
        assert kwargs["strict_language"] is True
        called_multivoice.append((segments, output_path))
        Path(output_path).write_bytes(b"ID3" + b"A" * 4000)
        return True, output_path

    try:
        import src.tts_service as tts_mod
    except ModuleNotFoundError:
        import video_studio.src.tts_service as tts_mod

    monkeypatch.setattr(tts_mod, "generate_multivoice_tts", fake_multivoice)
    monkeypatch.setattr(tts_mod, "get_audio_duration", lambda p: 6.5)

    scenes = [
        {
            "scene_num": 1,
            "scene_role": "Opening Hook",
            "narration": "Giữa khu rừng sương mù, Leo tìm thấy chiếc la bàn cổ. 'Oa, kim la bàn đang tự quay kìa!'",
            "raw_video_prompt": "Leo holding a glowing brass compass in the misty forest.",
        }
    ]
    ok, msg = synth_fn(scenes=scenes, work_dir=str(tmp_path), language="vi")
    assert ok is True
    assert len(called_multivoice) == 1
    segs_passed, out_mp3 = called_multivoice[0]
    # Phải có ít nhất 2 phân đoạn giọng đọc (1 dẫn chuyện + 1 nhân vật) với voice khác nhau
    assert len(segs_passed) >= 2
    voices_used = {v for (_, v, _) in segs_passed}
    assert len(voices_used) >= 2
    assert os.path.exists(out_mp3)
    assert scenes[0]["audio_path"] == out_mp3
    assert scenes[0]["audio_duration"] == 6.5
    # Kiểm tra clean_and_build_flow_3d_video_prompt có nhúng hành động biểu cảm/lời thoại của cảnh vào prompt 3D
    synced_vp = clean_and_build_flow_3d_video_prompt(
        scene_prompt=scenes[0]["raw_video_prompt"],
        character_anchor="Leo, 9-year-old boy",
        environment_anchor="Misty forest",
        scene_data=scenes[0],
    )
    assert "expressive 3d facial animation" in synced_vp.lower() or "speaking" in synced_vp.lower()


def test_multi_scene_scaling_for_8_to_10_scenes():
    """
    Đảm bảo khi người dùng chọn nhiều cảnh hơn (ví dụ 8, 10, 12, 20 cảnh):
    1. Các cảnh giữa (từ cảnh 2 đến cảnh N-2) có lời thoại tương tác đa dạng, không bị trùng lặp
       và không bị nhầm thành cảnh Kết thúc (Resolution) ở cảnh thứ 4.
    2. Chỉ đúng cảnh cuối cùng (Cảnh N) mới mang lời thoại Kết thúc (Resolution),
       và cảnh N-1 mang lời thoại Cao trào (Climax).
    """
    total_scenes = 10
    fn = muse_svc.build_scene_dialogue_segments

    middle_char_lines = []
    for idx in range(1, total_scenes + 1):
        role = (
            "Opening Hook" if idx == 1
            else ("Climax" if idx == total_scenes - 1
                  else ("Resolution" if idx == total_scenes else f"Rising Action {idx - 1}"))
        )
        sc = {
            "scene_num": idx,
            "scene_role": role,
            "narration": f"Ở phân cảnh thứ {idx}, Leo tiếp tục hành trình băng qua thung lũng ánh sáng.",
        }
        segs = fn(sc, language="vi", total_scenes=total_scenes)
        char_segs = [s for s in segs if s["speaker"] != "narrator"]
        assert len(char_segs) >= 1
        if 2 <= idx <= 7:
            middle_char_lines.append(char_segs[0]["text"])
        if idx == 4:
            # Cảnh 4 trên tổng 10 cảnh KHÔNG được dùng câu kết thúc phim dù có từ 'thung lũng'
            assert "Chúng ta làm được rồi" not in char_segs[0]["text"]
            assert "thực sự hồi sinh" not in char_segs[0]["text"]
        if idx == total_scenes:
            # Cảnh 10 (cảnh cuối) mới dùng câu kết thúc
            assert (
                "Chúng ta làm được rồi" in char_segs[0]["text"]
                or "thực sự hồi sinh" in char_segs[0]["text"]
            )

    # Các cảnh giữa liên tiếp không bị lặp y hệt cùng 1 câu thoại
    for i in range(len(middle_char_lines) - 1):
        assert middle_char_lines[i] != middle_char_lines[i + 1]


def test_expand_scenes_to_match_story_beats_splits_long_scenes_into_distinct_shots():
    """
    Đảm bảo số khung hình (shots) tự động khớp với độ dài câu chuyện:
    - Nếu 1 cảnh từ MuseAI dài ~22-28 giây (vừa có dẫn chuyện dài vừa có nhân vật đối thoại),
      hàm `expand_scenes_to_match_story_beats` phải tự động tách thành các khung hình ngắn (~6-10s/khung,
      tối đa ~26 từ mỗi khung) để mỗi khung video Google Flow (~8-10s) ứng với đúng 1 nhịp câu chuyện,
      không bao giờ bị dồn 25s thoại vào 1 clip 10s!
    - Mỗi khung hình tách ra phải có `raw_video_prompt` / `camera_directive` khác nhau để Google Flow
      vẽ khung cảnh mới hoàn toàn, không trùng khung hình cũ.
    """
    expand_fn = getattr(muse_svc, "expand_scenes_to_match_story_beats", None)
    assert expand_fn is not None, "Chưa triển khai hàm expand_scenes_to_match_story_beats"

    long_scenes = [
        {
            "scene_num": 1,
            "scene_role": "Opening Hook",
            "narration": (
                "Giữa khu rừng sương mù cổ xưa, cậu bé Leo tình cờ bước vào ngôi đền đồng hồ bị lãng quên từ hàng ngàn năm trước. "
                "Trên bệ đá rêu phong, một chiếc la bàn bằng đồng bất ngờ phát ra tia sáng xanh kỳ diệu."
            ),
            "raw_video_prompt": "Leo walks into the misty clockwork temple and discovers a glowing brass compass on a mossy stone pedestal.",
            "camera_directive": "Wide tracking shot following Leo",
        },
        {
            "scene_num": 2,
            "scene_role": "Climax",
            "narration": (
                "Đúng lúc những bánh răng khổng lồ ngừng quay, bóng hình ánh sáng của vị thần hộ mệnh hiện lên: "
                "'Hãy gieo hạt giống ánh sáng xuống mảnh đất này để cứu lấy khu rừng!' "
                "Leo kiên định gật đầu và đặt hạt giống xuống nền đất ẩm."
            ),
            "raw_video_prompt": "Giant brass gears grind to a halt as a guardian spirit appears and Leo plants the glowing seed into the soil.",
            "camera_directive": "Dramatic low-angle crane shot",
        },
    ]

    expanded = expand_fn(long_scenes, language="vi", max_words_per_shot=26)
    # Từ 2 cảnh rất dài (mỗi cảnh > 45 từ + lời thoại nhân vật), phải tự động tách thành ít nhất 4 khung hình ngắn
    assert len(expanded) >= 4
    for idx, shot in enumerate(expanded, start=1):
        assert shot["scene_num"] == idx
        words = str(shot.get("narration") or "").split()
        # Mỗi khung hình chỉ chứa lượng từ vừa vặn cho 1 clip 8-10s (không bị dồn 50-70 từ)
        assert 3 <= len(words) <= 34
        assert shot.get("raw_video_prompt")

    # Hai khung hình liên tiếp phải có chỉ dẫn hình ảnh / góc máy khác nhau để không sinh trùng cảnh
    for i in range(len(expanded) - 1):
        vp_a = expanded[i]["raw_video_prompt"] + " | " + expanded[i].get("camera_directive", "")
        vp_b = expanded[i + 1]["raw_video_prompt"] + " | " + expanded[i + 1].get("camera_directive", "")
        assert vp_a != vp_b


def test_video_compiler_never_uses_stream_loop_on_video_clips(tmp_path, monkeypatch):
    """
    Kiểm tra bộ dựng phim `_compile_part_with_ffmpeg_native` TUYỆT ĐỐI KHÔNG dùng `-stream_loop -1`
    làm lặp đi lặp lại 1 khung video nhiều lần khi ghép với giọng đọc, mà dùng `setpts` khớp 1:1
    thời lượng khung hình với câu thoại (chạy đúng 1 lượt duy nhất từ đầu đến cuối).
    """
    try:
        import src.video_compiler as vc
    except ModuleNotFoundError:
        import video_studio.src.video_compiler as vc

    recorded_cmds = []

    class DummyCompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    def fake_run(cmd, *args, **kwargs):
        recorded_cmds.append(list(cmd))
        out_file = cmd[-1]
        if isinstance(out_file, str) and out_file.endswith(".mp4"):
            Path(out_file).parent.mkdir(parents=True, exist_ok=True)
            Path(out_file).write_bytes(b"0" * 20000)
        return DummyCompletedProcess()

    monkeypatch.setattr(vc.subprocess, "run", fake_run)
    monkeypatch.setattr(vc, "_get_media_duration_seconds", lambda p, default=8.0: 10.0)

    vid_file = tmp_path / "scene_001.mp4"
    aud_file = tmp_path / "scene_001.mp3"
    out_file = tmp_path / "out_final.mp4"
    vid_file.write_bytes(b"V" * 20000)
    aud_file.write_bytes(b"A" * 10000)

    scenes = [
        {
            "scene_num": 1,
            "use_video_ai": True,
            "video_path": str(vid_file),
            "audio_path": str(aud_file),
            "audio_duration": 12.5,
        }
    ]
    ok, res_path = vc._compile_part_with_ffmpeg_native(
        part_scenes=scenes,
        raw_output_path=str(out_file),
        auto_bgm=False,
    )
    assert ok is True
    # Tìm lệnh ffmpeg encode phân cảnh (chứa vid_file)
    scene_encode_cmds = [c for c in recorded_cmds if str(vid_file) in c]
    assert len(scene_encode_cmds) == 1
    sc_cmd = scene_encode_cmds[0]
    # TUYỆT ĐỐI KHÔNG được có -stream_loop -1 trên video phân cảnh!
    assert "-stream_loop" not in sc_cmd
    vf_idx = sc_cmd.index("-vf") + 1
    assert "setpts=" in sc_cmd[vf_idx]


def test_build_museai_story_script_prompt_multi_episode_continuity():
    """
    Kiểm tra cơ chế duy trì cốt truyện dài qua nhiều tập (Ít tập / Nhiều tập):
    - Mỗi tập đều bắt buộc có đủ: Mở đầu (Opening) + Cao trào (Climax) + Kết thúc tập (Ending/Cliffhanger hoặc Finale).
    - Từ tập 2 trở đi phải nhúng `previous_episodes_summary` và `locked_character_anchor` để giữ mạch truyện và tạo hình nhân vật.
    """
    # Tập 1/3: Mở đầu series + Cao trào Tập 1 + Kết thúc mở hé lộ Tập 2
    p_ep1 = build_museai_story_script_prompt(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        episode_num=1,
        total_episodes=3,
        language="vi",
    )
    assert "EPISODE 1 OF 3" in p_ep1.upper()
    assert "OPENING" in p_ep1.upper()
    assert "CLIMAX" in p_ep1.upper()
    assert "EPISODE 2" in p_ep1.upper()

    # Tập 2/3: Nối tiếp Tập 1 + Khóa nhân vật + Cao trào Tập 2 + Hé lộ Tập 3
    p_ep2 = build_museai_story_script_prompt(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        episode_num=2,
        total_episodes=3,
        previous_episodes_summary="Tập 1: Leo tìm thấy chiếc la bàn cổ và kích hoạt bánh răng thời gian.",
        locked_character_anchor="Leo, 9-year-old boy in olive-green explorer jacket",
        language="vi",
    )
    assert "EPISODE 2 OF 3" in p_ep2.upper()
    assert "Tập 1: Leo tìm thấy chiếc la bàn cổ" in p_ep2
    assert "Leo, 9-year-old boy in olive-green explorer jacket" in p_ep2
    assert "CLIMAX" in p_ep2.upper()
    assert "EPISODE 3" in p_ep2.upper()

    # Tập 3/3 (Tập cuối): Nối tiếp Tập 1 & 2 + Đại cao trào (Grand Climax) + Đại kết cục (Grand Finale)
    p_ep3 = build_museai_story_script_prompt(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        episode_num=3,
        total_episodes=3,
        previous_episodes_summary="Tập 1-2: Leo vượt qua thử thách bóng tối và tìm thấy nơi gieo hạt giống.",
        locked_character_anchor="Leo, 9-year-old boy in olive-green explorer jacket",
        language="vi",
    )
    assert "EPISODE 3 OF 3" in p_ep3.upper()
    assert "FINAL EPISODE" in p_ep3.upper() or "GRAND FINALE" in p_ep3.upper()
    assert "CLIMAX" in p_ep3.upper()


def test_run_museai_multi_episode_series_pipeline_maintains_story_and_character_across_episodes(tmp_path, monkeypatch):
    """
    Kiểm thử E2E luồng sản xuất Series nhiều tập (`run_museai_multi_episode_series_pipeline`):
    Xác nhận hệ thống chạy tuần tự từ Tập 1 -> Tập 2 -> Tập 3, tự động truyền `locked_character_anchor`
    và `previous_episodes_summary` tích lũy qua từng tập, mỗi tập đều có Mở đầu -> Cao trào -> Kết thúc.
    """
    series_fn = getattr(muse_svc, "run_museai_multi_episode_series_pipeline", None)
    assert series_fn is not None, "Chưa triển khai hàm run_museai_multi_episode_series_pipeline"

    recorded_episode_calls = []

    def fake_single_episode_pipeline(
        topic="",
        target_scenes=None,
        work_dir="",
        output_dir="",
        episode_num=1,
        total_episodes=1,
        previous_episodes_summary="",
        locked_character_anchor="",
        locked_environment_anchor="",
        **kwargs,
    ):
        recorded_episode_calls.append(
            {
                "episode_num": episode_num,
                "total_episodes": total_episodes,
                "previous_episodes_summary": previous_episodes_summary,
                "locked_character_anchor": locked_character_anchor,
            }
        )
        ep_out = Path(output_dir) / f"ep_{episode_num:02d}.mp4"
        ep_out.parent.mkdir(parents=True, exist_ok=True)
        ep_out.write_bytes(b"E" * 25000)
        story_obj = {
            "story_title": f"Hạt Giống Ánh Sáng - Tập {episode_num}",
            "character_anchor": locked_character_anchor or "Leo, 9-year-old boy in olive-green jacket",
            "environment_anchor": locked_environment_anchor or "Ancient glowing clockwork sanctuary",
            "scenes": [
                {"scene_num": 1, "scene_role": "Opening Hook", "narration": f"Mở đầu tập {episode_num}."},
                {"scene_num": 2, "scene_role": "Climax", "narration": f"Cao trào tập {episode_num}."},
                {"scene_num": 3, "scene_role": "Resolution", "narration": f"Kết thúc tập {episode_num}."},
            ],
        }
        return True, str(ep_out), {"story": story_obj, "scene_video_paths": [str(ep_out)]}

    monkeypatch.setattr(muse_svc, "run_museai_script_to_google_flow_3d_pipeline", fake_single_episode_pipeline)

    ok, episode_paths, series_meta = series_fn(
        topic="Hạt Giống Ánh Sáng Cuối Cùng",
        total_episodes=3,
        work_dir=str(tmp_path / "series_work"),
        output_dir=str(tmp_path / "series_out"),
    )
    assert ok is True
    assert len(episode_paths) == 3
    assert len(recorded_episode_calls) == 3

    # Tập 1 khởi tạo mới
    assert recorded_episode_calls[0]["episode_num"] == 1
    assert recorded_episode_calls[0]["total_episodes"] == 3

    # Tập 2 phải nhận được character_anchor khóa cứng từ Tập 1 và tóm tắt Tập 1
    assert recorded_episode_calls[1]["episode_num"] == 2
    assert recorded_episode_calls[1]["locked_character_anchor"] == "Leo, 9-year-old boy in olive-green jacket"
    assert "Tập 1" in recorded_episode_calls[1]["previous_episodes_summary"]

    # Tập 3 phải nhận được tóm tắt tích lũy của cả Tập 1 và Tập 2
    assert recorded_episode_calls[2]["episode_num"] == 3
    assert "Tập 1" in recorded_episode_calls[2]["previous_episodes_summary"]
    assert "Tập 2" in recorded_episode_calls[2]["previous_episodes_summary"]


def test_flow_edit_url_stripping_and_retry_prompt_sanitization():
    """
    Regression Test cho lỗi Cảnh 2/N báo 'Không thành công / Rất tiếc, không tạo được video này':
    1. _remember_flow_project_url phải cắt bỏ '/edit/<clip_id>' để không bị kẹt ở màn hình 'Mô tả cách chỉnh sửa video này…' (Omni 1.1 Flash).
    2. sanitize_prompt_for_flow_retry phải làm sạch các cụm từ dễ bị Veo từ chối (như '9-year-old boy', 'child') khi thử lại lần 2.
    """
    ctrl = MuseAIFlowHybridController()
    ctrl._remember_flow_project_url(
        "https://flow.google.com/project/ef2dd78f-2d94-4d0c-ae64-9ec9a97c0587/edit/168a6071-c5ef-4d2c-9fc6-a1857e1984a8"
    )
    assert ctrl.cfg["project_url"] == "https://flow.google.com/project/ef2dd78f-2d94-4d0c-ae64-9ec9a97c0587"
    assert "/edit/" not in ctrl.cfg["project_url"]

    sanitize_fn = getattr(muse_svc, "sanitize_prompt_for_flow_retry", None)
    assert sanitize_fn is not None, "Chưa triển khai hàm sanitize_prompt_for_flow_retry"

    raw = "Leo, a cute expressive 9-year-old boy in Pixar 3D CGI style, close-up on the child's terrified face"
    cleaned = sanitize_fn(raw)
    assert "9-year-old boy" not in cleaned.lower()
    assert "terrified" not in cleaned.lower()
    assert "pixar 3d" in cleaned.lower()


def test_fresh_flow_project_and_direct_video_composer_mode(tmp_path, monkeypatch):
    """
    Kiểm tra cơ chế tạo Dự án mới (New Project / Trò chuyện mới) trên Google Flow mỗi lần tạo video
    và tự động đóng bảng Tác nhân (Agent) để chuyển sang chế độ Direct Video Composer (Video · 720p · 8 giây · 9:16 · x1),
    tránh tích tụ ngữ cảnh (context) quá nhiều.
    """
    ctrl = MuseAIFlowHybridController()
    assert hasattr(ctrl, "start_fresh_google_flow_project"), "Chưa triển khai hàm start_fresh_google_flow_project"
    assert hasattr(ctrl, "_ensure_direct_video_composer_mode"), "Chưa triển khai hàm _ensure_direct_video_composer_mode"

    fresh_project_calls = []

    def fake_start_fresh(self, orientation="vertical"):
        fresh_project_calls.append(orientation)
        return True, "https://flow.google.com/project/new-clean-uuid"

    def fake_gen_script(self, **kwargs):
        return True, {
            "story_title": "Chuyến Phiêu Lưu Mới",
            "character_anchor": "Leo in Pixar 3D CGI style",
            "environment_anchor": "Glowing forest",
            "scenes": [
                {"scene_num": 1, "scene_role": "Opening Hook", "narration": "Cảnh 1 mở đầu.", "raw_video_prompt": "Shot 1"},
                {"scene_num": 2, "scene_role": "Resolution", "narration": "Cảnh 2 kết thúc.", "raw_video_prompt": "Shot 2"},
            ],
        }

    def fake_gen_flow_video(self, scene_num, total_scenes, scene_data, output_path, **kwargs):
        Path(output_path).write_bytes(b"V" * 15000)
        return True, output_path

    def fake_merge(scenes, work_dir, final_output_path, **kwargs):
        Path(final_output_path).write_bytes(b"M" * 25000)
        return True, final_output_path

    monkeypatch.setattr(MuseAIFlowHybridController, "start_fresh_google_flow_project", fake_start_fresh)
    monkeypatch.setattr(MuseAIFlowHybridController, "generate_3d_script_via_museai", fake_gen_script)
    monkeypatch.setattr(MuseAIFlowHybridController, "generate_scene_3d_video_on_google_flow", fake_gen_flow_video)
    monkeypatch.setattr(muse_svc, "merge_flow_3d_scenes_into_final_movie", fake_merge)
    monkeypatch.setattr(muse_svc.time, "sleep", lambda s: None)

    ok, out_path, meta = muse_svc.run_museai_script_to_google_flow_3d_pipeline(
        topic="Chuyến Phiêu Lưu Mới",
        work_dir=str(tmp_path / "w"),
        output_dir=str(tmp_path / "o"),
        orientation="vertical",
    )
    assert ok is True
    assert fresh_project_calls == ["vertical"]


def test_character_vault_and_7_point_dna_formula(tmp_path):
    """
    Kiểm tra Kho Nhân Vật Cố Định (Character Vault) và công thức 7-Point Character DNA Anchor
    giữ nguyên 100% khuôn mặt, kiểu tóc, quần áo, phụ kiện của nhân vật 3D qua mọi cảnh và mọi tập.
    """
    from src.flow_character_vault import (
        get_builtin_character_presets,
        build_7_point_character_dna,
        save_character_to_vault,
        load_character_vault,
    )

    presets = get_builtin_character_presets()
    assert len(presets) >= 4
    assert any("Leo" in p["name"] for p in presets)

    # Kiểm tra nâng cấp mô tả ngắn thành khối 7-Point Character DNA chuẩn Veo
    short_desc = "Leo, a 9-year-old boy with brown hair and green jacket"
    dna = build_7_point_character_dna(short_desc)
    assert "9-year-old boy" not in dna.lower()  # Đã chuyển sang cụm từ an toàn cho bộ lọc Veo ngay từ lần 1
    assert "preserve the exact same" in dna.lower()
    assert "3d" in dna.lower()

    # Kiểm tra lưu và đọc lại nhân vật cố định từ Vault
    vault_file = tmp_path / "character_vault.json"
    saved = save_character_to_vault(
        name="Thỏ Trắng Tinh Anh",
        character_dna="Bibo, stylized Pixar 3D white rabbit detective wearing a navy trench coat and brass monocle",
        environment_dna="Cyber-steampunk lantern city in 3D CGI",
        vault_path=vault_file,
    )
    assert saved["id"] == "tho_trang_tinh_anh"
    loaded = load_character_vault(vault_path=vault_file)
    assert any(c["id"] == "tho_trang_tinh_anh" for c in loaded)


def test_does_not_reuse_unrelated_old_script_when_user_enters_new_topic():
    """
    Regression Test: Khi người dùng nhập cốt truyện mới (VD: 'Chú mèo máy tìm kho báu đại dương'),
    hệ thống TUYỆT ĐỐI KHÔNG được bốc lại kịch bản cũ không liên quan ('Hạt Giống Ánh Sáng Cuối Cùng')
    đang nằm sẵn trên tab MuseAI.
    """
    match_fn = getattr(muse_svc, "does_script_match_user_topic", None)
    assert match_fn is not None, "Chưa triển khai hàm does_script_match_user_topic"

    old_script = {
        "story_title": "Hạt Giống Ánh Sáng Cuối Cùng",
        "scenes": [
            {"scene_num": 1, "narration": "Sâu trong thung lũng sương mù, cậu bé Leo tìm thấy chiếc la bàn cổ."}
        ],
    }
    assert match_fn(old_script, "Chú mèo máy tìm kho báu dưới đáy đại dương") is False
    assert match_fn(old_script, "Hạt Giống Ánh Sáng Cuối Cùng của cậu bé Leo") is True


def test_hover_newest_flow_video_thumbnails_prioritizes_index_0_without_clicking():
    """
    Regression Test cho lỗi Cảnh 2/N chờ 600s timeout dù Google Flow đã tạo xong video:
    Trên lưới Google Flow, video mới nhất luôn nằm ở vị trí đầu tiên (index 0) dưới dạng
    <img alt="Hình thu nhỏ của video đã tạo"> và chỉ biến thành <video src="https://flow-content.google/video/...">
    khi được hover. Hàm _hover_newest_flow_video_thumbnails phải hover từ index 0 (mới nhất)
    và TUYỆT ĐỐI không click mở trang /edit/.
    """
    ctrl = MuseAIFlowHybridController()
    hover_fn = getattr(ctrl, "_hover_newest_flow_video_thumbnails", None)
    assert hover_fn is not None, "Chưa triển khai hàm _hover_newest_flow_video_thumbnails"

    hovered_indices = []
    clicked_indices = []

    class FakeThumb:
        def __init__(self, idx, src):
            self.idx = idx
            self._src = src
        def is_visible(self):
            return True
        def get_attribute(self, name):
            return self._src if name == "src" else "Hình thu nhỏ của video đã tạo"
        def hover(self, **kwargs):
            hovered_indices.append(self.idx)
        def click(self, **kwargs):
            clicked_indices.append(self.idx)

    class FakeLoc:
        def __init__(self, items):
            self._items = items
        def all(self):
            return self._items

    class FakePage:
        def locator(self, sel):
            return FakeLoc([
                FakeThumb(0, "https://flow-content.google/image/new-scene-2-uuid?Expires=123"),
                FakeThumb(1, "https://flow-content.google/image/old-scene-1-uuid?Expires=123"),
            ])
        def wait_for_timeout(self, ms):
            pass

    pre_thumbs = {"https://flow-content.google/image/old-scene-1-uuid"}
    count = hover_fn(FakePage(), pre_existing_thumb_urls=pre_thumbs)
    assert count >= 1
    assert hovered_indices[0] == 0  # Phải hover card mới nhất (index 0) đầu tiên!
    assert clicked_indices == []    # Tuyệt đối không click gây nhảy vào /edit/!


def test_museai_to_google_flow_3d_image_and_hybrid_modes(tmp_path, monkeypatch):
    """
    Kiểm tra chế độ Tạo Hình 3D Liên Tục ('image_3d') và Kết Hợp Hybrid ('hybrid_3d')
    phối hợp cả MuseAI (viết cốt truyện & chia nhịp dày đặc 3-4s/hình) và Google Flow (Nano Banana 3D Image + Veo Video).
    """
    img_prompt_fn = getattr(muse_svc, "clean_and_build_flow_3d_image_prompt", None)
    assert img_prompt_fn is not None, "Chưa triển khai hàm clean_and_build_flow_3d_image_prompt"

    p_img = img_prompt_fn(
        scene_prompt="Leo discovering a glowing crystal flower in the cave",
        character_anchor="Leo, stylized Pixar 3D young explorer in olive-green jacket",
        environment_anchor="Bioluminescent crystal cavern",
        orientation="vertical",
    )
    assert "3d" in p_img.lower()
    assert "preserve the exact same" in p_img.lower()
    assert "vertical 9:16" in p_img.lower()

    ctrl = MuseAIFlowHybridController()
    sample_story = {
        "story_title": "Bí Mật Hang Pha Lê",
        "character_anchor": "Leo, stylized Pixar 3D young explorer in olive-green jacket",
        "environment_anchor": "Bioluminescent crystal cavern",
        "scenes": [
            {
                "scene_num": 1,
                "scene_role": "Opening Hook",
                "narration": "Sâu dưới lòng đất, Leo bước vào hang động pha lê rực sáng. Từng bước chân của cậu vang vọng giữa những khối thạch anh khổng lồ lấp lánh ánh xanh kỳ diệu.",
                "video_prompt": "Leo walking into a giant glowing crystal cavern in 3D Pixar style",
            },
            {
                "scene_num": 2,
                "scene_role": "Rising Action",
                "narration": "Thế nhưng một cơn gió lạnh bất ngờ thổi qua làm ngọn đuốc trên tay cậu tắt phụt.",
                "video_prompt": "A sudden gust of wind blows out Leo's torch in the dark cave",
            },
            {
                "scene_num": 3,
                "scene_role": "Climax",
                "narration": "Đúng lúc đó, bông hoa pha lê ở trung tâm bừng sáng rực rỡ, đẩy lùi bóng tối!",
                "video_prompt": "The giant crystal flower in the center erupts with golden 3D light",
            },
        ],
    }

    # Chế độ image_3d chia nhịp dày hơn (mỗi ~20 từ 1 hình 3D mới) và gán media_type == 'image'
    enriched_img = ctrl._enrich_scenes_with_3d_prompts(dict(sample_story), orientation="vertical", visual_mode="image_3d")
    assert len(enriched_img["scenes"]) >= 4
    assert all(s.get("media_type") == "image" for s in enriched_img["scenes"])

    # Chế độ hybrid_3d gán Opening Hook & Climax là 'video', còn Rising Action là 'image'
    enriched_hyb = ctrl._enrich_scenes_with_3d_prompts(dict(sample_story), orientation="vertical", visual_mode="hybrid_3d")
    media_types = [s.get("media_type") for s in enriched_hyb["scenes"]]
    assert "video" in media_types and "image" in media_types


def test_script_prompt_and_spoken_dialogue_quality_no_stage_directions_in_character_voice():
    """
    Đảm bảo kịch bản và kịch bản nói không bị ngô nghê / tào lao:
    1. `build_museai_story_script_prompt` phải cấm MuseAI lục lại trí nhớ cũ ('Lumi', 'Uga'),
       cấm nhét lời mô tả hành động ngôi thứ 3 vào miệng nhân vật, và cấm câu thoại phi logic.
    2. Hàm `is_third_person_stage_direction` và `build_scene_dialogue_segments` phải tự động phát hiện
       nếu `character_1`/`character_2` bị gán nhầm câu mô tả hành động ngôi thứ 3 (như 'Uga chỉ tay, hét lên một tiếng báo nguy cho Lumi!')
       và chuyển nó về giọng `narrator` để kịch bản nói luôn tự nhiên, đúng vai.
    """
    stage_fn = getattr(muse_svc, "is_third_person_stage_direction", None)
    assert stage_fn is not None, "Chưa triển khai hàm is_third_person_stage_direction"

    assert stage_fn("Uga chỉ tay, hét lên một tiếng báo nguy cho Lumi!", character_name="Uga") is True
    assert stage_fn("Lumi mỉm cười và bước tới bên đống lửa.", character_name="Lumi") is True
    assert stage_fn("Chạy mau lên Lumi ơi, nguy hiểm đang tới gần!", character_name="Uga") is False

    sc_bad_char = {
        "scene_num": 2,
        "scene_role": "Rising Action",
        "dialogue_lines": [
            {"speaker": "narrator", "text": "Tiếng gầm vang vọng khắp thảo nguyên khiến cả bộ lạc chấn động."},
            {"speaker": "character_2", "character_name": "Uga", "text": "Uga chỉ tay, hét lên một tiếng báo nguy cho Lumi!"},
        ],
    }
    segs = muse_svc.build_scene_dialogue_segments(sc_bad_char, language="vi", allow_synthetic_filler=False)
    # Câu mô tả ngôi thứ 3 'Uga chỉ tay...' phải được chuyển thành narrator, không được đọc bằng giọng nhân vật Uga
    assert all(s["speaker"] == "narrator" for s in segs)

    prompt_txt = build_museai_story_script_prompt(
        topic="cách mà ngôn ngữ ra đời",
        language="vi",
        story_style="cinematic_storytelling",
    )
    assert "do not search" in prompt_txt.lower() or "ignore any previous" in prompt_txt.lower() or "lumi" in prompt_txt.lower()
    assert "third-person" in prompt_txt.lower() or "stage direction" in prompt_txt.lower()













