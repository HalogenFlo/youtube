# Chức năng: Kịch bản sản xuất video hoàn chỉnh tự động từ A-Z với nhân vật Stickman áo xanh.
# Trích dẫn: Tích hợp đầy đủ Ollama kịch bản, Edge-TTS lồng tiếng, Faster-Whisper phụ đề, và Visual Beats Engine.

import os
import sys
import json
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Đảm bảo UTF-8 trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from src.config import TEMP_DIR, OUTPUT_DIR, FONT_PATH
from src.llm_service import generate_script
from src.tts_service import generate_tts
from src.whisper_service import get_word_timestamps
from src.video_compiler import compile_video_pipeline


def create_stickman_scene_frame(
    mascot_img: Image.Image,
    scene_num: int,
    bg_color_tuple: tuple,
    scene_label: str,
    output_path: str,
    target_size=(720, 1280)
):
    """
    Tạo khung hình phân cảnh 9:16 chất lượng cao với nhân vật Stickman áo xanh làm trung tâm,
    nền chuyển màu gradient nhẹ nhàng và bối cảnh tối giản theo quy chuẩn repo tiktok-ytb.
    """
    tw, th = target_size
    img = Image.new("RGB", (tw, th), color=bg_color_tuple[0])
    draw = ImageDraw.Draw(img)

    # Gradient nền
    for y in range(th):
        factor = y / th
        r = int(bg_color_tuple[0][0] * (1 - factor) + bg_color_tuple[1][0] * factor)
        g = int(bg_color_tuple[0][1] * (1 - factor) + bg_color_tuple[1][1] * factor)
        b = int(bg_color_tuple[0][2] * (1 - factor) + bg_color_tuple[1][2] * factor)
        draw.line([(0, y), (tw, y)], fill=(r, g, b))

    # Vẽ các hoa văn công nghệ nhẹ nhàng (thế giới AI)
    grid_color = (255, 255, 255, 25)
    for gx in range(0, tw, 80):
        draw.line([(gx, 0), (gx, th)], fill=(r + 15, g + 15, b + 20), width=1)
    for gy in range(0, th, 80):
        draw.line([(0, gy), (tw, gy)], fill=(r + 15, g + 15, b + 20), width=1)

    # Đặt mascot Stickman ở vị trí trung tâm
    # Mascot reference giữ tỉ lệ
    mw, mh = mascot_img.size
    scale = min((tw * 0.75) / mw, (th * 0.55) / mh)
    new_mw, new_mh = int(mw * scale), int(mh * scale)
    resized_mascot = mascot_img.resize((new_mw, new_mh), Image.Resampling.LANCZOS)

    # Offset vị trí hơi biến chuyển theo từng cảnh
    offset_x = (tw - new_mw) // 2
    offset_y = (th - new_mh) // 2 - 40
    if scene_num % 2 == 1:
        offset_x += 10
    else:
        offset_x -= 10

    if resized_mascot.mode == 'RGBA':
        img.paste(resized_mascot, (offset_x, offset_y), resized_mascot)
    else:
        img.paste(resized_mascot, (offset_x, offset_y))

    # Lưu ảnh phân cảnh
    img.save(output_path, "PNG", quality=95)
    print(f"   ✓ Đã tạo ảnh phân cảnh {scene_num}: {output_path}")


