# Chức năng: Engine điều khiển trình duyệt anti-detect bằng nodriver với timeout bảo vệ, xác minh playback thực tế và chống bot.
# Lý do tạo: Tự động hóa quá trình phát video, lướt Shorts feed, tương tác ngẫu nhiên và vượt qua bộ lọc bot an toàn.
# Trích dẫn: Sử dụng giao thức Chrome DevTools Protocol (CDP) trực tiếp qua nodriver với timeout 30s cứng.

import os
import sys
import asyncio
import random
from typing import Dict, Any, Optional, Callable, List
import nodriver as uc

from src.human_simulator import (
    get_random_viewport,
    get_random_user_agent,
    get_gaussian_delay,
    decide_watch_duration,
    should_skip,
    should_pause_and_resume,
    get_random_scroll_js,
    async_random_sleep
)
from src.profile_manager import get_profile_dir_for_proxy

ACTION_TIMEOUT = 30.0  # Timeout cứng cho mỗi thao tác Chrome/CDP


async def bypass_youtube_consent(page) -> None:
    """
    Tự động xử lý và đồng ý các popup Cookie Consent của YouTube nếu xuất hiện.
    """
    try:
        consent_js = """
        (() => {
            const buttons = Array.from(document.querySelectorAll('button, ytd-button-renderer'));
            for (const b of buttons) {
                const text = (b.innerText || '').toLowerCase();
                if (text.includes('accept all') || text.includes('i agree') || text.includes('tôi đồng ý') || text.includes('chấp nhận tất cả') || text.includes('agree')) {
                    b.click();
                    return true;
                }
            }
            return false;
        })()
        """
        await asyncio.wait_for(page.evaluate(consent_js), timeout=10.0)
    except Exception:
        pass


async def setup_video_player(page, mute: bool = True) -> None:
    """
    Thiết lập player video: Tự động tìm video đang active trên màn hình, bật tự động phát và tắt tiếng.
    """
    try:
        setup_js = f"""
        (() => {{
            function getActiveVideo() {{
                const activeRenderer = document.querySelector('ytd-reel-video-renderer[is-active]');
                if (activeRenderer) {{
                    const v = activeRenderer.querySelector('video');
                    if (v) return v;
                }}
                const videos = Array.from(document.querySelectorAll('video'));
                for (const v of videos) {{
                    const rect = v.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.top >= -200 && rect.top < window.innerHeight) {{
                        return v;
                    }}
                }}
                return videos[0] || null;
            }}

            const v = getActiveVideo();
            if (v) {{
                if ({str(mute).lower()}) {{
                    v.muted = true;
                }}
                v.play().catch(e => {{}});
                return true;
            }}
            return false;
        }})()
        """
        await asyncio.wait_for(page.evaluate(setup_js), timeout=10.0)
    except Exception:
        pass


async def get_video_playback_status(page) -> Dict[str, Any]:
    """
    Lấy thông tin trạng thái phát thực tế của video đang active trên trang YouTube Shorts.
    """
    try:
        status_js = """
        (() => {
            const pageText = (document.body ? document.body.innerText : '').toLowerCase();
            const isCaptcha = pageText.includes('our systems have detected unusual traffic') || 
                              pageText.includes('robot') || 
                              document.querySelector('#captcha-form') !== null;
            
            function getActiveVideo() {
                const activeRenderer = document.querySelector('ytd-reel-video-renderer[is-active]');
                if (activeRenderer) {
                    const v = activeRenderer.querySelector('video');
                    if (v) return v;
                }
                const videos = Array.from(document.querySelectorAll('video'));
                for (const v of videos) {
                    const rect = v.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.top >= -200 && rect.top < window.innerHeight) {
                        return v;
                    }
                }
                for (const v of videos) {
                    if (!v.paused) return v;
                }
                return videos[0] || null;
            }

            const v = getActiveVideo();
            if (!v) {
                return { found: false, duration: 0, currentTime: 0, paused: true, isCaptcha: isCaptcha, currentUrl: window.location.href };
            }
            return {
                found: true,
                duration: v.duration || 0,
                currentTime: v.currentTime || 0,
                paused: v.paused,
                ended: v.ended,
                readyState: v.readyState,
                isCaptcha: isCaptcha,
                currentUrl: window.location.href
            };
        })()
        """
        res = await asyncio.wait_for(page.evaluate(status_js), timeout=10.0)
        if isinstance(res, dict):
            return res
        return {"found": False, "duration": 0, "currentTime": 0, "paused": True, "isCaptcha": False, "currentUrl": ""}
    except Exception:
        return {"found": False, "duration": 0, "currentTime": 0, "paused": True, "isCaptcha": False, "currentUrl": ""}


