"""Exercise on-demand AI illustrations, cache reuse, failure handling and routing.

Ensures missing subjects are generated instead of replaced with the stock desk.
The fake image backend supplies pixels; PNG processing/rendering stay real.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import whiteboard_ai_assets as ai
from src import museai_3d_service as svc


def scene(subject="A red apple next to a yellow banana"):
    return {"scene_num": 1, "narration": "Một quả táo và một quả chuối.",
            "whiteboard_items": [{"type": "ai_image", "prompt": subject, "x": .5, "y": .5, "w": .6, "h": .5}]}


def write_art(path):
    im = Image.new("RGB", (256, 256), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((48, 45, 180, 185), fill="red", outline="black", width=4)
    d.ellipse((87, 84, 135, 132), fill="white", outline="black", width=4)
    im.save(path)


def test_generate_then_reuse_same_subject_across_scenes_and_runs(tmp_path):
    calls = []
    original = [scene(), dict(scene(), scene_num=2)]
    def generate(**kw):
        calls.append(kw)
        write_art(kw["output_path"])
        return True, kw["output_path"]
    ok, prepared, report = ai.resolve_whiteboard_ai_assets(original, generate, asset_dir=tmp_path)
    assert ok, report
    assert len(calls) == 1 and report["generated"] == 1 and report["cache_hits"] == 1
    assert all(s["whiteboard_items"][0]["type"] == "image" for s in prepared)
    assert original == [scene(), dict(scene(), scene_num=2)]
    assert "whiteboard" in calls[0]["prompt"] and "3D CGI" not in calls[0]["prompt"]
    ok, _, again = ai.resolve_whiteboard_ai_assets(original, generate, asset_dir=tmp_path)
    assert ok and len(calls) == 1 and again["cache_hits"] == 2


def test_new_character_design_or_subject_needs_a_new_image(tmp_path):
    assert ai.asset_identity(ai.build_whiteboard_image_prompt("cat", "red shirt")) != ai.asset_identity(
        ai.build_whiteboard_image_prompt("cat", "blue shirt"))
    assert ai.asset_identity(ai.build_whiteboard_image_prompt("cat")) != ai.asset_identity(ai.build_whiteboard_image_prompt("dog"))


def test_white_margin_is_transparent_but_enclosed_white_is_preserved(tmp_path):
    source, final = tmp_path / "source.png", tmp_path / "final.png"
    write_art(source)
    ai.prepare_generated_illustration(source, final)
    with Image.open(final) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((110, 110)) == (255, 255, 255, 255)
        assert image.getpixel((65, 100))[3] == 255


def test_invalid_ai_output_retries_and_never_substitutes_stock_art(tmp_path):
    calls = []
    def generate(**kw):
        calls.append(kw)
        Image.new("RGB", (256, 256), "white").save(kw["output_path"])
        return True, kw["output_path"]
    ok, prepared, report = ai.resolve_whiteboard_ai_assets([scene()], generate, asset_dir=tmp_path)
    assert not ok and len(calls) == 2 and "trống" in report["error"]
    assert prepared[0]["whiteboard_items"][0]["type"] == "ai_image"
    assert not list((tmp_path / "ai").glob("*.json"))


def test_cache_metadata_or_image_corruption_forces_generation(tmp_path):
    calls = []
    def generate(**kw):
        calls.append(1)
        write_art(kw["output_path"])
        return True, kw["output_path"]
    _, prepared, _ = ai.resolve_whiteboard_ai_assets([scene()], generate, asset_dir=tmp_path)
    output = tmp_path / prepared[0]["whiteboard_items"][0]["asset"]
    output.write_bytes(b"corrupt")
    ok, _, report = ai.resolve_whiteboard_ai_assets([scene()], generate, asset_dir=tmp_path)
    assert ok and len(calls) == 2 and report["generated"] == 1


def test_cancel_or_disabled_generation_never_calls_backend(tmp_path):
    def forbidden(**kw):
        pytest.fail("Backend must not be invoked")
    ok, _, report = ai.resolve_whiteboard_ai_assets([scene()], forbidden, enabled=False, asset_dir=tmp_path)
    assert not ok and "bật AI" in report["error"]
    ok, _, report = ai.resolve_whiteboard_ai_assets([scene()], forbidden, asset_dir=tmp_path, is_cancelled_callback=lambda: True)
    assert not ok and "bỏ qua" in report["error"]
    assert ai.resolve_whiteboard_ai_assets([{"whiteboard_items": []}], forbidden, asset_dir=tmp_path)[0]


def test_whiteboard_flow_route_keeps_the_2d_prompt(monkeypatch, tmp_path):
    captured = []
    def generate(self, **kw):
        captured.append(kw)
        return True, kw["output_path"]
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "_generate_image_on_google_flow", generate)
    controller = svc.MuseAIFlowHybridController()
    prompt = ai.build_whiteboard_image_prompt("a teacher at an airport")
    controller.generate_whiteboard_illustration_on_google_flow(prompt, str(tmp_path / "art.png"))
    assert captured[0]["image_style"] == "whiteboard"
    assert captured[0]["scene_data"]["image_prompt"] == prompt


def test_prompt_allows_new_subjects_and_disabled_option_is_explicit():
    prompt = svc.build_museai_story_script_prompt(visual_mode="whiteboard")
    assert 'type="ai_image"' in prompt and "NOT a limit" in prompt
    off = svc.build_museai_story_script_prompt(visual_mode="whiteboard", whiteboard_ai_enabled=False)
    assert "do not output ai_image" in off


def test_normalization_preserves_generation_request_until_it_is_resolved():
    controller = svc.MuseAIFlowHybridController()
    prepared = controller._enrich_scenes_with_3d_prompts({"scenes": [scene()]}, "horizontal", "whiteboard")
    item = prepared["scenes"][0]["whiteboard_items"][0]
    assert item["type"] == "ai_image" and item["prompt"] == scene()["whiteboard_items"][0]["prompt"]


def test_unknown_stock_subject_is_promoted_to_ai_instead_of_dropped():
    from src.whiteboard_video import layout_scene_items
    items = layout_scene_items({"whiteboard_items": [{"type": "illustration", "asset": "airport_check_in"}]})
    assert items[0]["type"] == "ai_image" and "airport check in" in items[0]["prompt"]


def test_saved_ai_script_reuses_cached_art_on_rerender(tmp_path):
    def generate(**kw):
        write_art(kw["output_path"])
        return True, kw["output_path"]
    _, prepared, _ = ai.resolve_whiteboard_ai_assets([scene()], generate, asset_dir=tmp_path)
    normalized = svc.MuseAIFlowHybridController()._enrich_scenes_with_3d_prompts(
        {"scenes": prepared}, "horizontal", "whiteboard")["scenes"]
    def forbidden(**kw):
        pytest.fail("Re-rendering a saved AI script should use its valid cached art")
    ok, _, report = ai.resolve_whiteboard_ai_assets(normalized, forbidden, asset_dir=tmp_path)
    assert ok and report["cache_hits"] == 1


def test_pipeline_generates_missing_art_before_rendering_and_saves_provenance(tmp_path, monkeypatch):
    from src import whiteboard_video as board
    monkeypatch.setattr(ai, "ASSET_DIR", tmp_path / "assets")
    calls = []
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_3d_script_via_museai",
                        lambda self, **kw: (True, {"story_title": "Trái cây", "scenes": [scene()]}))
    def fresh(self, **kw):
        calls.append("fresh")
        return True, "test"
    def generate(self, **kw):
        calls.append("generate")
        write_art(kw["output_path"])
        return True, kw["output_path"]
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "start_fresh_google_flow_project", fresh)
    monkeypatch.setattr(svc.MuseAIFlowHybridController, "generate_whiteboard_illustration_on_google_flow", generate)
    def render(scenes, work_dir, *a, **kw):
        calls.append("render")
        assert scenes[0]["whiteboard_items"][0]["type"] == "image"
        path = Path(work_dir) / "scene.mp4"
        path.write_bytes(b"video")
        scenes[0]["video_path"] = str(path)
        return True, "ok"
    monkeypatch.setattr(board, "render_whiteboard_story_scenes", render)
    def merge(scenes, work_dir, final_output_path, *a, **kw):
        Path(final_output_path).write_bytes(b"merged")
        return True, final_output_path
    monkeypatch.setattr(svc, "merge_flow_3d_scenes_into_final_movie", merge)
    ok, path, meta = svc.run_museai_script_to_google_flow_3d_pipeline(
        visual_mode="whiteboard", with_tts_and_subtitles=False, work_dir=str(tmp_path / "work"), output_dir=str(tmp_path / "out"))
    assert ok, path
    assert calls == ["fresh", "generate", "render"]
    assert meta["whiteboard_ai_assets"]["generated"] == 1
    saved = json.loads(Path(meta["script_file"]).read_text(encoding="utf-8"))
    assert saved["scenes"][0]["whiteboard_items"][0]["asset"].startswith("ai/")
