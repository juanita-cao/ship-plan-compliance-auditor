"""Stage-level unit tests for E1b pipeline helper functions.

Tests each stage in isolation using synthetic numpy images and hand-crafted
_BlobCandidate fixtures — no real ship images, no API calls.

  Stage                           | Function
  ─────────────────────────────── | ────────────────────────────
  E1b-1 Transform (mask)          | _e1b_build_red_mask
  E1b-2 Detect  (blobs)           | _e1b_find_blobs_in_window
  E1b-3 Transform (filter)        | _e1b_filter_candidates
  E1b-4 Transform (display_bbox)  | _e1b_compute_display_bbox

Integration tests (public API) remain in test_e2.py.
"""

from __future__ import annotations

import numpy as np

from src.backend.e_nodes import (
    _MIN_BLOB_AREA_PX,
    _BlobCandidate,
    _e1b_build_red_mask,
    _e1b_compute_display_bbox,
    _e1b_filter_candidates,
    _e1b_find_blobs_in_window,
)

# _e1b_filter_candidates now takes max_dist_px as an explicit argument (no longer a
# fixed module constant — see e_nodes.py _MAX_DIST_FRAC_OF_WINDOW). Tests pick a fixed
# value here purely to exercise the gate; production code derives it from window size.
_TEST_MAX_DIST_PX = 35.0

# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _blob(
    area: int = 50,
    abs_cx: float = 100.0,
    abs_cy: float = 100.0,
    dist: float = 10.0,
    bbox_w: int = 10,
    bbox_h: int = 10,
    bbox_abs_x1: int = 0,
    bbox_abs_y1: int = 0,
) -> _BlobCandidate:
    return _BlobCandidate(
        area=area, abs_cx=abs_cx, abs_cy=abs_cy,
        dist=dist, bbox_w=bbox_w, bbox_h=bbox_h,
        bbox_abs_x1=bbox_abs_x1, bbox_abs_y1=bbox_abs_y1,
    )


def _gray_with_red(
    w: int = 200,
    h: int = 200,
    rects: list[tuple[int, int, int, int]] | None = None,
) -> np.ndarray:
    """Return a BGR ndarray (gray background) with red rectangles (x,y,rw,rh)."""
    img = np.full((h, w, 3), 180, dtype=np.uint8)
    for x, y, rw, rh in rects or []:
        img[y:y + rh, x:x + rw] = (0, 0, 200)  # BGR red
    return img


# ─── E1b-1: _e1b_build_red_mask ───────────────────────────────────────────────


def test_mask_pure_bgr_red_pixel_is_white():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[5, 5] = (0, 0, 200)
    mask = _e1b_build_red_mask(img)
    assert mask[5, 5] > 0


def test_mask_gray_image_is_all_zero():
    img = np.full((10, 10, 3), 150, dtype=np.uint8)
    assert _e1b_build_red_mask(img).sum() == 0


def test_mask_bgr_green_pixel_is_zero():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[5, 5] = (0, 200, 0)
    assert _e1b_build_red_mask(img)[5, 5] == 0


def test_mask_output_shape_matches_input():
    img = _gray_with_red(300, 200, [(50, 50, 20, 20)])
    mask = _e1b_build_red_mask(img)
    assert mask.shape == (200, 300)


# ─── E1b-2: _e1b_find_blobs_in_window ────────────────────────────────────────


def test_blobs_single_blob_in_window_detected():
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[90:110, 90:110] = 255  # 20×20 blob centered at (100,100)
    candidates, _ = _e1b_find_blobs_in_window(
        mask, cx_px=100, cy_px=100, hw_px=40, hh_px=40
    )
    assert len(candidates) == 1
    assert candidates[0].area == 20 * 20
    assert abs(candidates[0].abs_cx - 100) < 1.0
    assert abs(candidates[0].abs_cy - 100) < 1.0


def test_blobs_outside_window_not_returned():
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[10:20, 10:20] = 255  # blob far from center
    candidates, _ = _e1b_find_blobs_in_window(
        mask, cx_px=150, cy_px=150, hw_px=30, hh_px=30
    )
    assert candidates == []


def test_blobs_window_bounds_correct():
    mask = np.zeros((200, 200), dtype=np.uint8)
    _, (x1, y1, x2, y2) = _e1b_find_blobs_in_window(
        mask, cx_px=100, cy_px=100, hw_px=20, hh_px=30
    )
    assert x1 == 80 and x2 == 120
    assert y1 == 70 and y2 == 130


