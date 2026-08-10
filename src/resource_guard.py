# Chức năng: Giám sát tài nguyên máy tính (RAM, CPU), ngăn chặn OOM và dọn dẹp các tiến trình Chrome mồ côi (zombie).
# Lý do tạo: Bảo vệ máy tính khi chạy tool đa luồng hoặc treo máy 24/7.
# Trích dẫn: Sử dụng thư viện psutil để quản lý tiến trình và tài nguyên hệ thống.

import os
import psutil
from typing import Dict, Any, List


def get_memory_usage_pct() -> float:
    """Trả về phần trăm RAM hiện tại đang được sử dụng của hệ thống."""
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return 50.0


def get_cpu_usage_pct() -> float:
    """Trả về phần trăm CPU đang dùng."""
    try:
        return psutil.cpu_percent(interval=None)
    except Exception:
        return 0.0


def get_chrome_process_count() -> int:
    """Đếm số tiến trình Chrome đang chạy trên máy."""
    count = 0
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name and 'chrome' in name.lower():
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return count


def can_spawn_worker(max_ram_pct: float = 80.0, max_chrome_procs: int = 40) -> bool:
    """
    Kiểm tra xem hệ thống có đủ tài nguyên để khởi chạy thêm 1 worker hay không.
    """
    current_ram = get_memory_usage_pct()
    if current_ram >= max_ram_pct:
        return False
    
    current_procs = get_chrome_process_count()
    if current_procs >= max_chrome_procs:
        return False
        
    return True


def kill_orphan_chrome_processes(keywords: List[str] = None) -> int:
    """
    Tìm và tắt các tiến trình Chrome zombie hoặc mồ côi được khởi tạo bởi automation.
    """
    if keywords is None:
        keywords = ["--test-type", "--remote-debugging-port", "temp/profiles", "nodriver"]

    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            p_name = proc.info.get('name') or ""
            if 'chrome' in p_name.lower():
                cmdline = " ".join(proc.info.get('cmdline') or [])
                # Nếu tiến trình chứa các cờ automation hoặc profile trong temp
                if any(kw in cmdline for kw in keywords):
                    proc.kill()
                    killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return killed_count


def get_system_stats() -> Dict[str, Any]:
    """Lấy tổng quan thông số tài nguyên hệ thống."""
    vmem = psutil.virtual_memory()
    return {
        "ram_percent": vmem.percent,
        "ram_used_gb": round((vmem.total - vmem.available) / (1024 ** 3), 2),
        "ram_total_gb": round(vmem.total / (1024 ** 3), 2),
        "cpu_percent": get_cpu_usage_pct(),
        "chrome_processes": get_chrome_process_count()
    }
