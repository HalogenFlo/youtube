# MuseAI: whiteboard minh họa màu và bàn tay thật

Tính năng này giữ MuseAI làm người viết kịch bản, dựng whiteboard ngay trên máy bằng Pillow và FFmpeg. Ảnh bàn tay thật cầm bút dạ xám di chuyển theo các nét viền của hình. Với minh họa màu, nét viền được vẽ trước rồi màu pastel xuất hiện theo lượt tô của tay. Hỗ trợ thêm chữ, sơ đồ và người que; xuất 1920×1080 hoặc 1080×1920, 24 FPS.

Ảnh tay và minh họa người ngồi máy tính ban đầu được tạo bằng công cụ imagegen tích hợp, lưu tại `video_studio/assets/whiteboard/`. Thông tin và prompt tạo hai ảnh ban đầu nằm trong `generation_manifest.json`. Các biểu tượng màu có sẵn được vẽ bằng Pillow. Khi bài cần hình mới, ứng dụng gọi Google Flow để tạo minh họa theo cảnh; phần tay vẽ và dựng MP4 vẫn chạy trên máy, không cần OpenCV.

## Cách sử dụng

1. Mở Video Studio, chọn **MuseAI Studio (3D / Người que bàn tay vẽ)**.
2. Nhập đề tài, chọn **Whiteboard minh họa màu / Người que + Bàn tay thật cầm bút** trong **Kiểu video**.
3. Chọn khung hình, ngôn ngữ và số tập. Bật **Lồng tiếng & Phụ đề** để có lời đọc.
4. Giữ **AI tự tạo minh họa mới khi cần (Google Flow)** được bật, đăng nhập MuseAI và Google Flow trên Chrome của dự án, rồi bấm **Bắt đầu sản xuất video**. Nếu mọi hình đã có trong kho thì không cần gọi Flow.
5. Tải MP4 và JSON trên giao diện, hoặc lấy trong `video_studio/output/`, tên bắt đầu bằng `museai_whiteboard_`.

Có thể bật **Đọc kịch bản đang có sẵn trên tab MuseAI** để dùng lại kịch bản cùng đề tài. Nếu kịch bản không có `whiteboard_items`, hệ thống tự bố trí tiêu đề và người que theo nhân vật có thoại. Muốn sơ đồ giải thích chi tiết, cần bố cục `whiteboard_items` từ MuseAI; dùng yêu cầu mới ở chế độ whiteboard sẽ yêu cầu MuseAI trả đủ bố cục này.

Kho nhân vật 3D dùng cho các kiểu hoạt hình 3D. Với whiteboard, MuseAI chọn hình phù hợp trong kho hoặc mô tả hình cần AI tạo mới. Mười hình có sẵn chỉ là kho dùng nhanh, không giới hạn chủ đề: bài học có thể cần trái cây, động vật, nhà hàng, sân bay, giáo viên, học viên hoặc một tình huống cụ thể khác. Vẫn có thể dùng người que, sơ đồ và ảnh minh họa riêng.

## AI tự tạo hình theo nội dung cảnh

MuseAI trả phần tử `ai_image` gồm `prompt` mô tả vật thể/hành động, cùng vị trí và khung bao `x`, `y`, `w`, `h`. Khi hình có sẵn không thể hiện đúng nội dung, kịch bản mới phải dùng phần tử này thay vì cố chọn một hình mẫu không liên quan. Tên minh họa ngoài kho cũng được chuyển thành yêu cầu tạo hình, không bị bỏ qua để quay về người que.

Ứng dụng gửi yêu cầu sang Google Flow ở chế độ tạo ảnh, giữ phong cách 2D nét viền và màu pastel, nền trắng, không chữ hay bàn tay trong ảnh. Bộ xử lý chuyển ảnh sang PNG và bỏ phần nền trắng nối với mép ảnh; các vùng trắng được bao kín bởi nét vẽ vẫn được giữ. Sau đó tay thật vẽ nét viền rồi tô màu ảnh mới. Việc tạo ảnh không sử dụng bộ ép phong cách Pixar 3D.