def produce_complete_demo_video():
    print("=" * 65)
    print("🎬 BẮT ĐẦU SẢN XUẤT VIDEO HOÀN CHỈNH TỰ ĐỘNG (END-TO-END)")
    print("   Nhân vật chính: Người que Stickman áo xanh (#8CCFE8)")
    print("   Động cơ chuyển động: Visual Beats Engine")
    print("=" * 65)

    topic = "Anh chàng người que áo xanh đi lạc trong thế giới AI"
    print(f"\n[1/5] Biên soạn kịch bản với Ollama...")
    print(f"   Chủ đề: \"{topic}\"")
    
    # 1. Gọi sinh kịch bản
    success, script_data = generate_script(topic=topic, style_preset="Minimalist stickman illustration, navy outline")
    if not success or "scenes" not in script_data or not script_data["scenes"]:
        print("   ⚠ Ollama phản hồi chậm hoặc chưa đúng format, sử dụng kịch bản phân cảnh chuẩn tối ưu:")
        scenes_def = [
            {
                "scene_num": 1,
                "narration": "Chào mọi người! Tôi là anh chàng người que áo xanh, hôm nay tôi lỡ bước chân vào thế giới AI kỳ bí.",
                "video_prompt": "Stickman CH01 in light blue shirt looking curious at glowing digital matrix portals, minimalist"
            },
            {
                "scene_num": 2,
                "narration": "Ở đây, mọi hình ảnh và âm thanh đều được sinh ra từ những dòng lệnh siêu tốc.",
                "video_prompt": "Stickman CH01 pointing happily at floating AI algorithms and colorful data streams"
            },
            {
                "scene_num": 3,
                "narration": "Với Google Flow và nhịp Visual Beats, từng bước đi của tôi trở nên sống động hơn bao giờ hết!",
                "video_prompt": "Stickman CH01 dancing enthusiastically with visual beats motion effect in futuristic studio"
            },
            {
                "scene_num": 4,
                "narration": "Hãy bấm theo dõi kênh ngay hôm nay để đón xem nhiều chuyến phiêu lưu hấp dẫn nhé!",
                "video_prompt": "Stickman CH01 waving goodbye with a big cheerful smile, subscribe button graphics"
            }
        ]
    else:
        scenes_def = script_data["scenes"][:4] # Lấy 4 cảnh đầu để sản xuất video Shorts chuẩn

    print(f"   ✓ Kịch bản gồm {len(scenes_def)} phân cảnh.")

    # 2. Tạo âm thanh lồng tiếng TTS
    print(f"\n[2/5] Lồng tiếng AI (Edge-TTS giọng Nữ vi-VN-HoaiMyNeural)...")
    audio_dir = Path(TEMP_DIR) / "demo_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    for sc in scenes_def:
        s_num = sc["scene_num"]
        txt = sc["narration"]
        out_aud = str(audio_dir / f"scene_{s_num}.mp3")
        if not os.path.exists(out_aud):
            ok_tts, path_tts = generate_tts(text=txt, output_path=out_aud, voice="vi-VN-HoaiMyNeural")
            if not ok_tts:
                raise RuntimeError(f"Lỗi tạo TTS scene {s_num}: {path_tts}")
            sc["audio_path"] = path_tts
        else:
            sc["audio_path"] = out_aud
        print(f"   ✓ Scene {s_num} TTS hoàn tất.")

    # 3. Phân tích timestamps từng từ (Word-level timestamps)
    print(f"\n[3/5] Phân tích âm thanh lấy mốc thời gian phụ đề (Faster-Whisper)...")
    all_words = []
    cumulative_time = 0.0

    for sc in scenes_def:
        from moviepy.editor import AudioFileClip
        a_clip = AudioFileClip(sc["audio_path"])
        duration = float(a_clip.duration)
        a_clip.close()
        sc["audio_duration"] = duration

        ok_whisp, words_or_err = get_word_timestamps(sc["audio_path"], language="vi")
        words = words_or_err if (ok_whisp and isinstance(words_or_err, list)) else []

        # Đẩy mốc thời gian từ vào danh sách toàn bài
        for w in words:
            all_words.append({
                "word": w["word"],
                "start": w["start"] + cumulative_time,
                "end": w["end"] + cumulative_time
            })
        cumulative_time += duration
        print(f"   ✓ Scene {sc['scene_num']}: Thời lượng {duration:.2f}s ({len(words)} từ)")

    # 4. Chuẩn bị hình ảnh cho nhân vật Stickman
    print(f"\n[4/5] Khởi tạo khung hình nhân vật Người Que Áo Xanh...")
    mascot_path = ROOT_DIR / "assets" / "characters" / "channel-mascot" / "reference-v1.png"
    if not mascot_path.exists():
        raise FileNotFoundError(f"Không tìm thấy mascot: {mascot_path}")

    mascot_img = Image.open(mascot_path)
    img_dir = Path(TEMP_DIR) / "demo_images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Bảng màu background tương phản đẹp cho từng phân cảnh
    palettes = [
        ((235, 245, 255), (190, 220, 245)), # Xanh nhạt sáng
        ((250, 240, 255), (225, 205, 250)), # Tím nhạt công nghệ
        ((240, 255, 245), (200, 245, 220)), # Xanh ngọc tươi mát
        ((255, 248, 235), (255, 225, 195)), # Vàng cam ấm áp
    ]

    for idx, sc in enumerate(scenes_def):
        s_num = sc["scene_num"]
        out_img = str(img_dir / f"scene_{s_num}.png")
        bg_pal = palettes[idx % len(palettes)]
        create_stickman_scene_frame(
            mascot_img=mascot_img,
            scene_num=s_num,
            bg_color_tuple=bg_pal,
            scene_label=sc.get("video_prompt", ""),
            output_path=out_img,
            target_size=(720, 1280)
        )
        sc["image_path"] = out_img
        sc["is_video"] = False

    # 5. Render Video Hoàn Chỉnh với Visual Beats Engine
    print(f"\n[5/5] Render Video với Visual Beats & Subtitles (MoviePy + FFmpeg)...")
    success, final_vids, err = compile_video_pipeline(
        scenes=scenes_def,
        words_timestamps=all_words,
        max_duration=60.0,
        orientation="vertical"
    )

    if not success or not final_vids:
        print(f"\n❌ [ERROR] Render thất bại: {err}")
        return None

    final_path = final_vids[0]
    file_size_mb = os.path.getsize(final_path) / (1024 * 1024)

    print("\n" + "=" * 65)
    print("🎉 SẢN XUẤT VIDEO HOÀN TẤT THÀNH CÔNG RỰC RỠ!")
    print(f"📁 Video thành phẩm: {final_path}")
    print(f"📊 Dung lượng file: {file_size_mb:.2f} MB")
    print(f"⏱️ Tổng thời lượng: {cumulative_time:.2f} giây")
    print("=" * 65)
    return final_path


if __name__ == "__main__":
    produce_complete_demo_video()
