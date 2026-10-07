"""
Tests for F-Spotlight node: render_spotlight_node()

F-Spotlight-S01  display_bbox available                → returns PIL Image (uses bbox path)
F-Spotlight-S02  display_bbox=None, center available   → returns PIL Image (center fallback)
F-Spotlight-S03  selected_category filter              → returns PIL Image (only matching highlighted)
F-Spotlight-S04  render_spotlight raises               → SOFT: returns PIL Image, no exception
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.backend.schemas import CANONICAL_CATEGORIES, DetectedInstance
from src.frontend.spotlight import render_spotlight_node
from src.frontend.view_models import ResultsViewModel


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def test_image(tmp_path: Path) -> Path:
    img = Image.new("RGB", (200, 200), (200, 200, 200))
    p = tmp_path / "test.png"
    img.save(p)
    return p


def _make_vm(image_path: Path, instances: list[DetectedInstance]) -> ResultsViewModel:
    return ResultsViewModel(
        session_id="test",
        image_path=str(image_path),
        instances=instances,
        total_by_category={cat: 0 for cat in CANONICAL_CATEGORIES},
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_fspotlight_s01_display_bbox_returns_image(test_image: Path) -> None:
    inst = DetectedInstance(
        instance_id="i1",
        category="extinguisher_CO2_5kg",
        nearby_text="CO2",
        location_desc="deck",
        display_bbox=[0.1, 0.1, 0.4, 0.4],
    )
    vm = _make_vm(test_image, [inst])

    result = render_spotlight_node(vm)

    assert isinstance(result, Image.Image)


def test_fspotlight_s02_center_fallback_returns_image(test_image: Path) -> None:
    inst = DetectedInstance(
        instance_id="i1",
        category="extinguisher_dry_powder_6kg",
        nearby_text="P6",
        location_desc="deck",
        center=[0.5, 0.5],
        display_bbox=None,
    )
    vm = _make_vm(test_image, [inst])

    result = render_spotlight_node(vm)

    assert isinstance(result, Image.Image)


def test_fspotlight_s03_category_filter_returns_image(test_image: Path) -> None:
    inst_co2 = DetectedInstance(
        instance_id="i1",
        category="extinguisher_CO2_5kg",
        nearby_text="CO2",
        location_desc="deck",
        center=[0.3, 0.3],
    )
    inst_pow = DetectedInstance(
        instance_id="i2",
        category="extinguisher_dry_powder_6kg",
        nearby_text="P6",
        location_desc="deck",
        center=[0.7, 0.7],
    )
    vm = _make_vm(test_image, [inst_co2, inst_pow])

    result = render_spotlight_node(vm, selected_category="extinguisher_CO2_5kg")

    assert isinstance(result, Image.Image)


def test_fspotlight_s04_render_failure_soft_returns_image(test_image: Path) -> None:
    inst = DetectedInstance(
        instance_id="i1",
        category="extinguisher_CO2_5kg",
        nearby_text="CO2",
        location_desc="deck",
        center=[0.5, 0.5],
    )
    vm = _make_vm(test_image, [inst])

    with patch("src.frontend.spotlight.render_spotlight", side_effect=RuntimeError("mock render fail")):
        result = render_spotlight_node(vm)

    assert isinstance(result, Image.Image)
