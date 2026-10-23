# Luồng Kết Hợp Tự Động: MuseAI Viết Kịch Bản Cốt Truyện 3D ➔ Google Flow Sinh Video 3D Từng Cảnh

Kiến trúc này kết hợp đúng thế mạnh tốt nhất của cả hai công cụ trên cùng một cửa sổ Chrome (`Port 9222` — dùng chung `flow_chrome_profile`):
1. **Tab 1 — MuseAI (`https://muse.ai/`) làm Đạo diễn & Biên kịch**: Thay thế hoàn toàn Ollama Local, tự sáng tác cốt truyện 3D có đầu có cuối (**Mở đầu Hook ➔ Diễn biến ➔ Cao trào ➔ Kết thúc**), khóa thiết kế nhân vật 3D (`character_anchor`) và xuất danh sách phân cảnh JSON.
2. **Tab 2 — Google Flow (`https://flow.google.com/` - Google Veo) làm Xưởng Render Video 3D**: Tự động nhận từng phân cảnh từ kịch bản của MuseAI, gỡ bỏ hoàn toàn bộ lọc ép 2D stickman cũ, và render từng video clip hoạt hình 3D CGI thật (`scene_001.mp4`, `scene_002.mp4`...).
3. **Bước 3 — Tự động Lồng Tiếng & Ghép Phim Hoàn Chỉnh**: Ghép nối toàn bộ các video 3D vừa tải từ Google Flow theo đúng thứ tự câu chuyện (tự động lồng tiếng giọng đọc AI + phụ đề đáy từ module `video_compiler.py` sẵn có của bạn hoặc ghép FFmpeg lossless) và xuất ra thư mục `output/`.

## 1. Tại sao trước đây Google Flow của bạn chỉ ra hình 2D hoặc lỗi?

Trong tệp `src/flow_browser_service.py` cũ của dự án `video_studio`:
- **Dòng 43 (`STICKMAN_CANONICAL_GUIDANCE`) và dòng 548 (`generate_scene_video`)** bị khóa cứng câu lệnh:
  > `"Generate exactly ONE 2D ANIMATION VIDEO CLIP, not a still image and strictly NO 3D... Keep the same canonical character CH01 in every shot: a cute 2D minimalist stickman cartoon"`
- Ngoài ra, Bước 1 trong `src/batch_producer.py` bắt buộc gọi `http://localhost:11434/api/generate` (Ollama Local), nên khi không bật Ollama thì Google Flow không bao giờ được gọi.

Trong tệp `museai_3d_service.py` mới, toàn bộ câu lệnh gửi sang Google Flow đã được thay bằng chuẩn **`PIXAR_3D_CANONICAL_GUIDANCE`** (ép Google Veo render hoạt hình 3D Pixar / DreamWorks / Unreal Engine 5 Lumen và cấm tuyệt đối 2D stickman / hình học 2D).

## 2. Prompt Gửi Lên Tab 1 (MuseAI) Để Viết Kịch Bản Cốt Truyện 3D

Khi chạy `museai_3d_service.py`, công cụ sẽ tự động gửi prompt này vào tab MuseAI và đọc khối JSON trả về:

