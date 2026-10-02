# Chức năng: Tự động hóa đăng tải và hẹn giờ video lên YouTube Studio (studio.youtube.com) qua Chrome CDP.
# Lý do tạo: Tự động hóa đăng 3 video hoạt hình vào các khung giờ vàng 8h, 11h, 18h và tuân thủ chính sách AI (Altered or synthetic content).
# Trích dẫn: Tuân thủ quy định chính sách YouTube về công bố nội dung AI và giao thức Playwright CDP.

import os
import re
import time
import asyncio
from collections import Counter
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from playwright.async_api import async_playwright, BrowserContext, Page
from src.config import OUTPUT_DIR, BASE_DIR, GMAIL_YTB, PASS_YTB

YOUTUBE_STUDIO_URL = "https://studio.youtube.com"
GOLDEN_HOURS = ["08:00", "11:00", "18:00"]


def safe_print(msg: str):
    try:
        print(msg)
    except Exception:
        try:
            print(str(msg).encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass


def parse_studio_date(date_text: str) -> Optional[date]:
    """Phân tích các định dạng ngày hiển thị trên YouTube Studio."""
    clean = date_text.strip().lower()
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(clean, fmt).date()
        except Exception:
            pass
    # Xử lý tiếng Việt '3 thg 10, 2026' hoặc '3 thg 10'
    m = re.search(r"(\d{1,2})\s+thg\s+(\d{1,2})(?:,\s*(\d{4}))?", clean)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else date.today().year
        try:
            return date(year, month, day)
        except Exception:
            pass
    return None


def extract_scheduled_slots_from_shorts_rows(row_texts: List[str]) -> List[Tuple[date, str]]:
    """Suy ra các slot vàng đã dùng từ những dòng trong tab Shorts.

    YouTube Studio chỉ hiển thị ngày (không hiển thị giờ) trong bảng.
    Luồng này luôn điền lần lượt 08:00, 11:00, 18:00, nên số Short
    đã hẹn trong ngày xác định slot tiếp theo.
    """
    scheduled_counts: Counter[date] = Counter()
    date_pattern = re.compile(
        r"(\d{1,2}\s+thg\s+\d{1,2}(?:,\s*\d{4})?|"
        r"\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})",
        re.IGNORECASE,
    )
    for row_text in row_texts:
        lowered = row_text.lower()
        if "đã lên lịch" not in lowered and "scheduled" not in lowered:
            continue
        match = date_pattern.search(row_text)
        if not match:
            continue
        parsed_date = parse_studio_date(match.group(1))
        if parsed_date:
            scheduled_counts[parsed_date] += 1

    slots: List[Tuple[date, str]] = []
    for scheduled_date, count in sorted(scheduled_counts.items()):
        for hour in GOLDEN_HOURS[:min(count, len(GOLDEN_HOURS))]:
            slots.append((scheduled_date, hour))
    return slots


def calculate_next_available_slots(
    existing_slots: List[Tuple[date, str]],
    count: int = 3,
    start_from_date: Optional[date] = None
) -> List[Tuple[str, str]]:
    """
    Tính toán danh sách `count` slot (ngày, giờ) tiếp theo còn trống trong 3 khung giờ 8h, 11h, 18h.
    Bắt đầu ngay sau slot muộn nhất đã có trên kênh để lấp đầy các khoảng trống liên tục.
    Trả về list dạng: [('04/10/2026', '08:00'), ('04/10/2026', '11:00'), ...]
    """
    if start_from_date is None:
        start_from_date = date.today() + timedelta(days=1)

    booked_set = set(existing_slots)

    if existing_slots:
        sorted_slots = sorted(existing_slots, key=lambda x: (x[0], x[1]))
        latest_date, latest_hour = sorted_slots[-1]
        cur_date = latest_date
    else:
        latest_hour = ""
        cur_date = start_from_date

    result_slots: List[Tuple[str, str]] = []
    for day_offset in range(30):
        check_date = cur_date + timedelta(days=day_offset)
        for h in GOLDEN_HOURS:
            # Nếu là ngày muộn nhất hiện tại, chỉ xét các giờ SAU giờ muộn nhất
            if existing_slots and check_date == cur_date and latest_hour and h <= latest_hour:
                continue
            if (check_date, h) not in booked_set:
                result_slots.append((check_date.strftime("%d/%m/%Y"), h))
                booked_set.add((check_date, h))
                if len(result_slots) >= count:
                    return result_slots

    return result_slots


class YouTubeStudioUploader:
    """Điều khiển YouTube Studio qua CDP để tải lên và hẹn giờ video."""

    def __init__(self, cdp_port: int = 9222):
        self.cdp_port = cdp_port
        self.cdp_url = f"http://127.0.0.1:{cdp_port}"

    def _ensure_chrome_running(self) -> bool:
        """Đảm bảo Chrome đang chạy với cổng 9222."""
        import socket
        import subprocess
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.8)
                if s.connect_ex(("127.0.0.1", self.cdp_port)) == 0:
                    return True
        except Exception:
            pass

        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        chrome_exe = next((p for p in candidates if os.path.exists(p)), "")
        if not chrome_exe:
            return False

        profile_dir = os.path.join(BASE_DIR, "flow_chrome_profile")
        cmd = [
            chrome_exe,
            f"--remote-debugging-port={self.cdp_port}",
            f"--user-data-dir={profile_dir}",
            "--profile-directory=Default",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "https://studio.youtube.com"
        ]
        try:
            creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008) if os.name == "nt" else 0
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            for _ in range(25):
                time.sleep(0.4)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                    s2.settimeout(0.4)
                    if s2.connect_ex(("127.0.0.1", self.cdp_port)) == 0:
                        return True
        except Exception:
            pass
        return False

    async def _handle_google_login_if_needed(self, page: Page):
        """Hỗ trợ tự động điền tài khoản từ .env nếu bị chuyển hướng sang trang đăng nhập Google."""
        if not GMAIL_YTB:
            return
        try:
            cur_url = page.url.lower()
            if "accounts.google.com" in cur_url or "signin" in cur_url:
                safe_print(f"[*] Phát hiện trang đăng nhập Google Studio. Đang hỗ trợ điền tài khoản: {GMAIL_YTB}...")
                email_input = page.locator("input[type='email']").first
                if await email_input.is_visible(timeout=3000):
                    await email_input.fill(GMAIL_YTB)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(3000)

                pass_input = page.locator("input[type='password']").first
                if PASS_YTB and await pass_input.is_visible(timeout=3000):
                    await pass_input.fill(PASS_YTB)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(4000)
        except Exception:
            pass

    async def connect_studio_page(self, playwright_instance) -> Tuple[Optional[BrowserContext], Optional[Page]]:
        """Kết nối Chrome CDP và mở hoặc chuyển tới tab YouTube Studio."""
        self._ensure_chrome_running()
        try:
            browser = await playwright_instance.chromium.connect_over_cdp(self.cdp_url)
            contexts = browser.contexts
            context = contexts[0] if contexts else await browser.new_context()

            # Tìm tab studio.youtube.com nếu có sẵn
            for page in context.pages:
                if "studio.youtube.com" in page.url:
                    await page.bring_to_front()
                    await self._handle_google_login_if_needed(page)
                    return context, page

            # Nếu chưa có, mở tab mới
            page = await context.new_page()
            await page.goto(YOUTUBE_STUDIO_URL, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)
            await self._handle_google_login_if_needed(page)
            return context, page
        except Exception as e:
            try:
                safe_print(f"[!] Loi ket noi trinh duyet YouTube Studio qua CDP: {e}")
            except Exception:
                pass
            return None, None

    async def scan_latest_scheduled_slots(self, page: Page) -> List[Tuple[date, str]]:
        """Quét tab Shorts trên YouTube Studio để tìm lịch đăng cuối."""
        scheduled_slots: List[Tuple[date, str]] = []
        try:
            safe_print("[*] Đang kiểm tra danh sách Shorts đã lên lịch trên kênh...")
            channel_match = re.search(r"/channel/([^/]+)", page.url)
            if not channel_match:
                channel_links = page.locator("a[href*='/channel/']")
                for index in range(await channel_links.count()):
                    href = await channel_links.nth(index).get_attribute("href") or ""
                    channel_match = re.search(r"/channel/([^/]+)", href)
                    if channel_match:
                        break
            if not channel_match:
                try:
                    await page.goto(YOUTUBE_STUDIO_URL, wait_until="commit", timeout=15000)
                except Exception:
                    pass
                await page.wait_for_timeout(2500)
                channel_match = re.search(r"/channel/([^/]+)", page.url)
            if not channel_match:
                raise RuntimeError("Không xác định được kênh YouTube Studio đang đăng nhập.")

            channel_id = channel_match.group(1)
            shorts_url = (
                f"https://studio.youtube.com/channel/{channel_id}/videos/short"
                "?filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C"
                "%22sortOrder%22%3A%22DESCENDING%22%7D"
            )
            await page.goto(shorts_url, wait_until="commit", timeout=30000)
            rows = page.locator("ytcp-video-row")
            try:
                await rows.first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(1200)

            count = await rows.count()
            safe_print(f"[*] Tìm thấy {count} Shorts trong trang lịch gần nhất...")
            row_texts = [await rows.nth(index).inner_text() for index in range(count)]
            scheduled_slots = extract_scheduled_slots_from_shorts_rows(row_texts)
            for scheduled_date, hour in scheduled_slots:
                safe_print(f"[✓] Short đã chiếm slot: {scheduled_date} lúc {hour}")

        except Exception as e:
            safe_print(f"[*] Lưu ý khi quét lịch YouTube Studio: {e}")
            raise

        return scheduled_slots

    async def get_next_missing_slots(self, count: int = 3, fallback_start_date: Optional[date] = None) -> List[Tuple[str, str]]:
        """Tự động kết nối YouTube Studio, kiểm tra video mới nhất và trả về danh sách slot còn thiếu."""
        async with async_playwright() as p:
            context, page = await self.connect_studio_page(p)
            if not page:
                raise RuntimeError(f"Không thể kết nối YouTube Studio qua cổng {self.cdp_port}.")
            existing_slots = await self.scan_latest_scheduled_slots(page)
            return calculate_next_available_slots(existing_slots, count=count, start_from_date=fallback_start_date)

    async def upload_and_schedule_single_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: List[str],
        schedule_date: str,
        schedule_time: str,
        is_ai_content: bool = True
    ) -> Tuple[bool, str]:
        """Tải một video lên YouTube Studio và thiết lập lịch phát sóng 8h/11h/18h."""
        if not os.path.exists(video_path):
            return False, f"Tệp video không tồn tại: {video_path}"

        async with async_playwright() as p:
            context, page = await self.connect_studio_page(p)
            if not page:
                return False, f"Không thể kết nối Chrome Studio trên cổng {self.cdp_port}. Vui lòng mở Chrome cổng 9222."

            try:
                safe_print(f"[*] Bắt đầu quy trình tải video lên YouTube Studio: {title}")
                await page.goto(YOUTUBE_STUDIO_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # 1. Bấm nút Tạo / Create
                create_btn = page.locator("#create-icon, button[aria-label*='Tạo'], button[aria-label*='Create'], ytcp-button#create-icon").first
                await create_btn.wait_for(state="visible", timeout=15000)
                await create_btn.click()
                await page.wait_for_timeout(1000)

                # 2. Chọn Tải video lên
                upload_item = page.locator("tp-yt-paper-item:has-text('Tải video lên'), tp-yt-paper-item:has-text('Upload videos')").first
                if await upload_item.is_visible():
                    await upload_item.click()
                await page.wait_for_timeout(2000)

                # 3. Nạp tệp video vào input file
                file_input = page.locator("input[type='file']").first
                await file_input.wait_for(state="attached", timeout=15000)
                await file_input.set_input_files(os.path.abspath(video_path))
                safe_print(f"[✓] Đã đính kèm tệp video: {video_path}")

                # Chờ modal chi tiết video xuất hiện
                await page.wait_for_timeout(6000)

                # 4. Điền Tiêu đề
                title_box = page.locator("div#textbox[aria-label*='tiêu đề'], div#textbox[aria-label*='Title']").first
                if await title_box.is_visible():
                    await title_box.click()
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await title_box.fill(title[:95])
                    safe_print(f"[✓] Đã điền tiêu đề: {title[:50]}...")

                # 5. Điền Mô tả
                desc_box = page.locator("div#description-textarea div#textbox, div#textbox[aria-label*='mô tả'], div#textbox[aria-label*='Description']").first
                if await desc_box.is_visible():
                    await desc_box.click()
                    await desc_box.fill(description)
                    safe_print(f"[✓] Đã điền mô tả kèm cam kết chính sách AI.")

                # 6. Chọn đối tượng: Không dành cho trẻ em
                not_for_kids = page.locator("tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS'], tp-yt-paper-radio-button:has-text('không phải nội dung dành cho trẻ em')").first
                if await not_for_kids.is_visible():
                    await not_for_kids.click()

                # 7. Mở rộng 'Hiện thêm' (Show more) để khai báo chính sách AI & Tags
                show_more = page.locator("ytcp-button#toggle-button:has-text('HIỆN THÊM'), ytcp-button#toggle-button:has-text('SHOW MORE'), div#toggle-button").first
                if await show_more.is_visible():
                    await show_more.click()
                    await page.wait_for_timeout(1000)

                # 8. TÍCH CHỌN CHÍNH SÁCH AI (ALTERED OR SYNTHETIC CONTENT)
                if is_ai_content:
                    try:
                        # Radio button Có (Yes) cho nội dung bị thay đổi hoặc do AI tạo ra
                        ai_yes_radio = page.locator("tp-yt-paper-radio-button[name='ALTERED_CONTENT_YES'], tp-yt-paper-radio-button:has-text('Có'):near(:text('Nội dung đã chỉnh sửa')), tp-yt-paper-radio-button:has-text('Yes'):near(:text('Altered content'))").first
                        if await ai_yes_radio.is_visible():
                            await ai_yes_radio.click()
                            safe_print("[✓] Đã bật khai báo chính sách YouTube: Nội dung do AI tạo ra (Altered/Synthetic Content).")
                    except Exception as ai_e:
                        safe_print(f"[*] Lưu ý khai báo AI: {ai_e}")

                # 9. Điền Thẻ tags
                if tags:
                    tags_input = page.locator("input[placeholder*='Thêm thẻ'], input[placeholder*='Add tag']").first
                    if await tags_input.is_visible():
                        tag_str = ",".join([t.replace("#", "").strip() for t in tags if t])
                        await tags_input.fill(tag_str)
                        await page.keyboard.press("Enter")

                # 10. Chuyển qua các bước tiếp theo (Bấm nút Tiếp 3 lần)
                for step in range(3):
                    next_btn = page.locator("ytcp-button#next-button:not([disabled])").first
                    await next_btn.wait_for(state="visible", timeout=10000)
                    await next_btn.click()
                    await page.wait_for_timeout(1500)

                # 11. BƯỚC CHẾ ĐỘ HIỂN THỊ (VISIBILITY) & HẸN GIỜ (SCHEDULE)
                schedule_radio = page.locator("tp-yt-paper-radio-button#schedule-radio, tp-yt-paper-radio-button:has-text('Lên lịch'), tp-yt-paper-radio-button:has-text('Schedule')").first
                await schedule_radio.wait_for(state="visible", timeout=10000)
                await schedule_radio.click()
                await page.wait_for_timeout(1500)

                # Nhập thời gian hẹn giờ
                time_input = page.locator("ytcp-datetime-picker ytcp-dropdown-trigger[aria-label*='thời gian'], input#input:near(:text('thời gian')), ytcp-text-dropdown-trigger[aria-label*='thời gian']").first
                if await time_input.is_visible():
                    await time_input.click()
                    await page.wait_for_timeout(500)
                    time_opt = page.locator(f"tp-yt-paper-item:has-text('{schedule_time}')").first
                    if await time_opt.is_visible():
                        await time_opt.click()
                    else:
                        await page.keyboard.type(schedule_time)
                        await page.keyboard.press("Enter")

                safe_print(f"[✓] Đã thiết lập lịch đăng phát: {schedule_date} lúc {schedule_time}.")

                # 12. Bấm nút hoàn tất Lên lịch
                done_btn = page.locator("ytcp-button#done-button:not([disabled])").first
                await done_btn.wait_for(state="visible", timeout=10000)
                await done_btn.click()
                await page.wait_for_timeout(4000)

                safe_print(f"[✅] Đã lên lịch thành công video '{title}' lúc {schedule_time} ngày {schedule_date}!")
                return True, f"Thành công lên lịch đăng vào {schedule_time} ngày {schedule_date}."

            except Exception as e:
                err = f"Lỗi trong quá trình upload & hẹn giờ YouTube: {str(e)}"
                safe_print(f"[X] {err}")
                return False, err


def upload_and_schedule_sync(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    schedule_date: str,
    schedule_time: str
) -> Tuple[bool, str]:
    """Hàm đồng bộ gọi upload và lên lịch YouTube Studio."""
    uploader = YouTubeStudioUploader()
    return asyncio.run(uploader.upload_and_schedule_single_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        schedule_date=schedule_date,
        schedule_time=schedule_time
    ))
