#!/usr/bin/env python3
"""
Deterministic HTML5 Canvas Multi-Frame to MP4 Renderer.
Supports Headless Chromium batched frame capture + FFmpeg image2pipe muxing.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from typing import List, Optional, Tuple


def render_html_file_to_mp4(
    html_path: str,
    output_mp4_path: str,
    audio_path: Optional[str] = None,
    duration: float = 5.0,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    batch_size: int = 45,
) -> Tuple[bool, str]:
    if not os.path.exists(html_path):
        return False, f"HTML file not found: {html_path}"

    os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    total_frames = max(1, int(round(duration * fps)))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-r", str(fps),
        "-i", "-",
    ]
    if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        cmd.extend(["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k"])
    else:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"])

    cmd.extend([
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-crf", "19",
        "-movflags", "+faststart",
        "-shortest",
        output_mp4_path,
    ])

    driver = None
    browser = None
    playwright = None
    proc = None
    try:
        from playwright.sync_api import sync_playwright
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        driver = browser.new_page(viewport={"width": width, "height": height})
        driver.set_content(html_content, wait_until="load")

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        for start_f in range(0, total_frames, batch_size):
            count = min(batch_size, total_frames - start_f)
            b64_list: List[str] = driver.evaluate(
                f"window.renderFrameBatch({start_f}, {count}, {fps}, {duration:.4f})"
            )
            for b64_jpg in b64_list:
                proc.stdin.write(base64.b64decode(b64_jpg))

        proc.stdin.close()
        proc.stdin = None
        _, stderr_bytes = proc.communicate(timeout=120)
        if proc.returncode != 0:
            return False, f"FFmpeg error: {stderr_bytes.decode('utf-8', errors='replace')[-400:]}"
        return True, output_mp4_path
    except Exception as e:
        return False, f"Render failed: {e}"
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass

        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.communicate()


def main() -> int:
    parser = argparse.ArgumentParser(description="Render HTML5 Canvas animation frames to MP4")
    parser.add_argument("--html", required=True, help="Input HTML file path")
    parser.add_argument("--output", required=True, help="Output MP4 file path")
    parser.add_argument("--audio", default=None, help="Optional audio track path")
    parser.add_argument("--duration", type=float, default=5.0, help="Duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--width", type=int, default=1080, help="Canvas width")
    parser.add_argument("--height", type=int, default=1920, help="Canvas height")
    args = parser.parse_args()

    ok, msg = render_html_file_to_mp4(
        html_path=args.html,
        output_mp4_path=args.output,
        audio_path=args.audio,
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    if ok:
        print(json.dumps({"status": "ok", "output": msg}))
        return 0
    print(json.dumps({"status": "error", "error": msg}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