Ảnh được lưu tại `video_studio/assets/whiteboard/ai/`, kèm JSON mô tả nội dung và prompt. Khóa lưu dựa trên mô tả và tạo hình nhân vật, nên cùng yêu cầu ở cảnh/tập sau được dùng lại; yêu cầu hoặc tạo hình khác sẽ tạo ảnh khác. Chỉ mở Flow khi thực sự cần ảnh chưa có. Nếu ảnh bị lỗi hoặc trống, ứng dụng thử lại rồi trả lỗi rõ ràng; không âm thầm thay bằng hình máy tính mẫu.

Công tắc AI được bật mặc định. Khi tắt, MuseAI chỉ được dùng hình có sẵn; kịch bản cũ còn yêu cầu ảnh mới sẽ báo cần bật AI. Để có bố cục phù hợp với tính năng mới, nên yêu cầu MuseAI viết bài mới thay vì đọc lại một kịch bản cũ vốn chỉ dùng kho mẫu.

## Dạy tiếng Anh bằng lời giảng tiếng Việt

Trong **Ngôn ngữ kịch bản / lời dẫn**, chọn **Dạy tiếng Anh: giảng Việt + phát âm Anh**. Ví dụ một cảnh sẽ đọc theo thứ tự:

1. Giọng Việt dẫn vào tình huống: “Bạn gặp người bạn mới vào buổi sáng và muốn mở lời thân thiện.”
2. Giọng Việt nêu nhu cầu: “Để chào buổi sáng, bạn có thể nói…”
3. Giọng Anh: “Good morning!”
4. Giọng Việt giải nghĩa, cách dùng; sau đó luyện lại nếu cần.

MuseAI trả `lesson_context` cho mỗi cảnh có câu mẫu tiếng Anh. Đây là 1–2 câu dẫn nói bằng tiếng Việt, mô tả hoàn cảnh và mục tiêu giao tiếp; ứng dụng đặt ở đầu `speech_segments` đúng một lần. Kịch bản xâu chuỗi tình huống, không chỉ liệt kê các thẻ từ vựng. Các hình đầu cảnh minh họa tình huống, rồi mới đến chữ/câu mẫu. Lời dẫn được tính vào audio, phụ đề và thời lượng nét vẽ. Nếu dùng lại kịch bản cũ thiếu `lesson_context`, cần yêu cầu MuseAI viết lại theo chế độ vẽ tay; ứng dụng báo rõ thay vì tự bịa bối cảnh.

Ví dụ hashtag cho bài đi chợ: `#giaotieplade #TiengAnhDiCho #MuaTraiCay #HocTiengAnh #TiengAnhGiaoTiep`. Đây là ví dụ theo nội dung, không phải bộ cố định cho mọi bài. Các kiểu video khác dùng hashtag kênh `#hochoidoday`.

MuseAI tách nội dung thành từng đoạn có nhãn ngôn ngữ. Các ví dụ tiếng Anh dùng giọng Anh, phần giải thích và nghĩa dùng giọng Việt. Phụ đề giữ đủ cả hai, được căn theo thời lượng âm thanh của từng đoạn; thời gian từng từ trong đoạn vẫn được ước lượng theo trọng số từ. Từ/câu Anh không bị thêm lời dẫn tiếng Việt khi dịch vụ giọng đọc gặp lỗi. Nếu không tạo được giọng nói thật hoặc không ghép được âm thanh, bài học trả lỗi, không thay phát âm bằng âm báo thử nghiệm hoặc đọc cả bài bằng một giọng.

Kịch bản bài học phải có `content_mode: "english_teaching_vi"`; mỗi cảnh có `speech_segments`, ví dụ:

