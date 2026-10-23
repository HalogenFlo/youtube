"""Validate the real marker-hand asset and contour/fill drawing behavior.

Added to distinguish an actual pen-following reveal from the previous rectangle wipe.
"""
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.whiteboard_drawing import make_plan, draw_progress
from src.whiteboard_illustrations import ASSET_DIR, ILLUSTRATIONS, illustration_image, local_image_path
from src.whiteboard_video import WhiteboardRenderer, layout_scene_items, _make_hand_sprite


def test_reveal_follows_the_marker_tip_instead_of_a_vertical_wipe():
    plan = make_plan([[(10., 10.), (90., 10.)], [(90., 90.), (10., 90.)]], 5)
    mask, tip = draw_progress(plan, .25, (100, 100))
    assert tip == (50., 10.)
    assert mask.getpixel((45, 10)) == 255
    assert mask.getpixel((45, 90)) == 0
    assert mask.getpixel((80, 10)) == 0
    later, _ = draw_progress(plan, .75, (100, 100))
    assert np.all(np.asarray(later) >= np.asarray(mask))


def test_production_hand_is_a_transparent_photographic_asset():
    assert (ASSET_DIR / "hand_photo_v1.png").is_file()
    hand, tip = _make_hand_sprite(256)
    assert hand.mode == "RGBA" and hand.getpixel((0, 0))[3] == 0
    assert hand.size == (256, 384)
    assert tip == (87, 24)
    # Photographic texture contains far more colors than the former geometric hand.
    opaque = np.asarray(hand)
    pixels = opaque[opaque[:, :, 3] > 240, :3]
    assert len(np.unique(pixels, axis=0)) > 1000


@pytest.mark.parametrize("asset", sorted(ILLUSTRATIONS))
def test_illustrations_have_color_and_transparency(asset):
    image = illustration_image(asset)
    rgba = np.asarray(image)
    assert image.mode == "RGBA" and rgba[:, :, 3].min() == 0
    rgb = rgba[:, :, :3].astype(int)
    colored = (rgb.max(axis=2) - rgb.min(axis=2) > 35) & (rgba[:, :, 3] > 220)
    assert colored.any()


def test_outline_precedes_fill_and_finished_frame_keeps_full_color():
    items = layout_scene_items({"whiteboard_items": [
        {"type": "illustration", "asset": "browser", "x": .5, "y": .45, "w": .75, "h": .65}]})
    renderer = WhiteboardRenderer(items, 5, (480, 270), show_hand=False)
    start, end = renderer.schedule[0]
    outline = np.asarray(renderer.render_frame(start + (end - start) * .45)).astype(int)
    final = np.asarray(renderer.render_frame(5)).astype(int)
    assert np.max(outline.max(axis=2) - outline.min(axis=2)) <= 15  # charcoal is slightly cool
    assert ((final.max(axis=2) - final.min(axis=2)) > 35).any()
    assert np.asarray(renderer.render_frame(0)).min() == 255  # random-access reset


def test_local_illustrations_cannot_escape_asset_directory():
    with pytest.raises(ValueError):
        local_image_path("../outside.png")
    with pytest.raises(ValueError):
        local_image_path("hand_photo_v1.png.exe")


def test_custom_local_art_is_accepted_without_stretching(tmp_path, monkeypatch):
    import src.whiteboard_illustrations as library
    monkeypatch.setattr(library, "ASSET_DIR", tmp_path)
    Image.new("RGBA", (200, 100), (40, 120, 210, 255)).save(tmp_path / "custom.png")
    items = layout_scene_items({"whiteboard_items": [
        {"type": "image", "asset": "custom.png", "x": .5, "y": .5, "w": .5, "h": .5}]})
    # Use the normal layer builder; the photo hand itself stays in the production registry.
    from src.whiteboard_video import _draw_item_layer
    layer = _draw_item_layer(items[0], (400, 400))
    x0, y0, x1, y1 = layer.getchannel("A").getbbox()
    assert abs((x1 - x0) / (y1 - y0) - 2) < .1
