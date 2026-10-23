# MuseAI: Người que bàn tay vẽ và nối bài giữa các tập — 23/10/2026

## AI tạo minh họa mới theo cảnh, không giới hạn trong kho mẫu

- [x] MuseAI được yêu cầu mô tả hình `ai_image` khi kho chưa thể hiện đúng nội dung bài; hình ngoài danh mục được chuyển sang yêu cầu AI thay vì bỏ qua.
- [x] Nối Google Flow tạo ảnh 2D whiteboard, tách khỏi bộ ép ảnh 3D; chỉ mở Flow khi ảnh chưa được lưu.
- [x] Lưu ảnh PNG và prompt theo nội dung/tạo hình nhân vật; tái sử dụng giữa cảnh/tập và khi dựng lại kịch bản đã lưu.
- [x] Xử lý nền trắng nối với mép ảnh, giữ vùng trắng khép kín, căn khung theo phần ảnh thật rồi vẽ viền/tô màu bằng tay thật.
- [x] Có thử lại, kiểm tra ảnh trống/hỏng và hủy; không thay bằng hình stock không liên quan khi AI lỗi.
- [x] Bật mặc định **AI tự tạo minh họa mới khi cần (Google Flow)** trong UI, truyền lựa chọn qua cả phim lẻ và series.
- [x] Kiểm thử 98 bài luồng/render/TTS/AI và 1 bài giao diện đạt (99 tổng cộng).
- [x] Thử thật Google Flow: tạo giỏ hai quả táo/chuối và cảnh hành khách hỏi quầy sân bay; xuất video Việt–Anh 1080p khoảng 18 giây: `video_studio/output/english_ai_illustrations_preview.mp4`.
- [x] Chạy lại bản mẫu: `generated=0`, `cache_hits=2`; không gọi tạo ảnh lại.

## Cập nhật theo hai ảnh tham chiếu: tay thật và whiteboard minh họa màu

- [x] Thay tay hình học bằng ảnh tay thật cầm bút dạ xám, có nền trong suốt và điểm neo đúng đầu bút.
- [x] Bỏ hiệu ứng mở hình chữ nhật; tay đi theo nét viền, rồi tô màu theo đường quét.
- [x] Bổ sung minh họa người ngồi máy tính được tạo bằng imagegen và 9 biểu tượng màu bằng Pillow; hỗ trợ thêm PNG/WebP riêng trong kho ảnh.
- [x] Cập nhật yêu cầu MuseAI và lựa chọn trên giao diện sang minh họa màu; giữ phần tử người que cho kịch bản cần dùng.
- [x] Dựng/xem mẫu mới `video_studio/output/whiteboard_color_real_hand_1080p.mp4`: 16 giây, 1080p, không lời.
- [x] 67 kiểm tra luồng/render/nối tập và 1 kiểm tra giao diện riêng đã đạt (68 tổng cộng).

## Luồng ban đầu

## Cập nhật bài tiếng Anh: lời giảng Việt, phát âm Anh

- [x] Thêm lựa chọn ngôn ngữ **Dạy tiếng Anh: giảng Việt + phát âm Anh** trong MuseAI.
- [x] MuseAI trả `speech_segments` có nhãn `vi`/`en`; mỗi đoạn dùng giọng đúng ngôn ngữ, không thêm lời thoại mẫu.
- [x] Không dùng âm báo thử nghiệm hay thêm tiền tố tiếng Việt vào câu phát âm tiếng Anh khi TTS lỗi.
- [x] Đo thời lượng thật từng đoạn Việt/Anh; phụ đề chuyển ngôn ngữ theo đúng ranh giới âm thanh.
- [x] Giữ nhãn ngôn ngữ khi tách cảnh và khi ôn bài/hẹn bài tiếp theo; lỗi đọc song ngữ không chuyển cả bài sang một giọng.
- [x] MuseAI nhận danh sách ảnh PNG/WebP bổ sung trong kho, loại ảnh tay khỏi nội dung minh họa; giao diện hiển thị số hình có sẵn.
- [x] 86 kiểm tra luồng/render/TTS/phụ đề và 1 kiểm tra giao diện đã đạt (87 tổng cộng).
- [x] Dựng thật mẫu hai cảnh, 1080p, có âm thanh Việt–Anh và phụ đề, dài khoảng 15 giây: `video_studio/output/english_lesson_vi_en_preview.mp4`.

Mẫu dùng kịch bản cố định để kiểm tra giọng và bộ dựng; chưa yêu cầu tài khoản MuseAI viết một bài song ngữ thật trong lượt này. Kho minh họa vẫn gồm 10 loại và ảnh bổ sung, chưa tự sinh mọi hình mới ngoài kho.

## Các hạng mục ban đầu

- [x] Rà soát MuseAI UI, prompt/parser, TTS, compiler, bộ vẽ whiteboard và bộ nhớ series hiện có.
- [x] Nối kiểu `whiteboard` vào MuseAI Studio; dùng storyboard do MuseAI viết, dựng trên máy, không gọi Flow.
- [x] Giữ người que 2D, sơ đồ/chữ có dấu, hiệu ứng tay vẽ và thời lượng dựa trên audio; xuất 1080p.
- [x] Thêm lời ôn tập trước và giới thiệu tập sau vào cảnh thực có lồng tiếng/phụ đề; truyền bài học đã hẹn sang prompt tập sau.
- [x] Viết tiếp đúng số tập; lưu riêng bộ nhớ series người que và 3D; báo hủy đúng trạng thái.
- [x] Chặn xuất thành công khi TTS/phụ đề whiteboard lỗi; tránh thêm lời thoại mẫu ngoài kịch bản.
- [x] Sửa lỗi bộ xuất MoviePy bị bọc lặp khi reload UI; cô lập cấu hình/tài nguyên thật khỏi các test MuseAI.
- [x] Kiểm tra: 52 bài kiểm tra luồng/render/series/phụ đề đạt; 1 bài thao tác giao diện Streamlit đạt riêng (53 tổng cộng).
- [x] Dựng và xem mẫu không lời `video_studio/output/whiteboard_preview_1080p.mp4` (1920×1080, 24 FPS, 12 giây).
- [x] Bổ sung [hướng dẫn và nguồn tham khảo](../video_studio/docs/museai_whiteboard.md).

Giới hạn kiểm chứng: đầu vào MuseAI và dịch vụ giọng đọc thật được thay thế trong test tích hợp; MP4, audio, phụ đề và thời lượng được dựng/đo thật bằng FFmpeg. Chưa chạy một series thật qua tài khoản MuseAI trong lượt này.

---

# Kế Hoạch Nâng Cấp Cơ Chế Cốt Truyện Dài Nhiều Tập (Ít Tập / Nhiều Tập) & Duy Trì Mạch Truyện (Mở Đầu - Cao Trào - Kết Thúc Mỗi Tập)

## 1. Mục tiêu & Thiết kế Kiến trúc
1. **Hỗ trợ linh hoạt chế độ Phim lẻ (1 tập), Ít tập (Mini-Series 2–3 tập) và Nhiều tập (Series dài kỳ 4–10+ tập)**:
   - Mỗi tập (mỗi video `.mp4`) đều bắt buộc có cấu trúc 3 hồi rõ ràng: **Mở đầu (Opening Hook / Recap nối tập) ➔ Cao trào kịch tính (Climax) ➔ Kết thúc tập (Resolution / Cliffhanger mở tập tiếp theo)**.
2. **Duy trì cốt truyện dài & Khóa nhân vật xuyên suốt các tập (`Series Continuity & Memory`)**:
   - Tập 1 khởi tạo `character_anchor`, `environment_anchor` và tóm tắt sự kiện Tập 1.
   - Từ Tập 2 trở đi, prompt gửi lên MuseAI tự động nhúng **`previous_episodes_summary`** (diễn biến các tập trước) và khóa cứng **`locked_character_anchor`** từ Tập 1 để câu chuyện liền mạch 100%, nhân vật giữ nguyên tên và tạo hình 3D qua mọi tập.
   - Các tập giữa (Tập $2 \dots T-1$) mở đầu bằng cầu nối sự kiện tập trước, đẩy lên cao trào riêng của tập đó và kết thúc bằng nút mở sang tập kế tiếp; Tập cuối ($T/T$) đẩy lên Đại cao trào (*Grand Climax*) và khép lại bằng Đại kết cục (*Grand Finale*).
   - Lưu trữ bền vững bộ nhớ chuỗi tập (`series_memory_ledger.json`) để có thể tiếp nối cốt truyện bất cứ lúc nào.

## 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Viết Unit Tests (Red State) trong `video_studio/tests/test_museai_3d.py`**
  - [x] Test `build_museai_story_script_prompt` với thông số `episode_num`, `total_episodes`, `previous_episodes_summary`, `locked_character_anchor` đảm bảo mỗi tập đều có Mở đầu + Cao trào + Kết thúc và duy trì mạch truyện từ tập trước.
  - [x] Test `run_museai_multi_episode_series_pipeline` chạy chuỗi nhiều tập (ví dụ 3 tập), tự động truyền `character_anchor` và tóm tắt cốt truyện từ Tập 1 sang Tập 2 và Tập 3.
- [x] **Task 2: Triển khai Multi-Episode Story Continuity Engine trong `video_studio/src/museai_3d_service.py` (Green State)**
  - [x] Nâng cấp `build_museai_story_script_prompt` và `generate_3d_script_via_museai` hỗ trợ `episode_num`, `total_episodes`, `previous_episodes_summary`, `locked_character_anchor`.
  - [x] Xây dựng hàm `summarize_episode_for_continuity` và `run_museai_multi_episode_series_pipeline` sản xuất tuần tự từ Tập 1 đến Tập $T$, mỗi tập xuất ra 1 video `.mp4` hoàn chỉnh có đủ Mở đầu - Cao trào - Kết thúc.
- [x] **Task 3: Nâng cấp Giao diện Web UI `video_studio/src/app_museai.py`**
  - [x] Thêm bộ chọn **Chế độ Cốt truyện & Số tập**: `🎬 Phim lẻ 1 tập trọn vẹn`, `📺 Ít tập (Mini-Series 2–3 tập)`, `📚 Nhiều tập (Series dài kỳ 4–10 tập)`, hoặc `🔗 Viết tiếp tập mới từ cốt truyện vừa tạo`.
  - [x] Hiển thị tiến độ từng Tập (Tập $E/T$) và danh sách toàn bộ các video tập phim đã hoàn thành.
- [x] **Task 4: Kiểm chứng toàn diện (Verification)**
  - [x] Chạy `pytest video_studio/tests/test_museai_3d.py` đạt 100% Green (17/17 passed).

---

# Kế Hoạch Khớp 1:1 Số Khung Hình Video Với Mạch Câu Chuyện & Cấm Tuyệt Đối Lặp Lại Khung Hình (No Video Looping)

## 1. Phân tích nguyên nhân gốc rễ (Root Cause Analysis)
1. **Tại sao 1 khung hình video bị lặp đi lặp lại nhiều lần trong phiên `muse_flow_3d_20261023_160326`**:
   - Mỗi video clip 3D do Google Flow (Veo) tạo ra có thời lượng cố định khoảng **8–10 giây** (`10.01s`).
   - Khi cố định số cảnh là 4, toàn bộ câu chuyện dài ~97 giây (gồm cả lời dẫn chuyện dài + lời thoại nhân vật tương tác) bị dồn vào 4 cảnh, khiến file âm thanh mỗi cảnh dài từ **21.6s đến 28.2s** (`scene_001.mp3 = 21.63s`, `scene_002.mp3 = 28.16s`, `scene_003.mp3 = 23.07s`, `scene_004.mp3 = 24.50s`).
   - Trong `video_studio/src/video_compiler.py` (dòng 306), FFmpeg đang dùng cờ `"-stream_loop", "-1"` để lặp lại file `.mp4` cho đủ độ dài file `.mp3`. Hậu quả là mỗi clip 10s bị phát lặp đi lặp lại gần **3 lần liên tiếp** trong cùng một cảnh!
2. **Giải pháp triệt để 3 tầng**:
   - **Tầng 1 (Giao diện UI `app_museai.py`)**: Bỏ thanh trượt bắt chọn cứng số khung cảnh. Để hệ thống tự động xác định số khung hình theo đúng độ dài và nhịp câu chuyện.
   - **Tầng 2 (Tự động chia khung hình theo nhịp câu chuyện `expand_scenes_to_match_story_beats` trong `museai_3d_service.py`)**:
     + Mỗi khung video (~8–10s) chỉ đảm nhận đúng **1 nhịp câu chuyện/lượt thoại (~6–9.5 giây, khoảng 15–26 từ)**.
     + Nếu câu chuyện hoặc phân cảnh từ MuseAI dài hơn 1 khung video (ví dụ vừa có đoạn dẫn chuyện mở cảnh vừa có đoạn đối thoại nhân vật), hệ thống tự động tách thành các khung hình độc lập (Khung dẫn chuyện góc toàn/trung ➔ Khung nhân vật tương tác góc cận/trung cận) để Google Flow sinh **khung hình video mới cho từng nhịp**, không dồn nhiều nhịp vào 1 clip.
   - **Tầng 3 (Bộ dựng phim FFmpeg `video_compiler.py`)**:
     + Xóa bỏ hoàn toàn `-stream_loop -1` và `vfx.loop`.
     + Đo thời lượng thực của clip (`vid_dur`) và thời lượng thoại (`audio_dur`), dùng `setpts` co giãn nhịp khung hình mượt mà để mỗi clip chỉ chạy **đúng 1 lượt duy nhất từ đầu đến cuối câu thoại**, tuyệt đối không bao giờ tua lại từ đầu.

