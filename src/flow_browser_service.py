# Chức năng: Điều khiển Chrome qua CDP / Playwright để tự động tương tác với Google Flow (flow.google.com):
#          Tự động điền prompt, bấm sinh video/ảnh AI, theo dõi tiến trình và tải file thành phẩm về máy.
# Lý do tạo: Tự động hóa 100% quy trình từ Prompt trên Web app -> Google Flow của user -> Video hoàn chỉnh.

import os
import sys
import json
import time
import base64
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from playwright.sync_api import sync_playwright, Page, Frame, BrowserContext, Browser

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_log(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'), flush=True)
        except Exception:
            pass

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "flow_config.json"
ATTEMPTS_DIR = ROOT_DIR / "temp" / "flow_attempts"
ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)

# Nhận diện nhân vật nhất quán giữa các phân cảnh của kênh.
STICKMAN_CANONICAL_GUIDANCE = (
    "Keep the same canonical character CH01 in every shot: a clean minimalist stickman, "
    "white round head, dark navy outline and oval eyes, light blue shirt #8CCFE8, friendly expression. "
    "No captions, subtitles, logos or watermarks inside the generated visual."
)


def load_flow_config() -> Dict[str, Any]:
    """Tải cấu hình Google Flow từ flow_config.json."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            safe_log(f"[WARNING] Lỗi đọc flow_config.json: {e}")
    return {
        "project_url": "https://flow.google.com/project/4763b8d1-5c45-4532-85b9-960a80cefcb4",
        "tool_url": "https://flow.google.com/project/4763b8d1-5c45-4532-85b9-960a80cefcb4/tool/a1dc8db6-3417-4d6b-a00a-50832cb508e1?mode=APP",
        "cdp_port": 9222,
        "chrome_user_data_dir": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        "profile_directory": "Default",
        "timeout_seconds": 180,
        "video_timeout_seconds": 1800,
    }


def is_cdp_available(port: int = 9222) -> bool:
    """Kiểm tra xem Chrome đã mở cổng CDP 9222 hay chưa."""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_flow_readiness(port: int = 9222) -> str:
    """Trả về disconnected, login_required hoặc ready dựa trên tab Flow thật."""
    import urllib.request
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{port}/json/list", method="GET")
        with urllib.request.urlopen(request, timeout=2.0) as response:
            tabs = json.loads(response.read().decode("utf-8"))
    except Exception:
        return "disconnected"

    flow_urls = [str(tab.get("url", "")) for tab in tabs if "flow.google.com" in str(tab.get("url", ""))]
    if any("/project/" in url or "/tool/" in url for url in flow_urls):
        return "ready"
    # Người dùng đã đăng nhập có thể đang ở dashboard gốc `flow.google.com/?pli=1`.
    # Phiên chưa đăng nhập bị chuyển rõ ràng sang `/about` hoặc accounts.google.com.
    if any("/about" not in url and "accounts.google.com" not in url for url in flow_urls):
        return "ready"
    if flow_urls:
        return "login_required"
    return "login_required"


class FlowBrowserController:
    """Bộ điều khiển tương tác tự động với Google Flow qua Playwright CDP."""

    def __init__(self):
        self.cfg = load_flow_config()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.seen_video_urls: set = set()
        self.seen_video_hashes: set = set()

    def is_video_response(self, res) -> bool:
        """Kiểm tra một network response có phải là luồng video hợp lệ từ Flow hay không (hỗ trợ HTTP 200/206)."""
        try:
            r_url = getattr(res, "url", "")
            status = getattr(res, "status", 0)
            if status not in (200, 206):
                return False
            headers = getattr(res, "headers", {}) or {}
            ct = str(headers.get("content-type", "")).lower()
            if "video/" in ct:
                return True
            if "flow-content.google/video/" in r_url or ".mp4" in r_url or "googlevideo.com" in r_url:
                return True
        except Exception:
            pass
        return False

    def _launch_flow_chrome(self) -> Tuple[bool, str]:
        """Tự mở lại Chrome profile riêng nếu tiến trình bị đóng/crash."""
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        chrome_exe = next((path for path in candidates if os.path.exists(path)), "")
        if not chrome_exe:
            return False, "Không tìm thấy Google Chrome trên máy."

        user_data = self.cfg.get("chrome_user_data_dir") or str(ROOT_DIR / "flow_chrome_profile")
        profile = self.cfg.get("profile_directory", "Default")
        project_url = self.cfg.get("project_url", "https://flow.google.com")
        cmd = [
            chrome_exe,
            f"--remote-debugging-port={self.cfg.get('cdp_port', 9222)}",
            f"--user-data-dir={user_data}",
            f"--profile-directory={profile}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            project_url,
        ]
        try:
            creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008) if os.name == "nt" else 0
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            for _ in range(30):
                time.sleep(0.5)
                if is_cdp_available(self.cfg.get("cdp_port", 9222)):
                    return True, "Đã tự mở lại Chrome Google Flow."
            return False, "Chrome đã mở nhưng cổng điều khiển chưa phản hồi."
        except Exception as exc:
            return False, f"Không thể tự mở Chrome: {exc}"

    def connect(self) -> Tuple[bool, str]:
        """Kết nối tới trình duyệt đang mở Google Flow."""
        port = self.cfg.get("cdp_port", 9222)
        project_url = self.cfg.get("project_url", "https://flow.google.com")

        try:
            if not self.playwright:
                self.playwright = sync_playwright().start()

            if not is_cdp_available(port):
                launched, launch_message = self._launch_flow_chrome()
                if not launched:
                    return False, launch_message

            if is_cdp_available(port):
                safe_log(f"[*] Đang kết nối tới Chrome Google Flow qua cổng CDP {port}...")
                self.browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=10000)
                self.context = self.browser.contexts[0] if self.browser.contexts else None
            else:
                return False, f"Cổng điều khiển 9222 chưa sẵn sàng. Vui lòng chạy qua file run.bat hoặc mở Chrome với cổng 9222 để tool thao tác trực tiếp trên tab của bạn."

            if not self.context:
                return False, "Không thể kết nối vào trình duyệt Chrome."

            # Tìm tab đã mở flow.google.com
            for p in self.context.pages:
                if "flow.google.com" in p.url:
                    self.page = p
                    break

            if not self.page:
                self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                safe_log(f"[*] Đang điều hướng tới Google Flow: {project_url}")
                try:
                    self.page.goto(project_url, wait_until="domcontentloaded", timeout=20000)
                except Exception:
                    pass

            if "/about" in self.page.url or "/accounts.google.com/" in self.page.url:
                return False, "Google Flow đang mở nhưng profile riêng chưa đăng nhập. Hãy đăng nhập một lần trong cửa sổ Chrome Flow."

            return True, "Kết nối thành công tới Google Flow."

        except Exception as e:
            return False, f"Lỗi kết nối Google Flow: {str(e)}"

    def _ensure_page(self) -> Optional[Page]:
        try:
            if not self.page or self.page.is_closed():
                ok, msg = self.connect()
                if not ok:
                    safe_log(f"[ERROR] {msg}")
                    return None
            # Thử truy cập url để chắc chắn target page/context chưa bị đóng
            _ = self.page.url
            return self.page
        except Exception:
            safe_log("[*] Phát hiện trang hoặc trình duyệt đã bị ngắt kết nối. Đang tự động kết nối lại...")
            self.browser = None
            self.context = None
            self.page = None
            ok, msg = self.connect()
            if not ok:
                safe_log(f"[ERROR] {msg}")
                return None
            return self.page

    def generate_scene_video(
        self,
        prompt: str,
        output_path: str,
        orientation: str = "vertical",
        timeout_sec: Optional[int] = None,
        status_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Tự động đưa prompt lên Google Flow (Google Veo / Videos section),
        kích hoạt tạo video, kiên trì đợi render và tải file .mp4 về output_path.
        """
        if timeout_sec is None:
            timeout_sec = int(self.cfg.get("video_timeout_seconds", 1800))

        page = self._ensure_page()
        if not page:
            return False, "Không thể mở trang Google Flow."

        project_url = self.cfg.get("project_url", "https://flow.google.com")
        safe_log(f"[*] Đang thao tác trên Google Flow để sinh video cho prompt: \"{prompt[:50]}...\"")

        # Đăng ký listener bắt response video mới từ network
        new_network_videos: List[str] = []
        def _on_response(res):
            try:
                if self.is_video_response(res):
                    r_url = res.url
                    if r_url not in self.seen_video_urls and r_url not in new_network_videos:
                        new_network_videos.append(r_url)
            except Exception:
                pass

        try:
            page.on("response", _on_response)
        except Exception:
            pass

        try:
            # 1. Chỉ điều hướng nếu tab hiện tại không thuộc Flow hoặc bị đẩy ra trang login/about
            if "flow.google.com" not in page.url or "/project/" not in page.url:
                safe_log(f"[*] Đang điều hướng tới Google Flow: {project_url}")
                page.goto(project_url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_timeout(4000)
                except Exception:
                    pass

            if "/about" in page.url or "/accounts.google.com/" in page.url:
                return False, "Google Flow chưa đăng nhập hoặc tài khoản không có quyền mở project."

            # Ghi nhận toàn bộ video đã tồn tại trên trang trước khi tạo cảnh mới
            for existing_video in page.locator("video").all():
                try:
                    existing_src = existing_video.get_attribute("src")
                    if existing_src:
                        self.seen_video_urls.add(existing_src)
                except Exception:
                    pass
            for existing_source in page.locator("video source").all():
                try:
                    s_src = existing_source.get_attribute("src")
                    if s_src:
                        self.seen_video_urls.add(s_src)
                except Exception:
                    pass

            # Đóng onboarding nếu có
            got_it = page.get_by_role("button", name="Got it, dismiss onboarding message", exact=True)
            if got_it.count() > 0 and got_it.first.is_visible():
                got_it.first.click()
                page.wait_for_timeout(300)

            # 2. Tìm ô nhập prompt video của Google Flow (chờ tối đa 15s cho React SPA nạp xong)
            try:
                page.wait_for_selector("textarea", timeout=15000)
            except Exception:
                pass

            input_box = None
            selectors = [
                "textarea[placeholder*='create' i]",
                "textarea[placeholder*='prompt' i]",
                "textarea[placeholder*='describe' i]",
                "textarea[placeholder*='video' i]",
                "textarea[placeholder*='mô tả' i]",
                "textarea",
                "input[type='text'][placeholder*='prompt' i]",
                "div[contenteditable='true']",
            ]
            for sel in selectors:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    input_box = loc.first
                    break

            if not input_box:
                # Nếu đang ở trong view applet phụ không có ô chat, chuyển về giao diện dự án chính
                safe_log("[*] Chưa thấy ô chat, đang chuyển về giao diện dự án chính của Flow...")
                try:
                    page.goto(project_url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    for sel in selectors:
                        loc = page.locator(sel)
                        if loc.count() > 0 and loc.first.is_visible():
                            input_box = loc.first
                            break
                except Exception:
                    pass

            if not input_box:
                page.screenshot(path=str(ATTEMPTS_DIR / "error_no_prompt_input.png"))
                return False, "Không tìm thấy ô nhập prompt trên Google Flow. Đã lưu ảnh chẩn đoán."

            # 3. Điền prompt vào ô.
            try:
                input_box.click(force=True, timeout=5000)
            except Exception:
                pass
            try:
                input_box.fill("")
            except Exception:
                pass
            ratio_hint = "vertical 9:16 portrait" if orientation == "vertical" else "horizontal 16:9 landscape"
            full_prompt = (
                "Generate exactly ONE AI VIDEO CLIP, not a still image. Use the configured video model.\n"
                f"Scene: {prompt.strip()}\n{STICKMAN_CANONICAL_GUIDANCE}\n"
                f"Composition: {ratio_hint}. Cinematic motion, smooth camera movement, no audio."
            )
            input_box.fill(full_prompt)
            page.wait_for_timeout(500)

            # 4. Tìm và bấm nút Generate / Tạo (hoặc ấn Enter)
            btn_generate = None
            btn_selectors = [
                "button[aria-label='Start generation']",
                "button[aria-label*='generate' i]",
                "button[aria-label*='tạo' i]",
                "button:has-text('Generate')",
                "button:has-text('Tạo')",
                "button[type='submit']",
            ]
            for b_sel in btn_selectors:
                b_loc = page.locator(b_sel)
                if b_loc.count() > 0 and b_loc.first.is_visible():
                    btn_generate = b_loc.first
                    break

            clicked = False
            if btn_generate:
                try:
                    btn_generate.click(force=True, timeout=5000)
                    clicked = True
                except Exception:
                    pass
            if not clicked:
                try:
                    input_box.press("Enter")
                except Exception:
                    pass

            # Một số cấu hình Agent yêu cầu xác nhận trước khi tiêu credits.
            page.wait_for_timeout(1500)
            for confirm_name in ["Generate", "Confirm", "Continue", "Tạo", "Xác nhận"]:
                confirm_button = page.get_by_role("button", name=confirm_name, exact=True)
                try:
                    if confirm_button.count() > 0 and confirm_button.first.is_visible():
                        confirm_button.first.click()
                        break
                except Exception:
                    pass

            safe_log("[*] Đã bấm nút Tạo video trên Google Flow! Đang chờ AI render clip...")

            # 5. Theo dõi kết quả sinh video
            start_time = time.time()
            min_generation_wait = 12.0  # Chống bắt nhầm clip cũ trong 12 giây đầu

            while time.time() - start_time < timeout_sec:
                if page.is_closed():
                    safe_log("[!] Tab Flow bị đóng. Đang kết nối lại...")
                    self.browser = None
                    self.context = None
                    self.page = None
                    ok_reconnect, reconnect_message = self.connect()
                    if not ok_reconnect or not self.page:
                        return False, reconnect_message
                    page = self.page

                try:
                    page.wait_for_timeout(3000)
                except Exception:
                    pass

                elapsed = time.time() - start_time
                if elapsed < min_generation_wait:
                    continue

                if int(elapsed) % 30 < 4:
                    msg = f"[*] Đang theo dõi tiến độ sinh video từ Google Flow ({int(elapsed)}s/{timeout_sec}s)... Tiếp tục chờ AI render clip hoàn chỉnh..."
                    safe_log(msg)
                    if status_callback:
                        try:
                            status_callback(int(elapsed), msg)
                        except Exception:
                            pass

                candidate_url = None

                # Ưu tiên URL từ network listener
                if new_network_videos:
                    for n_url in list(new_network_videos):
                        if n_url not in self.seen_video_urls:
                            candidate_url = n_url
                            break

                # Tiếp theo kích hoạt preview trên thẻ video vừa sinh để ép Flow tải stream
                if not candidate_url:
                    try:
                        # Thử hover vào card trong gallery All media (cột bên trái)
                        media_items = page.locator("main div[role='button'], main div[tabindex='0'], [role='grid'] div, aside img, [class*='chat'] img").all()
                        if media_items:
                            media_items[0].hover()
                    except Exception:
                        pass

                    try:
                        download_btns = page.locator("button[aria-label*='Download' i], button[aria-label*='Tải' i], [data-icon='download']").all()
                        for dl in download_btns:
                            if dl.is_visible():
                                dl.hover()
                    except Exception:
                        pass

                    try:
                        play_btns = page.locator("button:has-text('play_circle'), [aria-label*='Play'], [aria-label*='play']").all()
                        if play_btns:
                            play_btns[-1].hover()
                    except Exception:
                        pass

                    # Kiểm tra thẻ <video> mới trong DOM
                    for v in page.locator("video").all():
                        try:
                            src = v.get_attribute("src")
                            if src and src not in self.seen_video_urls and ("blob:" in src or "http" in src):
                                candidate_url = src
                                break
                        except Exception:
                            pass

                    # Kiểm tra thẻ <source> bên trong <video>
                    if not candidate_url:
                        for s in page.locator("video source").all():
                            try:
                                s_src = s.get_attribute("src")
                                if s_src and s_src not in self.seen_video_urls and ("blob:" in s_src or "http" in s_src):
                                    candidate_url = s_src
                                    break
                            except Exception:
                                pass


                if candidate_url:
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                    save_js = """
                    async (src) => {
                        const response = await fetch(src);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    }
                    """
                    try:
                        data_url = page.evaluate(save_js, candidate_url)
                        if data_url and "," in data_url:
                            b64_data = data_url.split(",")[1]
                            import base64, hashlib
                            video_bytes = base64.b64decode(b64_data)
                            file_hash = hashlib.sha256(video_bytes).hexdigest()

                            if file_hash in self.seen_video_hashes:
                                safe_log(f"[!] Bỏ qua video trùng lặp nội dung ({file_hash[:8]}), tiếp tục chờ Flow sinh clip mới...")
                                self.seen_video_urls.add(candidate_url)
                                continue

                            # Lưu thành công clip hoàn toàn mới
                            with open(output_path, "wb") as f:
                                f.write(video_bytes)
                            self.seen_video_hashes.add(file_hash)
                            self.seen_video_urls.add(candidate_url)
                            safe_log(f"[✓] Đã tạo thành công clip video độc lập từ Google Flow: {candidate_url[:50]}... (hash {file_hash[:8]})")
                            return True, output_path
                    except Exception as ex:
                        safe_log(f"[!] Lỗi khi tải video blob: {ex}")

            diagnostic_path = output_path if output_path.endswith(".png") else output_path.replace(".mp4", "_diagnostic.png")
            try:
                if page and not page.is_closed():
                    page.screenshot(path=diagnostic_path)
            except Exception:
                pass
            return False, f"Hết thời gian chờ video từ Google Flow ({timeout_sec}s). Ảnh chẩn đoán: {diagnostic_path}"

        except Exception as e:
            return False, f"Lỗi trong quá trình tương tác Google Flow: {str(e)}"
        finally:
            try:
                if page and not page.is_closed():
                    page.remove_listener("response", _on_response)
            except Exception:
                pass


    def generate_scene_image(
        self,
        prompt: str,
        output_path: str,
        orientation: str = "vertical",
        style_preset: str = "",
        timeout_sec: int = 90
    ) -> Tuple[bool, str]:
        """Tự động sinh ảnh từ Google Flow Nano Banana / Imagen 3."""
        page = self._ensure_page()
        if not page:
            return False, "Không thể kết nối vào tab Google Flow."

        safe_log(f"[*] Đang yêu cầu Google Flow sinh ảnh tĩnh (Imagen 3): \"{prompt[:50]}...\"")
        project_url = self.cfg.get("project_url", "https://flow.google.com")

        new_images: List[str] = []
        def _on_image_response(res):
            try:
                r_url = res.url
                if ("flow-content.google/image/" in r_url or ("flow-content.google" in r_url and ".png" in r_url)) and res.status == 200:
                    new_images.append(r_url)
            except Exception:
                pass

        try:
            page.on("response", _on_image_response)
        except Exception:
            pass

        try:
            # 1. KIỂM TRA TOOL FRAME (Applet Tool "GIA SƯ STICKMAN STUDIO 4K" / Nano Banana Pro)
            tool_frame = None
            for f in page.frames:
                try:
                    for b in f.locator("button").all():
                        t = b.inner_text()
                        if "TẠO ẢNH" in t or "CINEMATIC" in t or "TẢI ẢNH" in t:
                            tool_frame = f
                            break
                    if tool_frame:
                        break
                except Exception:
                    pass

            if tool_frame:
                safe_log("[*] Phát hiện Google Flow Tool iframe (Nano Banana Pro). Đang điền prompt...")
                try:
                    # Nếu màn hình đang hiển thị kết quả phân cảnh trước (có nút add), bấm add để reset form
                    for b_el in tool_frame.locator("button").all():
                        if "add" in b_el.inner_text().lower():
                            b_el.click()
                            page.wait_for_timeout(800)
                            break

                    existing_tool_imgs = {img.get_attribute("src") for img in tool_frame.locator("img").all() if img.get_attribute("src")}
                    ta = tool_frame.locator("textarea").first
                    ta.fill(prompt)
                    page.wait_for_timeout(300)
                    gen_btn = tool_frame.locator("button").first
                    gen_btn.click()
                    safe_log("[*] Đã bấm nút 'TẠO ẢNH CINEMATIC' trong Flow Tool. Đang chờ Nano Banana Pro hoàn tất...")

                    start_time = time.time()
                    while time.time() - start_time < timeout_sec:
                        page.wait_for_timeout(2000)
                        for img in tool_frame.locator("img").all():
                            try:
                                src = img.get_attribute("src") or ""
                                if src and src not in existing_tool_imgs and src.startswith("data:image/"):
                                    import base64
                                    b64 = src.split(",", 1)[1]
                                    data = base64.b64decode(b64)
                                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                                    with open(output_path, "wb") as f_out:
                                        f_out.write(data)
                                    safe_log(f"[✓] Đã tạo thành công ảnh từ Google Flow Tool (Nano Banana Pro): {output_path}")
                                    return True, output_path
                            except Exception:
                                pass
                    return False, f"Hết thời gian chờ ảnh từ Flow Tool ({timeout_sec}s)."
                except Exception as e_tool:
                    safe_log(f"[!] Lỗi tương tác Flow Tool: {e_tool}")

            # 2. TRƯỜNG HỢP GIAO DIỆN FLOW GỐC (DỰ ÁN KHÔNG QUA APPLET FRAME)
            if "flow.google.com" not in page.url or "/project/" not in page.url:
                page.goto(project_url, wait_until="domcontentloaded", timeout=25000)
                try:
                    page.wait_for_timeout(3000)
                except Exception:
                    pass

            # Thu thập ảnh đã có để tránh lấy trùng
            existing_imgs = set()
            for img in page.locator("img").all():
                try:
                    s = img.get_attribute("src")
                    if s:
                        existing_imgs.add(s)
                except Exception:
                    pass

            # Tìm ô input
            selectors = [
                "textarea[placeholder*='create' i]",
                "textarea[placeholder*='prompt' i]",
                "textarea[placeholder*='describe' i]",
                "textarea",
                "input[type='text'][placeholder*='prompt' i]",
                "div[contenteditable='true']",
            ]
            input_box = None
            for sel in selectors:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    input_box = loc.first
                    break

            if not input_box:
                return False, "Không tìm thấy ô nhập prompt trên Flow."

            try:
                input_box.click(force=True, timeout=5000)
                input_box.fill("")
            except Exception:
                pass

            ratio_hint = "vertical 9:16 portrait" if orientation == "vertical" else "horizontal 16:9 landscape"
            full_prompt = (
                "Generate a high-detail still cinematic image, not a video. Use the configured image model (Imagen 3 / Nano Banana Pro).\n"
                f"Scene: {prompt.strip()}\n{STICKMAN_CANONICAL_GUIDANCE}\n"
                f"Style: {style_preset}. Composition: {ratio_hint}. 4k resolution, rich colors, no text, no captions."
            )
            input_box.fill(full_prompt)
            page.wait_for_timeout(500)

            # Bấm Generate
            btn_selectors = [
                "button[aria-label='Start generation']",
                "button[aria-label*='generate' i]",
                "button:has-text('Generate')",
                "button:has-text('Tạo')",
            ]
            btn = None
            for b_sel in btn_selectors:
                b_loc = page.locator(b_sel)
                if b_loc.count() > 0 and b_loc.first.is_visible():
                    btn = b_loc.first
                    break
            if btn:
                try:
                    btn.click(force=True, timeout=5000)
                except Exception:
                    input_box.press("Enter")
            else:
                input_box.press("Enter")

            safe_log("[*] Đã gửi lệnh sinh ảnh lên Google Flow. Đang chờ ảnh hoàn tất...")
            start_time = time.time()
            while time.time() - start_time < timeout_sec:
                page.wait_for_timeout(2000)
                # Kiểm tra network
                for img_url in list(new_images):
                    if img_url not in existing_imgs:
                        # Tải ảnh về
                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        save_js = """
                        async (src) => {
                            const response = await fetch(src);
                            const blob = await response.blob();
                            return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            });
                        }
                        """
                        try:
                            data_url = page.evaluate(save_js, img_url)
                            if data_url and "," in data_url:
                                b64 = data_url.split(",")[1]
                                import base64
                                with open(output_path, "wb") as f:
                                    f.write(base64.b64decode(b64))
                                safe_log(f"[✓] Đã tạo thành công ảnh từ Google Flow: {output_path}")
                                return True, output_path
                        except Exception:
                            pass

                # Kiểm tra DOM img
                for img in page.locator("img[src*='flow-content']").all():
                    try:
                        src = img.get_attribute("src")
                        if src and src not in existing_imgs:
                            save_js = """
                            async (src) => {
                                const response = await fetch(src);
                                const blob = await response.blob();
                                return new Promise((resolve) => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result);
                                    reader.readAsDataURL(blob);
                                });
                            }
                            """
                            data_url = page.evaluate(save_js, src)
                            if data_url and "," in data_url:
                                b64 = data_url.split(",")[1]
                                import base64
                                with open(output_path, "wb") as f:
                                    f.write(base64.b64decode(b64))
                                safe_log(f"[✓] Đã lưu ảnh từ thẻ DOM Flow: {output_path}")
                                return True, output_path
                    except Exception:
                        pass

            return False, f"Hết thời gian chờ ảnh từ Google Flow ({timeout_sec}s)."
        except Exception as exc:
            return False, f"Lỗi sinh ảnh trên Flow: {exc}"
        finally:
            try:
                page.remove_listener("response", _on_image_response)
            except Exception:
                pass


_CONTROLLER_LOCAL = threading.local()

def get_flow_controller() -> FlowBrowserController:
    """Mỗi thread dùng một controller riêng vì Playwright sync không thread-safe."""
    controller = getattr(_CONTROLLER_LOCAL, "controller", None)
    if controller is None:
        controller = FlowBrowserController()
        _CONTROLLER_LOCAL.controller = controller
    return controller
