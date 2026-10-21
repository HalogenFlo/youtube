# Chức năng: Kiểm thử tự động bộ thẩm định chất lượng hình ảnh và nâng cấp độ phân giải Google Flow.
# Mục đích: Đảm bảo loại bỏ 100% ảnh placeholder mờ xám (skeleton/shimmer) và chỉ dùng ảnh hoạt hình 2D sắc nét, đúng chuẩn.

import os
import io
import numpy as np
from PIL import Image
import pytest
from src.flow_browser_service import is_valid_production_image, upgrade_to_high_res_flow_url


def test_upgrade_to_high_res_flow_url():
    url_512 = "https://flow.google.com/asb/abcd1234efgh=s512-rw"
    high_res = upgrade_to_high_res_flow_url(url_512)
    assert high_res == "https://flow.google.com/asb/abcd1234efgh=s2048-rw"

    url_normal = "https://flow.google.com/asb/abcd1234efgh"
    assert upgrade_to_high_res_flow_url(url_normal) == url_normal


def test_is_valid_production_image_rejects_gray_placeholder(tmp_path):
    # Tạo một ảnh xám mờ giống hệt placeholder của Google Flow (1000x1000, R == G == B)
    gray_arr = np.full((500, 500, 3), 125, dtype=np.uint8)
    # Thêm nhiễu nhẹ
    noise = np.random.randint(-10, 10, (500, 500), dtype=np.int16)
    for c in range(3):
        gray_arr[:, :, c] = np.clip(125 + noise, 0, 255).astype(np.uint8)

    gray_file = tmp_path / "gray_placeholder.png"
    Image.fromarray(gray_arr).save(gray_file)

    # Phải bị loại bỏ
    assert is_valid_production_image(str(gray_file)) is False


def test_is_valid_production_image_accepts_colorful_2d_cartoon(tmp_path):
    # Tạo một ảnh hoạt hình 2D nhiều màu sắc (trời xanh, cỏ xanh lá, stickman áo xanh, lửa đỏ)
    arr = np.zeros((512, 286, 3), dtype=np.uint8)
    arr[:200, :, :] = [135, 206, 235]   # Trời xanh
    arr[200:350, :, :] = [34, 139, 34]   # Cỏ xanh lá
    arr[350:, :, :] = [255, 69, 0]       # Lửa cam/đỏ

    cartoon_file = tmp_path / "colorful_cartoon.png"
    Image.fromarray(arr).save(cartoon_file)

    # Phải được chấp nhận
    assert is_valid_production_image(str(cartoon_file)) is True


def test_is_valid_production_image_against_actual_job_files():
    job_dir = r"temp\autonomous_factory\job_7edd6e9670"
    if os.path.exists(job_dir):
        bad_img = os.path.join(job_dir, "scene_flow_1.png")
        if os.path.exists(bad_img):
            assert is_valid_production_image(bad_img) is False, "Ảnh xám mờ scene_flow_1.png phải bị loại bỏ"

        good_img = os.path.join(job_dir, "scene_flow_2.png")
        if os.path.exists(good_img):
            assert is_valid_production_image(good_img) is True, "Ảnh hoạt hình thật scene_flow_2.png phải được chấp nhận"