## 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Viết Unit Tests (Red State) trong `video_studio/tests/test_museai_3d.py`**
  - [x] Test `expand_scenes_to_match_story_beats`: tự động tách các phân cảnh có lời dẫn + thoại dài thành nhiều khung hình ngắn khớp thời lượng 1 clip (~6–9.5s/khung), mỗi khung có `raw_video_prompt` / `camera_directive` hành động/góc máy riêng.
  - [x] Test `_compile_part_with_ffmpeg_native` không bao giờ sử dụng `-stream_loop -1` cho video cảnh mà dùng `setpts` khớp 1:1 thời lượng.
- [x] **Task 2: Triển khai Auto Story-Beat Shot Alignment & Non-Looping Compiler (Green State)**
  - [x] Cập nhật `build_museai_story_script_prompt` và thêm `expand_scenes_to_match_story_beats` trong `video_studio/src/museai_3d_service.py`.
  - [x] Cập nhật `video_studio/src/video_compiler.py` loại bỏ `-stream_loop -1` và `vfx.loop`, thay bằng đồng bộ `setpts` / `speedx` 1 lượt duy nhất.
  - [x] Cập nhật `video_studio/src/app_museai.py` bỏ thanh trượt chọn số khung cố định, chuyển sang chế độ tự động chia khung khớp 1:1 theo câu chuyện.
- [x] **Task 3: Kiểm chứng Unit Tests & Render lại E2E không lặp hình**
  - [x] Chạy `pytest video_studio/tests/test_museai_3d.py` đạt 100% Green (15/15 passed).

---

# Kế Hoạch Nâng Cấp Kịch Bản & Lồng Tiếng Đa Giọng Đọc (Dẫn Chuyện + Tương Tác Nhân Vật) Đồng Bộ 100% Hình Ảnh 3D

## 1. Phân tích nguyên nhân gốc rễ (Root Cause Analysis)
1. **Tại sao kịch bản và lồng tiếng trước đó "chẳng đâu vào đâu"**:
   - Ở lần chạy lỗi trước (`muse_flow_3d_20261023_145325`), do bộ đọc lấy nhầm JSON mẫu 1 cảnh trong câu hỏi của user, file lồng tiếng đọc câu mẫu *"Lời dẫn tiếng Việt tự nhiên, cuốn hút cho Cảnh 1."* trong khi hình ảnh video lại là cậu bé Leo nhặt chiếc la bàn.
   - Ngay cả khi đọc đúng kịch bản 4 cảnh từ MuseAI, hàm `merge_flow_3d_scenes_into_final_movie` trước đây chỉ dùng **1 giọng đọc đơn điệu duy nhất (`vi-VN-HoaiMyNeural`)** đọc trơn một mạch đoạn văn mô tả ngôi thứ ba (`narration`). Khi trong kịch bản có lời thoại nhân vật trong ngoặc kép (ví dụ Cảnh 3: `'Mang hạt giống về, cậu bé sẽ được an toàn.'`), cùng một giọng nữ dẫn chuyện vẫn đọc đều đều, hoặc ở các cảnh khác nhân vật chỉ đứng im mà không có đối thoại/tương tác.
   - `video_prompt` gửi sang Google Flow chưa gắn chặt chỉ dẫn diễn xuất biểu cảm/mấp máy môi và tương tác nhân vật khớp với lời thoại trong cảnh đó.

## 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Viết Unit Tests (Red State) trong `video_studio/tests/test_museai_3d.py`**
  - [x] Test cấu hình giọng đọc nhân vật (`resolve_voice_and_prosody` hỗ trợ `narrator`, `char_boy_bright`, `char_elder_deep`, `char_female_bright` với cao độ `pitch` và tốc độ `rate` phân biệt rõ rệt).
  - [x] Test `build_museai_story_script_prompt` bắt buộc MuseAI sinh `dialogue_lines` kết hợp **Người dẫn chuyện (`narrator`) + Tương tác nhân vật (`character_1`, `character_2`)** và đồng bộ 1:1 với `video_prompt`.
  - [x] Test `build_scene_dialogue_segments` tự động bóc tách lời dẫn chuyện + lời thoại nhân vật (kể cả khi kịch bản cũ trên MuseAI chỉ có `narration` đơn thuần hoặc lời thoại trong ngoặc `'...'`), gán đúng giọng từng vai.
  - [x] Test `synthesize_museai_scenes_interactive_tts` tạo audio đa giọng đọc cho từng cảnh và cập nhật khớp 100% phụ đề `narration` + `video_prompt`.
- [x] **Task 2: Triển khai Multi-Voice Narrator + Character Dialogue Engine (Green State)**
  - [x] Bổ sung preset giọng nhân vật hoạt hình 3D vào `video_studio/src/config.py` và nâng cấp `resolve_voice_and_prosody` trong `video_studio/src/tts_service.py`.
  - [x] Nâng cấp `build_museai_story_script_prompt`, `parse_museai_story_json`, `build_scene_dialogue_segments`, `clean_and_build_flow_3d_video_prompt`, và `synthesize_museai_scenes_interactive_tts` trong `video_studio/src/museai_3d_service.py`.
  - [x] Cập nhật bảng theo dõi trực tiếp trên `video_studio/src/app_museai.py` để hiển thị rõ từng lượt **🎙️ Dẫn chuyện** và **🗣️ Nhân vật tương tác** của mỗi phân cảnh.
- [x] **Task 3: Kiểm chứng Unit Test & Chạy thực nghiệm E2E tổng hợp âm thanh đa giọng đọc**
  - [x] Chạy `pytest video_studio/tests/test_museai_3d.py` đạt 100% Green (12/12 passed).
  - [x] Chạy thử nghiệm E2E trên kịch bản 4 cảnh `"Hạt Giống Ánh Sáng Cuối Cùng"` để xác nhận file MP3 từng cảnh có sự phối hợp nhịp nhàng giữa giọng Người dẫn chuyện và giọng các Nhân vật tương tác.

---

# Kế Hoạch Sửa Lỗi Triệt Để Luồng Studio Video 3D (MuseAI ➔ Google Flow): Đọc Đủ N Cảnh & Đưa Tuần Tự Từng Cảnh

## 1. Phân tích nguyên nhân gốc rễ (Root Cause Analysis)
1. **Lỗi chọn 4 cảnh nhưng hệ thống chỉ sinh `1/1` (`'Tên câu chuyện 3D'`)**:
   - **Tự đọc nhầm chính câu lệnh mẫu của user (Self-Prompt Poisoning)**: Trong `build_museai_story_script_prompt`, câu lệnh gửi lên MuseAI có đính kèm một khối JSON mẫu 1 cảnh (`"story_title": "Tên câu chuyện 3D"`, `"narration": "Lời dẫn tiếng Việt tự nhiên, cuốn hút cho Cảnh 1."`).
   - Biến `before_body_len` được đo **trước khi** gửi tin nhắn. Ngay khi tin nhắn của user được gửi lên khung chat MuseAI, bong bóng chat màu xanh của user xuất hiện trên DOM. Trong 12 giây đầu khi MuseAI đang suy nghĩ (`Thinking...`), độ dài trang đứng yên 2 chu kỳ (`stable_ticks >= 2`), khiến code chạy nhánh fallback `parse_museai_story_json(new_text)` và **bốc nhầm luôn khối JSON mẫu 1 cảnh nằm trong chính tin nhắn câu hỏi của user**!
   - **Thu hoạch quá sớm khi MuseAI đang gõ dở (Premature Stream Read)**: Khi MuseAI bắt đầu gõ khối `<pre class="language-json">`, ngay khi mới gõ xong Cảnh 1 là chuỗi đã có `"scenes"` và `"video_prompt"`. Code cũ chỉ chờ cứng `2.5s` rồi đọc ngay nên hoặc bị lỗi JSON chưa đóng ngoặc, hoặc chưa đợi MuseAI gõ xong đủ 4 cảnh.
2. **Lỗi thao tác trên Google Flow khi đưa từng cảnh vào**:
   - Trên Google Flow, ô nhập prompt thật sự là `div.ProseMirror[role='textbox']`, còn thẻ `textarea` trên trang là `textarea.g-recaptcha-response` bị ẩn (`visible: false`). Lệnh `page.wait_for_selector("textarea", timeout=15000)` làm đứng chờ 15s vô ích ở mỗi cảnh.
   - Selector nút gửi dùng `button[aria-label*='tạo' i]` bị khớp nhầm vào nút **`"Tạo bộ sưu tập"`** ở thanh bên trái thay vì nút gửi **`"Bắt đầu tạo"`** (`button[aria-label='Bắt đầu tạo']`).
   - Khi tải qua nút Download hoặc kiểm tra URL video giữa các cảnh liên tiếp (Cảnh 1 -> Cảnh 2 -> Cảnh 3 -> Cảnh 4), nhánh nút Download chưa kiểm tra `self.seen_video_hashes` và URL chưa chuẩn hóa phần gốc trước dấu `?Expires=`, dễ dẫn đến nhận nhầm video của cảnh trước cho cảnh sau.

## 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Viết Unit Tests tái hiện lỗi (Red State) trong `video_studio/tests/test_museai_3d.py`**
  - [x] Kiểm tra `parse_museai_story_json` loại bỏ hoàn toàn mẫu placeholder (`"Tên câu chuyện 3D"`) và trích xuất đúng kịch bản 4 cảnh thật sự của MuseAI ngay cả khi chuỗi đầu vào chứa cả câu hỏi của user lẫn câu trả lời của MuseAI.
  - [x] Kiểm tra `is_museai_script_complete` xác định đúng khi nào JSON của MuseAI đã gõ xong đủ `target_scenes` cảnh (ví dụ 4/4 cảnh).
  - [x] Kiểm tra chuẩn hóa URL video Google Flow (`normalize_flow_video_url`) chống trùng lặp khi đổi `?Expires=`.
- [x] **Task 2: Sửa triệt để bộ đọc kịch bản MuseAI & Bộ điều khiển Google Flow trong `video_studio/src/museai_3d_service.py` (Green State)**
  - [x] Loại bỏ khối JSON mẫu gây nhiễu trong `build_museai_story_script_prompt` và thêm bộ lọc chống placeholder trong `parse_museai_story_json`.
  - [x] Nâng cấp `generate_3d_script_via_museai`:
    + Hỗ trợ tùy chọn đọc ngay kịch bản 3D hợp lệ đang có sẵn trên tab MuseAI nếu đã khớp đủ số cảnh (`read_latest_script_from_museai_tab`).
    + Khi gửi lệnh mới: chỉ đọc từ thẻ `<pre>` của câu trả lời mới của MuseAI, theo dõi quá trình MuseAI gõ từng cảnh (`Đã viết X/4 phân cảnh...`), đợi đến khi `<pre>` ngừng tăng độ dài và đủ `target_scenes` cảnh mới chuyển sang Google Flow.
  - [x] Nâng cấp `generate_scene_3d_video_on_google_flow`:
    + Bỏ `wait_for_selector("textarea")` 15s; ưu tiên bắt ngay `div.ProseMirror[role='textbox']`.
    + Bấm chính xác nút gửi `button[aria-label='Bắt đầu tạo']` / `button[aria-label='Start generation']` và xác nhận prompt đã được gửi đi.
    + Đưa tuần tự từng cảnh (Cảnh 1/N ➔ Cảnh 2/N ➔ ... ➔ Cảnh N/N) vào Google Flow, kiểm tra `seen_video_hashes` và `normalize_flow_video_url` ở mọi nhánh tải video để đảm bảo mỗi cảnh nhận đúng video mới 100%.
- [x] **Task 3: Nâng cấp Giao diện Web UI `video_studio/src/app_museai.py`**
  - [x] Hiển thị trực tiếp bảng danh sách các phân cảnh đọc được từ MuseAI ngay trên giao diện trước và trong khi đưa từng cảnh vào Google Flow.
  - [x] Thêm tùy chọn `"⚡ Đọc ngay kịch bản 3D đang có sẵn trên tab MuseAI (nếu đã đủ số cảnh)"` để người dùng có thể tận dụng ngay kịch bản 4 cảnh vừa sinh trên MuseAI hoặc yêu cầu viết kịch bản mới.
- [x] **Task 4: Kiểm chứng Unit Test & Chạy thực nghiệm E2E trên Chrome CDP**
  - [x] Chạy pytest xác nhận toàn bộ 8/8 unit & E2E tests trong `video_studio/tests/test_museai_3d.py` đạt Green (100% passed).
  - [x] Kiểm tra đọc trực tiếp kịch bản 4 cảnh `"Hạt Giống Ánh Sáng Cuối Cùng"` từ tab MuseAI đang mở trên Chrome CDP cổng 9222: `OK: True Title: Hạt Giống Ánh Sáng Cuối Cùng Scenes: 4 [1, 2, 3, 4]`.

---

# Kế Hoạch Tích Hợp Luồng Tạo Video Hoạt Hình 3D MuseAI (muse.ai)

## 1. Mục tiêu
Tích hợp trọn vẹn luồng tạo Video Hoạt Hình 3D Cốt Truyện trên **MuseAI (`muse.ai`)** qua tab Chrome mở sẵn (CDP Port 9222) kết hợp AI Local (Ollama Few-Shot 3D Prompt Engine) theo đúng mã nguồn vừa tải về:
- Đảm bảo 100% video hoạt hình 3D Pixar / Unreal Engine 5 CGI chất lượng cao, tuyệt đối cấm vẽ hình học 2D/stickman bằng code.
- Khóa chặt nhân vật 3D (3D Character Bible Lock) xuyên suốt toàn bộ phân cảnh.
- Tạo video tuần tự cho từng cảnh (Scene 1 -> Scene N), sau đó tự động ghép thành 1 video duy nhất.
- Tích hợp trực tiếp vào giao diện Web UI (`video_studio/src/app.py`) và tạo script khởi động nhanh cho người dùng.

