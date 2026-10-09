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

## 13. Cô Lập Đa Ngôn Ngữ và Triệt Tiêu Pinyin Khỏi Giọng Tiếng Việt (Multivoice & Pinyin Isolation)
- **Hiện tượng lỗi**: 
  1. Giọng tiếng Việt cố đọc chữ Hán gây méo tiếng.
  2. Giọng tiếng Việt phát âm bập bẹ "nờ ho là xin chào" khi cố đọc phiên âm Pinyin Latin có thanh điệu Unicode (`nǐ hǎo`, `zǎo`...).
- **Nguyên nhân gốc rễ**: 
  - Microsoft Edge TTS `vi-VN` không hỗ trợ phân tích Pinyin tiếng Trung có thanh điệu (`ǐ`, `ǎo`, `ā`...). Khi gặp ký tự Latin lạ, engine đánh vần rời rạc từng chữ cái Latin thành "nờ-ho".
  - Mã nguồn cũ còn ghép `f"Đọc là {pinyin}."` và các đoạn Pinyin trong ngoặc đơn `(nǐ hǎo)` vào phân đoạn do giọng `vi-VN` đọc.
- **Quy tắc phòng ngừa**:
  1. **Tuyệt đối KHÔNG để giọng tiếng Việt đọc Pinyin**:
     - Bỏ hoàn toàn chuỗi `"Đọc là <pinyin>"`.
     - Pinyin CHỈ dùng để hiển thị trên phụ đề màn hình (visual subtitle) để mắt người xem theo dõi.
  2. **Quy chuẩn 4 phân đoạn âm thanh chuẩn (4-Segment Flow)**:
     - Đoạn 1: Lời dẫn tiếng Việt thuần túy (`clean_narr_vi`, giọng `vi-VN`, tốc độ `+0%`).
     - Đoạn 2: Giọng bản ngữ Trung Quốc phát âm chuẩn lần 1 (`chinese_text`, giọng `zh-CN-XiaoxiaoNeural`, tốc độ `-5%`).
     - Đoạn 3: Giọng bản ngữ Trung Quốc phát âm rõ ràng lần 2 (`chinese_text`, giọng `zh-CN-XiaoxiaoNeural`, tốc độ `-18%`).
     - Đoạn 4: Lời giải nghĩa / cách dùng thuần Việt (`clean_use_vi`, giọng `vi-VN`, tốc độ `+0%`).
  3. **Bộ lọc an toàn `clean_vietnamese_tts_text`**:
     - Lọc sạch chữ Hán CJK và các đoạn Pinyin trong ngoặc đơn.
     - Lọc các từ chứa ký tự Pinyin độc quyền (`[āēīōūǎěǐǒǔüǖǘǚǜ]`), TUYỆT ĐỐI không lọc nhầm nguyên âm tiếng Việt (`à, á, è, é...`).

## 14. Đồng Bộ Chữ Ký Hàm (Signature Parity & Keyword Argument Aliasing)
- **Hiện tượng lỗi**: `TypeError: generate_flow_batch_queue() got an unexpected keyword argument 'output_dir'`.
- **Nguyên nhân gốc rễ**: Khi tích hợp giữa hai module mới (`batch_producer.py` và `flow_image_service.py`), tên tham số truyền vào bị lệch (`temp_dir` vs `output_dir`, `status_callback` vs `progress_callback`), khiến Python ném lỗi ngoại lệ khi truyền qua keyword arguments.
- **Quy tắc phòng ngừa**:
  1. Hỗ trợ bí danh tham số (Keyword Argument Aliasing): Tại các điểm ranh giới module công khai, luôn hỗ trợ cả hai tên gọi thông dụng: `effective_dir = temp_dir or output_dir`, `effective_callback = status_callback or progress_callback`.
  2. Đồng bộ chữ ký hàm chặt chẽ trên toàn bộ codebase và có bài kiểm thử unit test / E2E với đầy đủ các keyword arguments thực tế.



## 15. Cơ Chế Bắt và Tải Video Stream Trực Tiếp Qua CDP Request (Bỏ Qua JS FileReader DOM)
- **Hiện tượng lỗi**: Video trên Google Flow (Veo 2) đã render xong hoàn tất trên giao diện chat và thẻ video hiển thị rõ ràng, nhưng hệ thống vẫn tiếp tục đếm giây lố lên hơn 800s - 900s và cuối cùng báo lỗi timeout.
- **Nguyên nhân gốc rễ**:
  1. *Lỗi bộ đọc JS FileReader*: Code cũ dùng `page.evaluate` chạy `fetch(src)` rồi đọc blob thành base64 qua `FileReader.readAsDataURL`. Với các video CDN dung lượng lớn (3-5MB) có header phân đoạn streaming, `fetch` trong JavaScript browser context bị lỗi CORS hoặc tràn bộ nhớ/abort, ném exception và bị bỏ qua, dẫn đến vòng lặp `while True` tiếp tục chạy đến hết timeout.
  2. *Bẫy logic `seen_video_urls`*: Pre-scan trước khi submit prompt đã đưa URL video hiện có trên trang vào `seen_video_urls`. Khi video mới xuất hiện nếu Flow tái sử dụng URL hoặc sau lần retry, điều kiện `if src not in seen_video_urls` loại bỏ luôn thẻ video đó, khiến hệ thống không bao giờ nhận diện được clip đã hoàn thành.
  3. *Timeout quá dài*: `video_timeout_seconds` đặt ở mức 1800s (30 phút) khiến thời gian chờ bị kéo dài bất hợp lý khi có lỗi xảy ra.
