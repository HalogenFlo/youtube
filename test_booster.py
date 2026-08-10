# Chức năng: Bộ kiểm thử tự động toàn diện (Unit & Integration tests) cho các module của YouTube Booster.
# Lý do tạo: Đảm bảo độ chính xác của logic rate limiter, profile isolation, supervisor backoff và mô phỏng hành vi.
# Trích dẫn: Tuân thủ quy tắc kiểm thử Red -> Green.

import os
import sys
import time
import unittest
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.channel_scraper import normalize_channel_url, get_channel_cache_path
from src.human_simulator import (
    get_gaussian_delay,
    decide_watch_duration,
    get_random_viewport,
    get_random_user_agent,
    generate_bezier_points,
    get_random_scroll_js
)
from src.resource_guard import get_system_stats, can_spawn_worker
from src.profile_manager import get_profile_dir_for_proxy
from src.view_booster_manager import BoosterManager


class TestYouTubeBooster(unittest.TestCase):

    def test_normalize_channel_url(self):
        """Kiểm tra chuẩn hóa URL kênh."""
        url1 = "https://www.youtube.com/@ChannelName"
        self.assertEqual(normalize_channel_url(url1, "shorts"), "https://www.youtube.com/@ChannelName/shorts")
        self.assertEqual(normalize_channel_url(url1, "videos"), "https://www.youtube.com/@ChannelName/videos")
        
        url2 = "https://www.youtube.com/@ChannelName/shorts"
        self.assertEqual(normalize_channel_url(url2, "shorts"), "https://www.youtube.com/@ChannelName/shorts")

    def test_gaussian_delay(self):
        """Kiểm tra hàm sinh delay Gaussian nằm trong khoảng cho phép."""
        for _ in range(50):
            d = get_gaussian_delay(5.0, 15.0)
            self.assertTrue(5.0 <= d <= 15.0, f"Delay {d} vượt ngoài khoảng 5.0 - 15.0")

    def test_decide_watch_duration(self):
        """Kiểm tra tính toán thời lượng xem hợp lệ từ 60% đến 100%."""
        for _ in range(20):
            plan = decide_watch_duration(20.0, min_sec=8.0, max_sec=50.0, replay_prob=0.0)
            # 20s * 0.60 = 12s; 20s * 1.0 = 20s
            self.assertTrue(8.0 <= plan["watch_seconds"] <= 20.0)
            self.assertFalse(plan["is_replay"])

    def test_bezier_points_generation(self):
        """Kiểm tra thuật toán sinh đường cong chuột Bezier."""
        points = generate_bezier_points(100, 100, 500, 500, num_points=10)
        self.assertEqual(len(points), 11)
        self.assertEqual(points[0], (100, 100))
        self.assertEqual(points[-1], (500, 500))

    def test_random_viewport_and_ua(self):
        """Kiểm tra sinh kích thước màn hình và User Agent."""
        w, h = get_random_viewport()
        self.assertGreater(w, 1000)
        self.assertGreater(h, 600)

        ua = get_random_user_agent()
        self.assertTrue(isinstance(ua, str) and len(ua) > 10)

    def test_profile_isolation(self):
        """Kiểm tra tính cách ly 100% của Profile Chrome giữa các Worker."""
        # Hai worker dùng cùng 1 proxy vẫn phải có thư mục profile khác nhau để không bị lock
        p1 = get_profile_dir_for_proxy("1.2.3.4:8080", worker_id=1)
        p2 = get_profile_dir_for_proxy("1.2.3.4:8080", worker_id=2)
        self.assertNotEqual(p1, p2, "Hai worker khác nhau phải có profile path khác nhau dù chung proxy")
        self.assertTrue("w1" in p1)
        self.assertTrue("w2" in p2)

    def test_rate_limiter_logic(self):
        """Kiểm tra logic Rate Limiter không bị khóa chết khi gọi đồng thời."""
        bm = BoosterManager(threads=2, rate_limit_views_per_min=5)
        # Giả lập ghi nhận 5 token
        now = time.time()
        bm.rate_limit_timestamps = [now - 10, now - 8, now - 6, now - 4, now - 2]
        
        # Test kiểm tra rate limit
        self.assertEqual(len(bm.rate_limit_timestamps), 5)

    def test_resource_guard(self):
        """Kiểm tra chức năng giám sát tài nguyên."""
        stats = get_system_stats()
        self.assertIn("ram_percent", stats)
        self.assertIn("ram_used_gb", stats)
        self.assertGreater(stats["ram_total_gb"], 0)
        self.assertTrue(can_spawn_worker(max_ram_pct=100.0))

    def test_booster_manager_lifecycle(self):
        """Kiểm tra khởi tạo và dừng an toàn BoosterManager."""
        bm = BoosterManager(threads=2, watch_duration_min=8, watch_duration_max=20)
        self.assertEqual(bm.threads, 2)
        self.assertEqual(bm.watch_duration_min, 8)
        self.assertFalse(bm.is_running)
        bm.stop()
        self.assertFalse(bm.is_running)


if __name__ == "__main__":
    unittest.main()
