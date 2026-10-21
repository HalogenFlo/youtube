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


## 18. Cơ Chế Ngắt Tức Thì (Instant Cancellation) và Tự Phục Hồi Hàng Đợi (Zombie Job Auto-Recovery)
- **Hiện tượng lỗi**:
  - Người dùng bấm nút "Hủy việc này" hoặc "Bỏ qua video này" trên giao diện xưởng, nhưng hệ thống vẫn tiếp tục đứng chờ ở "Đang chờ: 1, Đang chạy: 0" mà việc tiếp theo không chịu chạy.
- **Nguyên nhân gốc rễ**:
  1. *Lỗ hổng Abort Gap*: Khi người dùng bấm Hủy/Bỏ qua, mã nguồn chỉ cập nhật trạng thái trong file JSON sang `failed`. Tuy nhiên, các tiến trình I/O dài hạn (`generate_flow_video` 300s, `generate_flow_image` 90s, `FlowBatchQueueEngine`, `TTS Parallel`) không nhận `is_cancelled_callback`. Worker thread nền vẫn tiếp tục bị giam cầm trong tiến trình cũ hàng phút cho đến khi xong hết tất cả các cảnh của công việc đã hủy rồi mới thoát ra.
  2. *Lỗi Zombie Job chặn đứng hàng đợi*: Nếu một công việc bị đánh dấu là `running` trong JSON nhưng worker thread thực thi nó đã thoát hoặc bị mồ côi, hàm `_next_job()` kiểm tra `any(job["status"] == "running")` sẽ luôn trả về `None`, khiến toàn bộ hàng đợi phía sau bị khóa cứng (deadlock).
- **Quy tắc phòng ngừa**:
  1. **Truyền `is_cancelled_callback` xuyên suốt mọi tác vụ con**:
     - `generate_scene_video` và `generate_scene_image` (Playwright): Kiểm tra `is_cancelled()` trong từng chu kỳ polling 1-2 giây. Nếu có lệnh hủy, lập tức ngắt ngay, trả về `False, "Đã bỏ qua theo yêu cầu người dùng"`.
     - `FlowBatchQueueEngine.process_tasks`: Kiểm tra cancellation trong vòng lặp thu hoạch kết quả; hủy ngay các futures còn lại và thoát ThreadPoolExecutor tức thì.
  2. **Giải phóng ngay `_CURRENT_RUNNING_JOB_ID` và Đánh thức Worker**:
     - Khi gọi `skip_current_job` hoặc `cancel_job`: Đặt `_CURRENT_RUNNING_JOB_ID = None` ngay lập tức và gọi `_WAKE_EVENT.set()`.
  3. **Cơ chế tự phục hồi Zombie Job (`recover_stale_running_jobs`)**:
     - Tự động quét và đưa các running job mồ côi (không có active worker thread) về `queued` để giải phóng hàng đợi, đảm bảo dây chuyền luôn tuần tự bốc việc tiếp theo ngay khi có chỗ trống.
  4. **Cung cấp nút reset chủ động trên UI**:
     - Bổ sung nút `🔄 Khởi động lại dây chuyền (Reset Worker)` để người dùng có thể tự giải phóng trạng thái kẹt và đánh thức worker bất cứ lúc nào.


## 19. Xử Lý Phòng Thủ Kiểu Dữ Liệu LLM & State JSON (Chống Lỗi 'str' object has no attribute 'get')
- **Hiện tượng lỗi**:
  - Dây chuyền sản xuất tự động dừng lại đột ngột với thông báo: `Dây chuyền gặp lỗi: 'str' object has no attribute 'get'` (thể hiện trên giao diện là: `Cần xử lý · Dây chuyền gặp lỗi: 'str' object has no attribute 'get'`).
- **Nguyên nhân gốc rễ**:
  1. *Tính phi tất định của LLM (LLM Non-Determinism)*: Khi yêu cầu Ollama sinh hoặc biên tập kịch bản phân cảnh (`scenes`), mặc dù system prompt yêu cầu JSON object, mô hình đôi khi trả về danh sách các chuỗi thô: `{"scenes": ["Cảnh 1: Lời dẫn...", "Cảnh 2: Lời dẫn..."]}` thay vì danh sách các dict `[{"scene_num": 1, "narration": "..."}]`.
  2. *Giả định ngây thơ về cấu trúc dữ liệu*: Các hàm xử lý kịch bản (`_sanitize_scenes`, `build_exact_tts_timestamps`, `split_scenes_into_parts`, `compile_video_pipeline`, `generate_video_metadata`, `generate_scenes_tts_parallel`, `generate_flow_batch_queue`) lặp qua các phần tử của `scenes` và gọi trực tiếp `scene.get(...)` mà không kiểm tra `isinstance(scene, dict)`.
  3. *Truy xuất thuộc tính lồng nhau không an toàn*: Trong `autonomous_factory.py`: `metadata.get("editorial_report", {}).get(...)` nếu `metadata["editorial_report"]` tồn tại và mang kiểu chuỗi `str`, giá trị fallback `{}` bị bỏ qua, dẫn đến việc gọi `.get()` trên `str`.
  4. *Dữ liệu ngoại vi thoái hóa*: File lưu điểm kỹ năng (`studio_skill_scores.json`) hoặc danh sách tabs từ Chrome CDP (`/json/list`) có thể chứa giá trị string hoặc phần tử không phải dict.