```json
"speech_segments": [
  {"language": "vi", "text": "Để chào buổi sáng, bạn có thể nói:"},
  {"language": "en", "text": "Good morning!"},
  {"language": "vi", "text": "Nghĩa là chào buổi sáng."}
]
```

Kịch bản cũ chưa có nhãn ngôn ngữ cần được MuseAI viết lại bằng lựa chọn này; hệ thống không tự đoán một đoạn Latin không dấu là tiếng Việt hay tiếng Anh. Đoạn ôn tập và hẹn tập sau vẫn dùng lời Việt; có thể đánh dấu ví dụ Anh bằng `[en]...[/en]` trong nội dung nối tập.

Để dựng bài mẫu hai cảnh có giọng đọc thật và các hình khác nhau, chạy `video_studio/scripts/render_english_lesson_preview.py` bằng Python của dự án. Kết quả nằm ở `video_studio/output/english_lesson_vi_en_preview.mp4`. Có thể truyền `--script` trỏ đến JSON đã xuất từ MuseAI để dùng kịch bản bài học riêng.

## Series từ hai tập trở lên

- Tập đầu có đoạn giới thiệu bài học của tập tiếp theo.
- Các tập giữa có đoạn nhắc bài vừa học và đoạn giới thiệu bài kế tiếp.
- Tập cuối nhắc bài trước và kết thúc, không hẹn thêm tập.
- Các đoạn nối là cảnh thực trong kịch bản, được dựng hình, lồng tiếng và có phụ đề khi bật lồng tiếng.
- `next_episode_topic` được truyền nguyên nội dung sang yêu cầu MuseAI viết tập kế tiếp, để bài học được giới thiệu và bài học được viết cùng chủ đề. Nội dung do MuseAI viết vẫn cần được kiểm tra khi dùng cho bài giảng.
- `episode_learning_summary` của tập vừa hoàn thành được dùng cho lời ôn tập ở tập sau; phần giới thiệu tương lai không được đưa vào tóm tắt những gì đã xảy ra.
- Nếu kịch bản thiếu bài học kế tiếp của một tập chưa phải tập cuối, hệ thống báo lỗi rõ ràng, không tự bịa nội dung giới thiệu.

Chọn **Viết tiếp tập mới** để đọc bộ nhớ đã lưu và tiếp tục số tập, ví dụ sau tập 3 là tập 4. Bộ nhớ người que nằm ở `video_studio/temp/museai_flow_3d/series_memory_ledger_whiteboard.json`; bộ nhớ 3D dùng file riêng. Trong thư mục làm việc của mỗi series cũng có bản lưu bộ nhớ riêng. Hiện giao diện viết tiếp series gần nhất theo kiểu video đã chọn.

## Dữ liệu MuseAI trả về

Kịch bản gồm `visual_mode: "whiteboard"`, `story_title`, `character_anchor`, `environment_anchor`, `episode_learning_summary`, `next_episode_topic` và `scenes`.

Mỗi cảnh gồm lời đọc `narration`, tùy chọn `dialogue_lines`, mô tả `video_prompt` và danh sách `whiteboard_items`. Danh sách này cũng quyết định thứ tự tay vẽ:

| Loại | Thuộc tính bổ sung |
| --- | --- |
| `text` | `text`, `size` theo chiều rộng khung |
| `circle` | `r` theo chiều rộng khung, `label` |
| `box` | `w`, `h` theo chiều rộng/cao khung, `label` |
| `arrow` | Điểm cuối `x2`, `y2`, `label` |
| `stickman` | `h` theo chiều cao, `name`, `emotion` |
| `illustration` | `asset` trong thư viện màu, `w`, `h` là khung bao tối đa |
| `image` | `asset` là tên ảnh PNG/WebP trong `assets/whiteboard/`, `w`, `h` |
| `ai_image` | `prompt` mô tả hình cần AI tạo, `w`, `h` là khung bao tối đa |

