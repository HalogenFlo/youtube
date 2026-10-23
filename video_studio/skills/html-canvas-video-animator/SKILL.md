---
name: html-canvas-video-animator
description: Generate animated 2D cartoon and motion-graphics videos by authoring self-contained HTML5 Canvas multi-frame animations and rendering them deterministically frame-by-frame to MP4 via Headless Chromium and FFmpeg. Use when the user asks to create animated videos from HTML frames, cartoon animations, motion graphics, HyperFrames-style HTML-to-video, or an alternative to Google Flow video generation.
---

# HTML Canvas Video Animator

Create frame-accurate 2D cartoon and motion-graphics videos (`.mp4`) by generating a self-contained HTML5 `<canvas>` scene with deterministic frame-stepping hooks and rendering it through Headless Chromium and FFmpeg.

## Summary

This skill implements the deterministic HTML-to-Video workflow inspired by open-source agent video skills (`nexu-io/html-video` HyperFrames, `siegerts/skill-canvas-video`, and `AZR-Software-Solutions/html-animation-to-mp4`). Instead of relying on fragile screen recording or slow external video generators, each scene is authored as an HTML5 Canvas animation that exposes `window.renderFrameAt(timeSec, durationSec)` and `window.renderFrameBatch(startFrame, count, fps, durationSec)`, enabling fast multi-threaded frame extraction and FFmpeg H.264/AAC encoding.

## When to Use

- The user wants to generate animated videos, 2D cartoons, explainer animations, or kinetic typography from code or HTML frames.
- The user wants an offline or fast local alternative to external AI video generators like Google Flow.
- The user asks to render an HTML/CSS/Canvas animation into a smooth `.mp4` video with synchronized audio and subtitles.
- The user wants audio-reactive 2D character lip-sync (`audioEnvelope`) driven by TTS narration tracks.

## Steps

### 1. Plan the Scene Timeline and Safe Zones

- Use `1080x1920` (9:16 vertical for TikTok / YouTube Shorts) or `1920x1080` (16:9 horizontal for YouTube).
- Respect platform UI safe zones: for `1080x1920`, keep essential visual elements and subtitles inside `X: [90..990]` and `Y: [180..1540]`.
- Extract the audio amplitude envelope (`audioEnvelope`) from the narration `.mp3`/`.wav` file at `fps` samples per second so character mouth shapes and visual beats react 1:1 to the voice track.

### 2. Author the Self-Contained HTML5 Canvas Scene

Every generated scene HTML file must include:

- A `<canvas id="stage" width="1080" height="1920"></canvas>` element.
- Smooth easing utilities (`lerp(a, b, t)`, `easeOutCubic(t)`, `easeInOutCubic(t)`, `clamp(v, min, max)`).
- Layered 2D rendering inside `window.renderFrameAt(t, duration)`:
  1. **Background & Parallax Layer**: Gradient sky/room, moving clouds/stars/grid, and depth-scaled foreground props.
  2. **2D Cartoon Character Rig**: Breathing torso bob (`Math.sin(t * 3)`), natural eye blinks every 2.8 seconds, expressive hand/arm gestures, and mouth opening proportional to `audioEnvelope[frameIndex]`.
  3. **Visual Callouts & Atmospheric FX**: Floating particles (fireflies, sparkles, data nodes) and animated concept badges.
- A batched extraction hook `window.renderFrameBatch(startFrame, count, fps, duration)` returning an array of Base64 JPEG payloads (`canvas.toDataURL("image/jpeg", 0.90)`), plus a live browser preview loop (`requestAnimationFrame`) with `Space` (play/pause) and `R` (restart) controls.

### 3. Render Deterministically to MP4 via Headless Chromium and FFmpeg

Run the bundled renderer script `scripts/render_html_frames.py` (or call `render_html_scene_to_mp4` in Python):

```bash
python3 skills/html-canvas-video-animator/scripts/render_html_frames.py \
  --html scene_001.html \
  --audio scene_001.mp3 \
  --output scene_001.mp4 \
  --width 1080 --height 1920 --fps 30
```

- Load the HTML via `data:text/html;base64,...` or local HTTP so Headless Chromium executes canvas scripts without `file://` origin restrictions.
- Capture frames in batches of 30-60 frames per WebDriver call and stream raw JPEG bytes into `ffmpeg -f image2pipe -vcodec mjpeg -r <fps> -i -` paired with `-i <audio_path> -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest`.
- Verify the resulting `.mp4` with `ffprobe` to confirm both `h264` video and `aac` audio streams exist and match the target duration.

## Gotchas

- **Avoid `file://` CORS blocks on Canvas**: Always load self-contained HTML via `data:text/html;base64,...` or a local HTTP server so `canvas.toDataURL()` never throws a tainted-canvas or script execution error.
- **Avoid per-frame WebDriver HTTP overhead**: Calling `driver.get_screenshot_as_png()` 180 times for a 6-second clip adds massive IPC latency. Always use `window.renderFrameBatch()` to render 30-60 frames inside V8 and return them in a single call.
- **Ensure audible audio streams**: Always verify with `ffprobe` and `volumedetect` that the muxed audio stream has `mean_volume > -28 dB` and `max_volume > -10 dB`.

## Project integration (2026-10-21)

- Production renderer: `src/cartoon_timeline.py` + `src/cartoon_timeline.js`, shared deterministic drawing commands for browser and Python.
- Author approach/action/resolve beats and articulated limbs; do not use whole-image oscillation as the main action.
- Select landscape layers from scene content and adapt portrait composition without cropping the actor.
- Chrome capture uses Playwright, not Selenium.
- Installed upstream references: `../hyperframes-animation/`, `../hyperframes-keyframes/`, `../hyperframes-creative/`.
- Verification and limits: `../../docs/animation_upgrade.md`.
