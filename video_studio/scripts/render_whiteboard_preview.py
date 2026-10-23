"""Render an offline 1080p preview of the stickman drawing-hand effect.

No script-writing service is required; this is only a renderer demonstration.
Reference ideas: https://github.com/skys-xk/videomake_gpt and
https://github.com/ChenShuo2004/cs-board.
"""
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.whiteboard_video import render_whiteboard_scene_video, WhiteboardRenderer, layout_scene_items


def preview_scene():
    return {"whiteboard_items": [
        {"type": "text", "x": .5, "y": .12, "text": "Mỗi bước tăng gấp 10 lần", "size": .045},
        {"type": "circle", "x": .14, "y": .43, "r": .025, "label": "1"},
        {"type": "text", "x": .14, "y": .56, "text": "1 triệu $", "size": .025},
        {"type": "arrow", "x": .18, "y": .43, "x2": .26, "y2": .43, "label": "×10"},
        {"type": "circle", "x": .32, "y": .43, "r": .045, "label": "10"},
        {"type": "text", "x": .32, "y": .59, "text": "10 triệu $", "size": .025},
        {"type": "arrow", "x": .38, "y": .43, "x2": .46, "y2": .43, "label": "×10"},
        {"type": "circle", "x": .55, "y": .43, "r": .075, "label": "100"},
        {"type": "text", "x": .55, "y": .64, "text": "100 triệu $", "size": .025},
        {"type": "arrow", "x": .64, "y": .43, "x2": .73, "y2": .43, "label": "×10"},
        {"type": "circle", "x": .83, "y": .43, "r": .09, "label": "1 tỷ $"},
        {"type": "stickman", "x": .26, "y": .75, "h": .24, "emotion": "thinking"},
        {"type": "stickman", "x": .7, "y": .75, "h": .24, "emotion": "surprised"},
    ]}


def color_preview_scene():
    return {"whiteboard_items": [
        {"type": "text", "x": .24, "y": .14, "text": "Vượt qua sự trì hoãn", "size": .034},
        {"type": "illustration", "asset": "study_desk", "x": .64, "y": .52, "w": .62, "h": .61},
        {"type": "illustration", "asset": "browser", "x": .22, "y": .40, "w": .29, "h": .34},
        {"type": "illustration", "asset": "clock", "x": .82, "y": .12, "w": .1, "h": .18},
        {"type": "text", "x": .65, "y": .13, "text": "5 phút", "size": .035},
        {"type": "illustration", "asset": "book", "x": .20, "y": .69, "w": .22, "h": .24},
    ]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Xem thử hiệu ứng người que và bàn tay vẽ; video không lời.")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "output" / "whiteboard_color_real_hand_1080p.mp4"))
    parser.add_argument("--style", choices=["color", "stickman"], default="color")
    args = parser.parse_args()
    scene = color_preview_scene() if args.style == "color" else preview_scene()
    duration = 16 if args.style == "color" else 12
    ok, result = render_whiteboard_scene_video(scene, args.output, duration, size=(1920, 1080))
    if not ok:
        raise SystemExit(result)
    renderer = WhiteboardRenderer(layout_scene_items(scene), duration, size=(1920, 1080))
    renderer.render_frame(4.25 if args.style == "color" else 5).save(str(Path(args.output).with_suffix(".png")))
    renderer.render_frame(duration).save(str(Path(args.output).with_suffix(".complete.png")))
    print(result)
