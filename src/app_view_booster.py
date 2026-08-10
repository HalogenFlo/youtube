# Chức năng: Giao diện Web UI Streamlit cho Tool Cày View YouTube & Shorts Kênh Đa Luồng.
# Lý do tạo: Cung cấp giao diện trực quan để người dùng dễ dàng quét kênh, cấu hình thông số và theo dõi tiến độ thời gian thực.
# Trích dẫn: Tích hợp với Streamlit framework và BoosterManager.

import os
import sys
import time
import streamlit as st

# Đảm bảo đường dẫn gốc trong sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.channel_scraper import extract_channel_videos
from src.view_booster_manager import BoosterManager
from src.resource_guard import get_system_stats, kill_orphan_chrome_processes
from src.profile_manager import cleanup_all_profiles

st.set_page_config(
    page_title="YouTube View & Shorts Booster",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Khởi tạo session state
if "manager" not in st.session_state:
    st.session_state.manager = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "scraped_videos" not in st.session_state:
    st.session_state.scraped_videos = []
if "is_running" not in st.session_state:
    st.session_state.is_running = False


def add_log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {msg}")
    if len(st.session_state.logs) > 300:
        st.session_state.logs.pop(0)


# --- HEADER & DISCLAIMER ---
st.title("🚀 YouTube View & Shorts Booster Pro")
st.caption("Hệ thống cày view và lướt Shorts đa luồng với cơ chế Anti-Detect (nodriver) & mô phỏng hành vi người dùng thật.")

with st.expander("⚠️ Cảnh báo an toàn & Điều khoản dịch vụ (Disclaimer)", expanded=False):
    st.warning(
        "**Lưu ý quan trọng:**\n"
        "- Việc sử dụng công cụ tự động xem có thể vi phạm Điều khoản Dịch vụ của YouTube.\n"
        "- Để view được tính hiệu quả và không bị lọc, bạn nên sử dụng **Residential/Mobile Proxies** chất lượng cao và đặt thời gian xem ngẫu nhiên hợp lý.\n"
        "- Tool mặc định chạy ở chế độ ẩn danh không đăng nhập để đảm bảo an toàn cho tài khoản cá nhân của bạn."
    )

# --- SIDEBAR CẤU HÌNH HỆ THỐNG ---
st.sidebar.header("⚙️ Cấu Hình Chung")

threads = st.sidebar.slider("Số Luồng Chạy Song Song", min_value=1, max_value=10, value=2, help="Mỗi luồng sẽ mở 1 phiên Chrome riêng biệt.")
headless = st.sidebar.checkbox("Chạy Ẩn Danh (Headless Mode)", value=True, help="Không mở cửa sổ trình duyệt để tiết kiệm 80% tài nguyên CPU/RAM.")
loop_mode = st.sidebar.checkbox("Lặp Vô Tận (24/7)", value=True, help="Tự động lặp lại danh sách sau khi xem hết.")

st.sidebar.subheader("⏱️ Thời Gian Xem (Giây)")
col_dur1, col_dur2 = st.sidebar.columns(2)
with col_dur1:
    watch_min = st.number_input("Tối Thiểu (s)", min_value=5, max_value=300, value=8, help="Khuyến nghị 8s cho video 10-11s")
with col_dur2:
    watch_max = st.number_input("Tối Đa (s)", min_value=10, max_value=600, value=20, help="Khuyến nghị 20s để video lặp lại tăng Retention")

replay_prob = st.sidebar.slider("Tỉ Lệ Xem Lại (Replay %)", min_value=0, max_value=100, value=30, help="Xác suất xem lặp lại Shorts để tăng Retention Rate.") / 100.0
rate_limit = st.sidebar.number_input("Giới Hạn Tối Đa (Views/Phút)", min_value=1, max_value=60, value=20)

st.sidebar.subheader("🌐 Cấu Hình Proxy")
proxy_text = st.sidebar.text_area(
    "Danh Sách Proxies (Mỗi dòng 1 proxy)",
    placeholder="ip:port\nuser:pass@ip:port\nsocks5://ip:port",
    help="Hỗ trợ HTTP và SOCKS5. Để trống nếu muốn chạy trực tiếp bằng IP máy."
)
proxy_list = [p.strip() for p in proxy_text.split("\n") if p.strip()]

# --- RESOURCE MONITOR SIDEBAR ---
sys_stats = get_system_stats()
st.sidebar.subheader("📊 Tài Nguyên Máy")
st.sidebar.progress(sys_stats["ram_percent"] / 100.0, text=f"RAM: {sys_stats['ram_used_gb']}/{sys_stats['ram_total_gb']} GB ({sys_stats['ram_percent']}%)")
st.sidebar.caption(f"Tiến trình Chrome đang chạy: {sys_stats['chrome_processes']}")

if st.sidebar.button("🧹 Dọn Dẹp Chrome Zombie"):
    killed = kill_orphan_chrome_processes()
    st.sidebar.success(f"Đã dọn {killed} tiến trình Chrome thừa.")


# --- MAIN TABS ---
tab1, tab2, tab3 = st.tabs(["🎬 Cày Toàn Bộ Shorts Kênh", "📹 Cày Video Thường / Direct URL", "📋 Nhật Ký & Thống Kê"])

# ==================== TAB 1: SHORTS CỦA KÊNH ====================
with tab1:
    st.subheader("1. Quét & Lấy Danh Sách Shorts Từ Kênh")
    col_inp, col_btn = st.columns([4, 1])
    with col_inp:
        channel_url = st.text_input(
            "Nhập link kênh YouTube:",
            value="https://www.youtube.com/@Remioo-br",
            placeholder="https://www.youtube.com/@TenKenh"
        )
    with col_btn:
        st.write("")
        st.write("")
        if st.button("🔍 Quét Shorts", use_container_width=True):
            if not channel_url:
                st.error("Vui lòng nhập link kênh!")
            else:
                with st.spinner("Đang quét toàn bộ danh sách Shorts từ kênh..."):
                    success, videos, err = extract_channel_videos(channel_url, mode="shorts", max_results=5000, force_refresh=True)
                    if success and videos:
                        st.session_state.scraped_videos = videos
                        st.success(f"✅ Đã quét thành công {len(videos)} video Shorts!")
                    else:
                        st.error(f"❌ Lỗi quét kênh: {err}")

    # Hiển thị danh sách video đã quét
    if st.session_state.scraped_videos:
        st.write(f"📋 **Danh sách {len(st.session_state.scraped_videos)} Shorts sẵn sàng:**")
        preview_data = [
            {"STT": i + 1, "Tiêu đề": v["title"], "Thời lượng": f"{int(v['duration'])}s" if v['duration'] else "Shorts", "URL": v["url"]}
            for i, v in enumerate(st.session_state.scraped_videos[:15])
        ]
        st.dataframe(preview_data, use_container_width=True)
        if len(st.session_state.scraped_videos) > 15:
            st.caption(f"... và {len(st.session_state.scraped_videos) - 15} video Shorts khác trong danh sách.")

    st.divider()
    st.subheader("2. Điều Khiển Tiến Trình Cày View")

    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("▶️ BẮT ĐẦU CÀY SHORTS", type="primary", use_container_width=True, disabled=st.session_state.is_running):
            if not st.session_state.scraped_videos:
                st.error("Chưa có danh sách video Shorts. Hãy quét kênh trước!")
            else:
                st.session_state.is_running = True
                add_log("Bắt đầu khởi chạy hệ thống cày Shorts...")
                
                manager = BoosterManager(
                    channels=[channel_url],
                    videos=st.session_state.scraped_videos,
                    proxies=proxy_list,
                    threads=threads,
                    watch_duration_min=watch_min,
                    watch_duration_max=watch_max,
                    replay_prob=replay_prob,
                    rate_limit_views_per_min=rate_limit,
                    headless=headless,
                    loop=loop_mode,
                    on_log=add_log
                )
                st.session_state.manager = manager
                manager.start()
                st.rerun()

    with col_stop:
        if st.button("⏹️ DỪNG TIẾN TRÌNH", type="secondary", use_container_width=True, disabled=not st.session_state.is_running):
            if st.session_state.manager:
                st.session_state.manager.stop()
                st.session_state.manager = None
            st.session_state.is_running = False
            add_log("Đã yêu cầu dừng toàn bộ tiến trình.")
            st.rerun()

    st.divider()
    if st.session_state.is_running and st.session_state.manager:
        st.success("🟢 **HỆ THỐNG ĐANG HOẠT ĐỘNG CÀY VIEW TỰ ĐỘNG**")
        st.info("💡 **Ghi chú**: Nếu bạn đang bật *Chạy Ẩn Danh (Headless)* ở Sidebar bên trái, trình duyệt đang chạy ngầm dưới nền. Để nhìn thấy tận mắt cửa sổ Chrome tự phát, hãy dừng lại và **bỏ tích chọn Chạy Ẩn Danh**.")
        
        col_st1, col_st2, col_st3 = st.columns(3)
        col_st1.metric("Tổng Lượt Xem", f"{st.session_state.manager.stats['total_views']} 👁️")
        col_st2.metric("Số Luồng Đang Chạy", f"{len(st.session_state.manager.workers)} / {threads} Luồng")
        col_st3.metric("RAM Hệ Thống", f"{st.session_state.manager.stats.get('ram_percent', 0)}%")
        
        st.write("📜 **Nhật ký hoạt động gần nhất:**")
        recent_logs = "\n".join(st.session_state.logs[-8:]) if st.session_state.logs else "Đang kết nối tới các luồng Chrome..."
        st.code(recent_logs, language="bash")
        
        # Tự động refresh sau vài giây để cập nhật số liệu
        time.sleep(3)
        st.rerun()


# ==================== TAB 2: VIDEO THƯỜNG ====================
with tab2:
    st.subheader("Cày View Theo Link Video Đơn / Nhiều Link")
    video_links = st.text_area(
        "Nhập danh sách link video (mỗi dòng 1 link):",
        placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/shorts/..."
    )
    if st.button("▶️ Bắt Đầu Cày Danh Sách Video Này", disabled=st.session_state.is_running):
        links = [l.strip() for l in video_links.split("\n") if l.strip()]
        if not links:
            st.error("Vui lòng nhập ít nhất 1 link video!")
        else:
            custom_videos = [{"id": l, "title": f"Custom Video {i+1}", "url": l, "duration": 30} for i, l in enumerate(links)]
            st.session_state.is_running = True
            manager = BoosterManager(
                channels=[],
                videos=custom_videos,
                proxies=proxy_list,
                threads=threads,
                watch_duration_min=watch_min,
                watch_duration_max=watch_max,
                replay_prob=replay_prob,
                rate_limit_views_per_min=rate_limit,
                headless=headless,
                loop=loop_mode,
                on_log=add_log
            )
            st.session_state.manager = manager
            manager.start()
            st.rerun()


# ==================== TAB 3: NHẬT KÝ & THỐNG KÊ ====================
with tab3:
    st.subheader("📊 Thống Kê Tiến Độ Thời Gian Thực")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    total_views = st.session_state.manager.stats["total_views"] if st.session_state.manager else 0
    failed_views = st.session_state.manager.stats["failed_views"] if st.session_state.manager else 0
    active_workers = len(st.session_state.manager.workers) if st.session_state.manager else 0
    
    col_m1.metric("Tổng Lượt Xem Thành Công", f"{total_views} 👁️")
    col_m2.metric("Lượt Xem Lỗi", f"{failed_views} ⚠️")
    col_m3.metric("Số Luồng Đang Chạy", f"{active_workers} / {threads}")
    col_m4.metric("Trạng Thái", "🟢 ĐANG CHẠY" if st.session_state.is_running else "⚪ ĐANG DỪNG")

    st.divider()
    st.subheader("📜 Console Logs Trực Tiếp")
    log_content = "\n".join(st.session_state.logs[-50:]) if st.session_state.logs else "Chưa có log hoạt động."
    st.text_area("Live Log Output", value=log_content, height=350)
    
    col_log_btn1, col_log_btn2 = st.columns(2)
    with col_log_btn1:
        if st.button("🔄 Làm mới hiển thị"):
            st.rerun()
    with col_log_btn2:
        if st.button("🗑️ Xóa sạch log"):
            st.session_state.logs = []
            st.rerun()
