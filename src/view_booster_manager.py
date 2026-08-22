# Chức năng: Bộ điều phối đa luồng nâng cao (Manager & Supervisor) cho hệ thống cày view YouTube.
# Lý do tạo: Quản lý hàng đợi video, rate limiter không khóa lock, supervisor tự phục hồi worker với exponential backoff, dọn dẹp an toàn.
# Trích dẫn: Sử dụng RotatingFileHandler, luồng Supervisor độc lập và hàng đợi an toàn.

import os
import time
import json
import random
import logging
import threading
import asyncio
from logging.handlers import RotatingFileHandler
from typing import List, Dict, Any, Optional, Callable

from src.config import OUTPUT_DIR
from src.resource_guard import can_spawn_worker, get_memory_usage_pct, kill_orphan_chrome_processes
from src.view_booster_service import YouTubeViewWorker


LOG_FILE = os.path.join(OUTPUT_DIR, "booster.log")
STATS_FILE = os.path.join(OUTPUT_DIR, "booster_stats.json")

logger = logging.getLogger("YouTubeBooster")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class BoosterManager:
    """
    Quản lý toàn bộ tiến trình cày view đa luồng, supervisor tự phục hồi và rate limiter theo từng view.
    """
    def __init__(
        self,
        channels: List[str] = None,
        videos: List[Dict[str, Any]] = None,
        proxies: List[str] = None,
        threads: int = 2,
        watch_duration_min: float = 8.0,
        watch_duration_max: float = 20.0,
        replay_prob: float = 0.30,
        rate_limit_views_per_min: int = 20,
        max_ram_pct: float = 80.0,
        max_cpu_pct: float = 90.0,
        headless: bool = False,
        loop: bool = True,
        max_videos_per_browser: int = 15,
        on_log: Optional[Callable[[str], None]] = None,
        on_stats_updated: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.channels = channels or []
        self.videos = videos or []
        self.proxies = [p.strip() for p in (proxies or []) if p.strip()]
        self.threads = max(1, min(threads, 15))
        self.watch_duration_min = watch_duration_min
        self.watch_duration_max = watch_duration_max
        self.replay_prob = replay_prob
        self.rate_limit_views_per_min = rate_limit_views_per_min
        self.max_ram_pct = max_ram_pct
        self.max_cpu_pct = max_cpu_pct
        self.headless = headless
        self.loop = loop
        self.max_videos_per_browser = max_videos_per_browser
        self.on_log = on_log
        self.on_stats_updated = on_stats_updated

        self.is_running = False
        self.is_paused = False
        self.workers: Dict[int, YouTubeViewWorker] = {}
        self.worker_threads: Dict[int, threading.Thread] = {}
        self.worker_backoffs: Dict[int, float] = {}

        self.supervisor_thread: Optional[threading.Thread] = None

        self.stats = {
            "start_time": None,
            "total_views": 0,
            "failed_views": 0,
            "views_by_video": {},
            "active_workers": 0,
            "ram_percent": 0.0
        }
        self.rate_limit_timestamps: List[float] = []
        self._lock = threading.Lock()

    def refresh_videos_from_channels(self) -> None:
        """Tự động quét lại các kênh để cập nhật nếu có video/Shorts mới được đăng."""
        if not self.channels:
            return
        from src.channel_scraper import extract_channel_videos
        new_list = []
        for ch in self.channels:
            ok, vids, _ = extract_channel_videos(ch, mode="shorts", max_results=5000, force_refresh=True)
            if ok and vids:
                new_list.extend(vids)
        if new_list:
            with self._lock:
                added = len(new_list) - len(self.videos)
                self.videos = new_list
                if added > 0:
                    self.log(f"🔔 Phát hiện {added} video mới được đăng trên kênh! Đã cập nhật vào hàng đợi (Tổng: {len(self.videos)} video).")
                else:
                    self.log(f"✅ Đã quét lại kênh (Tổng cộng {len(self.videos)} video).")

    def log(self, message: str) -> None:
        logger.info(message)
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass

    def save_stats(self) -> None:
        """Lưu thống kê ra file JSON."""
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _check_rate_limit(self) -> None:
        """
        Đảm bảo không vượt quá số lượt xem tối đa mỗi phút trên toàn hệ thống.
        Giải phóng lock TRƯỚC KHI sleep để không gây nghẽn các worker khác.
        """
        sleep_needed = 0.0
        with self._lock:
            now = time.time()
            self.rate_limit_timestamps = [t for t in self.rate_limit_timestamps if now - t < 60]
            if len(self.rate_limit_timestamps) >= self.rate_limit_views_per_min:
                sleep_needed = max(0.0, 60.0 - (now - self.rate_limit_timestamps[0]))
            else:
                self.rate_limit_timestamps.append(now)

        if sleep_needed > 0:
            self.log(f"[Rate Limiter] Đạt giới hạn {self.rate_limit_views_per_min} views/phút. Tạm nghỉ {round(sleep_needed, 1)}s...")
            time.sleep(sleep_needed)
            with self._lock:
                self.rate_limit_timestamps.append(time.time())

    def _on_video_started(self, worker_id: int, video: Dict[str, Any], plan: Dict[str, Any]) -> None:
        """Callback khi 1 worker bắt đầu xem 1 video cụ thể."""
        with self._lock:
            if "current_watching" not in self.stats:
                self.stats["current_watching"] = {}
            self.stats["current_watching"][worker_id] = {
                "title": video.get("title") or "Video Short",
                "url": video.get("url") or f"https://www.youtube.com/shorts/{video.get('id')}",
                "watch_time": plan.get("total_watch_time", plan.get("watch_seconds", 15.0)),
                "is_replay": plan.get("is_replay", False),
                "is_skipped": plan.get("is_skipped", False),
                "started_at": time.strftime("%H:%M:%S")
            }
            self.save_stats()

        if self.on_stats_updated:
            try:
                self.on_stats_updated(self.stats)
            except Exception:
                pass

    def _on_video_viewed(self, video: Dict[str, Any]) -> None:
        """Callback khi 1 video được xác minh xem thành công."""
        with self._lock:
            self.stats["total_views"] += 1
            vid_id = video.get("id") or video.get("video_id") or video.get("url") or "unknown"
            self.stats["views_by_video"][vid_id] = self.stats["views_by_video"].get(vid_id, 0) + 1
            self.stats["ram_percent"] = get_memory_usage_pct()
            self.save_stats()

        if self.on_stats_updated:
            try:
                self.on_stats_updated(self.stats)
            except Exception:
                pass

    def _run_worker_loop(self, worker_id: int, proxy: Optional[str]) -> None:
        """Chạy vòng đời của 1 worker thread độc lập với xử lý lỗi và dọn dẹp an toàn."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        worker = YouTubeViewWorker(
            worker_id=worker_id,
            proxy=proxy,
            headless=self.headless,
            log_callback=self.log
        )
        with self._lock:
            self.workers[worker_id] = worker

        try:
            while self.is_running:
                if self.is_paused:
                    time.sleep(2)
                    continue

                if not can_spawn_worker(max_ram_pct=self.max_ram_pct, max_cpu_pct=self.max_cpu_pct):
                    self.log(f"[Worker #{worker_id}] Hệ thống quá tải (RAM vượt {self.max_ram_pct}% hoặc CPU vượt {self.max_cpu_pct}%). Tạm nghỉ 10s...")
                    time.sleep(10)
                    continue

                if not self.videos:
                    self.log(f"[Worker #{worker_id}] Không có danh sách video. Nghỉ 5s...")
                    time.sleep(5)
                    continue

                # Tạo danh sách video cho worker và shuffle tự nhiên
                with self._lock:
                    worker_videos = list(self.videos)
                
                # Đảo vòng offset theo worker_id để tránh xem trùng cùng lúc
                offset = (worker_id * 7) % max(1, len(worker_videos))
                worker_videos = worker_videos[offset:] + worker_videos[:offset]

                # Chạy feed lướt toàn bộ shorts của kênh
                loop.run_until_complete(
                    worker.run_shorts_feed_loop(
                        shorts_list=worker_videos,
                        min_sec=self.watch_duration_min,
                        max_sec=self.watch_duration_max,
                        replay_prob=self.replay_prob,
                        max_videos_per_browser=self.max_videos_per_browser,
                        on_video_started=self._on_video_started,
                        on_video_completed=self._on_video_viewed,
                        rate_limiter_callback=self._check_rate_limit
                    )
                )

                if not self.loop or not self.is_running:
                    self.log(f"[Worker #{worker_id}] Đã hoàn thành danh sách video.")
                    break

                self.log(f"[Worker #{worker_id}] Hoàn thành 1 vòng danh sách. Nghỉ 10s trước khi lặp lại...")
                
                # Luồng chính tự động quét lại kênh để bắt video mới
                if worker_id == 1 and self.channels:
                    try:
                        self.refresh_videos_from_channels()
                    except Exception:
                        pass

                time.sleep(10)

            # Thành công: Reset backoff
            with self._lock:
                self.worker_backoffs[worker_id] = 5.0

        except Exception as e:
            self.log(f"[Worker #{worker_id}] Gặp lỗi ngoại lệ: {str(e)}")
            with self._lock:
                self.stats["failed_views"] += 1
                # Tăng exponential backoff nếu bị crash
                current_b = self.worker_backoffs.get(worker_id, 5.0)
                self.worker_backoffs[worker_id] = min(current_b * 2.0, 300.0)
        finally:
            try:
                loop.run_until_complete(worker.close())
            except Exception:
                pass
            loop.close()
            with self._lock:
                if worker_id in self.workers:
                    del self.workers[worker_id]

    def _supervisor_loop(self) -> None:
        """
        Luồng giám sát Supervisor chạy định kỳ kiểm tra sức khỏe của các worker.
        Tự động phục hồi worker bị chết với Exponential Backoff.
        """
        self.log("[Supervisor] Đã khởi động luồng giám sát sức khỏe worker.")
        while self.is_running:
            time.sleep(15)
            if not self.is_running:
                break

            with self._lock:
                active_count = len(self.workers)
                self.stats["active_workers"] = active_count
                self.stats["ram_percent"] = get_memory_usage_pct()

            # Tự động dọn dẹp khi vượt quá max_ram_pct
            ram_pct = self.stats["ram_percent"]
            if ram_pct >= self.max_ram_pct:
                self.log(f"[Supervisor] ⚠️ RAM hệ thống ({ram_pct}%) vượt quá ngưỡng cấu hình ({self.max_ram_pct}%). Đang tự động dọn dẹp Chrome zombie...")
                active_pids = []
                with self._lock:
                    for worker in self.workers.values():
                        if worker.browser and hasattr(worker.browser, "_process_pid") and worker.browser._process_pid:
                            active_pids.append(worker.browser._process_pid)
                
                killed = kill_orphan_chrome_processes(exclude_pids=active_pids)
                if killed > 0:
                    self.log(f"[Supervisor] 🧹 Đã giải phóng RAM bằng cách tắt {killed} tiến trình Chrome zombie.")
                else:
                    self.log(f"[Supervisor] Không phát hiện tiến trình Chrome zombie nào.")

            for wid in range(1, self.threads + 1):
                if not self.is_running:
                    break

                t = self.worker_threads.get(wid)
                if t is None or not t.is_alive():
                    if self.is_running and self.loop:
                        backoff = self.worker_backoffs.get(wid, 5.0)
                        self.log(f"[Supervisor] Phát hiện Worker #{wid} đã dừng. Đang tự phục hồi sau {backoff}s...")
                        time.sleep(backoff)
                        
                        if self.is_running:
                            proxy = self.proxies[(wid - 1) % len(self.proxies)] if self.proxies else None
                            new_t = threading.Thread(
                                target=self._run_worker_loop,
                                args=(wid, proxy),
                                daemon=True
                            )
                            self.worker_threads[wid] = new_t
                            new_t.start()

            # Kiểm tra nếu loop=False và tất cả thread đã kết thúc
            if not self.loop:
                all_done = all(not t.is_alive() for t in self.worker_threads.values() if t)
                if all_done and len(self.workers) == 0:
                    self.is_running = False
                    self.log("Toàn bộ các luồng đã hoàn thành lượt cày view.")
                    break

    def start(self) -> None:
        """Khởi động toàn bộ worker threads và supervisor."""
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self.stats["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log(f"Khởi chạy hệ thống Booster với {self.threads} luồng (Headless: {self.headless})...")

        killed = kill_orphan_chrome_processes()
        if killed > 0:
            self.log(f"Đã dọn dẹp {killed} tiến trình Chrome cũ.")

        for i in range(self.threads):
            wid = i + 1
            self.worker_backoffs[wid] = 5.0
            proxy = self.proxies[i % len(self.proxies)] if self.proxies else None
            t = threading.Thread(
                target=self._run_worker_loop,
                args=(wid, proxy),
                daemon=True
            )
            self.worker_threads[wid] = t
            t.start()
            time.sleep(2)

        # Khởi động supervisor thread
        self.supervisor_thread = threading.Thread(target=self._supervisor_loop, daemon=True)
        self.supervisor_thread.start()

    def stop(self) -> None:
        """Dừng toàn bộ hệ thống an toàn (Graceful Shutdown)."""
        self.is_running = False
        self.log("Đang gửi tín hiệu dừng an toàn tới toàn bộ các luồng...")
        
        for w in list(self.workers.values()):
            try:
                w.is_running = False
            except Exception:
                pass

        # Chờ tối đa 5 giây cho các thread kết thúc an toàn
        for wid, t in list(self.worker_threads.items()):
            if t and t.is_alive():
                t.join(timeout=1.5)

        self.save_stats()
        kill_orphan_chrome_processes()
        self.workers.clear()
        self.worker_threads.clear()
        self.log("✅ Đã dừng toàn bộ hệ thống và lưu thống kê thành công.")