- **Quy tắc phòng ngừa**:
  1. **Ưu tiên tải trực tiếp bằng `page.request.get(src)`**:
     - Playwright `page.request` kế thừa 100% session, cookie, token authentication của Chrome profile mà không bị giới hạn bởi CORS của page hay memory reader của JavaScript.
     - Tải tệp MP4 dung lượng nhiều MB chỉ trong vòng 0.5 giây.
  2. **Quản lý URL cục bộ & Lọc trùng lặp bằng SHA-256 Hash**:
     - Pre-scan URL chỉ lưu trong `pre_existing_urls` cục bộ cho lượt submit đó, không khóa vĩnh viễn trong instance.
     - Kiểm định video mới dựa trên `hashlib.sha256(video_bytes)` so với `self.seen_video_hashes`.
     - Sau 20s nếu chưa thấy URL mới, tự động quét lại toàn bộ thẻ video trên trang để kiểm tra xem có video nào có hash mới chưa từng lưu không.
  3. **Rút ngắn Timeout về mức hợp lý**:
     - Cấu hình `video_timeout_seconds = 300` (5 phút), đủ an toàn cho Veo 2 (thường sinh trong 60-150s) và không làm người dùng chờ đợi vô ích.

## 16. Ngăn Chặn WinError 32 File Lock Trên Windows và Thiết Kế Phụ Đề Chuẩn Safe Zone Cho Video Dọc
- **Hiện tượng lỗi**:
  1. *Lỗi render [WinError 32]*: Khi biên tập video, MoviePy `write_videofile` ném ngoại lệ: `[WinError 32] The process cannot access the file because it is being used by another process: '...\\temp\\temp-audio-part1.m4a'`.
  2. *Phụ đề che phần lớn hình ảnh*: Chữ phụ đề quá to (`font_size = 72`), căn giữa màn hình (`Alignment = 5`, `y = 960` trên khung hình 1920), đè ngay giữa nhân vật và hình ảnh chính.
  3. *Mạch truyện ngắt quãng*: Câu thoại giữa các cảnh nhảy ý đột ngột ("lúc này lúc kia"), thiếu liên từ chuyển tiếp.
- **Nguyên nhân gốc rễ**:
  1. *Cơ chế dọn dẹp file tạm của MoviePy trên Windows*: Tham số `remove_temp=True` khiến MoviePy gọi `os.remove(temp_audiofile)` ngay khi ffmpeg process vừa kết thúc. Trên Windows, handle file audio thường chưa được giải phóng hoàn toàn tại thời điểm đó, dẫn đến PermissionError / WinError 32. Ngoài ra, việc dùng tên cố định `temp-audio-part1.m4a` dễ gây xung đột giữa các lần chạy.
  2. *Thiết kế phụ đề kiểu cũ*: Căn giữa tâm màn hình (Center) với font quá lớn làm mất thẩm mỹ và che khuất chủ thể video AI.
  3. *Prompt LLM thiếu quy tắc bắc cầu*: Các cảnh được sinh như các đoạn độc lập mà không có chỉ thị về tính liên tục một dòng chảy (continuous narrative flow).
