# Bài Học Kinh Nghiệm (Lessons Learned)

## 1. Tránh import thư viện nặng (Diffusers / PyTorch) ở Module Level
- **Hiện tượng lỗi**: `AttributeError: '_DummyXPU' object has no attribute 'device_count'` và `ImportError: cannot import name 'CLIPImageProcessor' from 'transformers'`.
- **Nguyên nhân gốc rễ**: 
  - `diffusers` được import ngay tại đầu tệp `src/image_service.py` và `src/video_gen_service.py`. Khi `src/app.py` import các hàm này, Python buộc phải tải toàn bộ `diffusers` và các phụ thuộc nội bộ (`torch.xpu`, `transformers`).
  - Trên Windows, phiên bản `diffusers` và `transformers` cục bộ có thể xung đột phiên bản hoặc thiếu các thuộc tính phần cứng (như Intel XPU), dẫn đến crash ứng dụng Streamlit ngay khi vừa khởi động dù người dùng chỉ muốn dùng Google Flow.
- **Quy tắc phòng ngừa**:
  - **Luôn sử dụng Lazy Import** cho các mô hình AI/ML nặng (`diffusers`, `WanPipeline`, `StableDiffusionPipeline`, `torch`).
  - Chỉ import bên trong hàm thực thi cụ thể (`_setup_pipeline`) khi người dùng thực sự kích hoạt tính năng đó.
  - Các service độc lập như Google Flow hoặc Web UI phải khởi động nhanh, không bị chặn bởi các module local AI bị lỗi.

## 2. Quy chuẩn tệp Windows Batch (.bat) tương thích 100% CMD
- **Hiện tượng lỗi**: Double-click file `.bat` bị tắt ngay lập tức, báo các lỗi `'dp0"' is not recognized`, syntax error hoặc crash cửa sổ command prompt.
- **Nguyên nhân gốc rễ**: 
  - Tệp `.bat` bị lưu theo chuẩn xuống dòng Unix LF (`\n`) thay vì Windows CRLF (`\r\n`).
  - Dùng `goto` bên trong khối ngoặc đơn `if (...)`, khiến `cmd.exe` bị lỗi phân tích cú pháp khi nhảy nhãn.
  - Sử dụng ký tự đặc biệt như `&` không có escape, bị hiểu lầm thành toán tử nối lệnh.
- **Quy tắc phòng ngừa**:
  - Mọi tệp `.bat` trên Windows BẮT BUỘC phải dùng CRLF (`\r\n`).
  - Sử dụng cấu trúc rẽ nhánh một dòng: `if "%opt%"=="1" goto label` thay vì khối lệnh có ngoặc đơn phức tạp.
  - Luôn kiểm tra chạy thử qua `cmd.exe /c filename.bat` trước khi bàn giao.

## 3. Bản vá MoviePy `TypeError: must be real number, not NoneType` trên Python 3.12
- **Hiện tượng lỗi**: Khi gọi `write_videofile` với `fps=24` hoặc `fps=30`, ffmpeg writer ném lỗi `TypeError: must be real number, not NoneType` ở dòng `'-r', '%.02f' % fps`.
- **Nguyên nhân gốc rễ**:
  - Decorator `use_clip_fps_by_default` của MoviePy dùng `co_varnames` kiểm tra tham số, nhưng trên Python 3.12 với decorator 5.x, hàm bọc bên trong có `co_varnames=('args', 'kw')`, làm mất giá trị `fps` thành `None`.
- **Quy tắc phòng ngừa**:
  - Áp dụng monkey-patch tại `src/__init__.py` và `src/video_compiler.py`: gán `_safe_ffmpeg_write_video` vào `moviepy.video.VideoClip.ffmpeg_write_video` để tự động khôi phục `actual_fps = fps or getattr(clip, 'fps', None) or 30`.

## 4. Cô lập State và Background Workers trong Unit Tests
- **Hiện tượng lỗi**: Các bài test chạy tuần tự bị ảnh hưởng kết quả (`AssertionError: 5 != 3` hoặc mock method bị gọi bất ngờ từ luồng khác).
- **Nguyên nhân gốc rễ**: Khi test thêm job vào factory mà không cô lập `STATE_PATH` bằng `tempfile.TemporaryDirectory()`, file state thực tế bị ghi đè dữ liệu. Đồng thời, `ensure_factory_worker` khởi động thread nền thật, dẫn đến thread này xử lý job trong lúc các test khác đang chạy.
- **Quy tắc phòng ngừa**:
  - Mọi bài test liên quan đến `autonomous_factory` BẮT BUỘC phải dùng `unittest.mock.patch.object(factory, 'STATE_PATH', ...)` trỏ vào thư mục tạm.
  - BẮT BUỘC mock `factory.ensure_factory_worker` trừ khi bài test đó chuyên dụng để kiểm thử lifecycle của worker.

## 5. Trải nghiệm 1-Click: Tự Động Kết Nối Thay Vì Chặn Bằng Error Popup
- **Hiện tượng lỗi**: Người dùng click nút trên UI nhưng bị chặn lại bởi thông báo lỗi yêu cầu mở tiến trình ngoài desktop.
- **Nguyên nhân gốc rễ**: Đặt điều kiện kiểm tra cứng ở tầng giao diện (`elif not flow_ready: st.error(...)`) thay vì cơ chế tự phục hồi (Self-Healing / Auto-Launch).
- **Quy tắc phòng ngừa**:
  - Tầng UI phải cung cấp trải nghiệm mượt mà: nếu dịch vụ phụ thuộc chưa bật, tự động kích hoạt tiến trình trong nền và đưa yêu cầu vào hàng đợi.
  - Bổ sung cơ chế Heartbeat Auto-Refresh (ví dụ: `time.sleep(2.5)` + `st.rerun()`) để người dùng thấy tiến độ thay đổi theo thời gian thực mà không cần thao tác thêm.

