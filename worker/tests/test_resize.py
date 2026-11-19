import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from smartgate.run_gate import fit_to_screen, limit_width   # noqa: E402


def blank(w, h):
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_4k_video_is_shrunk_for_processing():
    assert limit_width(blank(3840, 2160), 1280).shape[:2] == (720, 1280)


def test_small_video_and_zero_keep_original_size():
    assert limit_width(blank(1280, 720), 1920).shape[:2] == (720, 1280)
    assert limit_width(blank(3840, 2160), 0).shape[:2] == (2160, 3840)


def test_preview_fits_screen_and_reports_scale():
    view, scale = fit_to_screen(blank(1920, 1080))
    assert view.shape[:2] == (720, 1280) and scale == pytest.approx(2 / 3)
    view, scale = fit_to_screen(blank(1080, 1920))          # portrait phone video
    assert view.shape[0] <= 720 and scale == pytest.approx(0.375)
    assert fit_to_screen(blank(800, 600))[1] == 1.0