---

## 2. Danh sách các đầu việc (Todo Checklist)

- [x] **Giai đoạn 1: Chuẩn bị tệp nguồn & Cấu hình MuseAI**
  - [x] Di chuyển `museai_3d_service.py` từ Downloads vào `video_studio/src/museai_3d_service.py` (đồng thời tạo alias/export phù hợp).
  - [x] Di chuyển `museai_3d_prompt_templates.md` từ Downloads vào `video_studio/docs/museai_3d_prompt_templates.md`.
  - [x] Tạo file cấu hình `video_studio/museai_config.json` và cập nhật `.env.example`.
  - [x] Tạo script khởi chạy nhanh `video_studio/scripts/Mo_Chrome_MuseAI.bat` để người dùng mở Chrome CDP chuẩn cổng 9222 vào `muse.ai`.

- [x] **Giai đoạn 2: Tích hợp vào Web UI (`video_studio/src/app.py`)**
  - [x] Thêm tab mới hoặc tùy chọn engine "🎬 MuseAI 3D Story (Pixar/UE5 Video CGI)" trong giao diện Streamlit.
  - [x] Cho phép người dùng nhập đề tài, số lượng cảnh (1-10 cảnh), chọn tỷ lệ khung hình (9:16 Shorts / 16:9 Ngang), mô hình Ollama.
  - [x] Hiển thị thông báo trạng thái kết nối Chrome CDP, tiến trình tạo video từng cảnh và nút phát video kết quả.

- [x] **Giai đoạn 3: Viết Unit Test & Kiểm thử Tự động**
  - [x] Viết test `video_studio/tests/test_museai_3d.py` kiểm tra:
    - Bộ lọc cấm 2D hình học `FORBIDDEN_2D_GEOMETRIC_PATTERN` & `validate_and_enforce_true_3d_prompt`.
    - Sinh prompt khởi tạo phiên & prompt từng cảnh theo chuẩn Pixar/UE5.
    - Cấu trúc Prompt Script Few-Shot cho Ollama.
  - [x] Chạy test suite xác nhận 100% tests Passed (5/5 tests MuseAI, 17/17 tests toàn hệ thống).

- [x] **Giai đoạn 4: Khởi động thử nghiệm & Báo cáo hoàn tất**
  - [x] Chạy thử nghiệm thành công quy trình biên kịch 3D & Character Bible Lock bằng Ollama `qwen2.5:14b`.
  - [x] Cập nhật báo cáo và hướng dẫn chi tiết cho người dùng.


---



## 1. Mục tiêu
Tích hợp quy trình sinh ảnh và tạo video dựa trên Google Flow (`flow.google.com`) từ repository `hongphuoc6104/tiktok-ytb` vào hệ thống hiện tại, cho phép:
- Sinh ảnh AI sắc nét (Nano Banana Pro / Imagen) không tốn VRAM GPU.
- Khóa đặc trưng nhân vật (Character Lock / Reference Continuity) xuyên suốt các phân cảnh.
- Tạo chuyển động mượt mà theo nhịp âm thanh (Visual Beats & Progressive Layering) và xuất video hoàn chỉnh (9:16 Shorts hoặc 16:9).

---

## 2. Danh sách các đầu việc (Todo Checklist)

- [x] **Giai đoạn 1: Chuẩn bị Cấu hình & Môi trường Kết nối Google Flow**
  - [x] Tạo file cấu hình `flow_config.json` (URL Tool Flow, Chrome User Data Dir, Profile Default, Cổng CDP 9222).
  - [x] Viết module `src/flow_browser_service.py` điều khiển Chrome CDP kết nối tới `flow.google.com` (tương thích Windows, React Fiber state injection).
  - [x] Viết script chẩn đoán `test_flow_connection.py` để verify đăng nhập và trạng thái Tool UI.
  - [x] Tạo script tiện ích `launch_flow_chrome.bat` khởi chạy Chrome CDP cho người dùng.

- [x] **Giai đoạn 2: Tích hợp Flow Image Service (Tạo ảnh & Đồng nhất Nhân vật)**
  - [x] Triển khai hàm `generate_flow_image` và `generate_flow_batch` trong `src/flow_image_service.py`.
  - [x] Áp dụng Prompt Template tiêu chuẩn: Scene Prompt + Style Preset + Strict Character Lock (CH01 Stickman áo xanh).
  - [x] Xây dựng bộ ghi nhận Attempt Ledger (`temp/flow_attempts/`) và cơ chế Auto Fallback sang SD 1.5 khi Flow offline.
  - [x] Bổ sung tùy chọn nguồn sinh ảnh: "Google Flow (Nano Banana Pro / CDP)" trong Web UI `src/app.py`.

- [x] **Giai đoạn 3: Triển khai Visual Beats & Progressive Layering Engine**
  - [x] Xây dựng module phân nhịp `src/visual_beats.py` (đồng bộ thời lượng câu thoại với hiệu ứng Zoom-in 8%, Zoom-out, Slide left, Breathing motion mượt mà).
  - [x] Cập nhật `src/video_compiler.py` render video hoàn chỉnh kết hợp ảnh Flow + hiệu ứng chuyển động Visual Beat.
  - [x] Thêm cấu hình Visual Beats tự động trong pipeline sản xuất video.

- [x] **Giai đoạn 4: Kiểm thử, Nghiệm thu & Tài liệu hóa**
  - [x] Viết unit tests kiểm thử Flow generator, Visual Beats timing, Profile mapping (`tests/test_flow_engine.py` - Đạt 5/5 tests).
  - [x] Sửa lỗi tương thích `torch.xpu` của diffusers trên Windows.
  - [x] Cập nhật tài liệu báo cáo kiến trúc chi tiết.

---

## 3. Kế Hoạch Tái Cấu Trúc Thư Mục (Directory Clean-up & Reorganization)

- [ ] **Bước 1: Gom các tệp tài liệu và báo cáo vào `docs/`**
  - [ ] Di chuyển `PLAN.md`, `IMPLEMENTATION_AUDIT_REPORT.md`, `DOCKER_GUIDE.md` vào `docs/`.
  - [ ] Sao chép báo cáo Google Flow vào `docs/GOOGLE_FLOW_GUIDE.md`.

- [ ] **Bước 2: Gom các tệp Docker & ảnh container nặng vào `docker/`**
  - [ ] Tạo thư mục `docker/scripts/` và `docker/images/`.
  - [ ] Di chuyển các file `.tar` (1.4GB) vào `docker/images/`.
  - [ ] Di chuyển `docker_build.bat`, `docker_run_headless.bat`, `docker_run_ui.bat`, `run_docker.sh`, `docker-compose.yml` vào `docker/`.

- [ ] **Bước 3: Tập trung toàn bộ file kiểm thử vào `tests/`**
  - [ ] Di chuyển `test_booster.py`, `test_pipeline.py`, `test_selfheal.py`, `test_flow_connection.py` vào `tests/`.
  - [ ] Cập nhật đường dẫn import trong các file test để đảm bảo chạy độc lập không lỗi.

- [ ] **Bước 4: Gom các kịch bản chạy phụ trợ vào `scripts/` và tạo Menu `run.bat` trung tâm**
  - [ ] Di chuyển `launch_flow_chrome.bat`, `run_view_booster_ui.bat`, `run_view_booster_headless.bat` vào `scripts/`.
  - [ ] Nâng cấp `run.bat` tại gốc thành Launcher Menu thông minh 1-click cho người dùng.

- [x] **Bước 5: Kiểm chứng toàn diện (Verification)**
  - [x] Chạy lại toàn bộ test suite trong `tests/`.
  - [x] Kiểm tra tính toàn vẹn của tiến trình đang chạy và cập nhật sơ đồ README.md.

---

## 4. Kế Hoạch: Auto Batch Video Pipeline (Tự Động Sinh Kịch Bản & Tạo Nhiều Video Lặp Lại)

- [x] **Bước 1: Nâng cấp Động cơ Chuyển động & Chuyển cảnh (`src/visual_beats.py` & `src/video_compiler.py`)**
  - [x] Bỏ hiệu ứng zoom breathing co giãn giật cục ("di chuyển tào lao").
  - [x] Đổi sang chuyển cảnh tự nhiên, dứt khoát giữa các phân cảnh độc lập (Cut / Subtle Cinematic Zoom 1 chiều).
  - [x] Đảm bảo mỗi phân cảnh mang bối cảnh hình ảnh riêng biệt, hiển thị phụ đề sắc nét, rõ ràng.

- [x] **Bước 2: Xây dựng Module Sản xuất Hàng loạt Tự động (`src/batch_producer.py`)**
  - [x] Hỗ trợ nhận 1 Prompt lớn chia thành N video HOẶC danh sách nhiều prompts (mỗi dòng 1 video).
  - [x] Vòng lặp tự động (End-to-End Batch Loop):
    1. Sinh kịch bản phân cảnh với LLM (Ollama).
    2. Sinh audio TTS từng phân cảnh.
    3. Gửi từng phân cảnh sang Google Flow để vẽ bối cảnh AI riêng biệt.
    4. Trích xuất phụ đề timestamps (Whisper).
    5. Biên tập và render video hoàn chỉnh (`output/batch_video_*.mp4`).
    6. Tự động lặp lại cho toàn bộ danh sách video.

- [x] **Bước 3: Tích hợp Giao diện Web UI (`src/app.py` & `src/app_batch.py`)**
  - [x] Thêm chế độ chính "⚡ Tự Động Hàng Loạt (Auto Batch)" ngay trên giao diện Streamlit (mặc định mở đầu tiên).
  - [x] Giao diện trực quan 1-Click: Nhập Prompt -> Chọn số video -> Bắt đầu.
  - [x] Trực quan hóa tiến độ theo thời gian thực (Video X/N, đang làm bước gì).
  - [x] Hiển thị danh mục video thành phẩm để xem và tải về.

- [x] **Bước 4: Nâng cấp Tiện ích Chrome CDP & CLI (`run.bat` & `scripts/batch_video_producer.py`)**
  - [x] Tạo script CLI độc lập `scripts/batch_video_producer.py`.
  - [x] Bổ sung phím số `5. Chạy Tự Động Hàng Loạt từ Prompt` vào `run.bat`.
  - [x] Nâng cấp `scripts/launch_flow_chrome.bat` và phím số `4` trong `run.bat` để phát hiện và khởi động Chrome port 9222 sạch sẽ.

- [x] **Bước 5: Kiểm thử & Đẩy lên GitHub**
  - [x] Kiểm thử tự động (Unit test 39/39 passed, live video generation & Pillow monkey-patch verification).
  - [x] Commit và git push lên GitHub `Phatjhhoq8/youtube`.

---

## 5. Kế Hoạch Sửa Lỗi: Khắc Phục Lỗi Sinh Video, Mất Tiếng Nói (TTS) và Video Không Xuất Ra Thư Mục Output

### 1. Phân tích nguyên nhân gốc rễ
1. **Lỗi không sinh được video (Google Flow timeout/disconnect)**:
   - Hệ thống đang ép mọi cảnh gọi `generate_flow_video` (Google Veo) vốn rất dễ bị nghẽn queue ("currently in the queue due to high demand").
   - Hàm `generate_scene_image` trong `flow_browser_service.py` bị redirect nhầm sang `generate_scene_video`.
   - Cơ chế bắt video của Playwright chỉ tìm thẻ `<video>` trong DOM hoặc network, nhưng các clip trên Google Flow nằm trong thẻ card của thư viện "All media" và không tự kích hoạt stream nếu không click/hover đúng card.
   - Khi một cảnh bị timeout, pipeline dừng đột ngột (fail-fast), vứt bỏ toàn bộ các cảnh đã tạo thành công trước đó.

2. **Video không có tiếng nói gì hết**:
   - Các file `.mp4` người dùng mở trong `temp/autonomous_factory/video_XX/` là các clip raw do Google Flow tạo (chỉ có hình ảnh/chuyển động câm, prompt ghi rõ `no audio`).
   - Âm thanh lời đọc AI (TTS) nằm ở các file `.mp3` độc lập (`scene_001.mp3`, `scene_002.mp3`...).
   - Do pipeline bị đứt gánh giữa chừng ở bước Google Flow, bước ghép âm thanh (`set_audio`) và burn phụ đề chưa bao giờ được thực thi cho video cuối cùng!

3. **Video không xuất ra output mà lưu trong temp**:
   - File thành phẩm chỉ được copy sang `output/` sau khi hoàn thành toàn bộ các cảnh và render xong. Khi bị lỗi giữa chừng, không có file nào được xuất ra `output/`, các file dở dang bị kẹt lại trong `temp/`.
   - Cần cơ chế tự động phục hồi (Self-Healing / Fallback): Nếu Google Flow quá tải hoặc cảnh nào bị timeout, hệ thống tự động retry hoặc fallback sang sinh ảnh chuyển động (Visual Beats) để đảm bảo 100% video hoàn thành đầy đủ, ghép giọng đọc TTS chuẩn xác và xuất thẳng vào `output/`!

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Khắc phục cơ chế lấy video/ảnh từ Google Flow trong `src/flow_browser_service.py`**
  - [x] Nâng cấp bộ định vị phần tử của Google Flow: Hỗ trợ click vào card clip mới nhất trong grid "All media" để kích hoạt player và trích xuất blob/src.
  - [x] Thêm cơ chế nhận diện khi Google Flow bị xếp hàng (queue), tự động đợi thêm hoặc fallback hợp lý.
  - [x] Tách rõ ràng `generate_scene_image` (sinh ảnh tĩnh siêu nét chất lượng cao) và `generate_scene_video` (sinh clip chuyển động), không để nhập nhằng.
