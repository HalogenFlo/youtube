<!--
Chức năng: Hướng dẫn cài đặt, thiết lập mô hình AI và khởi chạy hệ thống Pipeline sản xuất video ngắn.
Lý do tạo: Cung cấp tài liệu hướng dẫn nhanh cho nhà phát triển và người dùng cuối.
Trích dẫn: Tổng hợp hướng dẫn cấu hình và chạy từ PLAN.md.
-->

# 🎬 Pipeline Sản Xuất Video Ngắn Tự Động (YouTube Shorts, TikTok, Reels)

Hệ thống tự động sản xuất video ngắn local chạy trực tiếp trên card đồ họa **RTX 3060 12GB VRAM** sử dụng 100% các công cụ AI mã nguồn mở miễn phí. Giao diện Web **Streamlit** cho phép người dùng tương tác, kiểm soát và chỉnh sửa từng bước sản xuất (Kịch bản -> Tài nguyên ảnh/video -> Render thành phẩm).

---

## 🛠️ Yêu cầu hệ thống bắt buộc

1. **Hệ điều hành**: Windows (đã được test tốt nhất).
2. **Python**: Phiên bản 3.10 trở lên.
3. **FFmpeg**: Công cụ xử lý video/audio (Cần được cài đặt và thêm vào biến môi trường `PATH` của hệ thống).
4. **Ollama**: Công cụ chạy LLM local (Tải tại [ollama.com](https://ollama.com)).
5. **CUDA Toolkit**: Cần phiên bản 12.x để tăng tốc phần cứng bằng GPU.

---

## 🚀 Hướng dẫn cài đặt & Thiết lập mô hình

### Bước 1: Cài đặt thư viện Python
Mở terminal tại thư mục dự án và cài đặt các thư viện phụ thuộc:
```bash
pip install -r requirements.txt
```

### Bước 2: Chuẩn bị mô hình Ollama LLM
Đảm bảo Ollama đang chạy ở nền (hoặc chạy lệnh `ollama serve`), sau đó tải model Qwen 2.5 bằng lệnh:
```bash
ollama pull qwen2.5:7b-instruct
```

### Bước 3: Tải thử nghiệm mô hình sinh ảnh/video (Tùy chọn)
Hệ thống sẽ **tự động tải** các model này khi chạy lần đầu tiên. Nhưng bạn có thể tải trước bằng các lệnh sau để tránh thời gian chờ lâu khi chạy ứng dụng:

*   **Stable Diffusion 1.5** (Sinh ảnh):
    ```bash
    python -c "from diffusers import StableDiffusionPipeline; StableDiffusionPipeline.from_pretrained('Lykon/dreamshaper-8')"
    ```
*   **Wan 2.1 1.3B** (Sinh video):
    ```bash
    python -c "from diffusers import WanPipeline; WanPipeline.from_pretrained('Wan-AI/Wan2.1-T2V-1.3B')"
    ```

---

## 🧪 Chạy Kiểm Thử Tự Động (Integration Test)

Trước khi khởi chạy giao diện web, bạn nên kiểm tra xem các module AI cốt lõi và FFmpeg trên máy có hoạt động đồng bộ hay không bằng script kiểm thử tích hợp:

```bash
python test_pipeline.py
```

**Script này sẽ tự động:**
1. Kiểm tra tài nguyên GPU NVIDIA CUDA.
2. Gọi Ollama sinh 3 phân cảnh kịch bản nháp.
3. Sử dụng `edge-tts` sinh giọng đọc tiếng Việt.
4. Sử dụng `Stable Diffusion 1.5` để sinh hình ảnh.
5. Sử dụng `Faster-Whisper` để tách timestamps chi tiết.
6. Sử dụng `MoviePy + FFmpeg` để ghép nối, zoom hình ảnh (Ken Burns) và burn phụ đề ASS karaoke lên video đầu ra.
7. Đầu ra sẽ được ghi nhận tại thư mục `output/video_final_part1.mp4`.

---

## 🖥️ Khởi chạy ứng dụng Web UI

Bạn có thể chạy nhanh ứng dụng giao diện web bằng cách:

1. Click đúp chuột vào file **`run.bat`** ở thư mục gốc.
2. Hoặc chạy lệnh thủ công từ terminal:
   ```bash
   streamlit run src/app.py
   ```

Giao diện sẽ tự động mở ra trên trình duyệt web mặc định của bạn (thường là `http://localhost:8501`).

---

## 📂 Cấu trúc dự án
*   `src/config.py`: File cấu hình chung (Đường dẫn, các model AI, độ phân giải...).
*   `src/llm_service.py`: Xử lý gọi Ollama LLM để sinh kịch bản (JSON).
*   `src/tts_service.py`: Xử lý sinh âm thanh giọng đọc tiếng Việt bằng edge-tts.
*   `src/image_service.py`: Xử lý sinh ảnh AI bằng Stable Diffusion 1.5.
*   `src/video_gen_service.py`: Xử lý sinh video AI bằng Wan 2.1.
*   `src/whisper_service.py`: Xử lý chuyển âm thanh thành chữ và lấy timestamp từ Faster-Whisper.
*   `src/video_downloader.py`: Xử lý tải video từ link và tách audio bằng yt-dlp + FFmpeg.
*   `src/subtitle_builder.py`: Xây dựng tệp phụ đề karaoke ASS (.ass).
*   `src/video_compiler.py`: Ghép nối tài nguyên video, áp dụng hiệu ứng chuyển động, thuật toán chia nhỏ video tự động và burn phụ đề bằng FFmpeg.
*   `src/app.py`: Giao diện chính Streamlit.
*   `test_pipeline.py`: Kịch bản kiểm thử tích hợp tự động không qua UI.