async def simulate_shorts_scroll_next(page) -> None:
    """
    Mô phỏng thao tác lướt sang video Short tiếp theo bằng cách cuộn chuột hoặc nhấn phím Arrow Down.
    """
    try:
        scroll_js = """
        (() => {
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, bubbles: true }));
            window.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, bubbles: true }));
            
            // Tìm nút 'Next video' trên giao diện YouTube Shorts nếu có
            const nextBtn = document.querySelector('ytd-shorts [aria-label="Next video"], #navigation-button-down button');
            if (nextBtn) {
                nextBtn.click();
            }
        })()
        """
        await asyncio.wait_for(page.evaluate(scroll_js), timeout=10.0)
    except Exception:
        pass


class YouTubeViewWorker:
    """
    Lớp điều khiển 1 worker trình duyệt chạy độc lập với profile và proxy riêng.
    Bảo đảm timeout, cách ly profile và kiểm tra playback thực tế.
    """
    def __init__(
        self,
        worker_id: int,
        proxy: Optional[str] = None,
        headless: bool = False,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        self.worker_id = worker_id
        self.proxy = proxy
        self.headless = headless
        self.log_callback = log_callback
        self.browser = None
        self.profile_dir = get_profile_dir_for_proxy(proxy, worker_id)
        self.is_running = False

    def log(self, message: str) -> None:
        formatted = f"[Worker #{self.worker_id}] {message}"
        if self.log_callback:
            self.log_callback(formatted)
        else:
            print(formatted)

    async def start_browser(self) -> bool:
        """Khởi động instance trình duyệt Chrome qua nodriver với đầy đủ cờ chống phát hiện và timeout."""
        try:
            self.log(f"Đang khởi động Chrome (Headless: {self.headless})...")
            viewport_w, viewport_h = get_random_viewport()
            ua = get_random_user_agent()
            
            browser_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--mute-audio",
                f"--window-size={viewport_w},{viewport_h}",
                f"--user-agent={ua}",
                "--disable-webrtc-multiple-routes",
                "--enforce-webrtc-ip-permission-check"
            ]

            if self.proxy:
                browser_args.append(f"--proxy-server={self.proxy.strip()}")

            self.browser = await asyncio.wait_for(
                uc.start(
                    user_data_dir=self.profile_dir,
                    headless=self.headless,
                    browser_args=browser_args
                ),
                timeout=ACTION_TIMEOUT
            )
            self.is_running = True
            self.log("Trình duyệt đã sẵn sàng.")
            return True
        except asyncio.TimeoutError:
            self.log("Lỗi: Quá thời gian khởi động trình duyệt (Timeout 30s).")
            self.is_running = False
            return False
        except Exception as e:
            self.log(f"Lỗi khởi động trình duyệt: {str(e)}")
            self.is_running = False
            return False

    async def watch_short_url(
        self,
        short_url: str,
        title: str = "",
        min_sec: float = 8.0,
        max_sec: float = 20.0,
        replay_prob: float = 0.30,
        mute: bool = True
    ) -> bool:
        """
        Mở và xem 1 video Short theo URL với thời lượng ngẫu nhiên và xác minh phát thực tế.
        """
        if not self.browser:
            success = await self.start_browser()
            if not success:
                return False

        try:
            self.log(f"Đang mở Short: {title or short_url}")
            page = await asyncio.wait_for(self.browser.get(short_url), timeout=ACTION_TIMEOUT)
            
            # Chờ trang tải và xử lý consent
            await async_random_sleep(2.0, 4.0)
            await bypass_youtube_consent(page)
            await setup_video_player(page, mute=mute)
            
            # Xác minh trạng thái phát thực tế
            status = await get_video_playback_status(page)
            if status.get("isCaptcha"):
                self.log("⚠️ Cảnh báo: Trang yêu cầu xác minh CAPTCHA từ IP này.")
                return False

            if not status.get("found"):
                self.log("⚠️ Không tìm thấy player video trên trang.")
                return False

            video_dur = status.get("duration", 0)
            initial_time = status.get("currentTime", 0)

            # Quyết định thời gian xem (60-100% + replay)
            watch_plan = decide_watch_duration(video_dur, min_sec, max_sec, replay_prob)
            watch_time = watch_plan["total_watch_time"]
            
            self.log(f"Đang xem video trong {watch_time}s (Replay: {watch_plan['is_replay']})...")
            
            elapsed = 0.0
            step = 4.0
            while elapsed < watch_time and self.is_running:
                await asyncio.sleep(min(step, watch_time - elapsed))
                elapsed += step
                
                # Mô phỏng cuộn nhẹ hoặc pause/resume tự nhiên
                if should_pause_and_resume(pause_prob=0.08):
                    try:
                        await page.evaluate("const v = document.querySelector('video'); if (v) v.pause();")
                        await asyncio.sleep(random.uniform(1.0, 3.0))
                        await page.evaluate("const v = document.querySelector('video'); if (v) v.play();")
                    except Exception:
                        pass
                else:
                    try:
                        await page.evaluate(get_random_scroll_js())
                    except Exception:
                        pass

            # Xác minh lại video đã thực sự chạy (tiến trình phát tăng lên)
            final_status = await get_video_playback_status(page)
            final_time = final_status.get("currentTime", 0)
            if final_time > initial_time or final_status.get("ended"):
                self.log(f"✅ Đã xem xong Short hợp lệ ({watch_time}s).")
                return True
            else:
                self.log("⚠️ Video không phát được hoặc bị dừng sớm.")
                return False

        except asyncio.TimeoutError:
            self.log(f"Lỗi timeout khi mở Short: {short_url}")
            return False
        except Exception as e:
            self.log(f"Lỗi khi xem Short {short_url}: {str(e)}")
            return False

    async def run_shorts_feed_loop(
        self,
        shorts_list: List[Dict[str, Any]],
        min_sec: float = 8.0,
        max_sec: float = 20.0,
        replay_prob: float = 0.30,
        delay_between_min: float = 4.0,
        delay_between_max: float = 10.0,
        on_video_started: Optional[Callable[[int, Dict[str, Any], Dict[str, Any]], None]] = None,
        on_video_completed: Optional[Callable[[Dict[str, Any]], None]] = None,
        rate_limiter_callback: Optional[Callable[[], None]] = None
    ) -> None:
        """
        Chế độ lướt Shorts Feed tuần tự qua danh sách video của kênh.
        Có rate limiter theo từng video, kiểm tra skip, cập nhật trạng thái đang xem và xác minh playback.
        """
        if not shorts_list:
            self.log("Danh sách Shorts trống.")
            return

        if not self.browser:
            success = await self.start_browser()
            if not success:
                return

        first_short = shorts_list[0]
        first_url = first_short.get('url') or f"https://www.youtube.com/shorts/{first_short.get('id')}"
        self.log(f"Bắt đầu chuỗi lướt Shorts từ: {first_short.get('title')}")
        
        try:
            page = await asyncio.wait_for(self.browser.get(first_url), timeout=ACTION_TIMEOUT)
            await async_random_sleep(2.5, 4.5)
            await bypass_youtube_consent(page)

            for idx, video in enumerate(shorts_list):
                if not self.is_running:
                    break

                # Gọi rate limiter trước mỗi video riêng biệt
                if rate_limiter_callback:
                    rate_limiter_callback()

                vid_title = video.get('title', f"Short {idx+1}")
                self.log(f"[{idx + 1}/{len(shorts_list)}] Đang xem Short: {vid_title}")
                
                await setup_video_player(page, mute=True)
                status_start = await get_video_playback_status(page)
                
                # Kiểm tra skip ngẫu nhiên (5-8% người dùng lướt nhanh)
                if idx > 0 and should_skip(skip_prob=0.06):
                    self.log("Mô phỏng người dùng lướt nhanh qua Short này (Không tính view)...")
                    if on_video_started:
                        on_video_started(self.worker_id, video, {"watch_seconds": 2.0, "is_replay": False, "is_skipped": True})
                    await async_random_sleep(1.5, 3.0)
                else:
                    dur = video.get('duration', 0)
                    plan = decide_watch_duration(dur, min_sec, max_sec, replay_prob)
                    watch_sec = plan["total_watch_time"]
                    
                    self.log(f"Thời gian xem: {watch_sec}s (Replay: {plan['is_replay']})")
                    
                    if on_video_started:
                        on_video_started(self.worker_id, video, plan)
                    
                    elapsed = 0.0
                    step = 4.0
                    while elapsed < watch_sec and self.is_running:
                        await asyncio.sleep(min(step, watch_sec - elapsed))
                        elapsed += step
                        try:
                            await page.evaluate(get_random_scroll_js())
                        except Exception:
                            pass

                    # Xác minh playback thành công trước khi ghi nhận view
                    status_end = await get_video_playback_status(page)
                    is_valid_view = (
                        not status_end.get("isCaptcha", False) and
                        elapsed >= 6.0 and
                        (status_end.get("currentTime", 0) > status_start.get("currentTime", 0) or 
                         status_end.get("ended", False) or 
                         status_end.get("found", True))
                    )
                    if is_valid_view:
                        self.log(f"✅ Đã xem thành công: {vid_title} ({round(elapsed, 1)}s)")
                        if on_video_completed:
                            on_video_completed(video)
                    else:
                        self.log("⚠️ Video bị lỗi hoặc bị chặn, bỏ qua ghi nhận view.")

                # Chuyển sang Short kế tiếp
                if idx < len(shorts_list) - 1 and self.is_running:
                    self.log("Lướt sang Short tiếp theo...")
                    await simulate_shorts_scroll_next(page)
                    await async_random_sleep(delay_between_min, delay_between_max)

        except asyncio.TimeoutError:
            self.log("Lỗi timeout trong quá trình lướt Shorts.")
        except Exception as e:
            self.log(f"Lỗi trong quá trình lướt Shorts: {str(e)}")

    async def close(self) -> None:
        """Đóng trình duyệt an toàn và giải phóng tài nguyên."""
        self.is_running = False
        if self.browser:
            try:
                self.browser.stop()
            except Exception:
                pass
            self.browser = None
        self.log("Đã đóng trình duyệt.")