- **Quy tắc phòng ngừa**:
  1. **Chuẩn hóa phòng thủ (Defensive Data Normalization) ngay tại biên (Boundary)**:
     - Trong `_sanitize_scenes` và `produce_single_video_pipeline`: Kiểm tra từng phần tử `raw_item`. Nếu là `str`, tự động bọc thành dict hợp lệ `{"scene_num": i, "narration": raw_item, "video_prompt": ...}` trước khi chuyển tiếp cho bất kỳ module nào khác.
  2. **Luôn kiểm tra `isinstance(target, dict)` trước khi gọi `.get()`**:
     - Thay vì `metadata.get("editorial_report", {}).get(...)`, luôn tách thành:
       ```python
       editorial_report = metadata.get("editorial_report") if isinstance(metadata, dict) else {}
       skill_ids = editorial_report.get("selected_skill_ids", []) if isinstance(editorial_report, dict) else []
       ```
     - Trong các hàm xử lý scenes, audio, timestamps, metadata: Sử dụng `s.get(...) if isinstance(s, dict) else fallback`.
  3. **Ghi nhận Full Traceback khi bắt Exception**:
     - Trong vòng lặp worker của `autonomous_factory.py`: Khi có ngoại lệ, ghi lại `traceback.format_exc()` vào safe_log để lập tức phát hiện chính xác dòng và file phát sinh lỗi, không bị giấu thông tin.


## 20. Khắc Phục Lỗi Timeout 300s Khi Google Flow Đã Có Video & Chuẩn Hóa 100% 2D Hoạt Hình (Cấm 3D)

- **Hiện tượng lỗi**:
  1. Người dùng thấy trên giao diện web Google Flow video clip đã render xong, nhưng console báo lỗi: `Google Flow không thể tạo nội dung: Hết thời gian chờ video từ Google Flow (300s)... Hệ thống dừng theo yêu cầu không fallback sang ảnh.`
  2. Video AI đôi khi bị render ra dạng 3D / CGI / photorealistic không đúng yêu cầu ("làm video kiểu 2d hoạt hình chứ đừng làm 3d").
- **Nguyên nhân gốc rễ**:
  1. *Đặc thù DOM của Google Flow*:
     - Khi video tạo xong, Flow hiển thị dưới dạng card thumbnail (`img[alt*='Hình thu nhỏ của video']`, `[aria-label*='Mở video']`, `div:has-text('play_circle')`). Trong DOM lúc này **CÓ 0 THẺ `<video>`**!
     - Thẻ `<video>` chỉ được khởi tạo khi người dùng click để mở player xem chi tiết. Code cũ chỉ gọi `.hover()`, không click, và chỉ tìm `page.locator("video")` nên bị timeout 300s dù video đã render xong từ trước.
     - Cơ chế trích xuất blob cũ phụ thuộc vào JavaScript blob reader trong context trang có thể bị CORS chặn nếu video host trên CDN ngoài.
  2. *Thời gian render của Google Flow vào giờ cao điểm*:
     - Hàng đợi của Google Flow có thể mất từ 5 đến 8 phút vào lúc cao điểm, 300s (5 phút) là quá ngắn.
  3. *Prompt sinh video chưa chặn triệt để 3D*:
     - Các prompt chứa từ "cinematic, dramatic lighting" khiến Google Veo thiên về render 3D chân thực nếu không có chỉ thị loại trừ nghiêm ngặt.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Tương tác chủ động (Active Trigger Engagement) với Video Card của Flow**:
     - Tự động click vào các trigger mở video: `button[aria-label*='Mở video' i]`, `img[alt*='Hình thu nhỏ của video' i]`, `div:has-text('play_circle')`.
     - Lắng nghe sự kiện `page.expect_download` khi click vào nút "Tải xuống" trên giao diện Flow.
     - Lấy thuộc tính `currentSrc || src` trên thẻ `<video>` ngay khi player xuất hiện và tải bằng `page.request.get(src)` siêu tốc.
  2. **Nâng `video_timeout_seconds` lên 600s (10 phút)**:
     - Đảm bảo đủ thời gian cho hàng đợi của Google Flow ngay cả khi hệ thống chịu tải cao.
  3. **Chuẩn hóa 100% Phong cách 2D Hoạt hình (Cel-shaded Flat Cartoon, Cấm 3D)**:
     - Trong `STICKMAN_CANONICAL_GUIDANCE`: `Style: Strictly vibrant 2D animation, flat 2D cartoon, hand-drawn vector art illustration, cel-shaded. STRICTLY NO 3D rendering, NO CGI, NO realistic 3D models, NO claymation.`
     - Trong `src/config.py`: `DEFAULT_IMAGE_STYLE = "2d animation, flat 2d cartoon, colorful cel-shaded vector art"`.
     - Trong `src/llm_service.py`: Toàn bộ các chế độ sinh kịch bản (`knowledge`, `chinese_teaching_vi`, `english_vocab_story`, `story_explainer`) đều ép buộc 2D hoạt hình và cấm từ khóa 3D/CGI.
     - Trong `src/studio_editorial_service.py`: Tự động thay thế các từ khóa 3D/CGI thành 2D animation phẳng.