```text
Act as a Pixar / DreamWorks 3D Animation Story Director.
Do NOT generate any images, videos, or run Python code. Your ONLY task right now is to write a complete 3D animated short film script and scene-by-scene 3D visual prompts so I can feed each scene into Google Flow (Veo) to render the 3D videos.

Story Topic / Idea: "{TOPIC}"
Target Format: exactly 5 sequential scenes (each scene ~5–6 seconds, 9:16 vertical portrait), voiceover narration in Vietnamese (Tiếng Việt).

MANDATORY RULES:
1. COMPLETE STORYLINE WITH BEGINNING, CLIMAX & ENDING (CÓ ĐẦU CÓ CUỐI LIỀN MẠCH):
   - Scene 1 (Hook / Beginning): Introduce the main 3D character, the 3D setting, and an intriguing problem or mystery.
   - Middle Scenes (Rising Action & Climax): Develop the story naturally with transitional bridging phrases in Vietnamese ("Thế nhưng...", "Chính vì vậy...", "Đúng lúc đó...", "Nhờ vậy...") so all scenes flow as one continuous story.
   - Final Scene (Resolution / Ending): Resolve the conflict with a warm, memorable conclusion.
2. STRICT 3D CHARACTER CONSISTENCY (`character_anchor`):
   - Design one canonical main character in high-poly Pixar 3D CGI style (specify exact age/species, sculpted 3D face, subsurface scattering skin tone, 3D groomed hair style/color, eye color, and exact 3D clothing/accessories in English).
   - Repeat the character's key visual traits inside EVERY scene's `video_prompt` so Google Flow keeps the character 100% consistent across all scenes.
3. TRUE 3D CGI PROMPTS ONLY (NO 2D / NO GEOMETRIC SHAPES):
   - Every `video_prompt` must be written in English, describing genuine 3D CGI animation (Pixar RenderMan / Unreal Engine 5 Lumen / Octane 3D render, sculpted 3D models, volumetric lighting, physical 3D camera movement, expressive 3D character action matching the `narration` 1:1).
   - Strictly NO 2D cartoon, NO stickman, NO geometric primitives/blocks, and NO readable text/numbers/signs inside the visual scene.
```

## 3. Cấu Trúc Prompt 3D Tự Động Đẩy Sang Tab 2 (Google Flow) Cho Từng Cảnh

Với mỗi phân cảnh đọc được từ MuseAI, công cụ tự động chuyển sang tab Google Flow (`https://flow.google.com/project/...`), điền cấu trúc prompt 3D dưới đây và đợi Google Veo xuất file `.mp4`:

```text
Generate exactly ONE 3D CGI ANIMATION VIDEO CLIP, not a still image, and strictly NO 2D flat cartoon or geometric shapes. Strictly mute video, no audio generation, silent video only.
Canonical 3D Character (keep 100% identical in every scene): {CHARACTER_ANCHOR}.
3D Environment & Lighting: {ENVIRONMENT_ANCHOR}.
Scene 3D Action: {VIDEO_PROMPT}.
Style: Masterpiece 3D feature-film animation, Pixar RenderMan and DreamWorks 3D CGI studio quality, Unreal Engine 5 Lumen global illumination, Octane 3D render, sculpted high-poly 3D character mesh with expressive facial blendshapes, realistic subsurface scattering (SSS) on skin, groomed 3D hair strands, physically based rendering (PBR) clothing and textures, volumetric lighting, shallow depth of field bokeh. STRICTLY NO 2D flat cartoon, NO 2D vector illustration, NO stickman, NO 2D geometric shapes/blocks, NO captions, subtitles, logos, or watermarks inside the video.
Camera & Composition: vertical 9:16 portrait (1080x1920), {CAMERA_DIRECTIVE}, fluid 3D skeletal animation, rich volumetric lighting, no audio.
```

## 4. Cách Chạy Ngay Trong Hệ Thống `video_studio` Của Bạn

1. Đặt tệp **`museai_3d_service.py`** vào thư mục `video_studio/src/museai_3d_service.py`.
2. Đảm bảo trên Chrome điều khiển (`flow_chrome_profile` — cổng `9222`) bạn đã đăng nhập sẵn tài khoản trên cả 2 tab: **MuseAI** và **Google Flow**.
3. Mở terminal tại thư mục `video_studio` và chạy:

```bash
python src/museai_3d_service.py --topic "Chú robot nhỏ bằng đồng đi tìm bông hoa phát sáng cuối cùng trong khu rừng mùa đông" --scenes 5
```

*(Nếu chỉ muốn ghép các video 3D gốc từ Google Flow mà không cần lồng tiếng TTS và phụ đề, thêm cờ `--no-tts`).*