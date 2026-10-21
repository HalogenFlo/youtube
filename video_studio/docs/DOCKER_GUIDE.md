# 🐳 Hướng Dẫn Đóng Gói & Chạy YouTube Booster Bằng Docker Trên Mọi Máy

Docker giúp bạn mang tool sang **bất kỳ máy tính nào (Windows, macOS, Linux, VPS)** và chạy ngay lập tức mà **không cần cài đặt Python, Chrome hay bất kỳ thư viện nào**.

---

### 🚀 1. Chạy Nhanh Từ Docker Hub (Trên Bất Kỳ Máy Tính / VPS Nào)

Bạn không cần build hay cài đặt Python/Chrome, chỉ cần máy có cài Docker:

### 🌐 Chế độ Web UI (Xem giao diện & theo dõi trực tiếp):
```bash
docker run -d -p 8501:8501 --name yt-booster halogenbrom/yt-booster:latest
```
👉 Mở trình duyệt truy cập: `http://localhost:8501` (hoặc `http://<ip-vps>:8501`).

---

### ⚡ Chế độ CLI Chạy Ngầm 24/7 (Treo máy nhẹ nhất):
```bash
docker run -d --name yt-booster-cli --restart unless-stopped halogenbrom/yt-booster:cli
```
.
   - **Chạy Ngầm 24/7 (Treo VPS)**:
     - *Trên Windows*: Click đúp `docker_run_headless.bat` (hoặc gõ `docker compose up -d booster-cli`).
     - *Trên Linux/VPS*: Gõ `./run_docker.sh cli`.

---

## 📦 Cách 2: Đóng Gói Thành File `.tar` Mang Sang Máy Không Có Mạng

Nếu bạn muốn đóng gói thành 1 file duy nhất để gửi qua USB hoặc Google Drive sang máy khác:

### Bước 1: Build và Xuất Image thành file `.tar` (Trên máy hiện tại)
Mở terminal tại thư mục dự án và chạy:
```bash
docker compose build
docker save -o yt-booster.tar yt-booster-ui:latest
```
*(File `yt-booster.tar` được tạo ra chứa đầy đủ hệ điều hành, Python, Chrome và mã nguồn).*

### Bước 2: Nạp và Chạy trên Máy Mới
Chuyển file `yt-booster.tar` và file `docker-compose.yml` sang máy mới, rồi gõ:
```bash
# Nạp image vào Docker
docker load -i yt-booster.tar

# Khởi chạy ngay
docker compose up booster-ui
```

---

## ☁️ Cách 3: Đẩy Lên Docker Hub (Tải về bằng 1 lệnh từ bất kỳ đâu)

Nếu bạn có tài khoản trên [hub.docker.com](https://hub.docker.com):

```bash
# 1. Đăng nhập Docker Hub
docker login

# 2. Gắn tag cho image (thay yourusername bằng tên tài khoản của bạn)
docker tag youtube-booster-ui:latest yourusername/yt-booster:latest

# 3. Đẩy lên cloud
docker push yourusername/yt-booster:latest

# 4. Trên bất kỳ máy tính/VPS nào trên thế giới, chỉ cần kéo về chạy:
docker run -d -p 8501:8501 yourusername/yt-booster:latest
```

---

## 🛠️ Các Lệnh Quản Lý Container Tiện Lợi

| Tác vụ | Lệnh thực hiện |
|:---|:---|
| Xem log chạy nền realtime | `docker compose logs -f booster-cli` |
| Dừng toàn bộ hệ thống | `docker compose down` |
| Khởi động lại container | `docker compose restart` |
