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

## 6. Trao Quyền Động Não Tự Động Hoàn Toàn Cho LLM (Autonomous LLM Ideation)
- **Kinh nghiệm thực tế**: Người dùng yêu cầu hệ thống phải tự sáng tạo đề tài hoàn toàn mới lạ, không bị gò bó bởi danh sách hạt giống cứng (`ANIMAL_SEEDS`).
- **Giải pháp tối ưu**:
  - Sử dụng prompt vai trò Giám đốc Sáng tạo (Creative Director), kích hoạt năng lực tự do động não (*Autonomous Brainstorming*) của LLM (Gemini) để tự chọn con vật và tình huống đời thường bất ngờ.
  - Áp dụng cấu trúc 4 phần giữ chân người xem cao nhất: `Hook` ➔ `Development` ➔ `Twist` ➔ `Ending`.
  - Phối hợp với thuật toán Smart Gap-filling để tự động quét lịch YouTube Studio và lấp đầy các slot còn thiếu (08:00, 11:00, 18:00) một cách liền mạch.

## 9. Nguyên Tắc Xử Lý Tuần Tự Tuyệt Đối (Strict Sequential Video-by-Video Lifecycle)
- **Hiện tượng lỗi**: Chưa render và lưu xong video 1 đã vội gửi tiếp prompt video 2 vào cùng một tab Gemini Web, khiến Gemini bị ngắt tiến trình hoặc quá tải.
- **Nguyên nhân gốc rễ**: Thiếu chốt chặn tuần tự khép kín (End-to-End per Video): không đợi hoàn tất cả 2 bước (Lưu video ➔ Đăng video) trước khi kích hoạt video tiếp theo.
- **Quy tắc phòng ngừa**:
  - Tuân thủ quy trình tuần tự nghiêm ngặt từng video:
    1. Gửi prompt Video N lên Gemini Web.
    2. Kiên nhẫn theo dõi Gemini render xong 100% ➔ Tải và lưu file `.mp4` vào `output/`.
    3. Upload và đặt lịch hẹn giờ Video N lên YouTube Studio.
    4. Mở cuộc trò chuyện mới (*New Chat*) trên Gemini Web để làm sạch ngữ cảnh.
    5. **CHỈ KHI ĐÓ MỚI BẮT ĐẦU** Video N + 1.
  - Nếu Video N gặp lỗi hoặc chưa tạo xong sau các lần thử lại: Dừng lại ngay lập tức, không gửi prompt của video tiếp theo.

## 10. Điều Phối Hàng Đợi Song Song Flow Batch (Flow Batch Queue Engine)
- **Vấn đề tiềm ẩn**: Khi sinh ảnh song song qua Chrome CDP với nhiều workers cùng lúc, nếu submit đồng thời ở t=0 sẽ gây race condition trên DOM input của trang Google Flow hoặc kích hoạt rate-limit / High Demand của server.
- **Giải pháp kỹ thuật**:
  1. Giới hạn `max_workers` ở mức tối đa 4 (khớp năng lực xử lý upstream của Google Flow).
  2. Áp dụng cơ chế Staggered Dispatch (`stagger_delay` 1.5s) giữa các worker để phân bổ đều tải gửi lệnh.
  3. Quản lý trạng thái và kết quả trên từng `FlowImageTask` độc lập kèm exponential backoff (`min(2^retry, 15)s`).
  4. Đảm bảo bảo toàn thứ tự phân cảnh 1..N và cơ chế tự phục hồi (Self-Healing Fallback) kế thừa bối cảnh hợp lệ liền trước nếu gặp lỗi quá tải sau toàn bộ số lần retry.

## 11. Tối Ưu Hóa Tương Tranh Cho Pipeline TTS: ThreadPoolExecutor vs asyncio
- **Vấn đề tiềm ẩn**:
  - Khi song song hóa tiến trình sinh giọng đọc AI (TTS) trong ứng dụng dựa trên nền tảng Streamlit, việc lạm dụng `asyncio.run()` hoặc gọi coroutine bất đồng bộ trực tiếp thường gây lỗi xung đột event loop (`RuntimeError: This event loop is already running`).
  - Hơn nữa, việc các luồng hoàn thành bất đồng bộ không theo thứ tự tự nhiên (cảnh 3 ngắn kết thúc trước cảnh 1 dài) nếu không được kiểm soát sẽ làm xáo trộn cấu trúc danh sách kịch bản `scenes`, dẫn đến lệch phụ đề và lời thoại của toàn bộ video thành phẩm.
- **Giải pháp kỹ thuật**:
  1. **Ưu tiên `concurrent.futures.ThreadPoolExecutor` thay vì `asyncio`**: Tận dụng cơ chế giải phóng GIL của `subprocess.run` (gọi edge-tts CLI), hoàn toàn cách ly và an toàn 100% trong môi trường Streamlit và đa nền tảng Windows mà không gặp lỗi ngắt WebSocket hay xung đột event loop.
  2. **Bảo toàn thứ tự phân cảnh 100% bằng `future_to_index` mapping**: Ánh xạ tương ứng `future_to_idx = {executor.submit(_worker, task): idx}`. Bất kể luồng nào hoàn thành trước hay sau, dữ liệu kết quả luôn được gán chính xác in-place vào đúng phần tử `scenes[idx]`.
  3. **Kiểm tra và tái sử dụng bộ nhớ đệm (Cache Reuse) trước khi vào Pool**: Bỏ qua việc submit các phân cảnh đã có file audio hợp lệ trên đĩa (>1000 bytes) để tiết kiệm băng thông và tăng tốc độ xử lý tối đa.
  4. **Tích hợp bộ đo thời lượng `get_audio_duration` tự động**: Sử dụng mutagen/wave/moviepy để gán `audio_duration` chính xác ngay sau khi sinh âm thanh.
