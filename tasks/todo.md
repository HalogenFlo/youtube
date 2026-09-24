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


