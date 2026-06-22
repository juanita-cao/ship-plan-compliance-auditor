"""
Tests for run_detection() — production entry point (no ground truth, D1 skipped).

S01  run_detection succeeds without ground_truth argument
S02  D1 is skipped: accuracy is None, D1_cloud absent from completed_nodes
S03  default backends is cloud only (local_eval is None)
S04  E4 voting still runs (voting is not None)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import src.backend.e_nodes as e_nodes_mod
import src.backend.vv as vv_mod
from src.backend.pipeline import run_detection
from src.backend.schemas import CANONICAL_CATEGORIES, E3CountResult

_IMAGE = Path("data/test.png")
_PROMPT = "Detect fire extinguishers."
_ZERO_COUNTS = {cat: 0 for cat in CANONICAL_CATEGORIES}


def _e1_ok(
    image_path: Path, prompt: str, backend: str, run_id: int, project_id: str = "demo_ship_a"
) -> E3CountResult:
    return E3CountResult(total_by_category=dict(_ZERO_COUNTS), run_id=run_id)


@pytest.fixture(autouse=True)
def _patch_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "cloud-model-v1")
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path / "results")
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path / "logs")


def test_run_detection_s01_succeeds_without_ground_truth() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_detection(_IMAGE, _PROMPT, n_runs=3)
    assert ctx.cloud_eval is not None
    assert ctx.cloud_eval.status == "success"


def test_run_detection_s02_d1_skipped_accuracy_none_and_absent_from_completed_nodes() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_detection(_IMAGE, _PROMPT, n_runs=3)
    assert ctx.cloud_eval is not None
    assert ctx.cloud_eval.accuracy is None
    assert "D1_cloud" not in ctx.completed_nodes
    assert "E4_cloud" in ctx.completed_nodes


def test_run_detection_s03_default_backend_is_cloud_only() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_detection(_IMAGE, _PROMPT, n_runs=3)
    assert ctx.cloud_eval is not None
    assert ctx.local_eval is None


def test_run_detection_s04_e4_voting_still_populated() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_detection(_IMAGE, _PROMPT, n_runs=3)
    assert ctx.cloud_eval is not None
    assert ctx.cloud_eval.voting is not None
    assert set(ctx.cloud_eval.voting.votes.keys()) == set(CANONICAL_CATEGORIES)
