#!/bin/bash
# Script điều khiển YouTube Booster trên VPS / Server Linux

case "$1" in
  ui)
    echo "🚀 Khởi chạy Web UI tại http://localhost:8501..."
    docker compose up booster-ui
    ;;
  cli)
    echo "🚀 Khởi chạy chạy nền 24/7..."
    docker compose up -d booster-cli
    echo "✅ Đang chạy nền. Xem log bằng: docker compose logs -f booster-cli"
    ;;
  logs)
    docker compose logs -f booster-cli
    ;;
  stop)
    echo "🛑 Dừng toàn bộ container..."
    docker compose down
    ;;
  build)
    echo "🔨 Build lại image..."
    docker compose build
    ;;
  *)
    echo "Cách dùng: ./run_docker.sh [ui | cli | logs | stop | build]"
    ;;
esac
