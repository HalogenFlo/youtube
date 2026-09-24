# 🎬 Xưởng Video Kiến Thức AI — Google Flow

Giao diện chính hiện là một dây chuyền sản xuất video tự động: nhập một chủ đề hoặc danh sách chủ đề, chọn số lượng video rồi để hệ thống tự viết kịch bản, tạo từng cảnh bằng Google Flow, sinh giọng đọc, dựng video và đóng gói metadata sẵn đăng.

## Chạy xưởng tự động

1. Chạy `run.bat`. Chrome sẽ mở với cổng điều khiển Google Flow và giao diện mở tại `http://localhost:8502`.
2. Đăng nhập Google Flow nếu được yêu cầu và giữ cửa sổ Chrome đó hoạt động.
3. Trong **Kho ý tưởng**, nhập chủ đề, số video, giọng đọc và khung hình.
4. Bấm **Khởi động dây chuyền**. Có thể để máy chạy; hàng đợi được lưu tại `temp/video_factory_state.json`.
5. Lấy video, tiêu đề, mô tả và hashtag trong tab **Kho thành phẩm**. Mỗi MP4 có một file JSON metadata cùng tên trong thư mục `output/`.

Nếu ứng dụng đóng giữa chừng, công việc đang chạy sẽ trở lại hàng chờ khi mở lại. Khi Chrome/Google Flow mất kết nối, xưởng tự tạm dừng để tránh làm hỏng toàn bộ hàng đợi.

---

# 🚀 YouTube View & Shorts Booster Pro & AI Video Pipeline

Hệ thống chuyên nghiệp tự động hóa cày view **YouTube Shorts & Video** thông minh chống phát hiện bot (Anti-detect nodriver), tích hợp luồng giám sát **Supervisor tự phục hồi 24/7**, giao diện **Streamlit Web UI** trực quan hiển thị trực tiếp video đang xem và đóng gói sẵn **Docker Container** triển khai chỉ với 1 lệnh.

---

## 🌟 Tính Năng Nổi Bật

* 🛡️ **Anti-Detect Tiên Tiến**: Sử dụng giao thức Chrome DevTools Protocol (CDP) trực tiếp qua `nodriver`, loại bỏ 100% binary WebDriver giúp qua mặt thuật toán quét bot của YouTube.
* 🎬 **Theo Dõi Trực Tiếp Thời Gian Thực**: Web UI hiển thị thẻ thông tin từng luồng: video đang xem, link Shorts, thời gian xem dự kiến, trạng thái Replay và bảng xếp hạng view từng video.
* 🤖 **Giả Lập Hành Vi Người Thật (Human Simulator)**: Đường cong chuột Cubic Bezier, cuộn trang ngẫu nhiên 100-400px, tỷ lệ xem tự nhiên 60%-100%, tạm dừng/phát ngẫu nhiên (pause/resume).
* 🔄 **Supervisor Tự Phục Hồi 24/7**: Luồng giám sát chạy ngầm tự động phát hiện và khởi động lại luồng bị gián đoạn mạng với cơ chế lùi thời gian lặp lại (Exponential Backoff $5\text{s} \rightarrow 300\text{s}$).
* 🔒 **Cách Ly Profile 100% (Profile Isolation)**: Mỗi luồng sở hữu một thư mục User Data riêng biệt, triệt tiêu nguy cơ Profile Collision/Lock khi nhiều luồng dùng chung Proxy.
* ⚡ **Bộ Điều Tốc Rate Limiter**: Kiểm soát số lượt xem mỗi phút trên toàn hệ thống không gây nghẽn luồng.
* 🐳 **Triển Khai 1-Click Với Docker**: Đóng gói sẵn trên Docker Hub `halogenbrom/yt-booster` tích hợp Google Chrome Stable và font tiếng Việt.

---

## 🐳 HƯỚNG DẪN 1: Cài Đặt & Chạy Trên Máy Khác Bằng Docker (Khuyên Dùng)

Bạn không cần cài đặt Python hay Chrome trên máy mới, chỉ cần máy có cài **Docker Desktop** (Windows/Mac) hoặc **Docker Engine** (Linux/VPS).

### 🌐 Cách 1.1: Chạy Bản Web UI (Xem giao diện trực quan)
Mở Terminal / PowerShell / CMD trên máy mới và gõ:
```bash
docker run -d -p 8501:8501 --name yt-booster halogenbrom/yt-booster:latest
```
👉 Mở trình duyệt truy cập: **`http://localhost:8501`** (hoặc `http://<IP-VPS>:8501`).

---

### ⚡ Cách 1.2: Chạy Bản CLI Treo Ngầm 24/7 (Tiết kiệm RAM nhất cho VPS)
```bash
docker run -d --name yt-booster-cli --restart unless-stopped halogenbrom/yt-booster:cli
```

---

### 💾 Cách 1.3: Nạp Offline Từ File `yt-booster-image.tar` (Không Cần Mạng)
Nếu máy mới không có kết nối internet tải Docker Hub:
1. Sao chép file **`yt-booster-image.tar`** sang máy mới.
2. Mở Terminal tại thư mục chứa file và gõ:
   ```bash
   docker load -i yt-booster-image.tar
   docker run -d -p 8501:8501 --name yt-booster youtube-booster-ui:latest
   ```

---

## 💻 HƯỚNG DẪN 2: Cài Đặt & Chạy Trực Tiếp Bằng Python (Local Machine)

### 1️⃣ Yêu cầu môi trường
* **Hệ điều hành**: Windows 10/11, Ubuntu 20.04+, macOS.
* **Python**: Phiên bản 3.10 hoặc 3.11.
* **Google Chrome**: Đã cài đặt phiên bản mới nhất trên máy.

