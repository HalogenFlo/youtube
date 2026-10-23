<!-- Chức năng: Ghi nhận kiến trúc hoạt hình và cách kiểm chứng. Lý do: Phân biệt tính năng đã tích hợp với nguồn tham khảo. -->
# Hoạt hình theo timeline

`src/cartoon_timeline.py` lập kế hoạch theo prompt: bối cảnh forest/city/lab/space/coast/meadow và hành động pick/wave/run/point. Mỗi cảnh có ba giai đoạn approach → action → resolve; thân, đầu, tay, khuỷu tay, chân và đầu gối được vẽ riêng. Nhân vật di chuyển đến vị trí đích rồi thực hiện hành động, không lắc toàn bộ một ảnh tĩnh.

Canvas và bộ dựng Python dùng chung danh sách lệnh vẽ tại từng frame. Render ở thời điểm bất kỳ không phụ thuộc thứ tự gọi. HTML xem trước dừng ở cuối cảnh; Space tạm dừng/tiếp tục, R chạy lại. Cảnh ngang/dọc có bố trí riêng. Màu áo CH01 giữ #8CCFE8.

Nhánh Chrome dùng Playwright đã có trong requirements, không cần Selenium. Khi không mở được Chrome, bộ dựng Python vẫn dùng đúng timeline và bố cục. Đây là bộ vẽ vector hoạt hình đơn giản; chưa phải hệ thống sinh hình tùy ý từ prompt hoặc thư viện diễn xuất chuyên nghiệp.

## Nguồn và skill

- https://github.com/heygen-com/hyperframes — skill animation, keyframes, creative đã cài tại `video_studio/skills/`; dùng nguyên tắc seek tất định, chia beat và dựng cảnh nhiều lớp. Không cài toàn bộ engine HyperFrames.
- https://github.com/motion-canvas/examples — tham khảo tổ chức chuyển động theo thời gian; không thêm dependency Motion Canvas.
- https://github.com/nexu-io/html-video — tham khảo storyboard nhiều cảnh.
- https://github.com/siegerts/skill-canvas-video — tham khảo Canvas → MP4.
- https://github.com/EsotericSoftware/spine-runtimes — tham khảo tư duy khớp xương; không tích hợp mã hoặc asset Spine.

Các skill tải về giữ nguyên hướng dẫn và tài nguyên của upstream. Bộ vẽ trong src là phần triển khai riêng của dự án.

## Flow và lời thoại

- Nút submit sinh ảnh hỗ trợ aria-label tiếng Việt “Bắt đầu tạo”.
- Kịch bản đầu vào phải qua schema trước khi vào bước biên tập.
- Nếu bản biên tập thiếu narration, giữ bản nháp gốc và đánh dấu chưa xác minh; không chấp nhận lời thoại rỗng.

## Kiểm chứng

Tại thư mục gốc, đặt PYTHONPATH tới `video_studio`, dùng Python của `.venv` chạy `-m pytest -q -k "not add_factory_jobs"` với `test_cartoon_timeline.py`, `test_flow_video_no_fallback.py`, `test_flow_2d_and_video_downloader.py` và `test_dynamic_story_scenes.py`.

Mẫu trong `output/animation_upgrade_preview/`: landscape.mp4 và portrait.mp4 (6 giây, 24 fps, 144 frame), canvas_browser.mp4 (3 giây, 72 frame qua Chrome), cùng HTML và bảng frame. `flow_live_check.png` là kết quả một lượt tạo và tải ảnh Flow thật thành công. Video mẫu không có giọng đọc đầu vào nên audio là track câm dùng để kiểm tra mux; không dùng mẫu này làm chứng cứ chất lượng TTS.

Kết quả kiểm tra: 18 bài qua; loại riêng bài thêm job vào hàng đợi thật. Video ngang/dọc giải mã được 144/144 frame khác nhau. Checkpoint kịch bản cũ sai schema được sinh lại thay vì khôi phục lời thoại rỗng.
