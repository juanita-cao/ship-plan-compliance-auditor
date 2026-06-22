"""
L2 Node Unit Tests for e1b_refine_centers (E1b · OpenCV Evidence Localizer).

E1b contract (post-refactor):
- Keeps LLM center unchanged (center / center_refined are NOT modified).
- Computes display_bbox = union of all qualifying red blob bboxes near LLM center.
- Sets display_bbox_method = "union_red_blobs_near_llm_center" when blobs found.
- Falls back to display_bbox=None when no qualifying blobs are found.
- Does not affect counts, voting, or D1 accuracy.

Contract Test Scenario List: E1b-S01 through E1b-S13.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.backend.e_nodes import e1b_refine_centers
from src.backend.schemas import DetectedInstance, E3CountResult

# ─── Helpers ──────────────────────────────────────────────────────────────────

_CANONICAL_ZEROS = {
    "extinguisher_CO2_5kg": 0,
    "extinguisher_CO2_5kg_spare": 0,
    "extinguisher_dry_powder_6kg": 0,
    "extinguisher_dry_powder_6kg_spare": 0,
    "extinguisher_foam_9L": 0,
    "extinguisher_foam_9L_spare": 0,
}


def _make_result(instances: list[DetectedInstance], run_id: int = 0) -> E3CountResult:
    return E3CountResult(
        total_by_category=_CANONICAL_ZEROS.copy(),
        run_id=run_id,
        instances=instances,
        input_image_size=(200, 200),
    )


def _make_inst(
    iid: str = "i1",
    center: list[float] | None = None,
    category: str = "extinguisher_dry_powder_6kg",
) -> DetectedInstance:
    return DetectedInstance(
        instance_id=iid,
        category=category,
        nearby_text="P 6",
        location_desc="test location",
        center=center,
    )


def _save_gray_with_red_rect(
    path: Path,
    w: int = 200,
    h: int = 200,
    rects: list[tuple[int, int, int, int]] | None = None,
) -> None:
    """Save a gray image with zero or more red rectangles (x, y, rw, rh)."""
    img = np.full((h, w, 3), 180, dtype=np.uint8)
    for x, y, rw, rh in rects or []:
        img[y : y + rh, x : x + rw] = (0, 0, 200)  # red in BGR
    cv2.imwrite(str(path), img)


# ─── E1b-S01: red blob found → display_bbox set, LLM center unchanged ────────


def test_e1b_s01_red_blob_found_display_bbox_set(tmp_path):
    w, h = 200, 200
    image_path = tmp_path / "img.png"
    _save_gray_with_red_rect(image_path, w, h, [(80, 80, 20, 20)])

    # LLM center close to the blob
    inst = _make_inst(center=[0.45, 0.45])
    result = e1b_refine_centers(image_path, _make_result([inst]))

    refined = result.instances[0]
    # display_bbox should be set
    assert refined.display_bbox is not None
    assert refined.display_bbox_method == "union_red_blobs_near_llm_center"
    # LLM center must NOT be modified
    assert refined.center == [0.45, 0.45]
    assert refined.center_refined is False
    # bbox is a valid 4-element normalized list
    x1, y1, x2, y2 = refined.display_bbox
    assert 0.0 <= x1 < x2 <= 1.0
    assert 0.0 <= y1 < y2 <= 1.0


# ─── E1b-S02: no red blob → display_bbox=None, center unchanged ──────────────


def test_e1b_s02_no_red_blob_display_bbox_none(tmp_path):
    image_path = tmp_path / "gray.png"
    _save_gray_with_red_rect(image_path)  # no rects → all gray

    original_center = [0.5, 0.5]
    inst = _make_inst(center=original_center[:])

    result = e1b_refine_centers(image_path, _make_result([inst]))

    refined = result.instances[0]
    assert refined.display_bbox is None
    assert refined.display_bbox_method is None
    assert refined.center == original_center
    assert refined.center_refined is False


# ─── E1b-S03: center=None instance passes through unchanged ──────────────────


def test_e1b_s03_none_center_unchanged(tmp_path):
    image_path = tmp_path / "img.png"
    _save_gray_with_red_rect(image_path, rects=[(80, 80, 20, 20)])
    inst = _make_inst(center=None)

    result = e1b_refine_centers(image_path, _make_result([inst]))

    assert result.instances[0].center is None
    assert result.instances[0].display_bbox is None
    assert result.instances[0].center_refined is False


# ─── E1b-S04: center near edge → clamp, no raise ─────────────────────────────


def test_e1b_s04_center_near_edge_no_raise(tmp_path):
    image_path = tmp_path / "edge.png"
    _save_gray_with_red_rect(image_path, rects=[(0, 0, 10, 10)])

    inst = _make_inst(center=[0.01, 0.01])
    result = e1b_refine_centers(image_path, _make_result([inst]))

    assert len(result.instances) == 1  # no exception raised


# ─── E1b-S05: instances=[] → empty list returned ─────────────────────────────


def test_e1b_s05_empty_instances(tmp_path):
    image_path = tmp_path / "img.png"
    _save_gray_with_red_rect(image_path, rects=[(80, 80, 20, 20)])

    result = e1b_refine_centers(image_path, _make_result([]))
    assert result.instances == []


# ─── E1b-S06: mixed instances → standardization gives both a display_bbox ────


def test_e1b_s06_mixed_instances_both_get_display_bbox(tmp_path):
    w, h = 200, 200
    image_path = tmp_path / "mixed.png"
    _save_gray_with_red_rect(image_path, w, h, [(55, 55, 10, 10)])

    # inst_with_blob: LLM center close to the red blob at centroid (60,60)
    inst_with_blob = _make_inst(iid="i1", center=[0.30, 0.30])
    # inst_no_blob: LLM center far from the blob, no red nearby
    inst_no_blob = _make_inst(iid="i2", center=[0.70, 0.70])

    result = e1b_refine_centers(image_path, _make_result([inst_with_blob, inst_no_blob]))

    # After standardization both instances get a display_bbox (same size)
    assert result.instances[0].display_bbox is not None
    assert result.instances[1].display_bbox is not None
    # No-blob instance gets the method label indicating fallback
    assert result.instances[1].display_bbox_method == "standardized_no_blobs_found"
    # Both boxes must be the same size
    b0 = result.instances[0].display_bbox
    b1 = result.instances[1].display_bbox
    assert abs((b0[2] - b0[0]) - (b1[2] - b1[0])) < 0.001
    assert abs((b0[3] - b0[1]) - (b1[3] - b1[1])) < 0.001
    # LLM centers unchanged
    assert result.instances[0].center == [0.30, 0.30]
    assert result.instances[1].center == [0.70, 0.70]


# ─── E1b-S07: other E3CountResult fields unchanged ───────────────────────────


def test_e1b_s07_other_fields_unchanged(tmp_path):
    image_path = tmp_path / "img.png"
    _save_gray_with_red_rect(image_path, rects=[(80, 80, 20, 20)])
    original = _make_result([_make_inst(center=[0.5, 0.5])], run_id=3)
    original_totals = dict(original.total_by_category)

    result = e1b_refine_centers(image_path, original)

    assert result.run_id == 3
    assert result.total_by_category == original_totals
    assert result.input_image_size == (200, 200)


# ─── E1b-S08: blob beyond MAX_DIST_PX filtered; near blob defines the bbox ───


def test_e1b_s08_very_far_blob_filtered_near_blob_in_bbox(tmp_path):
    w, h = 400, 400
    # LLM center at (200px, 200px)
    # Near blob:  10×10=100px² at (195,195) → dist≈7px   < max_dist_px → passes
    # Far blob:  18×18=324px² at (100, 100) → dist≈141px > max_dist_px → filtered
    image_path = tmp_path / "multi.png"
    _save_gray_with_red_rect(
        image_path, w, h,
        [(195, 195, 10, 10), (100, 100, 18, 18)],
    )

    inst = _make_inst(center=[0.50, 0.50])
    result = e1b_refine_centers(image_path, _make_result([inst]))

    refined = result.instances[0]
    assert refined.display_bbox is not None
    x1, y1, x2, y2 = refined.display_bbox
    # Far blob at (100,100) must NOT drag the box all the way to top-left
    assert x1 > 0.35   # far blob corner is at x=100/400=0.25
    assert y1 > 0.35
    assert refined.center == [0.50, 0.50]


# ─── E1b-S09: tiny noise blob ignored → display_bbox=None ────────────────────


def test_e1b_s09_tiny_noise_blob_ignored(tmp_path):
    w, h = 200, 200
    image_path = tmp_path / "noise.png"
    # Noise blob: 2×2 = 4 px² — well below _MIN_BLOB_AREA_PX (10)
    _save_gray_with_red_rect(image_path, w, h, [(100, 100, 2, 2)])

    inst = _make_inst(center=[0.50, 0.50])
    result = e1b_refine_centers(image_path, _make_result([inst]))

    assert result.instances[0].display_bbox is None
    assert result.instances[0].center == [0.50, 0.50]


# ─── E1b-S10: center out of [0,1] range → soft fallback ─────────────────────


def test_e1b_s10_out_of_range_center_soft_fallback(tmp_path):
    image_path = tmp_path / "img.png"
    _save_gray_with_red_rect(image_path, rects=[(80, 80, 20, 20)])

    inst = DetectedInstance.model_construct(
        instance_id="i1",
        category="extinguisher_dry_powder_6kg",
        nearby_text="P 6",
        location_desc="test location",
        center=[1.5, 0.5],
        center_refined=False,
    )
    result = e1b_refine_centers(image_path, _make_result([inst]))

    assert result.instances[0].center == [1.5, 0.5]
    assert result.instances[0].display_bbox is None


# ─── E1b-S11: unreadable image → returns original result without raise ───────


def test_e1b_s11_unreadable_image_returns_original(tmp_path):
    bad_path = tmp_path / "nonexistent.png"
    inst = _make_inst(center=[0.5, 0.5])
    original = _make_result([inst])

    result = e1b_refine_centers(bad_path, original)

    assert result.instances[0].center == [0.5, 0.5]
    assert result.instances[0].display_bbox is None
    assert result.run_id == original.run_id


# ─── E1b-S12: two blobs both within MAX_DIST_PX → union covers both ──────────


def test_e1b_s12_two_blobs_within_max_dist_union_covers_both(tmp_path):
    w, h = 400, 400
    # LLM center at (200px, 200px). max_dist_px is now derived from the search window
    # (_MAX_DIST_FRAC_OF_WINDOW * min(hw_px, hh_px)) rather than a fixed constant; on
    # this 400x400 canvas that works out to ≈16.7px, so both blobs are placed well
    # inside that radius.
    # Blob A: 10×10 at (188,195) → dist≈7px  → passes
    # Blob B: 10×10 at (205,195) → dist≈10px → passes
    # Union of A+B should span from ~188 to ~215 in x
    image_path = tmp_path / "two_near.png"
    _save_gray_with_red_rect(image_path, w, h, [(188, 195, 10, 10), (205, 195, 10, 10)])

    inst = _make_inst(center=[0.50, 0.50])
    result = e1b_refine_centers(image_path, _make_result([inst]))

    refined = result.instances[0]
    assert refined.display_bbox is not None
    x1, y1, x2, y2 = refined.display_bbox
    # bbox must span across both blobs (188px to 215px + padding)
    assert x1 <= (188 - 5) / 400   # left edge at or before blob A left (with padding)
    assert x2 >= (215 + 5) / 400   # right edge at or after blob B right (with padding)


# ─── E1b-S14: two nearby instances each keep only their own blob ─────────────
# Regression test for a real bug found on below_main_deck_mid: two extinguisher
# icons close together both had their search windows reach the other's red
# blob, so both instances' union boxes ended up pixel-identical and the second
# one drawn completely hid the first.


def test_e1b_s14_two_nearby_instances_do_not_merge_boxes(tmp_path):
    w, h = 400, 400
    image_path = tmp_path / "two_instances.png"
    # Blob A at (90,190)-(100,200) near instance A's center; blob B at
    # (140,190)-(150,200) near instance B's center. The two LLM centers are
    # close enough that the old code's search window for each reached both blobs.
    _save_gray_with_red_rect(image_path, w, h, [(90, 190, 10, 10), (140, 190, 10, 10)])

    inst_a = _make_inst(iid="a", center=[0.24, 0.49])  # ~(96,196)px, near blob A
    inst_b = _make_inst(iid="b", center=[0.37, 0.49])  # ~(148,196)px, near blob B

    result = e1b_refine_centers(image_path, _make_result([inst_a, inst_b]))
    ref_a, ref_b = result.instances

    assert ref_a.display_bbox is not None
    assert ref_b.display_bbox is not None
    # The two boxes must NOT be identical — each should hug only its own blob.
    assert ref_a.display_bbox != ref_b.display_bbox
    # A's box should not reach anywhere near blob B's region, and vice versa.
    assert ref_a.display_bbox[2] < 140 / w  # A's right edge stays left of blob B
    assert ref_b.display_bbox[0] > 100 / w  # B's left edge stays right of blob A


# ─── E1b-S13: only blob beyond MAX_DIST_PX → single instance gets no bbox ───


def test_e1b_s13_only_very_far_blob_display_bbox_none(tmp_path):
    w, h = 400, 400
    # LLM center at (200px, 200px)
    # Only blob: 22×22 at (50,50) → dist≈212px >> max_dist_px → filtered
    # Single instance → no standardization (max_w stays 0) → display_bbox stays None
    image_path = tmp_path / "far_only.png"
    _save_gray_with_red_rect(image_path, w, h, [(50, 50, 22, 22)])

    inst = _make_inst(center=[0.50, 0.50])
    result = e1b_refine_centers(image_path, _make_result([inst]))

    assert result.instances[0].display_bbox is None
    assert result.instances[0].center == [0.50, 0.50]