### 2️⃣ Cài đặt thư viện
Clone mã nguồn về máy mới:
```bash
git clone https://github.com/Phatjhhoq8/youtube.git
cd youtube
```

Tạo môi trường ảo và cài đặt thư viện chuyên dụng cho Booster:
```bash
# Tạo môi trường ảo (khuyên dùng)
python -m venv venv

# Kích hoạt trên Windows:
.\venv\Scripts\activate
# Kích hoạt trên Linux/macOS:
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements_booster.txt
```

### 3️⃣ Khởi chạy ứng dụng

#### 🚀 Cách nhanh nhất (Menu tương tác 1-Click):
Chỉ cần chạy file **`run.bat`** tại thư mục gốc, hệ thống sẽ hiển thị menu lựa chọn:
```text
============================================================
  🚀 YOUTUBE AUTOMATION & AI VIDEO PRODUCTION SUITE
============================================================
  [1] Khởi chạy AI Video Producer (Streamlit Web UI)
  [2] Khởi chạy YouTube View Booster (Streamlit Web UI - Port 8501)
  [3] Khởi chạy YouTube View Booster (CLI Chạy ngầm 24/7)
  [4] Mở Chrome CDP cho Google Flow (np368057@gmail.com - Port 9222)
  [5] Chạy kiểm tra chẩn đoán toàn diện hệ thống (Tests)
  [6] Thoát
```

#### 📁 Cấu Trúc Thư Mục Chuẩn Hóa
```text
youtube/
├── .agent/              # Quy tắc & hướng dẫn làm việc
├── assets/              # Tài nguyên tĩnh (mascot, fonts, âm thanh)
├── docker/              # Toàn bộ cấu hình, script và ảnh .tar của Docker
│   ├── images/          # Các file image .tar nạp offline
│   └── scripts/         # Script build và run Docker
├── docs/                # Toàn bộ tài liệu kỹ thuật & hướng dẫn
│   ├── PLAN.md          # Kế hoạch phát triển
│   ├── DOCKER_GUIDE.md  # Hướng dẫn chi tiết Docker
│   └── GOOGLE_FLOW_GUIDE.md # Báo cáo phân tích Google Flow
├── scripts/             # Script chạy phụ trợ (.bat cho Windows)
│   ├── launch_flow_chrome.bat
│   ├── run_view_booster_ui.bat
│   └── run_view_booster_headless.bat
├── src/                 # Toàn bộ mã nguồn cốt lõi
├── tasks/               # Quản lý tiến độ (todo.md)
├── temp/                # Dữ liệu tạm sinh ra khi chạy
├── tests/               # Toàn bộ các bài kiểm thử tự động
├── booster_config.json  # Cấu hình YouTube Booster
├── cli_booster.py       # Điểm chạy nền Booster CLI
├── flow_config.json     # Cấu hình Google Flow
├── requirements.txt     # Thư viện phụ thuộc
├── run.bat              # Menu khởi chạy trung tâm 1-click
└── README.md
```

---

## ⚙️ Cấu Hình Nâng Cao (`booster_config.json`)

Bạn có thể chỉnh sửa file `booster_config.json` để thay đổi thiết lập mặc định:
```json
{
  "channel_url": "https://www.youtube.com/@Remioo-br",
  "threads": 2,
  "watch_duration_min_sec": 8.0,
  "watch_duration_max_sec": 20.0,
  "replay_probability": 0.30,
  "rate_limit_views_per_min": 20,
  "max_system_ram_percent": 80.0,
  "headless": true,
  "loop": true,
  "proxies": [
    "http://user:pass@ip:port",
    "http://ip2:port2"
  ]
}
```

---

## 🧪 Kiểm Thử Tự Động (Unit & Integration Tests)

Để kiểm tra toàn bộ tính năng (Rate limiter, Profile isolation, Bezier curves, Resource guard, Lifecycle) trước khi chạy:
```bash
python test_booster.py
```
Kết quả mong đợi: `Ran 9 tests ... OK (100% Passed)`.

---

## 📂 Cấu Trúc Thư Mục Dự Án

```text
├── src/
│   ├── app_view_booster.py      # Giao diện Web UI Streamlit tương tác trực tiếp
│   ├── view_booster_service.py  # Engine điều khiển trình duyệt nodriver CDP & Anti-detect
│   ├── view_booster_manager.py  # Bộ điều phối đa luồng, Supervisor, Rate Limiter
│   ├── human_simulator.py       # Thuật toán mô phỏng chuột Bezier, scroll, delay Gaussian
│   ├── profile_manager.py       # Quản lý và cách ly Chrome Profile độc lập
│   ├── resource_guard.py        # Giám sát RAM, CPU và dọn dẹp tiến trình Chrome zombie
│   └── channel_scraper.py       # Trích xuất toàn bộ Shorts/Video từ kênh bằng yt-dlp
├── cli_booster.py               # Runner CLI 24/7 độc lập
├── booster_config.json          # File cấu hình trung tâm
├── test_booster.py              # Bộ kiểm thử tự động toàn diện
├── Dockerfile                   # Dockerfile tối ưu Chrome Stable + Python 3.11
├── docker-compose.yml           # Cấu hình đa dịch vụ Docker (UI & CLI)
├── DOCKER_GUIDE.md              # Hướng dẫn chi tiết triển khai container
└── README.md                    # Tài liệu hướng dẫn sử dụng
```

---

## 📜 Giấy Phép & Tuyên Bố Miễn Trừ Trách Nhiệm
Dự án được xây dựng phục vụ mục đích học tập, nghiên cứu tự động hóa trình duyệt và kiểm thử tải hệ thống. Người dùng tự chịu trách nhiệm về việc tuân thủ Điều khoản dịch vụ của các nền tảng liên quan.
