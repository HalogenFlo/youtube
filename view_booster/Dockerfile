# Base image Python 3.11 Debian Bookworm
FROM python:3.11-slim-bookworm

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    CHROME_BIN=/usr/bin/google-chrome \
    MODE=ui

WORKDIR /app

# Cài đặt các công cụ hệ thống, font tiếng Việt và Google Chrome Stable
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    curl \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    ffmpeg \
    procps \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements gọn nhẹ và cài đặt python dependencies
COPY requirements_booster.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Tạo thư mục cần thiết
RUN mkdir -p temp/profiles temp/channel_cache output

# Expose port cho Streamlit Web UI
EXPOSE 8501

# Entrypoint script xử lý chế độ chạy (UI hoặc CLI)
CMD if [ "$MODE" = "cli" ]; then \
        python cli_booster.py; \
    else \
        streamlit run src/app_view_booster.py --server.port=8501 --server.address=0.0.0.0; \
    fi
