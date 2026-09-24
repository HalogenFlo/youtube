# Chức năng: CLI chạy tự động sản xuất hàng loạt video từ Prompt (Auto Batch Video Producer).
# Cách dùng: python scripts/batch_video_producer.py --prompt "Chủ đề video" --count 3 --engine flow

import os
import sys
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from src.batch_producer import run_batch_video_loop
from src.config import TTS_VOICE_DEFAULT, DEFAULT_IMAGE_STYLE


def main():
    parser = argparse.ArgumentParser(description="Tự động tạo nhiều video từ Prompt theo kịch bản lặp.")
    parser.add_argument("--prompt", "-p", type=str, default="", help="Prompt hoặc chủ đề chính của video")
    parser.add_argument("--count", "-c", type=int, default=1, help="Số lượng video muốn tạo (vòng lặp)")
    parser.add_argument("--engine", "-e", type=str, default="flow", choices=["flow", "sd"], help="Mô hình sinh bối cảnh: flow hoặc sd")
    parser.add_argument("--lang", "-l", type=str, default="vi", choices=["vi", "en"], help="Ngôn ngữ kịch bản và giọng đọc")
    parser.add_argument("--orientation", "-o", type=str, default="vertical", choices=["vertical", "horizontal"], help="Định dạng: vertical (9:16) hoặc horizontal (16:9)")

    args = parser.parse_args()

    prompt = args.prompt
    if not prompt:
        print("\n" + "=" * 65)
        print("🎬 AUTO BATCH VIDEO PRODUCER (GOOGLE FLOW & AI SCRIPT)")
        print("=" * 65)
        prompt = input("\n👉 Nhập Prompt / Ý tưởng / Chủ đề của bạn: ").strip()
        if not prompt:
            print("[!] Chưa nhập prompt. Thoát chương trình.")
            return

    count = args.count
    if count <= 0:
        try:
            count_str = input("👉 Số lượng video muốn tạo tự động (mặc định 1): ").strip()
            count = int(count_str) if count_str else 1
        except Exception:
            count = 1

    print("\n" + "-" * 65)
    print(f"[*] Khởi động Pipeline tự động:")
    print(f"    - Prompt: \"{prompt}\"")
    print(f"    - Số video tạo: {count}")
    print(f"    - Engine bối cảnh: {args.engine.upper()}")
    print(f"    - Định dạng: {args.orientation}")
    print("-" * 65 + "\n")

    def cli_progress(video_num, total_videos, pct, msg):
        print(f"[{video_num}/{total_videos}] [{int(pct):3d}%] {msg}")

    videos, meta = run_batch_video_loop(
        prompt=prompt,
        count=count,
        language=args.lang,
        voice=TTS_VOICE_DEFAULT if args.lang == "vi" else "en-US-EmmaNeural",
        style_preset=DEFAULT_IMAGE_STYLE,
        orientation=args.orientation,
        image_engine=args.engine,
        progress_callback=cli_progress
    )

    print("\n" + "=" * 65)
    print(f"🎉 HOÀN THÀNH: Đã xuất bản {len(videos)}/{count} video!")
    for i, v in enumerate(videos):
        print(f"   [{i+1}] {v}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
