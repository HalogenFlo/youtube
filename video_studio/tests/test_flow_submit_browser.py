# Chức năng: Kiểm chứng nút gửi trong trình duyệt local, không kết nối Flow.
# Lý do: Tránh kết luận chỉ từ mock khi nút tạo bộ sưu tập nằm cùng trang.
from playwright.sync_api import sync_playwright
from src.flow_browser_service import submit_flow_prompt


def test_real_browser_clicks_submit_not_collection():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        try:
            page=browser.new_page()
            page.set_content('''
                <button aria-label="Tạo bộ sưu tập" onclick="window.collections++">Tạo</button>
                <form onsubmit="event.preventDefault();window.submissions++;document.querySelector('[contenteditable]').textContent=''">
                <div role="textbox" contenteditable="true"></div>
                <button type="submit" aria-label="Bắt đầu tạo" class="generate-icon-button">→</button>
                </form><script>window.collections=0;window.submissions=0</script>
            ''')
            editor=page.get_by_role('textbox')
            editor.fill('Local test prompt — not sent to any service')
            ok,message=submit_flow_prompt(page,editor)
            assert ok,message
            assert page.evaluate('window.submissions')==1
            assert page.evaluate('window.collections')==0
        finally:
            browser.close()