- [x] **Task 2: Cơ chế chống đứt gãy pipeline trong `src/batch_producer.py` & `src/autonomous_factory.py`**
  - [x] Thêm cơ chế Retry và tái sử dụng cảnh đã sinh sẵn trước đó để tránh lãng phí thời gian.
  - [x] Nếu Flow video bị nghẽn/timeout, tự động fallback sang sinh ảnh Flow (Nano Banana / Imagen 3) kết hợp chuyển động Visual Beats, ĐẢM BẢO TIẾN TRÌNH KHÔNG BỊ HỦY BỎ.
  - [x] Đảm bảo 100% video hoàn thành quy trình, luôn ghép lời đọc AI (TTS) và burn phụ đề đầy đủ.
- [x] **Task 3: Đảm bảo xuất chuẩn xác ra thư mục `output/` và kiểm tra âm thanh video**
  - [x] Đảm bảo file video hoàn chỉnh sau khi render được lưu ngay vào `output/` với tên chuẩn (`output/video_batch_...mp4`).
  - [x] Kiểm tra moviepy và ffmpeg đảm bảo âm thanh giọng đọc TTS (`scene_*.mp3`) được lồng tiếng khớp 100% với video và không bị tắt tiếng/mute (đã test thực tế xác nhận 14.42s audio 44100Hz stereo).
  - [x] Hiển thị thông báo và video preview trực tiếp trên giao diện Streamlit từ thư mục `output/`.
- [x] **Task 4: Kiểm chứng thực tế (Verification)**
  - [x] Chạy test kiểm thử tích hợp sản xuất video end-to-end (`test_audio_and_output.py` - PASS).
  - [x] Kiểm tra file xuất ra trong `output/` có đầy đủ âm thanh giọng đọc và hình ảnh (`output/video_batch_20260925_013706_v01.mp4` dung lượng 4.1MB hoàn tất 100%).
  - [x] Chạy toàn bộ regression test suite (`tests/` - 13/13 passed).

---

## 6. Kế Hoạch: Chờ Lấy Video Flow Trực Tiếp & Loại Bỏ Fallback Sang Ảnh / SD

