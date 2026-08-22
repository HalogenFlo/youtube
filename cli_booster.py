# Chức năng: Script chạy nền (CLI / Background Service) 24/7 cho Tool Cày View YouTube & Shorts.
# Lý do tạo: Cho phép treo máy lâu dài trên PC hoặc VPS mà không cần mở giao diện Web, tự động lưu log và phục hồi.
# Trích dẫn: Đọc cấu hình từ booster_config.json hoặc CLI arguments và khởi chạy BoosterManager.

import os
import sys
import json
import time
import signal
import argparse

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đảm bảo mã hóa UTF-8 trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.channel_scraper import extract_channel_videos
from src.view_booster_manager import BoosterManager
from src.resource_guard import get_system_stats

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "booster_config.json")


def load_config() -> dict:
    """Đọc file cấu hình booster_config.json nếu tồn tại."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CLI] Lỗi khi đọc {CONFIG_PATH}: {e}")
    return {}


def main():
    parser = argparse.ArgumentParser(description="YouTube View & Shorts Booster CLI 24/7")
    parser.add_argument("--channel", type=str, help="URL kênh YouTube (ví dụ: https://www.youtube.com/@ChannelName)")
    parser.add_argument("--threads", type=int, default=None, help="Số luồng chạy đồng thời (mặc định theo config)")
    parser.add_argument("--headless", action="store_true", help="Chạy ẩn danh không mở cửa sổ trình duyệt")
    parser.add_argument("--headed", action="store_true", help="Hiện cửa sổ trình duyệt (ưu tiên chống bot)")
    parser.add_argument("--loop", action="store_true", help="Lặp lại danh sách vô tận (24/7)")
    parser.add_argument("--refresh", action="store_true", help="Bắt buộc quét mới từ YouTube thay vì dùng cache")
    args = parser.parse_args()

    config = load_config()

    # Tham số ưu tiên: CLI args > booster_config.json > Mặc định
    channels = [args.channel] if args.channel else config.get("channels", [])
    threads = args.threads if args.threads is not None else config.get("threads", 2)
    # Luôn tự động quét mới khi khởi động để lấy video mới nhất vừa đăng của kênh
    force_refresh = not args.no_refresh if hasattr(args, 'no_refresh') else True
    
    headless = config.get("headless", True)
    if args.headless:
        headless = True
    elif args.headed:
        headless = False

    loop = args.loop if args.loop else config.get("loop", True)
    proxies = config.get("proxies", [])

    print("=" * 60)
    print("🚀 YOUTUBE VIEW & SHORTS BOOSTER - CHẾ ĐỘ CHẠY NỀN 24/7")
    print("=" * 60)
    print(f"📌 Số kênh cấu hình: {len(channels)}")
    print(f"📌 Số luồng chạy song song: {threads}")
    print(f"📌 Chế độ Headless: {headless}")
    print(f"📌 Chế độ lặp vô tận (Loop): {loop}")
    print(f"📌 Bắt buộc quét mới (Force Refresh): {force_refresh}")
    print(f"📌 Số lượng Proxy: {len(proxies)}")
    stats = get_system_stats()
    print(f"📌 RAM máy: {stats['ram_used_gb']}/{stats['ram_total_gb']} GB ({stats['ram_percent']}%)")
    print("=" * 60)

    if not channels:
        print("❌ Lỗi: Không có link kênh nào được cấu hình. Hãy truyền --channel hoặc chỉnh sửa booster_config.json")
        sys.exit(1)

    # 1. Quét danh sách Shorts từ kênh đầu tiên (hoặc tổng hợp các kênh)
    all_videos = []
    for ch_url in channels:
        print(f"🔍 Đang chuẩn bị danh sách Shorts từ: {ch_url} ...")
        success, videos, err = extract_channel_videos(ch_url, mode="shorts", max_results=5000, force_refresh=force_refresh)
        if success and videos:
            print(f"✅ Đã tải thành công {len(videos)} Shorts.")
            all_videos.extend(videos)
        else:
            print(f"⚠️ Không thể lấy danh sách từ {ch_url}: {err}")

    if not all_videos:
        print("❌ Lỗi: Không lấy được bất kỳ video nào để chạy.")
        sys.exit(1)

    print(f"🎬 Tổng cộng {len(all_videos)} video trong hàng đợi. Bắt đầu khởi động các luồng...")

    # 2. Khởi tạo và chạy BoosterManager
    manager = BoosterManager(
        channels=channels,
        videos=all_videos,
        proxies=proxies,
        threads=threads,
        watch_duration_min=config.get("watch_duration_min_sec", 12),
        watch_duration_max=config.get("watch_duration_max_sec", 50),
        replay_prob=config.get("replay_probability", 0.15),
        rate_limit_views_per_min=config.get("rate_limit_views_per_minute", 15),
        max_ram_pct=config.get("max_ram_percent", 80.0),
        max_cpu_pct=config.get("max_cpu_percent", 90.0),
        headless=headless,
        loop=loop
    )

    def handle_signal(sig, frame):
        print("\n🛑 Nhận tín hiệu dừng (Ctrl+C). Đang tắt an toàn các worker...")
        manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    manager.start()

    # Vòng lặp giám sát chính
    try:
        while manager.is_running:
            time.sleep(30)
            sys_stats = get_system_stats()
            print(
                f"[Monitor] Views: {manager.stats['total_views']} | "
                f"Lỗi: {manager.stats['failed_views']} | "
                f"RAM: {sys_stats['ram_percent']}% | "
                f"Workers: {len(manager.workers)}"
            )
    except KeyboardInterrupt:
        handle_signal(None, None)


if __name__ == "__main__":
    main()
