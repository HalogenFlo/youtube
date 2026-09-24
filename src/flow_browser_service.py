# Chức năng: Điều khiển Chrome qua CDP để tương tác với Google Flow (flow.google.com), nạp prompt, khoá nhân vật Stickman và trích xuất ảnh sinh ra.
# Lý do tạo: Thay thế mô hình local tốn VRAM bằng Google Flow Nano Banana Pro chất lượng cao, miễn phí và không tải GPU.
# Trích dẫn: Kế thừa cơ chế CDP Playwright và React Fiber state injection từ dự án tiktok-ytb.

import os
import sys
import json
import time
import base64
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from playwright.sync_api import sync_playwright, Page, Frame, BrowserContext

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

# Lời dẫn định hình chuẩn cho nhân vật người que stickman CH01 áo xanh
STICKMAN_CANONICAL_GUIDANCE = (
    " STRICT CHARACTER LOCK: CH01 must exactly match the attached reference. "
    "Round white head, thick navy outline, two solid black vertical oval eyes, "
    "open happy mouth with a visible coral-pink tongue. Exactly one light-blue short-sleeve T-shirt #8CCFE8, "
    "two navy stick arms and two navy stick legs. No teeth, eyebrows or white pupils. "
    "Preserve the same bold stroke weight and head/body proportions. "
    "Wide full-body shot: character entirely inside frame with generous 15 percent margins. "
    "Minimalist stickman illustration, clean navy outlines, off-white background."
)


