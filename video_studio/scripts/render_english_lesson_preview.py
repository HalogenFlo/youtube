"""Render a real Vietnamese/English voice-switching whiteboard demonstration.

Uses a fixed two-scene lesson solely for preview, or an exported MuseAI JSON
script with --script; no alternate script-writing service is introduced.
"""
from pathlib import Path
import argparse
import json
import sys

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))
from src.museai_3d_service import (MuseAIFlowHybridController, synthesize_museai_scenes_interactive_tts,
                                  merge_flow_3d_scenes_into_final_movie)
from src.whiteboard_video import render_whiteboard_story_scenes
from src.whiteboard_ai_assets import resolve_whiteboard_ai_assets
from src.english_teaching import prepare_whiteboard_lesson


def preview_lesson():
    return {"story_title": "Chào hỏi bằng tiếng Anh", "content_mode": "english_teaching_vi", "visual_mode": "whiteboard",
            "publishing": {"hashtags": ["#ChaoHoiTiengAnh", "#GioiThieuBanThan", "#TiengAnhGiaoTiep"]},
            "scenes": [
                {"scene_num": 1, "lesson_context": "Bạn gặp một người bạn vào buổi sáng và muốn mở lời thật thân thiện. Một lời chào phù hợp sẽ giúp cuộc trò chuyện bắt đầu tự nhiên hơn.", "speech_segments": [
                    {"language": "vi", "text": "Để chào buổi sáng, bạn có thể nói:"},
                    {"language": "en", "text": "Good morning!"},
                    {"language": "vi", "text": "Nghĩa là chào buổi sáng."}],
                 "whiteboard_items": [
                    {"type": "text", "text": "Good morning!", "x": .5, "y": .14, "size": .055},
                    {"type": "illustration", "asset": "clock", "x": .24, "y": .48, "w": .25, "h": .4},
                    {"type": "illustration", "asset": "building", "x": .65, "y": .48, "w": .35, "h": .5},
                    {"type": "text", "text": "Chào buổi sáng", "x": .5, "y": .74, "size": .035}]},
                {"scene_num": 2, "lesson_context": "Sau lời chào, người bạn mới vẫn chưa biết tên bạn. Đây là lúc giới thiệu bản thân để hai người dễ làm quen hơn.", "speech_segments": [
                    {"language": "vi", "text": "Khi muốn giới thiệu tên, bạn nói:"},
                    {"language": "en", "text": "My name is Lan."},
                    {"language": "vi", "text": "Nghĩa là tôi tên Lan. Bạn hãy thử nói tên mình nhé."}],
                 "whiteboard_items": [
                    {"type": "text", "text": "My name is Lan.", "x": .5, "y": .14, "size": .055},
                    {"type": "illustration", "asset": "book", "x": .28, "y": .48, "w": .31, "h": .4},
                    {"type": "illustration", "asset": "browser", "x": .69, "y": .48, "w": .32, "h": .4},
                    {"type": "text", "text": "Tôi tên Lan.", "x": .5, "y": .74, "size": .035}]}
            ]}


