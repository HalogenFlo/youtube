# Chức năng: Kiểm thử tự động cơ chế chuẩn hóa RGB 3 channels cho mọi định dạng ảnh (Grayscale Mode L, RGBA, WebP).
# Mục đích: Ngăn ngừa lỗi hồi quy NumPy broadcasting: could not broadcast input array from shape (1920,1080) into shape (1920,1080,3).

import os
import tempfile
import numpy as np
import pytest
from PIL import Image

from src.flow_browser_service import _ensure_rgb_image
from src.visual_beats import apply_visual_beat_motion
from src.video_compiler import apply_ken_burns


def test_ensure_rgb_image_converts_grayscale():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tmp_path = tf.name

    try:
        # Tạo ảnh Mode L (Grayscale 1 channel)
        gray_img = Image.new("L", (200, 200), color=128)
        gray_img.save(tmp_path, "PNG")

        with Image.open(tmp_path) as im:
            assert im.mode == "L"

        _ensure_rgb_image(tmp_path)

        with Image.open(tmp_path) as im:
            assert im.mode == "RGB"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_ensure_rgb_image_converts_rgba():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tmp_path = tf.name

    try:
        # Tạo ảnh Mode RGBA (4 channels)
        rgba_img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
        rgba_img.save(tmp_path, "PNG")

        with Image.open(tmp_path) as im:
            assert im.mode == "RGBA"

        _ensure_rgb_image(tmp_path)

        with Image.open(tmp_path) as im:
            assert im.mode == "RGB"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_visual_beat_motion_handles_grayscale_image():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tmp_path = tf.name

    try:
        # Ảnh gốc là Grayscale Mode L
        gray_img = Image.new("L", (100, 100), color=200)
        gray_img.save(tmp_path, "PNG")

        clip = apply_visual_beat_motion(tmp_path, duration=2.0, orientation="vertical")
        assert clip is not None
        assert clip.duration == 2.0
        # Frame phải có shape 3 channels (H, W, 3)
        frame = clip.get_frame(0.5)
        assert len(frame.shape) == 3
        assert frame.shape[2] == 3
        assert frame.shape[0] == 1920
        assert frame.shape[1] == 1080
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_ken_burns_handles_grayscale_image():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tmp_path = tf.name

    try:
        # Ảnh gốc là Grayscale Mode L
        gray_img = Image.new("L", (100, 100), color=50)
        gray_img.save(tmp_path, "PNG")

        clip = apply_ken_burns(tmp_path, duration=2.0, orientation="vertical")
        assert clip is not None
        assert clip.duration == 2.0
        frame = clip.get_frame(0.5)
        assert len(frame.shape) == 3
        assert frame.shape[2] == 3
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