- **Quy tắc phòng ngừa**:
  1. **Tạo tên file tạm ngẫu nhiên UUID và dọn dẹp an toàn**:
     - Luôn sinh tên ngẫu nhiên: `f"temp-audio-{uuid.uuid4().hex[:8]}-part{part_num}.m4a"`.
     - Đặt `remove_temp=False` trong `write_videofile` để MoviePy không xóa đồng bộ.
     - Đóng toàn bộ handle clips (`part_video_raw.close()`, `c.close()`, `gc.collect()`), sau đó dùng hàm `_safe_delete_file` với retry có độ trễ để dọn dẹp file tạm mà không làm crash pipeline.
  2. **Chuẩn hóa Phụ đề Safe Zone ở đáy màn hình**:
     - Cho video dọc (9:16 Shorts/Reels/TikTok): `Alignment = 2` (Bottom Center), `MarginV = 260` (cách đáy 260px, ở 1/6 dưới cùng màn hình).
     - Thu nhỏ `font_size` từ 72 về **44** (tinh tế, thanh thoát), `Outline = 3`, `Shadow = 1`.
  3. **Ép buộc mạch truyện liền mạch một dòng chảy**:
     - Thêm chỉ thị bắt buộc trong System Prompt và User Prompt: Toàn bộ video là MỘT CÂU CHUYỆN LIÊN TỤC, từ cảnh 2 trở đi bắt buộc phải có từ nối / liên từ bắc cầu (*thế nhưng, chính vì vậy, điều bất ngờ là, để làm được điều đó...*).
     - Loại bỏ triệt để chuỗi `f"Đọc là {pinyin}."` khỏi câu thoại nói để không gây gián đoạn luồng nghe.


## 17. Đồng Bộ Thời Lượng Tuyệt Đối (Video-Audio Sync Loop) và Mạch Truyện Chuỗi Tập (Series Continuity)
- **Hiện tượng lỗi**:
  1. *Video hết nhưng tiếng vẫn nói*: Video AI (Veo/Google Flow) kết thúc hoặc đứng hình bất động (freeze frame) từ giây thứ 4-5 trong khi giọng đọc tiếp tục kéo dài đến giây thứ 8-9, tạo cảm giác cụt hứng và lỗi kỹ thuật.
  2. *Hình ảnh và lời thoại không liên quan*: Lời thoại nói về hành động cụ thể nhưng prompt video lại mô tả phong cảnh chung chung không có hành động tương ứng.
  3. *Mạch truyện nhảy cóc giữa các video*: Khi sản xuất batch nhiều video hoặc chạy xưởng tự động, video 1 đang nói về câu chuyện A thì sang video 2 lại nhảy sang chủ đề X không liên quan ("đang abc cái nhảy qua 123").
- **Nguyên nhân gốc rễ**:
  1. *Cơ chế mặc định của MoviePy*: Hàm `clip.set_duration(dur)` trên `VideoFileClip` khi `dur > clip.duration` sẽ tự động đóng băng frame cuối (freeze frame), biến video thành ảnh chết trong khi âm thanh vẫn chạy. Khi ghép nhiều clip, nếu không ép duration tổng thể khớp chính xác với `combined_audio.duration`, thời lượng hình và tiếng sẽ bị lệch.
  2. *Thiếu chỉ thị Action-Narration Parity trong prompt*: Prompt kịch bản không yêu cầu bắt buộc trường `video_prompt` phải mô tả chuyển động cơ thể, cử chỉ khớp 100% với từng câu nói trong `narration`.
  3. *Sinh kịch bản độc lập (Stateless Script Generation)*: Các hàm tạo video hàng loạt gọi `generate_script(topic)` độc lập, LLM không nhận được ngữ cảnh kết thúc của video trước đó, dẫn đến mất tính liên kết câu chuyện.
- **Quy tắc phòng ngừa**:
  1. **Tự động lặp chuyển động mượt mà (Video Loop) và Cắt chuẩn xác**:
     - Trong `process_video_clip`: Nếu video ngắn hơn audio, sử dụng `vfx.loop(clip, duration=target_duration)` để chuyển động của nhân vật diễn ra liên tục, tự nhiên, triệt tiêu hoàn toàn hiện tượng freeze frame. Nếu video dài hơn audio, sử dụng `clip.subclip(0, target_duration)`.
     - Trong `compile_video_with_audio_and_subtitles`: Đặt `part_video_raw = part_video_raw.set_duration(total_audio_dur).set_audio(combined_audio)` đảm bảo thời lượng hình và tiếng kết thúc cùng một mili-giây.
  2. **Đồng bộ 1:1 Hành động hình ảnh và Lời thoại (Action-Narration Parity)**:
     - Thêm chỉ thị bắt buộc trong Prompt của LLM: Mọi `video_prompt` phải mô tả hành động, biểu cảm, cử chỉ cụ thể khớp trực tiếp với từng câu nói trong `narration`, loại bỏ hoàn toàn các mô tả tĩnh chung chung.
  3. **Cơ chế nối tiếp mạch truyện nhiều tập (Multi-Episode Series Continuity)**:
     - Hỗ trợ tham số `previous_context` trong `generate_script`.
     - Phân bổ chủ đề dạng Story Arc (Tập 1: Mở đầu & Khởi nguồn, Tập 2: Diễn biến & Thử thách, Tập 3: Đỉnh điểm & Hồi kết).
     - Trong vòng lặp tạo video hàng loạt (`run_batch_video_loop`), tự động trích xuất tóm tắt mở đầu và kết thúc của video trước để truyền làm tiền đề ngữ cảnh cho video sau.