def main():
    parser = argparse.ArgumentParser(description="Dựng thử bài tiếng Anh: giảng Việt, phát âm Anh, hình tay vẽ.")
    parser.add_argument("--script", type=Path)
    parser.add_argument("--ai-demo", action="store_true", help="AI tạo hình đi chợ và quầy sân bay ngoài kho mẫu.")
    parser.add_argument("--vieneu-voice", default="", help="Giọng VieNeu cho lời Việt, ví dụ Mai Anh.")
    parser.add_argument("--output", type=Path, default=STUDIO / "output" / "english_lesson_vi_en_preview.mp4")
    args = parser.parse_args()
    story = json.loads(args.script.read_text(encoding="utf-8")) if args.script else preview_lesson()
    if args.ai_demo:
        story = {"story_title": "Tiếng Anh khi đi chợ và đi sân bay",
                 "publishing": {"hashtags": ["#TiengAnhDiCho", "#TiengAnhSanBay", "#TiengAnhGiaoTiep"]}, "scenes": [
            {"scene_num": 1, "lesson_context": "Bạn đang đi chợ ở nước ngoài và muốn mua trái cây. Người bán đang chờ, nhưng bạn chưa biết mở lời thế nào.", "speech_segments": [
                {"language": "vi", "text": "Khi muốn mua hai quả táo, bạn có thể nói:"},
                {"language": "en", "text": "I'd like two apples, please."},
                {"language": "vi", "text": "Nghĩa là cho tôi hai quả táo."}],
             "whiteboard_items": [
                {"type": "text", "text": "At the market", "x": .5, "y": .12, "size": .05},
                {"type": "ai_image", "prompt": "A wicker shopping basket containing exactly two red apples and a small bunch of yellow bananas, cheerful market produce illustration, no people.",
                 "x": .5, "y": .47, "w": .7, "h": .52},
                {"type": "text", "text": "I'd like two apples, please.", "x": .5, "y": .76, "size": .035}]},
            {"scene_num": 2, "lesson_context": "Một tình huống khác: bạn vừa đến sân bay và cần gửi hành lý. Giữa nhiều quầy, bạn muốn hỏi nhân viên để tìm đúng nơi làm thủ tục.", "speech_segments": [
                {"language": "vi", "text": "Ở sân bay, khi muốn hỏi quầy làm thủ tục, bạn nói:"},
                {"language": "en", "text": "Where is the check-in counter?"},
                {"language": "vi", "text": "Nghĩa là quầy làm thủ tục ở đâu?"}],
             "whiteboard_items": [
                {"type": "text", "text": "At the airport", "x": .5, "y": .12, "size": .05},
                {"type": "ai_image", "prompt": "A friendly adult traveler with a rolling suitcase asking a female airline agent at an airport check-in counter, both in teal and blue clothing, clear side view of their interaction, no text or signage.",
                 "x": .5, "y": .47, "w": .7, "h": .52},
                {"type": "text", "text": "Where is the check-in counter?", "x": .5, "y": .76, "size": .035}]}
        ]}
    story["content_mode"] = "english_teaching_vi"
    story = prepare_whiteboard_lesson(story)
    controller = MuseAIFlowHybridController()
    ready = controller._enrich_scenes_with_3d_prompts(story, "horizontal", "whiteboard")
    flow_state = {"started": False}
    def generate_image(**request):
        if not flow_state["started"]:
            ok, error = controller.start_fresh_google_flow_project(orientation="horizontal")
            if not ok:
                return False, error
            flow_state["started"] = True
        return controller.generate_whiteboard_illustration_on_google_flow(**request, orientation="horizontal")
    ok, scenes, report = resolve_whiteboard_ai_assets(ready["scenes"], generate_image,
                    progress_callback=lambda pct, text: print(text, flush=True))
    if not ok:
        raise SystemExit(report["error"])
    ready["scenes"] = scenes
    ready["whiteboard_ai_assets"] = report
    work = STUDIO / "temp" / "english_lesson_preview"
    work.mkdir(parents=True, exist_ok=True)
    for stage in (
        lambda: synthesize_museai_scenes_interactive_tts(ready["scenes"], str(work), "vi_en",
                            vietnamese_voice=f"vieneu-v3:{args.vieneu_voice}" if args.vieneu_voice else ""),
        lambda: render_whiteboard_story_scenes(ready["scenes"], str(work), "horizontal"),
        lambda: merge_flow_3d_scenes_into_final_movie(ready["scenes"], str(work), str(args.output),
                                                    language="vi_en", orientation="horizontal", tts_already_ready=True)):
        ok, result = stage()
        if not ok:
            raise SystemExit(result)
    args.output.with_suffix(".json").write_text(json.dumps(ready, ensure_ascii=False, indent=2), encoding="utf-8")
    from src.video_library import ensure_metadata_for_new_video
    ensure_metadata_for_new_video(str(args.output))
    print(args.output)


if __name__ == "__main__":
    main()