Tên minh họa hợp lệ: `study_desk`, `browser`, `clock`, `book`, `phone`, `plant`, `chart`, `idea`, `brain`, `building`. Tỷ lệ ảnh được giữ nguyên khi đặt vào khung bao. Muốn dùng minh họa riêng, đặt ảnh PNG/WebP đã có nền trong suốt vào `video_studio/assets/whiteboard/`, rồi dùng phần tử `image` với tên file đó. Không dùng đường dẫn ra ngoài thư mục này. Các ảnh này cũng được vẽ viền trước, tô màu sau.

Khi gửi yêu cầu mới, MuseAI nhận cả danh sách ảnh bổ sung trong kho để chọn theo nội dung từng cảnh, ngoài các minh họa có sẵn. Ảnh tay được loại khỏi danh sách minh họa. Có thể phối nhiều hình ở vị trí/kích thước khác nhau trong một cảnh và yêu cầu AI tạo thêm hình khi cần.

Mọi phần tử có `x`, `y` chuẩn hóa 0–1 và `color` là `black`, `red`, `blue` hoặc `green`. Giữ hình trong vùng x=0.08–0.92, y=0.10–0.78 để dành chỗ cho phụ đề. Hỗ trợ cảm xúc `happy`, `sad`, `surprised`, `angry`, `neutral`, `thinking`. Font có dấu tiếng Việt được chọn từ hệ điều hành.

Thời lượng cảnh được đo từ file giọng đọc rồi mới dựng hình. Các phần tử hiện lần lượt và có khoảng dừng cuối cảnh để xem đủ sơ đồ. Phụ đề dùng bộ căn thời gian theo thời lượng câu của hệ thống hiện có; không phải nhận dạng từng từ bằng forced alignment. Khi tắt lồng tiếng, video không có âm thanh và thời lượng cảnh được ước tính từ số từ. Lỗi TTS hay ghép phụ đề ở chế độ có tiếng sẽ trả lỗi, không báo hoàn thành một video bị mất tiếng/phụ đề.

## Xem thử và kiểm tra

Từ thư mục gốc:

```powershell
.venv\Scripts\python.exe video_studio/scripts/render_whiteboard_preview.py
.venv\Scripts\python.exe video_studio/scripts/render_english_lesson_preview.py --ai-demo --output video_studio/output/english_ai_illustrations_preview.mp4
.venv\Scripts\python.exe -m pytest video_studio/tests/test_whiteboard_color_drawing.py video_studio/tests/test_museai_whiteboard_series.py video_studio/tests/test_whiteboard_video.py video_studio/tests/test_museai_3d.py video_studio/tests/test_subtitle_bottom_layout.py video_studio/tests/test_video_audio_sync_and_series.py -q
```

Lệnh xem thử tạo `video_studio/output/whiteboard_color_real_hand_1080p.mp4`, dài 16 giây, không lời đọc, cùng ảnh lúc đang vẽ và lúc hoàn thành. Thêm `--style stickman --output video_studio/output/stickman_real_hand.mp4` để xem người que với cùng bàn tay thật. Bài kiểm tra tích hợp dùng âm thanh tổng hợp để xác minh đường dựng MP4, phụ đề và thời lượng, không cần truy cập tài khoản MuseAI hoặc gọi dịch vụ TTS thật.

## Nguồn tham khảo thiết kế

- [kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director): cách tổ chức phong cách người que, biểu cảm và storyboard. MuseAI vẫn đảm nhiệm phần viết.
- [skys-xk/videomake_gpt](https://github.com/skys-xk/videomake_gpt): hướng dựng whiteboard bằng Pillow và FFmpeg từ lời đọc có sẵn.
- [ChenShuo2004/cs-board](https://github.com/ChenShuo2004/cs-board): cách chia cảnh, xuất hiện hình theo thời gian và quy trình whiteboard.

Tích hợp sử dụng bộ vẽ hiện có của dự án; không cài hoặc nhập các kho trên làm dịch vụ viết kịch bản thứ hai.