def test_blobs_window_clamped_at_image_edge():
    mask = np.zeros((200, 200), dtype=np.uint8)
    _, (x1, y1, x2, y2) = _e1b_find_blobs_in_window(
        mask, cx_px=5, cy_px=5, hw_px=30, hh_px=30
    )
    assert x1 == 0 and y1 == 0
    assert x2 <= 200 and y2 <= 200


def test_blobs_candidate_bbox_dimensions_populated():
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[90:100, 90:110] = 255  # 10 tall × 20 wide
    candidates, _ = _e1b_find_blobs_in_window(
        mask, cx_px=100, cy_px=95, hw_px=40, hh_px=40
    )
    assert len(candidates) == 1
    assert candidates[0].bbox_w == 20
    assert candidates[0].bbox_h == 10


def test_blobs_candidate_bbox_abs_coords_populated():
    mask = np.zeros((200, 200), dtype=np.uint8)
    # blob at absolute (80,60)→(100,80)
    mask[60:80, 80:100] = 255
    candidates, _ = _e1b_find_blobs_in_window(
        mask, cx_px=90, cy_px=70, hw_px=40, hh_px=40
    )
    assert len(candidates) == 1
    c = candidates[0]
    # bbox_abs_x1/y1 must be the absolute image coords of the blob's top-left
    assert c.bbox_abs_x1 == 80
    assert c.bbox_abs_y1 == 60


# ─── E1b-3: _e1b_filter_candidates ───────────────────────────────────────────


def test_filter_valid_candidate_passes():
    c = _blob(area=50, dist=10.0, bbox_w=10, bbox_h=10)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == [c]


def test_filter_area_below_min_rejected():
    c = _blob(area=_MIN_BLOB_AREA_PX - 1, dist=5.0)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == []


def test_filter_area_above_max_rejected():
    c = _blob(area=600, dist=5.0)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == []


def test_filter_dist_above_max_rejected():
    c = _blob(area=50, dist=_TEST_MAX_DIST_PX + 0.1)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == []


def test_filter_dist_exactly_at_max_passes():
    c = _blob(area=50, dist=_TEST_MAX_DIST_PX)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == [c]


def test_filter_elongated_blob_rejected():
    # aspect ratio = 50/5 = 10 > _MAX_ASPECT_RATIO (4.0)
    c = _blob(area=50, dist=5.0, bbox_w=50, bbox_h=5)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == []


def test_filter_near_square_blob_passes():
    # aspect ratio = 15/12 ≈ 1.25 < _MAX_ASPECT_RATIO
    c = _blob(area=50, dist=5.0, bbox_w=15, bbox_h=12)
    assert _e1b_filter_candidates([c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX) == [c]


def test_filter_mixed_list_only_valid_returned():
    good    = _blob(area=50,               dist=5.0,                    bbox_w=10, bbox_h=10)
    too_far = _blob(area=50,               dist=_TEST_MAX_DIST_PX + 1,  bbox_w=10, bbox_h=10)
    thin    = _blob(area=50,               dist=5.0,                    bbox_w=80, bbox_h=4)
    tiny    = _blob(area=_MIN_BLOB_AREA_PX - 1, dist=5.0)
    assert _e1b_filter_candidates(
        [good, too_far, thin, tiny], max_area=500, max_dist_px=_TEST_MAX_DIST_PX
    ) == [good]


# ─── E1b-3 ownership gate: other_centers_px (bug fix) ─────────────────────────


def test_filter_owned_by_me_when_no_other_centers_given():
    c = _blob(area=50, dist=10.0, abs_cx=100.0, abs_cy=100.0)
    assert _e1b_filter_candidates(
        [c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX, other_centers_px=[]
    ) == [c]


def test_filter_candidate_closer_to_other_instance_rejected():
    # blob at (100,100); my dist=10.0; other instance center at (102,100) → dist≈2.0 < 10.0
    c = _blob(area=50, dist=10.0, abs_cx=100.0, abs_cy=100.0)
    result = _e1b_filter_candidates(
        [c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX,
        other_centers_px=[(102.0, 100.0)],
    )
    assert result == []


def test_filter_candidate_closer_to_me_than_other_kept():
    # blob at (100,100); my dist=5.0; other instance center far away at (500,500)
    c = _blob(area=50, dist=5.0, abs_cx=100.0, abs_cy=100.0)
    result = _e1b_filter_candidates(
        [c], max_area=500, max_dist_px=_TEST_MAX_DIST_PX,
        other_centers_px=[(500.0, 500.0)],
    )
    assert result == [c]


def test_filter_two_nearby_instances_each_keep_only_own_blob():
    # Two blobs at x=90 and x=110; two instances at x=90 and x=110 (same y).
    # Each instance's own blob is dist=0 from itself; the other blob is dist=20.
    blob_a = _blob(area=50, dist=0.0, abs_cx=90.0, abs_cy=100.0)
    blob_b = _blob(area=50, dist=20.0, abs_cx=110.0, abs_cy=100.0)
    # From instance A's perspective (own center=90,100; other center=110,100):
    result_a = _e1b_filter_candidates(
        [blob_a, blob_b], max_area=500, max_dist_px=_TEST_MAX_DIST_PX,
        other_centers_px=[(110.0, 100.0)],
    )
    assert result_a == [blob_a]  # blob_b is closer to the other instance → rejected


# ─── E1b-4: _e1b_compute_display_bbox ────────────────────────────────────────


def test_display_bbox_empty_returns_none():
    assert _e1b_compute_display_bbox([], w_orig=200, h_orig=200) is None


def test_display_bbox_single_blob_covers_blob_region():
    # blob at absolute (80,60)→(90,70), 10×10
    c = _blob(bbox_w=10, bbox_h=10, bbox_abs_x1=80, bbox_abs_y1=60)
    result = _e1b_compute_display_bbox([c], w_orig=200, h_orig=200)
    assert result is not None
    x1, y1, x2, y2 = result
    # With padding the bbox should expand beyond the blob
    assert x1 <= 80 / 200
    assert y1 <= 60 / 200
    assert x2 >= 90 / 200
    assert y2 >= 70 / 200


def test_display_bbox_padding_applied():
    # blob exactly 10×10 at (100,100)→(110,110) in a 200×200 image
    c = _blob(bbox_w=10, bbox_h=10, bbox_abs_x1=100, bbox_abs_y1=100)
    result = _e1b_compute_display_bbox([c], w_orig=200, h_orig=200)
    assert result is not None
    x1, y1, x2, y2 = result
    # After padding, x1 < 100/200 and x2 > 110/200
    assert x1 < 100 / 200
    assert x2 > 110 / 200
    assert y1 < 100 / 200
    assert y2 > 110 / 200


def test_display_bbox_two_blobs_union_spans_both():
    # blob A at (10,10)→(20,20); blob B at (80,80)→(90,90)
    a = _blob(bbox_w=10, bbox_h=10, bbox_abs_x1=10, bbox_abs_y1=10)
    b = _blob(bbox_w=10, bbox_h=10, bbox_abs_x1=80, bbox_abs_y1=80)
    result = _e1b_compute_display_bbox([a, b], w_orig=200, h_orig=200)
    assert result is not None
    x1, y1, x2, y2 = result
    # x1 anchored near blob A's left edge (with padding might be 0)
    assert x1 <= 10 / 200
    # x2 must reach past blob B's right edge
    assert x2 >= 90 / 200
    assert y2 >= 90 / 200


def test_display_bbox_clamped_at_image_bounds():
    # blob at top-left corner (0,0)→(5,5)
    c = _blob(bbox_w=5, bbox_h=5, bbox_abs_x1=0, bbox_abs_y1=0)
    result = _e1b_compute_display_bbox([c], w_orig=200, h_orig=200)
    assert result is not None
    x1, y1, x2, y2 = result
    # Padding cannot push x1/y1 below 0 (normalized = 0.0)
    assert x1 >= 0.0
    assert y1 >= 0.0

    # blob at bottom-right corner
    c2 = _blob(bbox_w=5, bbox_h=5, bbox_abs_x1=195, bbox_abs_y1=195)
    result2 = _e1b_compute_display_bbox([c2], w_orig=200, h_orig=200)
    assert result2 is not None
    assert result2[2] <= 1.0
    assert result2[3] <= 1.0


def test_display_bbox_output_is_4_floats_normalized():
    c = _blob(bbox_w=20, bbox_h=20, bbox_abs_x1=90, bbox_abs_y1=90)
    result = _e1b_compute_display_bbox([c], w_orig=200, h_orig=200)
    assert result is not None
    assert len(result) == 4
    x1, y1, x2, y2 = result
    assert all(isinstance(v, float) for v in result)
    assert 0.0 <= x1 < x2 <= 1.0
    assert 0.0 <= y1 < y2 <= 1.0


def test_display_bbox_values_rounded_to_4dp():
    c = _blob(bbox_w=13, bbox_h=17, bbox_abs_x1=33, bbox_abs_y1=47)
    result = _e1b_compute_display_bbox([c], w_orig=300, h_orig=400)
    assert result is not None
    for v in result:
        assert len(str(v).split(".")[-1]) <= 4
