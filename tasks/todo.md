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

- [ ] **Bước 5: Kiểm chứng toàn diện (Verification)**
  - [ ] Chạy lại toàn bộ test suite trong `tests/`.
  - [ ] Kiểm tra tính toàn vẹn của tiến trình đang chạy và cập nhật sơ đồ README.md.