def load_flow_config() -> Dict[str, Any]:
    """Tải cấu hình Google Flow từ flow_config.json."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            safe_log(f"[WARNING] Loi doc flow_config.json: {e}")
    return {
        "tool_url": "https://flow.google.com/project/41d3d574-907c-4bb0-90a7-c98f85f5e22b/tool/2791e8ba-9ae0-4ca9-9368-b7efe600c53d",
        "cdp_port": 9222,
        "chrome_user_data_dir": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        "profile_directory": "Default",
        "default_aspect_ratio": "9:16",
        "workers": 2,
        "timeout_seconds": 180,
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


def ensure_chrome_with_cdp(cfg: Dict[str, Any]) -> bool:
    """Tự động kích hoạt Chrome với cổng CDP 9222 hoàn toàn tự động, không bắt người dùng mở thủ công."""
    port = cfg.get("cdp_port", 9222)
    if is_cdp_available(port):
        return True

    safe_log(f"[*] Cổng Google Flow ({port}) chưa sẵn sàng. Đang tự động kích hoạt Chrome...")
    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome_bin = next((c for c in chrome_candidates if os.path.exists(c)), None)
    if not chrome_bin:
        safe_log("[ERROR] Không tìm thấy Google Chrome trên máy tính.")
        return False

    user_data = cfg.get("chrome_user_data_dir", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
    profile = cfg.get("profile_directory", "Default")

    # Chromium chỉ mở cổng 9222 nếu được bật sạch từ đầu trên Profile đó.
    # Tự động đóng Chrome cũ và mở lại kèm --restore-last-session để giữ nguyên toàn bộ tab của người dùng!
    if os.name == 'nt':
        try:
            safe_log("[*] Đang khởi động lại Chrome để mở cổng gỡ lỗi 9222 trên tài khoản np368057@gmail.com...")
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2.0)
        except Exception:
            pass

    cmd = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data}",
        f"--profile-directory={profile}",
        "--remote-allow-origins=*",
        "--restore-last-session",
        cfg.get("tool_url", "https://flow.google.com")
    ]
    try:
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        for _ in range(25):
            time.sleep(0.5)
            if is_cdp_available(port):
                safe_log(f"[OK] Google Chrome ({profile} - np368057@gmail.com) đã kích hoạt thành công trên cổng {port}!")
                return True
    except Exception as e:
        safe_log(f"[ERROR] Không thể khởi chạy Chrome: {e}")
    return False



class FlowBrowserController:
    """Bộ điều khiển tương tác tự động với Google Flow qua Playwright CDP."""

    def __init__(self):
        self.cfg = load_flow_config()
        self.playwright = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.tool_frame: Optional[Frame] = None

    def connect(self) -> Tuple[bool, str]:
        """Kết nối tới Google Flow: Tự động khởi chạy Chrome với cổng 9222 và profile Default nếu chưa có."""
        port = self.cfg.get("cdp_port", 9222)
        tool_url = self.cfg.get("tool_url", "https://flow.google.com")

        # 1. Đảm bảo Chrome cổng 9222 được bật tự động 100% với Profile Default của người dùng
        if not is_cdp_available(port):
            safe_log(f"[*] Cổng 9222 chưa mở. Tự động khởi động Chrome với Profile Default...")
            ok_chrome = ensure_chrome_with_cdp(self.cfg)
            if not ok_chrome:
                return False, f"Không thể tự động kích hoạt Chrome cổng {port}."

        try:
            self.playwright = sync_playwright().start()
            safe_log(f"[*] Đang kết nối tới Chrome qua cổng CDP {port}...")
            self.browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=10000)
            self.context = self.browser.contexts[0] if self.browser.contexts else None

            if not self.context:
                return False, "Không thể khởi tạo phiên làm việc của trình duyệt."

            # Tìm tab đã mở tool_url hoặc mở tab mới
            for p in self.context.pages:
                if "flow.google.com" in p.url:
                    self.page = p
                    break

            if not self.page:
                self.page = self.context.new_page()
                try:
                    self.page.goto(tool_url, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    pass


            # Chờ và bắt iframe chứa VP Stickman Lab
            frame = self._find_tool_frame(timeout_sec=15)
            if not frame:
                safe_log("[!] Đã mở Flow nhưng chưa vào frame, tiếp tục với trang chính...")
                self.tool_frame = self.page.main_frame
            else:
                self.tool_frame = frame

            return True, "Kết nối thành công tới Google Flow."

        except Exception as e:
            return False, f"Lỗi kết nối Flow: {str(e)}"


    def _find_tool_frame(self, timeout_sec: int = 25) -> Optional[Frame]:
        """Quét tìm iframe con chứa giao diện VP Stickman Lab."""
        if not self.page:
            return None
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            for fr in self.page.frames:
                if fr == self.page.main_frame:
                    continue
                try:
                    # Kiểm tra xem iframe có tiêu đề VP Stickman Lab hoặc nút Initialize Generation không
                    heading = fr.get_by_role("heading", name="VP Stickman Lab", exact=True)
                    btn = fr.get_by_role("button", name="Initialize Generation", exact=False)
                    if heading.is_visible(timeout=300) or btn.is_visible(timeout=300):
                        return fr
                except Exception:
                    pass
            time.sleep(0.5)
        return None

    def inject_mascot_reference(self) -> bool:
        """Nạp ảnh nhân vật stickman mẫu vào React Fiber hook của selector."""
        if not self.tool_frame:
            return False

        mascot_rel = self.cfg.get("mascot_reference_path", "assets/characters/channel-mascot/reference-v1.png")
        mascot_path = ROOT_DIR / mascot_rel
        if not mascot_path.exists():
            safe_log(f"[WARNING] Khong tim thay file mascot: {mascot_path}")
            return False

        media_id = self.cfg.get("mascot_media_id", "de94a39b-155f-4afe-acbb-d9d4b59ad532")
        mascot_bytes = mascot_path.read_bytes()
        mascot_b64 = base64.b64encode(mascot_bytes).decode("utf-8")

        ref_payload = {
            "mediaId": media_id,
            "base64": mascot_b64,
            "mimeType": "image/png",
            "name": mascot_path.name
        }

        # Gọi hàm evaluate inject trực tiếp vào React Fiber State
        inject_js = """
        (ref) => {
            const el = document.getElementById('character-selector');
            if (!el) return false;
            let f = el[Object.keys(el).find(k => k.startsWith('__reactFiber$'))];
            while (f && !(typeof f.type === 'function' && f.type.name === 'App')) {
                f = f.return;
            }
            let h = f?.memoizedState;
            while (h && !(h.memoizedState?.topic && h.queue?.dispatch)) {
                h = h.next;
            }
            if (h && h.next && h.next.next && h.next.next.queue && h.next.next.queue.dispatch) {
                h.next.queue.dispatch(null); // Clear base scene
                h.next.next.queue.dispatch(ref); // Set character reference
                return true;
            }
            return false;
        }
        """
        try:
            success = self.tool_frame.evaluate(inject_js, ref_payload)
            if success:
                # Chờ nút 'Clear Character' xuất hiện để khẳng định nhân vật đã nạp
                clear_btn = self.tool_frame.get_by_role("button", name="Clear Character", exact=True)
                clear_btn.wait_for(state="visible", timeout=5000)
                return True
        except Exception as e:
            safe_log(f"[WARNING] Loi inject character hook: {e}")
        return False

    def generate_scene_image(
        self,
        prompt: str,
        output_path: str,
        orientation: str = "vertical",
        style_preset: str = "Clean minimalist stickman illustration, navy outlines, off-white background."
    ) -> Tuple[bool, str]:
        """
        Sinh 1 ảnh đơn lẻ cho phân cảnh thông qua Google Flow.
        Trả về Tuple[thành_công, đường_dẫn_ảnh_hoặc_lỗi].
        """
        if not self.tool_frame:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        frame = self.tool_frame
        try:
            # 1. Nạp nhân vật stickman mẫu
            self.inject_mascot_reference()

            # 2. Điền form
            ratio = "9:16" if orientation == "vertical" else "16:9"
            boxes = frame.get_by_role("textbox")
            try:
                boxes.nth(0).wait_for(state="visible", timeout=5000)
            except Exception:
                return False, "Google Flow chưa đăng nhập tài khoản hoặc tool chưa sẵn sàng."

            # Ghép prompt với character lock
            full_topic = f"{prompt.strip()} {STICKMAN_CANONICAL_GUIDANCE}"
            boxes.nth(0).fill(full_topic)

            boxes.nth(1).fill(style_preset)
            boxes.nth(2).fill("Match canonical blue shirt #8CCFE8, white head, oval black eyes, coral tongue.")
            boxes.nth(3).fill("")
            boxes.nth(4).fill("")

            # Chọn tỉ lệ
            frame.get_by_role("button", name=ratio, exact=True).click()

            # Chọn model Nano Banana Pro và 1 worker
            combos = frame.get_by_role("combobox")
            try:
                combos.nth(2).select_option(label="🍌 Nano Banana Pro")
                combos.nth(3).select_option(label="1 Worker")
            except Exception:
                pass

            # 3. Đưa vào queue
            frame.get_by_role("button", name="Initialize Generation", exact=True).click()
            time.sleep(1.0)

            # 4. Bấm Start Queue
            start_btn = frame.get_by_role("button", name="Start Queue", exact=True)
            start_btn.click()

            # 5. Theo dõi kết quả từ localStorage
            timeout_sec = self.cfg.get("timeout_seconds", 120)
            start_time = time.time()
            img_b64 = None
            mime_type = "image/png"

            while time.time() - start_time < timeout_sec:
                time.sleep(1.5)
                state = frame.evaluate("() => JSON.parse(localStorage.getItem('VP_LAB_STATE_V2') || '{}')")
                queue = state.get("queue", [])
                if queue:
                    latest_item = queue[-1]
                    status = latest_item.get("status", "")
                    if status in ("COMPLETED", "ACCEPTED") and latest_item.get("result", {}).get("base64"):
                        img_b64 = latest_item["result"]["base64"]
                        mime_type = latest_item["result"].get("mimeType", "image/png")
                        break
                    elif status in ("FAILED", "UNKNOWN"):
                        return False, f"Quá trình sinh ảnh trong Flow báo lỗi: {status}"

            if not img_b64:
                return False, f"Hết thời gian chờ ({timeout_sec}s) sinh ảnh từ Google Flow."

            # 6. Ghi ảnh ra đĩa
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            img_bytes = base64.b64decode(img_b64)
            out_file.write_bytes(img_bytes)

            return True, str(out_file)

        except Exception as e:
            return False, f"Lỗi quy trình sinh ảnh Google Flow: {str(e)}"

    def close(self):
        """Đóng kết nối CDP (giữ nguyên tab Chrome)."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.browser = None
        self.playwright = None
        self.page = None
        self.tool_frame = None


_global_controller = None

def get_flow_controller() -> FlowBrowserController:
    """Singleton lấy instance bộ điều khiển Flow."""
    global _global_controller
    if _global_controller is None:
        _global_controller = FlowBrowserController()
    return _global_controller
