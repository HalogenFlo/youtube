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
- [x] **Task 5: Viết bộ unit test `tests/test_skip_cancel_job.py` và kiểm chứng hồi quy**
  + Kiểm tra skip running job, cancel queued job, pipeline early abort.
  + Chạy full test suite (`pytest`) đạt 119/119 tests pass (100%).