## 21. Phát Hiện Card Thất Bại ("Không thành công / Rất tiếc, không tạo được video này") & Tự Động Thử Lại (Auto-Retry)

- **Hiện tượng lỗi**:
  - Dây chuyền báo lỗi: `Lỗi sinh video Flow cảnh 2: Google Flow không thể tạo nội dung: Hết thời gian chờ video từ Google Flow (600s)...`
  - Trên màn hình của Google Flow xuất hiện một thẻ màu đen kèm biểu tượng cảnh báo tam giác: **"Không thành công - Rất tiếc, không tạo được video này."** cùng nút thùng rác xóa.
- **Nguyên nhân gốc rễ**:
  1. *Lỗi sinh ngẫu nhiên từ server Veo (Generation Failure)*: Trong quá trình xử lý, một số prompt có thể bị server Google Veo từ chối hoặc lỗi nội bộ (hết tài nguyên GPU, kiểm duyệt nhầm hoặc pipeline timeout từ phía Google).
  2. *Thiếu bộ phát hiện Card thất bại (Failed Card Detection)*: Bộ quét chỉ kiểm tra các dấu hiệu thành công (thẻ `<video>`, response video, trigger play). Khi Flow trả về card lỗi "Không thành công", code không nhận diện được nên tiếp tục kiên trì chờ đến hết 600s timeout rồi mới báo lỗi.
  3. *Thiếu cơ chế Retry tự động cho Video Flow*: Ở chế độ ảnh tĩnh có retry 3 lần, nhưng ở chế độ `flow_video` chỉ gọi 1 lần duy nhất nên khi Google Flow vấp lỗi ngẫu nhiên 1 lần là cả dây chuyền bị dừng.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Phát hiện sớm trạng thái thất bại**:
     - Trong vòng lặp polling của [`src/flow_browser_service.py`](file:///c:/Users/Admin/Desktop/youtube/src/flow_browser_service.py), thêm kiểm tra các selector báo lỗi: `div:has-text('Không thành công')`, `div:has-text('Rất tiếc, không tạo được video')`, `div:has-text('Generation failed')`.
     - Khi phát hiện card lỗi: tự động click nút xóa (thùng rác) và trả về kết quả thất bại ngay lập tức (Fail-Fast) để không lãng phí 600s chờ đợi vô ích.
  2. **Thêm vòng lặp Auto-Retry cho Video Flow**:
     - Trong [`src/batch_producer.py`](file:///c:/Users/Admin/Desktop/youtube/src/batch_producer.py): bọc lệnh sinh video với `max_vid_attempts = 2`. Nếu lần 1 bị lỗi server ngẫu nhiên, tự động thử lại lần 2 với Google Flow trước khi quyết định dừng.
  3. **Tự động lưu vết cảnh đã thành công**:
     - Phân cảnh 1 (`scene_001.mp4`) đã được lưu và bảo toàn nguyên vẹn trên đĩa, khi chạy lại sẽ tái sử dụng ngay lập tức mà không cần tạo lại.


## 22. Khắc Phục Lỗi edge-tts NoAudioReceived Khi Bật Turbo Mode (Song Song Nhiều Luồng)

- **Hiện tượng lỗi**:
  - Dây chuyền sản xuất ở chế độ Turbo Batch báo lỗi:
    `Lỗi giọng đọc song song: Lỗi giọng đọc cảnh 1: Lỗi sinh giọng đọc edge-tts CLI... edge_tts.exceptions.NoAudioReceived: No audio was received. Please verify that your parameters are correct.`
- **Nguyên nhân gốc rễ**:
  1. *Rate Limiting / Socket Throttling từ máy chủ Microsoft Edge TTS*:
     - Khi chạy Turbo Batch, `ThreadPoolExecutor` dispatch đồng thời 4 task TTS. Khi 4 tiến trình cùng mở WebSocket tới máy chủ Microsoft cùng 1 giây với cùng IP, Microsoft tạm thời ngắt kết nối WebSocket (chống spam/DDoS), khiến edge-tts không nhận được audio chunk nào và ném ngoại lệ `NoAudioReceived`.
  2. *Độ trễ Staggered Dispatch quá nhỏ (0.35s)*:
     - Giãn cách 0.35 giây giữa các task chưa đủ để WebSocket handshake trước đó hoàn tất.
  3. *Gọi CLI qua subprocess thay vì Python API trực tiếp*:
     - Việc tạo subprocess CLI lặp lại làm tăng overhead, khó quản lý connection pool và dễ bị lỗi pipe/buffer trên Windows.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Chuyển sang sử dụng trực tiếp Python API `edge_tts.Communicate`**:
     - Thay vì gọi subprocess CLI `sys.executable -m edge_tts`, sử dụng trực tiếp `edge_tts.Communicate(text=..., voice=..., rate=...)` với async event loop riêng biệt.
  2. **Cơ chế Tự Phục Hồi Đa Tầng (Multi-tier Self-Healing Fallback)**:
     - Thử lại tối đa 3 lần với giọng chính (`vi-VN-HoaiMyNeural`) kèm exponential backoff (1s, 2s, 3s).
     - Nếu giọng chính vẫn bị chặn tạm thời, tự động chuyển ngay sang giọng dự phòng (`vi-VN-NamMinhNeural` đối với tiếng Việt; hoặc `en-US-JennyNeural` đối với tiếng Anh) để tiếp tục quy trình trơn tru 100%.
  3. **Tăng Staggered Dispatch Delay lên 1.2s**:
     - Trong `generate_scenes_tts_parallel`, giãn cách khởi động giữa các phân cảnh từ 0.35s lên 1.2s, tránh kích hoạt rate limit của Microsoft.


## 23. Tối Ưu Sinh Ảnh Duy Nhất Mỗi Phân Cảnh (Chống Lãng Phí Sinh 2 Biến Thể Cho Cùng 1 Cảnh)

- **Hiện tượng & Phản ánh của người dùng**:
  - *"Vấn đề tạo 2 ảnh 1 lượt nhưng là của 1 phân cảnh thì tạo làm gì, tạo 2 ảnh của 2 phân cảnh liên tiếp để tiết kiệm thời gian chứ tạo 2 ảnh của cùng 1 phân cảnh thì không cần thiết."*
- **Nguyên nhân gốc rễ**:
  1. *Hành vi mặc định của Google Flow (Multi-variant Generation)*:
     - Khi nhận prompt mà không có chỉ thị số lượng ảnh cụ thể, model Imagen 3 / Nano Banana Pro thường tự động sinh một mẻ gồm 2 biến thể (variant 1 & 2) cho cùng một prompt để người dùng chọn.
     - Bot chỉ lấy 1 ảnh đầu tiên rồi bỏ qua ảnh thứ 2, dẫn đến việc Google Flow tốn thời gian tính toán gấp đôi cho cùng 1 cảnh thay vì tạo cảnh tiếp theo.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Thêm chỉ thị dứt khoát vào prompt sinh ảnh**:
     - Trong [`src/flow_browser_service.py`](file:///c:/Users/Admin/Desktop/youtube/src/flow_browser_service.py):
       `"Generate exactly ONE single still image for this scene, DO NOT generate multiple variants or batches."`
  2. **Thêm chỉ thị video câm, không sinh audio phụ**:
     - `"Generate exactly ONE 2D ANIMATION VIDEO CLIP, not a still image and strictly NO 3D. Strictly mute video, no audio generation, silent video only."`
  3. **Đảm bảo phân phối 2 phân cảnh liên tiếp nhau**:
     - `FlowBatchQueueEngine` phân bổ rành mạch: Task 1 cho Cảnh 1, Task 2 cho Cảnh 2, đảm bảo 2 ảnh được tạo là của 2 phân cảnh kịch bản khác nhau, tiết kiệm tối đa thời gian.

## 24. Khắc Phục Lỗi Google Flow Xuất Rất Nhiều Ảnh Nhưng Bot Báo Lỗi/Timeout (Thay Đổi URL Endpoint /asb/)

- **Hiện tượng & Phản ánh của người dùng**:
  - Người dùng hỏi: *"nó xuất cả tỉ hình đây mà lỗi là sao"* kèm ảnh chụp màn hình Google Flow hiển thị hàng loạt ảnh hoạt hình 2D nhân vật trong rừng nguyên sinh đã render thành công rực rỡ, nhưng giao diện xưởng tự động báo lỗi thất bại ở Cảnh 2/4.
- **Nguyên nhân gốc rễ**:
  1. *Google Flow thay đổi URL CDN/Endpoint lưu trữ ảnh*:
     - Trước đây, Google Flow hiển thị và trả về ảnh tĩnh qua đường dẫn `https://flow-content.google/image/<ID>`.
     - Google Flow gần đây đã cập nhật kiến trúc lưu trữ ảnh tĩnh sang định dạng URL mới: `https://flow.google.com/asb/<IMAGE_HASH>=s512-rw`.
  2. *Bộ lắng nghe Network và Selector DOM cũ bị bỏ sót URL mới*:
     - Trong [`src/flow_browser_service.py`](file:///c:/Users/Admin/Desktop/youtube/src/flow_browser_service.py), bộ bắt phản hồi mạng `_on_image_response` chỉ lọc duy nhất `if "flow-content.google/image/" in r_url:`, bỏ qua toàn bộ các response ảnh từ endpoint `/asb/`.
     - Selector DOM chỉ quét `img[src*='flow-content']`, `aside [role='grid'] img` nên hoàn toàn không nhận diện được các thẻ `img[src*='/asb/']` mới trên canvas chính của Google Flow.
     - Hậu quả: Dù Google Flow render xong rất nhiều ảnh chất lượng cao, bot Playwright vẫn không bắt được URL khớp, dẫn đến việc đếm hết thời gian timeout 120s rồi báo lỗi thất bại.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Mở rộng bộ bắt Network cho URL ảnh và Content-Type**:
     - Trong `_on_image_response`: Bắt thêm mọi request URL chứa `/asb/` HOẶC có response header `content-type` bắt đầu bằng `image/` (`image/webp`, `image/png`, `image/jpeg`).
  2. **Nâng cấp Selector DOM ưu tiên thẻ ảnh `/asb/`**:
     - Thêm selector hàng đầu: `img[src*='/asb/']` và `main img[src*='flow.google.com/asb/']` trong `_extract_rendered_image_url`.
  3. **Tải ảnh siêu tốc kế thừa xác thực qua `page.request.get(src)`**:
     - Thay vì dùng `FileReader` JavaScript chậm chạp và dễ bị CORS/Canvas taint, sử dụng `page.request.get(src)` để tải ảnh trong 0.2 giây với đầy đủ session cookie của trình duyệt.
  4. **Cơ chế khử trùng lặp (SHA-256 Hash Deduplication)**:
     - Tính hash SHA-256 của ảnh vừa tải, nếu ảnh trùng với cảnh trước đó thì bỏ qua và quét tiếp ảnh mới nhất, đảm bảo mỗi phân cảnh nhận đúng ảnh riêng biệt của cảnh đó.


## 25. Khắc Phục Lỗi NumPy Broadcasting Mismatch Shape (1920, 1080) Vào (1920, 1080, 3) Khi Render Video

- **Hiện tượng lỗi**:
  - Khi render video bằng MoviePy, tiến trình ném exception:
    `could not broadcast input array from shape (1920,1080) into shape (1920,1080,3)`.
- **Nguyên nhân gốc rễ**:
  1. *Ảnh từ bên ngoài hoặc CDN có chế độ Mode L (Grayscale 1 channel)*:
     - Một số ảnh sinh ra từ Google Flow hoặc icon/placeholder có chế độ Grayscale (`Mode: L`, shape 2 chiều `(H, W)`).
     - Khi MoviePy nạp ảnh qua `ImageClip(image_path)` và resize, frame trả về mảng 2 chiều `(1920, 1080)`.
     - Khi ghép các clip vào dòng thời gian với các clip màu 3 channels `(1920, 1080, 3)`, NumPy không thể broadcast mảng 2D vào canvas 3D và gây crash render.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Chuẩn hóa ảnh ngay khi tải về máy (`flow_browser_service.py`)**:
     - Thêm hàm `_ensure_rgb_image(file_path)`: Mở ảnh bằng PIL và tự động `img.convert("RGB")` nếu mode khác `"RGB"` trước khi lưu.
  2. **Chuẩn hóa tại tầng MoviePy Clip Creation (`visual_beats.py` & `video_compiler.py`)**:
     - Trước khi tạo `ImageClip`, luôn mở file bằng PIL, kiểm tra `if pil_img.mode != "RGB": pil_img = pil_img.convert("RGB")` rồi chuyển thành `np.array(pil_img)` đảm bảo 100% frame có 3 channels (R, G, B).
  3. **Kiểm thử tự động**:
     - Viết unit test `tests/test_image_rgb_normalization.py` xác minh tự động chuẩn hóa cho cả ảnh Grayscale (Mode L) và RGBA (4 channels).




## 26. Tái Cấu Trúc Hệ Thống Theo Sơ Đồ Kiến Trúc Research & Story Architect (mermaid-diagram.svg)

- **Ngữ cảnh & Yêu cầu của người dùng**:
  - Người dùng cung cấp tệp sơ đồ `@mermaid-diagram.svg` và yêu cầu: *"chỉnh sửa luồng lại theo @mermaid-diagram.svg tôi mới thêm"*.
  - Sơ đồ xác định:
    + Cụm hạt nhân (`BRAIN`): **Skill Nghiên cứu & Kiến trúc Nội dung (Research & Story Architect)**.
    + 5 khâu hạ nguồn (`DOWNSTREAM`):
      1. `AUDIO`: Khâu Âm thanh (TTS Engine) — nhận `Âm tiết, Pause Cues, Voice Profile`.
      2. `IMAGE`: Khâu Hình ảnh (Flow CDP) — nhận `Background Plate, Sticker, Visual Action`.
      3. `RENDER`: Khâu Dựng & Chuyển động (Compiler) — nhận `Visual Beats, Camera Effects, Safe Subtitles`.
      4. `SOUND`: Khâu Thiết kế Âm thanh (Foley/SFX) — nhận `Semantic Anchors, Foley Cues, BGM Ducking`.
      5. `LEGAL`: Khâu Thẩm định & Pháp lý (Contract QA) — nhận `Sources, Claims, Coverage Verbatim Quotes`.
- **Nguyên nhân cần tái cấu trúc**:
  1. Trước đây, dữ liệu phân cảnh giữa LLM, Studio Editorial và Batch Producer chỉ là các dict phẳng (`narration`, `video_prompt`) dẫn tới việc các khâu âm thanh, hiệu ứng foley, nhịp dựng và kiểm duyệt bản quyền/pháp lý bị ghép nối rời rạc hoặc thiếu hợp đồng dữ liệu chuẩn.
  2. Cần chuẩn hóa hợp đồng dữ liệu hướng đối tượng phòng thủ (Data Contracts) để mọi phân cảnh kịch bản dù được sinh ra từ LLM hay nạp từ nguồn ngoài đều tự động suy diễn đầy đủ 5 hợp đồng mà vẫn bảo toàn 100% tính tương thích ngược với các trường cũ.
- **Quy tắc triển khai & Bài học kinh nghiệm**:
  1. **Định nghĩa Module Hợp Đồng Dữ Liệu (`src/story_contract_models.py`)**:
     - Cung cấp các dataclass chuẩn: `AudioContract`, `ImageContract`, `RenderContract`, `SoundContract`, `LegalContract`, `ArchitectedScene`.
     - Cung cấp hàm chuẩn hóa phòng thủ `normalize_architected_scene(raw_item, index)`: tự động đếm âm tiết, trích xuất điểm ngắt nghỉ từ dấu câu, suy diễn hiệu ứng âm thanh ngữ nghĩa (semantic foley), bảo đảm vùng an toàn phụ đề `bottom_1_6_safe_zone` và gán nguồn kiểm chứng giáo dục.
     - Hàm `build_downstream_contracts_report(scenes)` tổng hợp toàn bộ 5 hợp đồng thành báo cáo JSON chuẩn để lưu trữ vào metadata video.
  2. **Tích hợp sâu vào Hạt Nhân Biên Tập & Sản Xuất**:
     - `src/studio_editorial_service.py`: Chuẩn hóa 5 hợp đồng cho từng cảnh và nhúng `downstream_contracts` vào báo cáo thẩm định ban biên tập.
     - `src/batch_producer.py`: Đóng gói `downstream_contracts` cùng kịch bản vào file `metadata.json` của từng video thành phẩm.
  3. **Trực quan hóa trên Web UI (`src/app_batch.py`)**:
     - Thêm tab "Kiến trúc 5 Khâu" kết xuất sơ đồ Mermaid trực tiếp trên Streamlit.
     - Thêm khối mở rộng "Chi tiết Hợp Đồng 5 Khâu Hạ Nguồn" trên từng thẻ video thành phẩm trong Kho thành phẩm.
  4. **Kiểm thử tự động đa tầng**:
     - Viết `tests/test_story_contract_pipeline.py` và `tests/test_story_contract_integration.py` đạt 6/6 tests passed 100%.
     - Chạy regression test suite đạt 17/17 tests passed 100%.


## 27. Khắc Phục Lỗi Video Bị Ghép Màn Hình Xám Mờ (Chặn Ảnh Skeleton Placeholder & Thu Hoạch Gallery Google Flow)

- **Hiện tượng lỗi & Phản ánh của người dùng**:
  - Người dùng gửi 2 ảnh chụp:
    + Ảnh 1: Khung hình video bị **mờ câm, xám xịt** (chỉ thấy bóng mờ và phụ đề "phát hiện ra cách họ").
    + Ảnh 2: Màn hình dự án Google Flow của người dùng có **hơn 9 hình ảnh hoạt hình 2D rực rỡ sắc nét** (người tiền sử, hang đá, stickman...).
    + Người dùng thắc mắc: *"sao có hình quá chời mà nó ghép kì vậy"*.
- **Nguyên nhân gốc rễ**:
  1. *Lấy nhầm ảnh placeholder / skeleton của Google Flow*:
     - Khi Google Flow bắt đầu render hoặc tải trang, nó sinh một ảnh preview/shimmer xám mờ kích thước `(1000, 1000)` với `color_variance = 0.00` (kênh R == G == B, không hề có màu).
     - Bot Playwright chỉ kiểm tra `len(img_bytes) > 2000` và `bounding_box > 80x80`. Ảnh placeholder này nặng 121,293 bytes nên bot tưởng là ảnh thật, tải về gán cho Cảnh 1 (`scene_flow_1.png`).
     - Đến Cảnh 4, cơ chế self-healing thấy Cảnh 1 "completed" nên lại copy tiếp ảnh mờ này sang Cảnh 4.
  2. *Độ phân giải thumbnail bị giới hạn*:
     - Google Flow trả về URL có tham số `=s512-rw` (kích thước nhỏ `286x512`).
  3. *Không quét các ảnh đã có sẵn trên Gallery*:
     - Trên màn hình của user đã có sẵn rất nhiều ảnh đẹp do Flow vừa render, nhưng bot không biết nhặt các ảnh này mà lại đợi hoặc lấy nhầm skeleton.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Hàm thẩm định chất lượng ảnh nghiêm ngặt (`is_valid_production_image`)**:
     - Kiểm tra độ phong phú màu sắc `color_variance >= 8.0` (`diff_rg + diff_gb`). Loại bỏ 100% ảnh đơn sắc xám `R == G == B` (`color_variance = 0.00`).
     - Kiểm tra độ lệch chuẩn pixel `arr.std() >= 15.0` (loại bỏ ảnh một màu trơn).
     - Áp dụng bộ lọc này ở cả 3 tầng: network listener, DOM image extractor và self-healing fallback.
  2. **Tự động nâng cấp URL Google Flow sang High-Res (`upgrade_to_high_res_flow_url`)**:
     - Tự động thay thế `=s512` bằng `=s2048` để tải ảnh sắc nét gấp 4 lần.
  3. **Thu hoạch thông minh từ Gallery (`Smart Gallery Harvesting`)**:
     - Khi trên canvas của Google Flow đã xuất hiện các ảnh 2D hoạt hình sắc nét, bot tự động quét và thu hoạch các ảnh hợp lệ chưa từng dùng này để ghép vào các phân cảnh, đảm bảo video được tạo từ chính những hình ảnh tuyệt đẹp trên màn hình của user.


## 28. Khắc Phục Lỗi "No audio was received" Trong Dây Chuyền TTS Song Song & Cơ Chế Tự Phục Hồi Ngữ Cảnh

- **Hiện tượng lỗi**:
  - Dây chuyền báo lỗi: `Lỗi giọng đọc song song: Lỗi giọng đọc cảnh 2: Lỗi sinh giọng đọc edge-tts: No audio was received. Please verify that your parameters are correct.`
  - Trong cùng một job, Cảnh 1, 3, 4, 5 đều sinh audio bình thường, riêng Cảnh 2 bị thất bại.
- **Nguyên nhân gốc rễ**:
  1. *Ngắt stream âm thanh từ Microsoft Bing Edge TTS do câu ngắn / thiếu ngữ cảnh ngữ âm*:
     - Khi một phân cảnh chỉ chứa một cụm từ ngắn (ví dụ "Tổ tiên loài người" hoặc cụm ít hơn 4 từ), bộ tổng hợp ngữ âm của Microsoft Edge TTS không đủ thời lượng để đóng gói audio chunk tối thiểu và kết thúc stream sớm, gây ra ngoại lệ `NoAudioReceived`.
     - Chỉ cần có thêm liên từ dẫn nhập tự nhiên (như "Và rồi, Tổ tiên loài người" hoặc "Thế là, ..."), Microsoft Edge TTS sẽ lập tức tổng hợp thành công 100%.
  2. *Nghẽn socket WebSocket khi bắn song song nhiều luồng (Rate Limiting)*:
     - Khi chạy Turbo mode với 4 workers song song, các worker cùng mở WebSocket tới endpoint `speech.platform.bing.com`. Nếu 1 kết nối bị server tạm thời từ chối, code cũ thử lại với khoảng dừng quá ngắn (1s, 2s) khi các luồng khác vẫn đang chạy, dẫn đến việc tiếp tục bị từ chối và làm dừng toàn bộ job.
- **Quy tắc phòng ngừa & Cách khắc phục**:
  1. **Tự động đệm tiền tố ngữ cảnh (Smart Prefix Padding Recovery)**:
     - Trong `generate_tts`: Nếu gặp `NoAudioReceived` hoặc văn bản quá ngắn (< 35 ký tự), tự động thử lại với các tiền tố dẫn chuyện tự nhiên ("Và rồi, ...", "Thế là, ...", "Lúc này, ...") kết hợp hoán đổi giọng đọc (HoaiMy <-> NamMinh).
  2. **Vòng lặp phục hồi tuần tự (Sequential Recovery Pass)**:
     - Trong `generate_scenes_tts_parallel`: Nếu có phân cảnh bị lỗi khi chạy song song, KHÔNG vội hủy job. Hệ thống tự động gom các cảnh chưa xong và chạy lại tuần tự (mỗi cảnh cách nhau 2.0s) để giải tỏa hoàn toàn WebSocket rate-limit.
  3. **Tái sử dụng file âm thanh có sẵn**:
     - Các cảnh đã tạo xong trước đó (Cảnh 1, 3, 4, 5) được giữ nguyên, chỉ xử lý lại đúng phân cảnh bị nghẽn (Cảnh 2), tiết kiệm tối đa thời gian.


## 29. Chuyển Đổi Số Phân Cảnh Tự Động Theo Cốt Truyện Thay Vì Nhập Thủ Công Cố Định

- **Yêu cầu của người dùng**:
  - *"không cho chọn sô scanhr nữa số cảnh phụ thuộc vào cốt truyện"*
  - Loại bỏ hoàn toàn ô chọn số phân cảnh trên giao diện UI.
  - Số lượng phân cảnh phải do cốt truyện tự nhiên và AI quyết định, tránh tình trạng bị ép buộc cứng nhắc (như luôn luôn cắt ép thành đúng 5 cảnh hay 3 cảnh) làm gãy mạch truyện hoặc nông cạn nội dung.
- **Nguyên nhân cốt lõi của hạn chế trước đây**:
  - Giao diện có `target_scenes = c4.number_input(...)` cố định 5 cảnh (hoặc 3 cảnh).
  - Prompt gửi tới Ollama LLM bị ép cứng: `Kịch bản phải có ĐÚNG {actual_scenes} phân cảnh`.
  - Bộ lọc `_sanitize_scenes` và studio biên tập `run_studio_editorial_pipeline` kiểm tra nghiêm ngặt `len(scenes) == target_scenes` và cắt gọt `scenes[:target_scenes]`, khiến các kịch bản có diễn biến dài hơn hoặc ngắn hơn tự nhiên đều bị ép khuôn hoặc từ chối.
- **Quy tắc & Giải pháp triển khai**:
  1. **Loại bỏ input số cảnh trên Web UI (`src/app_batch.py`)**:
     - Bỏ trường `number_input` số phân cảnh. Hiển thị caption rõ ràng: *"🎭 Số phân cảnh linh hoạt: Tự động phân bổ theo cốt truyện và diễn biến tự nhiên, không bị gò bó cố định số cảnh."*
     - Khi submit job vào hàng đợi, truyền `target_scenes = None`.
  2. **Prompt định hướng số cảnh tự do theo cốt truyện trong LLM (`src/llm_service.py`)**:
     - Khi `target_scenes is None`, chỉ thị cho Ollama: *"SỐ PHÂN CẢNH TỰ DO THEO CỐT TRUYỆN: Hãy tự động quyết định số lượng phân cảnh tối ưu nhất (thường từ 3 đến 8 phân cảnh) sao cho mạch truyện phát triển tự nhiên, đầy đủ mở đầu, cao trào và kết thúc trọn vẹn nhất; tuyệt đối không bị gò bó hay cắt ngắn gượng ép; mỗi cảnh khoảng 5-10 giây."*
     - Vẫn giữ nguyên khả năng nhận `target_scenes` cụ thể để bảo toàn tính tương thích ngược cho unit test và API cũ.
  3. **Nới lỏng ràng buộc cắt gọt trong Studio Biên tập (`src/studio_editorial_service.py`)**:
     - Khi `target_scenes is None`: `_sanitize_scenes` duyệt qua toàn bộ các cảnh trong câu chuyện mà không cắt lát.
     - Vòng biên tập chấp nhận mọi kịch bản có `len(scenes) >= 1` thay vì bắt buộc bằng một số cứng.
  4. **Đồng bộ hàng đợi bền vững (`src/autonomous_factory.py`, `src/batch_producer.py`)**:
     - Cho phép `target_scenes: Optional[int] = None` xuyên suốt luồng sản xuất.
     - Kiểm chứng 100% bằng 6 unit tests mới (`tests/test_dynamic_story_scenes.py`) và toàn bộ regression test suite (16/16 tests passed).
