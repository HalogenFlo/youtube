# Chức năng: Package initialization cho module src.
# Tự động vá tương thích môi trường PyTorch / diffusers trên Windows.

try:
    import torch
    # Khắc phục triệt để lỗi PyTorch 2.6+ trên Windows thiếu thuộc tính XPU cho diffusers
    if not hasattr(torch, "xpu") or not hasattr(getattr(torch, "xpu", None), "device_count"):
        class _DummyXPU:
            empty_cache = staticmethod(lambda: None)
            device_count = staticmethod(lambda: 0)
            manual_seed = staticmethod(lambda *args, **kwargs: None)
            is_available = staticmethod(lambda: False)
            reset_peak_memory_stats = staticmethod(lambda *args, **kwargs: None)
            reset_max_memory_allocated = staticmethod(lambda *args, **kwargs: None)
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        torch.xpu = _DummyXPU()
except Exception:
    pass

try:
    # Vá lỗi Moviepy decorator use_clip_fps_by_default làm mất fps (None) trên Python 3.12
    import moviepy.video.VideoClip as _mpy_vc
    _orig_ffmpeg_write = _mpy_vc.ffmpeg_write_video
    def _safe_ffmpeg_write_video(clip, filename, fps, codec="libx264", **kw):
        actual_fps = fps or getattr(clip, "fps", None) or 30
        return _orig_ffmpeg_write(clip, filename, actual_fps, codec=codec, **kw)
    _mpy_vc.ffmpeg_write_video = _safe_ffmpeg_write_video
except Exception:
    pass

try:
    # Vá lỗi Pillow 10+ loại bỏ Image.ANTIALIAS làm sập moviepy.video.fx.resize
    import PIL.Image
    if not hasattr(PIL.Image, "ANTIALIAS"):
        PIL.Image.ANTIALIAS = getattr(PIL.Image.Resampling, "LANCZOS", getattr(PIL.Image, "LANCZOS", None))
except Exception:
    pass