## 12. Kiểm Soát Khối Lệnh Đa Nhánh (Multi-Branch Refactoring) và Kiểm Thử Tích Hợp E2E
- **Hiện tượng lỗi**: Khi bổ sung khối rẽ nhánh mới (`if turbo_mode: ... else: ...`) bao bọc một đoạn logic cũ lớn, nguy cơ xảy ra `IndentationError` do căn chỉnh thụt dòng không đồng bộ giữa các tầng lặp (`for i, sc in enumerate(scenes)`).
- **Nguyên nhân gốc rễ**: Thay thế mã bằng công cụ chỉnh sửa tự động với phạm vi dòng không bao trọn toàn bộ khối lệnh con hoặc căn lề thụt lùi giữa các khối `if-else` lồng nhau.
- **Quy tắc phòng ngừa**:
  1. **Quy chuẩn thụt lề 4 spaces**: Mọi khối lệnh con bên trong `else:` phải được tăng thụt lề đều đặn thêm 4 spaces cho tất cả các câu lệnh bên trong.
  2. **Chạy linter/syntax check ngay sau khi sửa**: Luôn chạy `python -m py_compile <file>` hoặc unit test tối thiểu ngay sau mỗi thao tác chỉnh sửa khối code lớn để phát hiện lỗi cú pháp tức thì.
  3. **Kiểm thử tích hợp End-to-End (E2E) với mock boundary**: Viết bài kiểm thử e2e bao trọn chu trình từ đầu vào Topic đến đầu ra file MP4 cho cả 2 nhánh (`turbo_mode=True` và `turbo_mode=False`), đảm bảo mọi nhánh rẽ đều được thực thi và xác nhận tính toàn vẹn.

## 13. Cô Lập Đa Ngôn Ngữ Tuyệt Đối Trong Pipeline TTS (Multivoice Language Isolation)
- **Hiện tượng lỗi**: Giọng đọc tiếng Việt (`vi-VN-HoaiMyNeural`) cố phát âm chữ Hán giản thể (CJK) khi LLM chèn chữ Hán vào các trường dẫn giải tiếng Việt (`narration_vi` hoặc `usage_vi`), dẫn đến phát âm kỳ dị, sai lệch hoặc nuốt chữ.
- **Nguyên nhân gốc rễ**: Khi mô hình sinh kịch bản dạy học tiếng Trung, nó thường tự nhiên kèm theo chữ Hán vào câu giải thích tiếng Việt (ví dụ: *"Từ 你好 dùng khi chào hỏi"*). Nếu phân đoạn này được giao cho giọng tiếng Việt, engine TTS của Microsoft Edge sẽ cố phân tích chữ Hán bằng âm đọc tiếng Việt sai lệch.
- **Quy tắc phòng ngừa**:
  1. **Phòng thủ đa lớp (Defense-in-Depth)**:
     - *Lớp 1 (Data Boundary)*: Làm sạch ở tầng kịch bản `normalize_chinese_teaching_scenes` (`batch_producer.py`) và `_sanitize_scenes` (`studio_editorial_service.py`) bằng regex loại bỏ ký tự CJK `[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+`.
     - *Lớp 2 (Engine Guardrail)*: Trong `generate_multivoice_tts` (`tts_service.py`), mọi phân đoạn gửi tới giọng `vi-VN` đều bắt buộc chạy qua `clean_vietnamese_tts_text`; phân đoạn chữ Hán chỉ giao độc quyền 100% cho giọng Trung Quốc (`zh-CN-XiaoxiaoNeural`).
  2. **Phân định trách nhiệm phát âm rõ ràng**:
     - Giọng `vi-VN`: Độc quyền lời dẫn tiếng Việt và phiên âm Pinyin (mẫu `"Đọc là <pinyin>."`).
     - Giọng `zh-CN`: Độc quyền chữ Hán giản thể chuẩn xác (`chinese_text`).

## 14. Đồng Bộ Chữ Ký Hàm (Signature Parity & Keyword Argument Aliasing)
- **Hiện tượng lỗi**: `TypeError: generate_flow_batch_queue() got an unexpected keyword argument 'output_dir'`.
- **Nguyên nhân gốc rễ**: Khi tích hợp giữa hai module mới (`batch_producer.py` và `flow_image_service.py`), tên tham số truyền vào bị lệch (`temp_dir` vs `output_dir`, `status_callback` vs `progress_callback`), khiến Python ném lỗi ngoại lệ khi truyền qua keyword arguments.
- **Quy tắc phòng ngừa**:
  1. Hỗ trợ bí danh tham số (Keyword Argument Aliasing): Tại các điểm ranh giới module công khai, luôn hỗ trợ cả hai tên gọi thông dụng: `effective_dir = temp_dir or output_dir`, `effective_callback = status_callback or progress_callback`.
  2. Đồng bộ chữ ký hàm chặt chẽ trên toàn bộ codebase và có bài kiểm thử unit test / E2E với đầy đủ các keyword arguments thực tế.