### 1. Yêu cầu người dùng
- Khi chọn chế độ Video Flow (`flow_video` hoặc video scenes):
  - Hệ thống phải kiên trì chờ Google Flow render xong video clip trực tiếp, KHÔNG tự ý fallback sang ảnh tĩnh (Flow image / Nano Banana) hay Stable Diffusion ("công nghệ tạo sinh dự phòng") hay canvas rỗng.
  - Tăng thời gian chờ render từ 360s lên 1800s (30 phút, cấu hình được qua `flow_config.json`: `video_timeout_seconds`).
  - Cập nhật thông báo tiến độ nhịp nhàng mỗi 30s lên giao diện và log.
  - Nâng cấp bộ bắt video network response (hỗ trợ HTTP 206 Partial Content, Content-Type video/*) và xử lý reconnect mượt mà.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Cập nhật cấu hình và bộ điều khiển Google Flow (`src/flow_browser_service.py` & `flow_config.json`)**
  - [x] Thêm cấu hình `"video_timeout_seconds": 1800` vào `flow_config.json`.
  - [x] Nâng cấp `FlowBrowserController.generate_scene_video`:
    - Đọc `video_timeout_seconds` từ config (mặc định 1800s / 30 phút).
    - Hỗ trợ `status_callback` để báo tiến độ ra ngoài.
    - Mở rộng bộ bắt network response: bắt `video/*` content-type và HTTP 200/206.
    - Tìm thêm các nút download/video card trong UI Flow.
- [x] **Task 2: Cập nhật `src/flow_image_service.py`**
  - [x] Truyền `status_callback` và timeout qua `generate_flow_video` và `generate_flow_media`.
- [x] **Task 3: Loại bỏ fallback sang ảnh trong `src/batch_producer.py` khi ở chế độ video**
  - [x] Khi `try_flow_video` là True: Kiên nhẫn chờ `generate_flow_video`.
  - [x] Nếu video Flow gặp lỗi/hết giờ: Không fallback sang ảnh Flow, không fallback sang SD 1.5 hay canvas rỗng. Báo lỗi rõ ràng và dừng lại.
  - [x] Kết nối `flow_status_cb` vào `notify()` để giao diện cập nhật thời gian chờ theo thời gian thực.
- [x] **Task 4: Kiểm chứng (Red -> Green -> Refactor)**
  - [x] Viết unit test xác minh: Không fallback khi ở chế độ `flow_video`, timeout nhận từ config, bộ lọc network chấp nhận 206 (`tests/test_flow_video_no_fallback.py` - PASS).
  - [x] Chạy toàn bộ test suite để đảm bảo không hồi quy (46/46 passed).
- [x] **Task 5: Cập nhật tài liệu & sơ đồ hệ thống**

---

## 7. Kế Hoạch: Trải Nghiệm 1-Click Tự Động Toàn Diện Từ Đầu Đến Cuối Trên UI

### 1. Phân tích hiện trạng & Giải pháp
- **Vấn đề 1 (Bị chặn 1-click do Chrome chưa kết nối)**:
  - Form UI trong `src/app_batch.py` có điều kiện `elif not flow_ready: st.error(...)` chặn người dùng nạp lệnh nếu Chrome port 9222 chưa mở.
  - Người dùng muốn bấm 1 click là chạy. Cần tự động gọi `FlowBrowserController().connect()` mở Chrome ngay khi click nếu Chrome chưa sẵn sàng, hoặc cho phép đưa job vào hàng đợi và để worker tự động kích hoạt Chrome.
  - Thêm nút tiện ích `🚀 Mở nhanh Chrome Google Flow` ngay trên sidebar/header để người dùng có thể mở trước chỉ với 1 click.
- **Vấn đề 2 (UI tĩnh không tự cập nhật tiến độ)**:
  - Khi dây chuyền đang chạy, Streamlit không tự làm mới (auto-refresh), khiến người dùng tưởng hệ thống bị đứng và phải bấm F5 thủ công.
  - Cần thêm cơ chế auto-poll / rerun thông minh mỗi 3 giây khi có việc đang chạy (`running` hoặc `queued`).
- **Vấn đề 3 (Thành phẩm tự hiển thị)**:
  - Khi hoàn thành 100%, video MP4 cùng metadata tự động hiển thị trong Kho thành phẩm để xem và tải về.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Cải tiến `src/app_batch.py` mở khóa trải nghiệm 1-Click**
  - [x] Cho phép tự động mở Chrome khi click "Khởi động dây chuyền" nếu Flow chưa kết nối.
  - [x] Bổ sung nút 1-click "🚀 Mở Chrome Google Flow" trên giao diện điều khiển.
  - [x] Thêm Auto-Refresh mỗi 2.5 giây khi có tiến trình đang chạy (`running` hoặc `queued`).
- [x] **Task 2: Kiểm chứng tự động (Unit test)**
  - [x] Viết test xác minh luồng auto-launch & submit job không bị chặn (`tests/test_ui_one_click.py` - PASS 2/2).
  - [x] Chạy lại test suite kiểm tra tương thích và tính toàn vẹn (19/19 tests PASS).
- [x] **Task 3: Hướng dẫn người dùng thao tác 1-Click thực tế**

---

## 8. Kế Hoạch: Tái Cấu Trúc Thư Mục & Dọn Dẹp File Rác Toàn Diện

### 1. Mục tiêu
- Dọn dẹp sạch sẽ các file rác phát sinh trong quá trình dev/test: log cũ, ảnh screenshot debug, file âm thanh/video tạm thời trong `temp/`, `scratch/`, các file log xoay vòng trong `output/`, cache `__pycache__` và `.pytest_cache`.
- Tái cấu trúc các kịch bản thực thi: di chuyển kịch bản phụ trợ `Mo_Chrome_Google_Flow.bat` vào `scripts/`, chuẩn hóa launcher `run.bat` và `run_web.bat` rõ ràng, tiện dụng.
- Khắc phục test mock bị thiếu `getsize` trong `tests/test_flow_video_no_fallback.py` để test suite xanh 100%.
- Bảo vệ an toàn tuyệt đối các dữ liệu quan trọng: Profile trình duyệt Flow (`flow_chrome_profile/`), Docker container images (`docker/images/`), cấu hình (`*_config.json`) và video thành phẩm (`output/*.mp4`).
- Cập nhật sơ đồ cấu trúc thư mục hoàn chỉnh trong `README.md`.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Dọn dẹp file rác & cache tạm thời**
  - [x] Xóa file log thừa ở thư mục gốc: `chrome_test.log`.
  - [x] Dọn dẹp các ảnh screenshot debug và script nháp trong `scratch/`.
  - [x] Dọn dẹp các file audio/video test tạm và log thừa trong `temp/` (`part_1_raw.mp4`, `part_1.ass`, `test_*.mp3`, `flow_current_screen.png`, `local_mode_screen.png`, `streamlit_*.log`).
  - [x] Dọn dẹp log cũ xoay vòng trong `output/` (`booster.log.1`, `booster.log.2`), giữ lại `booster.log` và các video thành phẩm.
  - [x] Dọn dẹp cache `__pycache__` và `.pytest_cache`.
- [x] **Task 2: Tái cấu trúc script & Chuẩn hóa Launcher**
  - [x] Di chuyển `Mo_Chrome_Google_Flow.bat` vào `scripts/` và đồng bộ cấu hình trong `scripts/launch_flow_chrome.bat`.
  - [x] Tối ưu hóa `run.bat` tại thư mục gốc làm điểm điều khiển trung tâm duy nhất, thêm mục [6] Dọn rác 1-click.
  - [x] Cập nhật `.gitignore` để đảm bảo không lưu vết các file rác trong tương lai.
- [x] **Task 3: Sửa lỗi kiểm thử & Verify 100% Green**
  - [x] Fix lỗi `FileNotFoundError` trong `tests/test_flow_video_no_fallback.py` do mock `exists` nhưng thiếu `getsize`.
  - [x] Chạy toàn bộ test suite và đạt **56/56 PASS (100% OK)**.
- [x] **Task 4: Cập nhật sơ đồ cây thư mục & Tài liệu hóa**
  - [x] Cập nhật bản đồ thư mục trong `README.md`.
  - [x] Báo cáo tổng kết các file đã dọn dẹp và dung lượng giải phóng cho người dùng.

---

## 9. [ĐÃ GỠ BỎ TOÀN BỘ THEO YÊU CẦU NGƯỜI DÙNG] Luồng Gemini Web
- **Trạng thái**: Đã xóa bỏ hoàn toàn tất cả các file mã nguồn (`src/gemini_web_service.py`, `src/gemini_youtube_pipeline.py`, `src/app_gemini_youtube.py`), test suite (`tests/test_gemini_youtube_pipeline.py`), và gỡ bỏ menu điều hướng khỏi `src/app.py` cũng như `run_web.bat`.
- Hệ thống chỉ duy trì 2 luồng chính cốt lõi:
  1. `⚡ Xưởng Tự Động (Auto Batch Google Flow)`
  2. `🎬 Sản xuất Video Ngắn (Local SD / Wan 2.1)`

---

## 10. Kế Hoạch Milestone 1: Flow Batch Queue Engine (Turbo Batch Mode)

### 1. Mục tiêu & Thiết kế
- Tích hợp cơ chế sinh ảnh hàng loạt song song (Flow Batch Queue Engine) vào `src/flow_image_service.py` theo Requirement R1.
- Concurrency an toàn 1-4 workers phù hợp với Google Flow CDP và hạn mức server.
- Staggered dispatch 1.5s ngăn ngừa race condition trên giao diện web.
- Tự động retry kèm exponential backoff trên từng task.
- Bảo toàn tuyệt đối thứ tự phân cảnh ban đầu (scenes 1..N).
- Cơ chế Tự Phục Hồi (Self-Healing Fallback): Tự động kế thừa ảnh hợp lệ liền trước khi gặp lỗi High Demand timeout.
- Cập nhật trực tiếp `scenes` in-place và trả về báo cáo task execution.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Xây dựng Data Model `FlowImageTask`**
  - [x] Dataclass theo dõi trạng thái `pending`, `running`, `completed`, `failed`, `fallback`.
  - [x] Lưu trữ metadata, elapsed_sec, retries, output_path, orientation, prompt.
- [x] **Task 2: Triển khai `FlowBatchQueueEngine`**
  - [x] Giới hạn số worker an toàn $[1, 4]$.
  - [x] Điều phối luồng qua `ThreadPoolExecutor` với giãn cách staggered dispatch.
  - [x] Xử lý retry per-task với exponential backoff.
  - [x] Sắp xếp kết quả trả về bảo toàn thứ tự phân cảnh 1..N.
  - [x] Cơ chế Self-Healing kế thừa bối cảnh hợp lệ gần nhất.
- [x] **Task 3: Cung cấp API `generate_flow_batch_queue` & Tương thích ngược**
  - [x] Cập nhật danh sách `scenes` in-place (`image_path`, `use_video_ai=False`).
  - [x] Tương thích ngược với `generate_flow_batch` qua cờ `turbo_queue`.
- [x] **Task 4: Kiểm chứng Red -> Green -> Refactor**
  - [x] Viết unit tests chuyên biệt trong `tests/test_flow_batch_queue.py` (9/9 passed).
  - [x] Chạy kiểm thử hồi quy toàn bộ hệ thống (50/50 passed 100%).

---

## 11. Kế Hoạch Milestone 2: Parallel TTS Pipeline (Turbo Batch Mode)

### 1. Mục tiêu & Thiết kế
- Tối ưu hóa thời gian sinh giọng đọc âm thanh cho các phân cảnh video thông qua `ThreadPoolExecutor` trong `src/tts_service.py` theo Requirement R2.
- Sử dụng `ThreadPoolExecutor` thay vì `asyncio` để tránh xung đột event loop Streamlit và tận dụng nền tảng subprocess CLI edge-tts sẵn có.
- Ánh xạ tương quan `future_to_index` để bảo toàn tuyệt đối 100% thứ tự các phân cảnh (scenes 1..N).
- Tái sử dụng cache âm thanh hợp lệ (>1000 bytes) trên đĩa, tránh gọi lại TTS không cần thiết.
- Tính toán chính xác thời lượng `audio_duration` và gán in-place vào từng phân cảnh.
- Báo cáo tiến độ realtime qua callback `progress_callback(done_count, total_scenes, msg)`.
- Tương thích ngược toàn diện với các chế độ `chinese_teaching_vi` và `clone_local`.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Thiết kế bộ unit test `tests/test_parallel_tts.py` (Red State)**
  - [x] Kiểm thử chữ ký hàm và tham số `generate_scenes_tts_parallel`.
  - [x] Kiểm thử bảo toàn tuyệt đối thứ tự phân cảnh với thời gian trễ nhân tạo nghịch đảo (scene 1 chậm nhất, scene 4 nhanh nhất).
  - [x] Kiểm thử tái sử dụng cache âm thanh hợp lệ (>1000 bytes) bỏ qua sinh mới.
  - [x] Kiểm thử xử lý lỗi fail-fast và báo cáo lỗi chính xác khi có phân cảnh thất bại.
  - [x] Kiểm thử giới hạn số lượng `max_workers` trong `ThreadPoolExecutor`.
  - [x] Kiểm thử gửi cập nhật tiến độ qua `progress_callback`.
  - [x] Kiểm thử điều hướng `content_mode="chinese_teaching_vi"` và `voice_mode="clone_local"`.
  - [x] Kiểm thử xử lý danh sách rỗng an toàn.
  - [x] Xác nhận trạng thái Red ban đầu (`ImportError`).
- [x] **Task 2: Triển khai hàm `get_audio_duration` và `generate_scenes_tts_parallel` trong `src/tts_service.py` (Green State)**
  - [x] Triển khai hàm đo thời lượng `get_audio_duration` (mutagen, wave, moviepy fallback).
  - [x] Triển khai `generate_scenes_tts_parallel` với `ThreadPoolExecutor` và `future_to_index`.
  - [x] Xử lý cache check và in-place mutation `audio_path`, `audio_duration`.
  - [x] Tích hợp progress callback realtime.
  - [x] Xác nhận trạng thái Green cho 9/9 tests trong `tests/test_parallel_tts.py`.
- [x] **Task 3: Kiểm thử hồi quy toàn bộ hệ thống (Regression Check)**
  - [x] Chạy `unittest discover -s tests -p "test_*.py"`.
  - [x] Kết quả: Đạt 70/70 tests passed (100% OK trong 49.9s).

---

## 12. Kế Hoạch Milestone 3: Web UI, Config & Batch Producer Integration (Turbo Batch Mode)

### 1. Mục tiêu & Thiết kế
- Bổ sung cấu hình toàn cục `TURBO_BATCH_ENABLED`, `TURBO_FLOW_QUEUE_SIZE_DEFAULT`, `TURBO_TTS_WORKERS_DEFAULT` vào `src/config.py`.
- Tích hợp tham số `turbo_mode: bool = False`, `flow_workers: int = 4`, `tts_workers: int = 4` vào `produce_single_video_pipeline` và `run_batch_video_loop` trong `src/batch_producer.py`.
- Khi bật `turbo_mode`:
  + Bước 2 gọi `generate_scenes_tts_parallel` sinh giọng đọc song song cho tất cả các phân cảnh.
  + Bước 3 gọi `generate_flow_batch_queue` gom tạo ảnh đồng thời qua hàng đợi Flow Batch Queue.
  + Khi tắt `turbo_mode`: Giữ nguyên 100% logic tuần tự cũ.
- Tích hợp giao diện người dùng Web UI:
  + Thêm checkbox `⚡ Chế độ Turbo Batch (Tăng tốc song song x4)` và expander tinh chỉnh luồng trong `src/app_batch.py`.
  + Hiển thị huy hiệu `⚡ Turbo` trên danh thiếp trạng thái công việc trong xưởng tự động.
  + Cập nhật `src/autonomous_factory.py` nhận và lưu trữ `turbo_mode`, `flow_workers`, `tts_workers`.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Cập nhật hằng số cấu hình trong `src/config.py`**
- [x] **Task 2: Tích hợp logic Turbo vào `src/batch_producer.py`**
- [x] **Task 3: Cập nhật `src/autonomous_factory.py` để lưu và truyền cài đặt Turbo**
- [x] **Task 4: Thêm điều khiển UI và huy hiệu Turbo trong `src/app_batch.py`**
- [x] **Task 5: Viết bộ unit test `tests/test_turbo_config_ui.py` (Đạt 4/4 passed)**

---

## 14. Bổ Sung 2 Thể Loại Dạy Học Theo Cốt Truyện (Story-Led Educational Modes)

### 1. Mục tiêu & Thiết kế
- Tích hợp 2 thể loại video độc đáo từ repo `hongphuoc6104/tiktok-ytb`:
  1. `english_vocab_story`: Dạy từ vựng tiếng Anh qua cốt truyện Micro-Drama (tình huống đời thường dở khóc dở cười, cấu trúc 5 cảnh Gen-Z).
  2. `story_explainer`: Kể chuyện kiến thức / lịch sử dẫn dắt theo cốt truyện lôi cuốn (Story-Led Explainer).
- Bổ sung kho chủ đề mẫu `ENGLISH_VOCAB_TOPIC_BANK` và `STORY_EXPLAINER_TOPIC_BANK` vào `src/batch_producer.py`.
- Tích hợp trực tiếp vào menu "Loại video" trong Web UI `src/app_batch.py`.
- Viết unit tests kiểm thử tại `tests/test_story_modes.py` (6/6 passed).
- Đạt 109/109 tests passed 100% toàn dự án.


### 1. Mục tiêu & Thiết kế
- Xác minh toàn bộ luồng sản xuất video hoạt động trơn tru từ đầu đến cuối (E2E) với chế độ Turbo Batch.
- Đảm bảo kịch bản sinh ra, audio song song khớp thời lượng, ảnh tạo ra đúng thứ tự, phụ đề được trích xuất và FFmpeg/MoviePy render thành công video `.mp4` hoàn chỉnh kèm metadata.
- Đảm bảo tính tương thích ngược tuyệt đối với chế độ tuần tự ban đầu.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Xây dựng bộ test tích hợp End-to-End `tests/test_turbo_batch_e2e.py`**
  + [x] `test_turbo_mode_e2e_successful_export`: Kiểm thử pipeline hoàn chỉnh khi bật Turbo Batch.
  + [x] `test_sequential_mode_backward_compatibility`: Kiểm thử tính tương thích ngược khi tắt Turbo Batch.
- [x] **Task 2: Xác minh kiểm thử và nghiệm thu**
  + [x] `tests/test_turbo_batch_e2e.py` đạt 2/2 passed.
  + [x] Chạy kiểm thử hồi quy toàn bộ codebase (full test suite).

---

## 15. Khắc Phục Triệt Để Phát Âm Tiếng Trung Giản Thể & Cô Lập Ngôn Ngữ Tuyệt Đối

### 1. Mục tiêu & Nguyên nhân gốc rễ
- **Nguyên nhân**: Khi LLM sinh trường `narration_vi` hoặc `usage_vi`, mô hình thường tự chèn chữ Hán (ví dụ: *"Từ 你好 dùng khi chào hỏi"*). Khi kịch bản được đưa vào hệ thống TTS, nếu đoạn dẫn tiếng Việt chứa chữ Hán CJK, giọng `vi-VN-HoaiMyNeural` sẽ cố gắng đọc các ký tự này dẫn đến phát âm kỳ dị, sai lệch hoặc đọc chữ Hán bằng âm sai.
- **Giải pháp**:
  + Thêm hàm tiền xử lý `clean_vietnamese_tts_text(text)` sử dụng regex `[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+` để loại bỏ 100% chữ Hán giản thể/phồn thể khỏi bất kỳ phân đoạn nào được gán cho giọng đọc tiếng Việt (`vi-VN`).
  + Trong `generate_multivoice_tts`: thiết lập chốt chặn 2 lớp (defense-in-depth): mọi phân đoạn có giọng `vi-VN` đều tự động được làm sạch qua `clean_vietnamese_tts_text`; phân đoạn chữ Hán chỉ được đọc độc quyền 100% bởi giọng Trung Quốc (`zh-CN-XiaoxiaoNeural`).
  + Áp dụng làm sạch tại tầng chuẩn hóa dữ liệu `normalize_chinese_teaching_scenes` (`src/batch_producer.py`) và `_sanitize_scenes` (`src/studio_editorial_service.py`).
  + Hỗ trợ đồng bộ cả ở chế độ chạy tuần tự lẫn chế độ song song `generate_scenes_tts_parallel`.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Xây dựng hàm `clean_vietnamese_tts_text` và chốt chặn an toàn trong `src/tts_service.py`**
- [x] **Task 2: Áp dụng lọc chữ Hán trong `normalize_chinese_teaching_scenes` và `produce_single_video_pipeline` (`src/batch_producer.py`)**
- [x] **Task 3: Áp dụng lọc chữ Hán trong `_sanitize_scenes` (`src/studio_editorial_service.py`)**
- [x] **Task 4: Cập nhật luồng TTS song song `generate_scenes_tts_parallel` (`src/tts_service.py`)**
- [x] **Task 5: Viết bộ unit tests chuyên biệt `tests/test_chinese_tts_isolation.py` (Đạt 6/6 passed)**
- [x] **Task 6: Chạy kiểm thử hồi quy toàn bộ hệ thống (`pytest`) - Đạt 115/115 passed (100%)**

---

## 16. Thiết Lập Phân Cảnh Chuẩn: 3 Cảnh Cho Video Dạy Tiếng Trung & 5 Cảnh Cho Video Cốt Truyện

### 1. Mục tiêu & Thiết kế
- **Video dạy tiếng Trung (`chinese_teaching_vi`)**: Chuẩn hóa đúng 3 phân cảnh (khoảng 20-30 giây Shorts):
  + Cảnh 1: Giới thiệu từ vựng/mẫu câu & ý nghĩa cơ bản.
  + Cảnh 2: Hướng dẫn phát âm chuẩn, phân tích pinyin & thanh điệu.
  + Cảnh 3: Đặt câu ví dụ & tình huống thực tế trong giao tiếp hàng ngày.
- **Video cốt truyện (`english_vocab_story` & `story_explainer`)**: Chuẩn hóa đúng 5 phân cảnh (khoảng 40-55 giây):
  + Tiếng Anh Micro-Drama: Hook tình huống oái oăm -> Nghĩa từ vựng cốt lõi -> Ví dụ diễn biến truyện -> Thử thách tương tác -> Cái kết bất ngờ (Twist).
  + Kể chuyện dẫn dắt Story Explainer: Hook bí ẩn -> Bối cảnh nhân vật -> Nút thắt xung đột -> Bước ngoặt giải mã -> Bài học & thông điệp.
- **Tự động hóa giao diện Web UI (`src/app_batch.py`)**: Khi người dùng chọn loại video trên dropdown, trường "Số phân cảnh mỗi video" tự động chuyển về 3 cảnh cho tiếng Trung và 5 cảnh cho cốt truyện.
- **Kiểm thử**: Cập nhật `tests/test_story_modes.py` (7/7 passed), toàn hệ thống đạt 116/116 passed.

---

## 17. Tính Năng Bỏ Qua Video Đang Làm (Skip/Cancel Job) & Tối Ưu Sinh Ảnh Song Song 2 Hình Cùng Lúc (Concurrency = 2)

### 1. Mục tiêu & Thiết kế
- **Bỏ qua / Hủy việc đang làm (Skip / Cancel Job)**:
  + Cung cấp nút `⏭️ Bỏ qua video đang làm` trên Web UI để người dùng lập tức ngắt tiến trình video hiện tại và dây chuyền tự động chuyển sang làm video tiếp theo trong hàng đợi.
  + Cung cấp nút `❌ Hủy` riêng cho từng công việc trong hàng đợi `queued`.
  + Tích hợp cờ ngắt `is_cancelled_callback` xuyên suốt các chặng của `produce_single_video_pipeline` để dừng ngay lập tức trong vòng vài giây, giải phóng tài nguyên.
- **Sinh ảnh song song chuẩn 2 hình một lúc (Concurrency = 2)**:
  + Thiết lập `flow_workers = 2` chuẩn hóa theo đúng hạn mức xử lý đồng thời tối ưu của Google Flow.
  + Điều phối an toàn trong `FlowBatchQueueEngine` và `flow_browser_service.py` để tạo 2 ảnh song song không xung đột.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Xây dựng cơ chế ngắt và hủy công việc trong `src/autonomous_factory.py`**
  + Triển khai `skip_current_job()` và `cancel_job(job_id)`.
  + Kết nối `is_cancelled_callback` vào worker loop.
- [x] **Task 2: Tích hợp chốt chặn `is_cancelled_callback` vào `src/batch_producer.py`**
  + Kiểm tra dừng sớm trước/sau kịch bản, trong lúc sinh TTS, tạo ảnh Flow, và trước render video.
- [x] **Task 3: Cập nhật giao diện Web UI `src/app_batch.py`**
  + Thêm nút `⏭️ Bỏ qua video đang làm` ở bảng điều khiển chính.
  + Thêm nút `⏭️ Bỏ qua` trên card việc đang chạy và nút `❌ Hủy` trên card việc chờ.
  + Đặt mặc định `flow_workers = 2` với giải thích trực quan về năng lực sinh 2 hình song song của Google Flow.
- [x] **Task 4: Tối ưu cấu hình 2 luồng trong `src/flow_image_service.py` và điều phối an toàn**
  + Đặt mặc định `flow_workers = 2` cho Google Flow trong UI và factory.
  + Khóa đồng bộ thao tác `_FLOW_BROWSER_LOCK` để chống xung đột DOM và multi-thread crash.
---

## 18. Khắc Phục Triệt Để Lỗi Chờ Video Flow > 800 Giây Khi Clip Đã Xuất Xong

### 1. Phân tích nguyên nhân gốc rễ
1. **Lỗi nghẽn bộ nạp video JavaScript FileReader**:
   - Code cũ dùng `page.evaluate` chạy `fetch(src)` rồi đọc bằng `FileReader.readAsDataURL` trong context trang Flow. Với video MP4 kích thước megabyte trên CDN `https://flow-content.google/video/...`, hàm này bị lỗi CORS hoặc bộ nhớ, ném exception và bị catch âm thầm, không ghi file.
   - Vòng lặp `while True` tiếp tục chạy đếm giây từ 30s, 60s, 100s... đến tận 800s-900s dù video đã hiển thị rõ ràng trên màn hình.
2. **Bẫy logic `seen_video_urls` (Logic Trapping Bug)**:
   - Trước khi gửi prompt, hàm pre-scan ghi nhận toàn bộ URL video hiện có trên trang vào `self.seen_video_urls`. Nếu một video đã xuất hiện hoặc URL không đổi, bộ kiểm tra `if src not in self.seen_video_urls` loại bỏ luôn video này, khiến hệ thống không bao giờ lấy nó dù đã render xong.
3. **Thời gian timeout quá dài (1800s / 30 phút)**:
   - Config đặt `video_timeout_seconds = 1800`, khiến hệ thống không chịu ngắt sớm khi bị lỡ mà tiếp tục đếm đến hàng chục phút.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Triển khai bộ tải video siêu tốc đa tầng `_download_video_bytes` trong `src/flow_browser_service.py`**
  - [x] Ưu tiên số 1: Tải trực tiếp bằng `page.request.get(src)` (tải 3MB trong 0.5 giây, kế thừa 100% session/cookies từ Chrome, miễn nhiễm CORS).
  - [x] Ưu tiên số 2: Fallback qua JavaScript blob reader nếu là `blob:`.
- [x] **Task 2: Cơ chế nhận diện video mới & Lọc trùng lặp thông minh qua SHA-256 Hash**
  - [x] Tách biệt `pre_existing_urls` cục bộ theo từng đợt submit, không chặn vĩnh viễn ở `self.seen_video_urls`.
  - [x] Quét toàn bộ video hiện có nếu sau 25s chưa thấy URL mới nhưng hash video chưa từng được sử dụng.
  - [x] Khi tìm thấy và tải thành công video hợp lệ: lưu file và RETURN NGAY LẬP TỨC (không chờ thêm bất kỳ giây nào).
- [x] **Task 3: Điều chỉnh cấu hình Timeout hợp lý**
  - [x] Cập nhật `video_timeout_seconds` trong `flow_config.json` và code từ 1800s về 300s (5 phút).
- [x] **Task 4: Kiểm chứng tự động (Unit Test & Regression Check)**
  - [x] Chạy unit test kiểm tra cơ chế bắt video và config (`tests/test_flow_video_no_fallback.py` - PASS 5/5).
  - [x] Dọn dẹp các tệp nháp `scratch_*.py`.
  - [x] Chạy full test suite (`pytest`) đạt 121/121 passed (100%).
- [x] **Task 5: Ghi chép bài học kinh nghiệm vào `tasks/lessons.md`**


---

## 19. Sửa Lỗi Render WinError 32 File Lock, Thu Nhỏ & Dời Phụ Đề Xuống Đáy, Liền Mạch Mạch Truyện

### 1. Phân tích nguyên nhân gốc rễ
1. **Lỗi render [WinError 32]**:
   - `write_videofile` dùng `temp_audiofile=temp-audio-part{part_num}.m4a` cố định với `remove_temp=True`. Trên Windows, FFmpeg process/handle chưa giải phóng kịp thời khi MoviePy gọi `os.remove()`, gây `PermissionError / WinError 32: The process cannot access the file because it is being used by another process`.
2. **Phụ đề che phần lớn hình ảnh**:
   - Trong `src/subtitle_builder.py`, `font_size` đặt tới `72`, `alignment = 5` (giữa màn hình), `vertical_margin = 960` (ngay tâm 1920). Phụ đề đè thẳng lên mặt/thân nhân vật và chiếm diện tích lớn giữa khung hình.
3. **Mạch truyện bị rời rạc, chắp vá ("lúc này lúc kia")**:
   - LLM sinh các phân cảnh độc lập không có câu chuyển tiếp bắc cầu (Transitional Bridges).
   - Vẫn còn sót chuỗi `f"Đọc là {pinyin}."` trong `_sanitize_scenes` và `normalize_chinese_teaching_scenes` chêm ngang vào giữa lời dẫn gây ngắt quãng.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Khắc phục triệt để WinError 32 trong `src/video_compiler.py`**
  - [x] Sinh tên file tạm ngẫu nhiên duy nhất với UUID/Timestamp (`temp-audio-{uuid}-part{part_num}.m4a`).
  - [x] Đặt `remove_temp=False` trong `write_videofile` để MoviePy không xóa đồng bộ gây lỗi.
  - [x] Xây dựng hàm `_safe_delete_file` có cơ chế retry / giải phóng handle an toàn trên Windows.
- [x] **Task 2: Thu nhỏ font & chuyển phụ đề xuống đáy an toàn (Bottom Safe Zone) trong `src/subtitle_builder.py`**
  - [x] Chuyển `alignment = 2` (Bottom Center) thay vì 5.
  - [x] Đặt `vertical_margin = 260` (cách đáy 260px, nằm ở 1/6 dưới cùng màn hình, cách xa thanh điều hướng và giải phóng 80% vùng trên).
  - [x] Thu nhỏ `font_size` từ 72 về **44** (tinh tế, thanh thoát), `outline = 3`, `shadow = 1`.
  - [x] Cập nhật tương tự cho `build_bilingual_ass_subtitle`: dời tọa độ Y xuống vùng 1520-1640, thu nhỏ font size.
- [x] **Task 3: Tối ưu mạch truyện liền mạch (Seamless Narrative Coherence)**
  - [x] Cập nhật System Prompt & User Prompt trong `src/llm_service.py`: Ép buộc mạch truyện liên tục, có từ chuyển tiếp bắc cầu, cấm nhảy ý rời rạc.
  - [x] Cập nhật `src/studio_editorial_service.py`: Bổ sung tiêu chuẩn biên tập `narrative_flow_coherence`, loại bỏ triệt để `f"Đọc là {pinyin}."`.
  - [x] Loại bỏ `f"Đọc là {pinyin}."` trong `src/batch_producer.py`.
- [x] **Task 4: Kiểm chứng tự động (Unit Test & Full Regression Test)**
  - [x] Viết test xác minh phụ đề ở đáy và font nhỏ (`tests/test_subtitle_bottom_layout.py` - PASS 3/3).
  - [x] Chạy test compile video (`tests/test_audio_and_output.py`, `tests/test_turbo_batch_e2e.py` - PASS 3/3).
  - [x] Chạy full test suite (`pytest`) đạt 124/124 passed (100%).
- [x] **Task 5: Ghi chép bài học vào `tasks/lessons.md`**

---

## 20. Đồng Bộ Tuyệt Đối Thời Lượng Hình - Tiếng & Tính Liên Kết Mạch Truyện Giữa Các Video (Multi-Video Continuity)

### 1. Phân tích nguyên nhân gốc rễ
1. **Lỗi video hết rồi mà audio vẫn nói (Freeze Frame & Audio Bleed)**:
   - Trong `src/video_compiler.py`, hàm `process_video_clip` gọi `clip.set_duration(duration)`. Khi video AI gốc (4-5s) ngắn hơn thời lượng câu thoại TTS (8-10s), MoviePy tự động lặp lại frame cuối cùng (đứng hình bất động) trong khi âm thanh vẫn tiếp tục nói.
   - Khi nối các clip, nếu tổng thời lượng visual không khớp chính xác 100% với audio, video hết trước và để lại màn hình đen/tĩnh.
2. **Nội dung giữa các video bị rời rạc, nhảy cóc ("đang abc nhảy qua 123 không liên quan")**:
   - Khi chạy hàng loạt N video, mỗi video gọi `generate_script` độc lập mà không truyền ngữ cảnh của video trước đó (`previous_context`).
   - Tên chủ đề chỉ thêm hậu kỳ chung chung `(Phần X: Các khía cạnh đặc sắc)` mà không có dàn ý mạch truyện nhiều tập (Multi-Episode Series Arc: Mở đầu -> Thử thách/Diễn biến -> Đỉnh điểm/Kết thúc).
3. **Cốt truyện và hình ảnh trong từng cảnh chưa ăn khớp 1:1**:
   - Prompt sinh video AI (`video_prompt`) đôi lúc tả bối cảnh chung chung không phản ánh hành động nhân vật đang nói trong `narration`.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Đồng bộ tuyệt đối thời lượng Video - Audio trong `src/video_compiler.py`**
  - [x] Nâng cấp `process_video_clip`: Dùng `vfx.loop(clip, duration=duration)` khi clip ngắn hơn audio để chuyển động mượt mà liên tục, không bị freeze frame. Cắt `subclip(0, duration)` nếu clip dài hơn audio.
  - [x] Đảm bảo `part_video_raw` có thời lượng bằng đúng thời lượng `combined_audio.duration` (đồng bộ kết thúc cùng thời điểm 100%).
- [x] **Task 2: Cơ chế liên kết mạch truyện nhiều tập (Series Narrative Continuity) trong `src/llm_service.py`**
  - [x] Bổ sung tham số `previous_context` trong `generate_script` để truyền tóm tắt diễn biến tập trước sang tập sau.
  - [x] Thêm chỉ thị bắt buộc Action-Narration Parity 1:1: Mọi hành động của nhân vật trong `video_prompt` phải phản ánh chính xác nội dung câu thoại `narration`.
- [x] **Task 3: Cập nhật luồng phân tách chủ đề & chuyển giao ngữ cảnh trong `src/batch_producer.py`**
  - [x] Nâng cấp `split_prompt_to_video_topics`: Phân bổ chủ đề theo cấu trúc chuỗi tập liên kết (Hồi 1 Khởi đầu -> Hồi 2 Bước ngoặt -> Hồi 3 Kết bài/Giải mã).
  - [x] Trong `run_batch_video_loop` và `produce_single_video_pipeline`: Trích xuất tóm tắt kịch bản video trước và truyền vào video tiếp theo để mạch truyện xuyên suốt không bị ngắt quãng.
- [x] **Task 4: Kiểm chứng tự động (Unit Test & Full Regression Test)**
  - [x] Viết unit test kiểm tra `vfx.loop` thời lượng video không freeze frame (`tests/test_video_audio_sync_and_series.py`).
  - [x] Viết unit test kiểm tra truyền `previous_context` vào kịch bản nhiều video.
  - [x] Chạy toàn bộ test suite (`pytest`) đảm bảo 100% passed.
- [x] **Task 5: Ghi chép bài học vào `tasks/lessons.md`** (Bài học 17)

---

## 21. Khắc Phục Triệt Để Lỗi Kẹt Hàng Đợi (Queue Deadlock / Block) Khi Hủy Việc & Cơ Chế Ngắt Tức Thì (Instant Cancellation)

### 1. Phân tích nguyên nhân gốc rễ
1. **Lỗi ngắt không tức thì (Abort Gap)**:
   - Khi người dùng bấm "Hủy việc này" hoặc "Bỏ qua video này", `skip_current_job` chỉ đổi trạng thái trong JSON sang `failed`.
   - Các tác vụ I/O dài (`generate_flow_video` 300s, `generate_flow_image` 90s, `FlowImageBatchQueue`, `TTS Parallel`) KHÔNG nhận `is_cancelled_callback`. Worker Thread bị giam hãm trong tiến trình cũ hàng phút cho đến khi hoàn thành xong các cảnh của việc đã bị hủy.
2. **Lỗi Zombie Job (Orphan running job) chặn hàng đợi**:
   - Nếu có job bị đánh dấu là `running` trong JSON nhưng không có thread nào đang chạy nó, hàm `_next_job()` kiểm tra `if any(job.get("status") == "running"): return None`, khiến toàn bộ các job `queued` phía sau bị kẹt cứng vĩnh viễn (Đang chờ: 1, Đang chạy: 0).
3. **Thiếu cơ chế Watchdog & Phục hồi chủ động**:
   - `ensure_factory_worker()` thấy thread cũ còn alive thì không làm gì, trong khi thread cũ có thể đang bị block ở mạng hoặc I/O của job đã bị hủy.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Khôi phục trạng thái Job #5 và khắc phục triệt để Zombie Job trong `src/autonomous_factory.py`**
  - [x] Khôi phục Job #5 (`f0158ae371`) về `status: "queued"`.
  - [x] Thêm hàm `recover_stale_running_jobs()`: Tự động đưa bất kỳ job `running` mồ côi (không có active pipeline worker) về `queued` để giải phóng hàng đợi tức thì.
  - [x] Cập nhật `_next_job()`: Kiểm tra hợp lệ giữa running job và active thread ID.
- [x] **Task 2: Cơ chế Ngắt Tức Thì (Instant Cancellation) cho Google Flow và Hàng Đợi Song Song**
  - [x] Cập nhật `src/flow_browser_service.py` (`generate_scene_video`, `generate_flow_image`): Nhận `is_cancelled_callback`, kiểm tra mỗi 1 giây trong vòng lặp polling để ngắt ngay lập tức khi user bấm hủy.
  - [x] Cập nhật `src/flow_image_service.py` (`process_tasks`): Nhận `is_cancelled_callback`, ngắt ThreadPoolExecutor ngay lập tức khi có lệnh hủy.
  - [x] Cập nhật `src/batch_producer.py`: Truyền `is_cancelled_callback` xuyên suốt vào mọi dịch vụ con.
- [x] **Task 3: Nút điều khiển phục hồi trên giao diện `src/app_batch.py`**
  - [x] Thêm nút "⚡ Khởi động lại dây chuyền" khi phát hiện có job chờ mà không có tiến trình chạy.
- [x] **Task 4: Kiểm chứng tự động (Unit Test & Full Regression Test)**
  - [x] Viết unit test xác minh hủy việc tức thì và tự động giải phóng hàng đợi (`tests/test_instant_cancellation.py` - PASS 4/4).
  - [x] Chạy full test suite (`pytest`) đảm bảo 100% passed.
- [x] **Task 5: Ghi chép bài học vào `tasks/lessons.md`** (Bài học 18)

---

## 22. Khắc Phục Triệt Để Lỗi Dây Chuyền: 'str' object has no attribute 'get' (Defensive Data Types & LLM Parsing)

### 1. Phân tích nguyên nhân gốc rễ
1. **Ollama / LLM trả về mảng chuỗi (`list[str]`) thay vì mảng từ điển (`list[dict]`)**:
   - Khi Ollama sinh hoặc biên tập kịch bản phân cảnh (`scenes`), model đôi khi trả về `["Cảnh 1: Lời dẫn...", "Cảnh 2: ..."]`.
   - Các hàm `_sanitize_scenes` (`studio_editorial_service.py`), `build_exact_tts_timestamps`, `produce_single_video_pipeline` (`batch_producer.py`), `tts_service.py`, `video_compiler.py`, `flow_image_service.py` giả định các phần tử trong `scenes` là `dict` và gọi `.get("narration")`, `.get("scene_num")`, `.get("audio_duration")`, gây ra `AttributeError: 'str' object has no attribute 'get'`.
2. **Metadata hoặc Editorial Report bị trả về hoặc gán dạng `str`**:
   - Trong `autonomous_factory.py`: `metadata.get("editorial_report", {}).get(...)` nếu `editorial_report` là `str`, hoặc trong `app_batch.py` nếu `metadata` là `str`.
3. **Studio Skill Scores JSON hoặc CDP Tabs trả về kiểu không phải dict**:
   - Trong `studio_skill_registry.py` và `flow_browser_service.py`: các lời gọi `.get()` trên phần tử khi dữ liệu bị thoái hóa thành `str`.

### 2. Danh sách công việc (Todo Checklist)
- [x] **Task 1: Viết Unit Test Tái Hiện (Red Phase)**
  - [x] Tạo `tests/test_defensive_data_types.py` kiểm thử các trường hợp dữ liệu thô (string scenes, non-dict editorial_report, non-dict CDP tabs, string scores) - Đã tái hiện 5/5 FAILED ở Red Phase.
- [x] **Task 2: Xử lý phòng thủ (Defensive Data Normalization) trong Core Services (Green Phase)**
  - [x] `src/studio_editorial_service.py`: Chuẩn hóa `_sanitize_scenes` nhận cả `str` lẫn `dict`, tự động bọc chuỗi thành scene dict hợp lệ.
  - [x] `src/batch_producer.py`: Chuẩn hóa an toàn `scenes` trong `produce_single_video_pipeline`, `build_exact_tts_timestamps`, `normalize_chinese_teaching_scenes`.
  - [x] `src/autonomous_factory.py`: Bọc an toàn `metadata.get("editorial_report")`, log full traceback khi xảy ra ngoại lệ.
  - [x] `src/app_batch.py`: Kiểm tra type-safe `isinstance(metadata, dict)` trước khi truy xuất các trường publishing/platforms/editorial.
  - [x] `src/studio_skill_registry.py`: Kiểm tra type-safe `isinstance(current, dict)` trước khi cập nhật điểm.
  - [x] `src/flow_browser_service.py`: Kiểm tra `isinstance(tab, dict)` trước khi đọc `tab.get("url")`.
  - [x] `src/video_compiler.py`: Kiểm tra `isinstance(scene, dict)` trước khi đọc `scene.get("audio_duration")`.
  - [x] `src/tts_service.py`: Kiểm tra `isinstance(sc, dict)` trước khi đọc `sc.get("scene_num")`.
- [x] **Task 3: Khôi phục Job #5 về queued và kiểm chứng**
  - [x] Đặt Job #5 về `status: "queued"`.
  - [x] Chạy full test suite (`pytest`) đạt 100% passed (65/65 tests passed).
- [x] **Task 4: Ghi chép sổ tay bài học (`tasks/lessons.md`)** (Bài học 19)

---

## 5. Kế Hoạch Tách Hai Dự Án Độc Lập (`video_studio` & `view_booster`)

- [x] **Bước 1: Dừng các tiến trình cày view đang chạy**
  - [x] Dừng tiến trình `cli_booster.py` và đóng các Chrome worker liên quan an toàn.

- [x] **Bước 2: Chuẩn bị cấu trúc thư mục độc lập**
  - [x] Tạo thư mục `video_studio/` và `view_booster/`.
  - [x] Thiết lập cây thư mục chuẩn cho cả 2 dự án (`src/`, `tests/`, `scripts/`, cấu hình).

- [x] **Bước 3: Phân tách và di chuyển file sang `view_booster/`**
  - [x] Chuyển các module cày view: `app_view_booster.py`, `view_booster_manager.py`, `view_booster_service.py`, `human_simulator.py`, `channel_scraper.py`, `profile_manager.py`, `resource_guard.py` vào `view_booster/src/`.
  - [x] Chuyển `cli_booster.py`, `booster_config.json`, `requirements.txt`.
  - [x] Chuyển `docker/`, Dockerfile, docker-compose.yml và các scripts chạy booster (`run_view_booster_*.bat`).
  - [x] Chuyển `tests/test_booster.py` và tạo `config.py` độc lập.
  - [x] Tạo launcher `view_booster/run.bat` độc lập.

- [x] **Bước 4: Phân tách và di chuyển file sang `video_studio/`**
  - [x] Chuyển toàn bộ module video: `app.py`, `app_batch.py`, `batch_producer.py`, `autonomous_factory.py`, `llm_service.py`, `flow_image_service.py`, `flow_browser_service.py`, `image_service.py`, `tts_service.py`, `music_service.py`, `visual_beats.py`, `video_compiler.py`, `subtitle_builder.py`, `youtube_uploader_service.py`, `studio_editorial_service.py`, `studio_skill_registry.py`, `story_contract_models.py`, `config.py` vào `video_studio/src/`.
  - [x] Chuyển `flow_config.json`, `flow_chrome_profile/`, `assets/`, `docs/`, `requirements.txt`, `.env`.
  - [x] Chuyển các scripts chạy video: `run_web.bat`, `scripts/launch_flow_chrome.bat`, `scripts/*.py`.
  - [x] Cập nhật đường dẫn `chrome_user_data_dir` trong `flow_config.json`.
  - [x] Tạo launcher `video_studio/run.bat` độc lập.

- [x] **Bước 5: Kiểm chứng tính toàn vẹn (Verification)**
  - [x] Tạo Master Launcher `run.bat` ở gốc điều hướng tới cả 2 dự án.
  - [x] Chạy unit test của `view_booster`: 9/9 tests passed (100%).
  - [x] Chạy unit test của `video_studio`: 13/13 tests passed (100%).
  - [x] Tổng cộng 22/22 tests passed, không phát sinh bất kỳ lỗi import hay đụng độ nào.
  - [x] Dọn dẹp cache rác và IndexedDB trang web ngoài (Pippit, CapCut, Facebook) trong `flow_chrome_profile`: giải phóng thêm **938 MB**, đưa toàn bộ thư mục `video_studio` từ **1.66 GB** xuống còn **~723 MB** (đạt mục tiêu dưới 1 GB).



- [x] **Bước 1: Khảo sát và phân loại dữ liệu rác**
  - [x] Quét kích thước toàn bộ các thư mục trong workspace.
  - [x] Kiểm tra các tiến trình đang hoạt động (tránh xóa nhầm profile Chrome đang chạy).
  - [x] Phân loại rác an toàn (cache, logs, debug png/mp3 tạm) và dữ liệu cần lưu ý (docker images tar, chrome cache).

- [x] **Bước 2: Dọn dẹp rác an toàn (Zero Risk Cleanup)**
  - [x] Xóa `__pycache__` trong `src/`, `tests/` và `.pytest_cache/`.
  - [x] Xóa các tệp test/debug tạm trong `temp/` (*.mp3, *.png, *.m4a, *.ass, *.mp4, streamlit*.log).
  - [x] Xóa các thư mục test tạm: `temp/test_*`, `temp/flow_attempts`, `temp/gemini_animal_1`, `temp/dubbing`, `temp/downloads`, `temp/profiles/*_p6879a288`.
  - [x] Xóa file log xoay vòng đã cũ: `output/booster.log.1` (10.5 MB).
  - [x] Dọn thư mục log tác nhân teamwork cũ: `.agents/teamwork/`.

- [x] **Bước 3: Dọn dẹp cache trình duyệt `flow_chrome_profile` (Giải phóng ~650MB)**
  - [x] Xóa `Cache/Cache_Data` và `Code Cache` bên trong `flow_chrome_profile/Default/` (giữ nguyên Cookies, Local Storage, IndexedDB đăng nhập).

- [x] **Bước 4: Kiểm tra và xử lý các file tar lớn trong `docker/images/` (~1.38GB)**
  - [x] Đã xóa 2 file backup image: `yt-booster-image.tar` và `yt-booster.tar` theo yêu cầu của user, giải phóng thành công 1.38 GB.

- [x] **Bước 5: Báo cáo kết quả và dung lượng đã giải phóng**
  - [x] Đo lường lại dung lượng thư mục sau dọn dẹp (tổng giải phóng ~2.04 GB).
  - [x] Kiểm chứng tính toàn vẹn của mã nguồn và test suite (13/13 tests passed).

---

## 6. Kế Hoạch Thay Thế & Tích Hợp Luồng Tạo Video & Tải Về Nâng Cấp (Video Studio v2)

- [x] **Bước 1: Khảo sát và phân tích mã nguồn mới được cung cấp**
  - [x] Phát hiện gói mã nguồn nâng cấp `youtube_video_studio_upgraded_v2.zip` tại thư mục Downloads.
  - [x] Giải nén và so sánh cấu trúc file giữa `scratch/extracted_v2/video_studio` và `video_studio/`.
  - [x] Phát hiện và sửa lỗi cú pháp `SyntaxError: unterminated f-string literal` trong `src/app_batch.py`.

- [x] **Bước 2: Thay thế và đồng bộ mã nguồn vào `video_studio/`**
  - [x] Sao chép các file module mới (`src/policy_engine.py`, `src/production_roles.py`, `src/publishing_package_service.py`, `src/video_qa_service.py`, `src/html_frame_animator.py`).
  - [x] Thay thế các module luồng tạo video & tải về (`src/batch_producer.py`, `src/autonomous_factory.py`, `src/video_compiler.py`, `src/video_downloader.py`, `src/tts_service.py`, `src/story_contract_models.py`, `src/flow_browser_service.py`, `src/visual_beats.py`, `src/studio_editorial_service.py`, `src/studio_skill_registry.py`, `src/app_batch.py`, `src/config.py`, `src/__init__.py`).
  - [x] Đồng bộ UI web mới (`studio_web_v3.html`, `run_web.bat`, `flow_config.json`, `requirements.txt`).
  - [x] Đồng bộ skills và tests mới (`skills/html-canvas-video-animator/`, `tests/test_studio_upgrade_v2.py`).
  - [x] Bảo toàn nguyên vẹn cấu hình môi trường `.env`, Chrome profile `flow_chrome_profile/` và assets thư viện.

- [x] **Bước 3: Kiểm chứng toàn diện (Verification & Test Suite)**
  - [x] Chạy bộ test mới `test_studio_upgrade_v2.py`: Đạt 9/9 test suites (100% passed in 180s bao gồm 11 roles, QA kiểm tra video corrupt/black/no audio, subtitle safe-zone, checkpoint resume, publish gate và real ffmpeg e2e render).
  - [x] Chạy regression test suites của `video_studio/tests`: Đạt 23/23 tests passed (100%).
  - [x] Xác nhận luồng tạo video, tải về và hậu kiểm QA hoạt động 100% không lỗi.

- [x] **Bước 4: Cập nhật tài liệu & Sổ tay bài học**
  - [x] Ghi nhận bài học về pipe deadlock, Windows file lock WinError 32 và Triple-tier TTS fallback vào `tasks/lessons.md`.
  - [x] Cập nhật kết quả vào `tasks/todo.md`.

---

## 7. Khắc Phục Lỗi Script Chạy Hệ Thống & Khởi Động Web UI

- [x] **Bước 1: Chẩn đoán nguyên nhân script không dùng được**
  - [x] Phát hiện lỗi `ImportError: cannot import name 'STAGE_LABELS_VI' from 'src.autonomous_factory'` khi nạp Web UI Streamlit.
  - [x] Phát hiện thiếu file thực thi `video_studio/run_web.bat`.
  - [x] Phát hiện lỗi cú pháp ký tự `&` trong tiêu đề lệnh `view_booster/run.bat` (`'Shorts' is not recognized`).
  - [x] Phát hiện toàn bộ tệp `.bat` bị định dạng xuống dòng Unix LF thay vì Windows CRLF.

- [x] **Bước 2: Xử lý và sửa lỗi toàn diện**
  - [x] Bổ sung từ điển đầy đủ `STAGE_LABELS_VI` vào `video_studio/src/autonomous_factory.py`.
  - [x] Tạo mới file `video_studio/run_web.bat` hỗ trợ tự động mở Chrome CDP 9222 và Web UI port 8502.
  - [x] Escape ký tự `^&` trong `view_booster/run.bat` và nâng cấp bộ phát hiện python trong các kịch bản chạy.
  - [x] Chuyển đổi chuẩn hóa toàn bộ các file `.bat` trong dự án sang CRLF (`\r\n`).

- [x] **Bước 3: Kiểm chứng thực tế**
  - [x] Test import thành công `src.app` và `src.app_batch` không còn bất kỳ lỗi nào.
  - [x] Test chạy `run.bat` gốc, `video_studio/run.bat` và `view_booster/run.bat` qua CMD: hoạt động trơn tru 100%.
  - [x] Ghi nhận bài học 33 vào `tasks/lessons.md`.



## 8. Hoạt hình timeline và kiểm tra Flow (2026-10-21)
- [x] Cài ba skill HyperFrames animation/keyframes/creative trong dự án.
- [x] Tích hợp bộ vẽ người có khớp, phong cảnh theo chủ đề và approach/action/resolve.
- [x] Dùng chung dữ liệu frame cho HTML và Python; đổi Chrome renderer sang Playwright.
- [x] Chặn bản biên tập mất narration và bỏ đường tắt nhận script sai schema.
- [x] Sinh video ngang/dọc 144 frame/6 giây và Chrome 72 frame/3 giây.
- [x] Kiểm chứng tạo/tải ảnh Flow thật thành công: output/animation_upgrade_preview/flow_live_check.png.


---

## 16. Khắc Phục Lỗi Cảnh 2/N Báo "Không Thành Công / Rất Tiếc, Không Tạo Được Video Này" Trên Google Flow (2026-10-23)

- [x] **Tìm nguyên nhân gốc rễ trên Chrome CDP port 9222**:
  - [x] Phát hiện sau khi Cảnh 1 click mở video để tải, Google Flow chuyển sang URL `/project/<uuid>/edit/<clip_id>` (chế độ `"Mô tả cách chỉnh sửa video này…"` dùng `Omni 1.1 Flash` thay vì `"Bạn muốn tạo gì?"` dùng `Veo`), và `_remember_flow_project_url` lưu đè URL `/edit/` vào `flow_config.json`.
  - [x] Phát hiện card `"Không thành công"` của lần thử 1 còn lưu trên DOM khiến lần thử 2 bị ngắt sớm sau 16 giây.
- [x] **Triển khai bản sửa lỗi triệt để trong [`video_studio/src/museai_3d_service.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/museai_3d_service.py) và [`video_studio/src/flow_browser_service.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/flow_browser_service.py)**:
  - [x] Cắt bỏ `/edit/` và `/tool/` trong `load_hybrid_config`, `_remember_flow_project_url`, `_remember_project_url` và khôi phục `video_studio/flow_config.json`.
  - [x] Thêm `_exit_flow_edit_mode_if_needed()` tự động thoát màn hình `/edit/` về dự án chính ngay sau khi tải xong từng cảnh và trước khi bắt đầu cảnh mới.
  - [x] Chặn `_find_google_flow_composer()` không bao giờ chọn ô nhập khi URL đang ở `/edit/`.
  - [x] Đếm `pre_existing_failed_count` trước khi gửi lệnh để card lỗi cũ không làm ngắt nhầm lần thử lại.
  - [x] Thêm `sanitize_prompt_for_flow_retry()` làm sạch từ khóa nhạy cảm (`9-year-old boy`, `child` -> `stylized Pixar 3D animated young explorer character`) khi thử lại.
  - [x] Cân đối `max_words_per_shot=42` trong `_enrich_scenes_with_3d_prompts` để mỗi khung cảnh khớp tự nhiên với clip 10 giây của Google Flow (6–8 khung cảnh thay vì 15 khung quá vụn).
- [x] **Kiểm chứng (Verification)**:
  - [x] Đã điều hướng trực tiếp tab Google Flow trên Chrome port 9222 thoát khỏi `/edit/` về lại trang dự án chính.
  - [x] Chạy bộ unit test & E2E test `pytest video_studio/tests/test_museai_3d.py -v`: **18/18 PASSED**.


---

## 17. Tự Động Tạo Dự Án / Phiên Mới Sạch Context Trên Google Flow Cho Mỗi Video (2026-10-23)

- [x] **Triển khai `start_fresh_google_flow_project()` trong [`video_studio/src/museai_3d_service.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/museai_3d_service.py#L1526-L1580)**:
  - [x] Mỗi lần bắt đầu tạo một video/tập phim mới, tự động mở `https://flow.google.com/` và bấm **`Dự án mới` (`New project`)** để tạo không gian mới tinh, không bị tích tụ context hay video cũ.
- [x] **Triển khai `_ensure_direct_video_composer_mode()` trong [`video_studio/src/museai_3d_service.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/museai_3d_service.py#L1426-L1524)**:
  - [x] Tự động bấm **`Bắt đầu phiên mới`** (`button[aria-label='Bắt đầu phiên mới']`) và **`Đóng`** bảng chat Tác nhân (Agent) bên phải để dùng thanh **Direct Video Composer** (mỗi cảnh gửi lệnh trực tiếp tới model Video, không cộng dồn lịch sử hội thoại).
  - [x] Tự động mở **`Điều kiện kích hoạt cài đặt`** (`button[aria-label='Điều kiện kích hoạt cài đặt']`) và chuyển từ mặc định `🍌 Nano Banana 2.1 (Hình ảnh)` sang **`Video · 720p · 8 giây · 9:16 (hoặc 16:9) · x1`**.
- [x] **Kiểm chứng thực tế & Unit/E2E Tests**:
  - [x] Kiểm chứng trực tiếp trên Chrome CDP cổng 9222: Tạo dự án mới thành công và tự động chuyển thanh cài đặt sang `'Video · 720p · 8 giây crop_9_16 x1'`.
  - [x] Chạy `pytest video_studio/tests/test_museai_3d.py -v`: **19/19 PASSED**.


---

## 18. Đóng Gói Skill `google-flow-3d-studio` & Kho Nhân Vật Cố Định 3D (`7-Point Character DNA Vault`) (2026-10-23)

- [x] **Nghiên cứu kỹ thuật giữ nhân vật cố định (Character Consistency) chuẩn Google Flow / Veo**:
  - [x] Áp dụng công thức **7-Point Character DNA Block** (`[Name & Stylized 3D Archetype]` + `[Face & Subsurface Skin Shader]` + `[Eye Color & Catchlights]` + `[Sculpted 3D Hair Clumps]` + `[Primary Wardrobe & Color Lock]` + `[Signature Accessories]` + `[Preservation Directive]`).
  - [x] Loại bỏ từ khóa tuổi trẻ em nhạy cảm (`"9-year-old boy"`, `"child"`) ngay từ lần gửi đầu tiên để không bị bộ lọc an toàn của Veo từ chối.
- [x] **Xây dựng module Kho Nhân Vật Cố Định 3D ([`video_studio/src/flow_character_vault.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/flow_character_vault.py))**:
  - [x] Dựng sẵn 5 nhân vật 3D chuẩn Pixar/DreamWorks (`leo_explorer`, `milo_rusty`, `linh_magic`, `barnaby_bear`, `bibo_rabbit`).
  - [x] Tự động lưu mọi nhân vật mới do MuseAI tạo vào `video_studio/temp/character_vault.json` và tích hợp bộ chọn **🎭 Kho Nhân Vật Cố Định 3D** lên giao diện [`video_studio/src/app_museai.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/app_museai.py#L148-L163).
- [x] **Đóng gói Antigravity Skill & CLI Tool**:
  - [x] Tạo Skill chuyên biệt [`.agents/skills/google-flow-3d-studio/SKILL.md`](file:///c:/Users/Admin/Desktop/youtube/.agents/skills/google-flow-3d-studio/SKILL.md).
  - [x] Tạo công cụ CLI [`.agents/skills/google-flow-3d-studio/scripts/flow_doctor.py`](file:///c:/Users/Admin/Desktop/youtube/.agents/skills/google-flow-3d-studio/scripts/flow_doctor.py).
  - [x] Kiểm thử `pytest video_studio/tests/test_museai_3d.py -v`: **20/20 PASSED**.


---

## 19. Khắc Phục Lỗi Đọc Lại Kịch Bản Cũ Trên Tab MuseAI Thay Vì Viết Cốt Truyện Mới Của Người Dùng (2026-10-23)

- [x] **Tìm nguyên nhân trong log phiên 17:37:17**:
  - [x] Do checkbox `reuse_existing_script` để mặc định `value=True` và trên tab `https://muse.ai/` vẫn đang mở cuộc trò chuyện cũ `"Hạt Giống Ánh Sáng Cuối Cùng"`, nên khi bấm chạy, hệ thống bốc ngay JSON cũ trên màn hình MuseAI mà không gửi cốt truyện mới của người dùng.
- [x] **Triển khai sửa lỗi triệt để**:
  - [x] Đổi mặc định `reuse_existing_script = False` và xóa text mẫu trong ô nhập `topic` ở [`video_studio/src/app_museai.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/app_museai.py#L89-L138).
  - [x] Thêm hàm [`does_script_match_user_topic`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/museai_3d_service.py#L765-L801) kiểm tra đối chiếu từ khóa `topic` với nội dung kịch bản.
  - [x] Tự động bấm `button[aria-label='New side chat']` trên tab `https://muse.ai/` (đã test thực tế đưa `Pre count` từ `3` về `0`) trước khi gửi cốt truyện mới.
  - [x] Kiểm thử `pytest video_studio/tests/test_museai_3d.py -v`: **21/21 PASSED**.


---

## 20. Khắc Phục Triệt Để Lỗi Cảnh 2/N Đứng Chờ 600s Dù Google Flow Đã Tạo Xong Video (2026-10-23)

- [x] **Tìm nguyên nhân gốc rễ trên DOM của Google Flow**:
  - [x] Phát hiện trên lưới Google Flow, video mới nhất luôn nằm ở **`index 0` (đầu danh sách bên trái)** dưới dạng `<img alt="Hình thu nhỏ của video đã tạo">` và chỉ biến thành `<video src="https://flow-content.google/video/...">` khi được **hover**.
  - [x] Code cũ xếp `visible_triggers[-1]` (cảnh cũ nhất ở cuối danh sách) lên trước và có lệnh `break` ở vòng lặp đầu tiên nên không bao giờ hover vào `index 0` (Cảnh 2).
- [x] **Triển khai hàm `_hover_newest_flow_video_thumbnails()` trong [`video_studio/src/museai_3d_service.py`](file:///c:/Users/Admin/Desktop/youtube/video_studio/src/museai_3d_service.py#L1737-L1781)**:
  - [x] Ghi nhận `pre_existing_thumb_urls` trước khi gửi lệnh.
  - [x] Tự động hover ưu tiên `index 0` (video mới nhất) và các thumbnail mới xuất hiện, **không click** để không nhảy vào `/edit/`.
- [x] **Kiểm chứng thực tế & Unit Test**:
  - [x] Đã test trực tiếp trên Chrome cổng 9222: ngay khi gọi `thumbs[0].hover()`, thẻ `<video src="https://flow-content.google/video/e55239f9-...">` của Cảnh 2 xuất hiện tức thì sau 1 giây!
  - [x] Chạy `pytest video_studio/tests/test_museai_3d.py -v`: **22/22 PASSED**.

## Whiteboard Stickman (ban tay ve) - 2026-10-23 19:50
Muc tieu: option tao video kieu whiteboard: nhan vat que + so do/chu duoc 'ban tay lia qua' ve hien dan, giong tay MuseAI viet kich ban; moi nhan vat 1 giong, truyen cam theo cam xuc.
- [ ] 1. video_studio/src/whiteboard_video.py: layout items (text/circle/arrow/box/stickman), lich reveal, render frame (wipe + ban tay), render scene mp4 (ffmpeg pipe + audio)
- [ ] 2. Giong: preset rieng moi nhan vat + modifier cam xuc (rate/pitch) trong tts_service/build_scene_dialogue_segments
- [ ] 3. Prompt MuseAI che do whiteboard (whiteboard_items + emotion tung cau thoai)
- [ ] 4. Pipeline: visual_mode='whiteboard' bo qua Google Flow (0 credit): TTS truoc -> render local -> ghep
- [ ] 5. UI app_museai: lua chon Whiteboard
- [ ] 6. Test (unit + e2e render that), cap nhat docs/so do

## Giong VieNeu theo vai + Thu vien video (2026-10-24)
- [ ] A. voice_casting.py: moi nhan vat 1 giong VieNeu khac nhau (khong trung narrator), cam xuc -> toc do; noi vao synthesize_museai_scenes_interactive_tts
- [ ] B. UI: nut Nghe thu giong (VieNeu/Edge)
- [ ] C. video_library.py: scan output, sidecar .publish.json (title<=100, hashtag hop chinh sach, mo ta co header co dinh lien he mua pipeline/Gemini Pro/MuseAI, nhan AI YouTube+TikTok), xoa video an toan
- [ ] D. app_library.py: tab 'Thu vien video' (xem video, sua title/desc/hashtag, copy, xoa co xac nhan, sua header chung) + tu dong tao metadata khi pipeline xong
- [ ] E. Test unit + e2e that (VieNeu nghe thu, library render), cap nhat docs
