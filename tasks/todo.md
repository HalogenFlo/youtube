# Kế Hoạch Tích Hợp Google Flow ("gg flow") & Progressive Layering Video Engine

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



