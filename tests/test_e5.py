"""
L2 Node Unit Tests for e5_generate_report (E5 · Execute · Report Generator).

Contract Test Scenario List: E5-S01 through E5-S10 (design_backend.md §7.10).

Verifies that E5:
- Generates correct text structure for full/degraded modes (E5-S01 to E5-S03).
- Writes JSON file with session_id filename (E5-S04).
- Returns JSON-serializable data (E5-S05).
- Includes all 7 core metric names in text (E5-S06).
- Raises ValueError on invalid report_mode (E5-S07).
- Creates output_dir if missing (E5-S08).
- Returns output_path=None on file write failure without raising (E5-S09).
- Returns data with required top-level keys (E5-S10).

Out of scope:
- Does not test E1–E4 or D1 logic.
- Does not test pipeline orchestration.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import src.backend.e_nodes as e_nodes_mod
from src.backend.e_nodes import e5_generate_report
from src.backend.schemas import (
    CANONICAL_CATEGORIES,
    VOTE_THRESHOLD_ACCEPT,
    VOTE_THRESHOLD_WARN,
    BackendEvalResult,
    CategoryAccuracy,
    CategoryVote,
    D1AccuracyDecision,
    E4VotingResult,
    GroundTruth,
    PipelineContext,
)

_7_METRICS = [
    "majority_vote_accuracy_pct",
    "single_run_accuracy_avg_pct",
    "accuracy_gain_pct",
    "image_level_exact_match",
    "auto_accept_rate",
    "accuracy_on_auto_accepted_pct",
    "manual_review_rate",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_voting(n_runs: int = 3) -> E4VotingResult:
    votes = {
        cat: CategoryVote(
            category=cat,
            voted_count=0,
            all_counts=[0] * n_runs,
            majority_freq=n_runs,
            n_runs=n_runs,
            ratio=1.0,
            is_tie=False,
            status="ACCEPTED",
            threshold_accept=VOTE_THRESHOLD_ACCEPT,
            threshold_warn=VOTE_THRESHOLD_WARN,
        )
        for cat in CANONICAL_CATEGORIES
    }
    return E4VotingResult(votes=votes)


def _make_accuracy() -> D1AccuracyDecision:
    per_category = [
        CategoryAccuracy(
            category=cat, ground_truth=0, voted_count=0, correct=True, vote_status="ACCEPTED"
        )
        for cat in CANONICAL_CATEGORIES
    ]
    return D1AccuracyDecision(
        per_category=per_category,
        n_correct=6,
        n_total=6,
        majority_vote_accuracy_pct=100.0,
        single_run_accuracy_avg_pct=90.0,
        accuracy_gain_pct=10.0,
        image_level_exact_match=True,
        auto_accept_rate=1.0,
        accuracy_on_auto_accepted_pct=100.0,
        manual_review_rate=0.0,
        decision="PASS",
        reason="All 6 categories match ground truth.",
        rule_triggered="PASS_ALL",
        inputs_snapshot={},
    )


def _make_backend(backend: str = "local", status: str = "success") -> BackendEvalResult:
    return BackendEvalResult(
        backend=backend,
        api_model_id=f"{backend}-model-v1",
        status=status,
        voting=_make_voting() if status == "success" else None,
        accuracy=_make_accuracy() if status == "success" else None,
    )


def _make_ctx(
    report_mode: str = "full",
    local: bool = True,
    cloud: bool = True,
) -> PipelineContext:
    return PipelineContext(
        image_path="data/test.png",
        prompt_label="short",
        n_runs=3,
        ground_truth=GroundTruth(counts={cat: 0 for cat in CANONICAL_CATEGORIES}),
        report_mode=report_mode,
        local_eval=_make_backend("local") if local else None,
        cloud_eval=_make_backend("cloud") if cloud else None,
    )


# ─── E5-S01 to E5-S03: mode-aware text structure ─────────────────────────────


def test_e5_s01_full_mode_text_contains_local_cloud_comparison(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx("full"))
    assert result.report_mode == "full"
    assert "LOCAL" in result.text
    assert "CLOUD" in result.text
    assert "COMPARISON" in result.text
    assert result.degraded_reason is None


def test_e5_s02_local_only_text_no_comparison_has_degraded_reason(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx("local_only", cloud=False))
    assert result.report_mode == "local_only"
    assert "COMPARISON" not in result.text
    assert "⚠" in result.text or "degraded" in result.text.lower()
    assert result.degraded_reason is not None


def test_e5_s03_cloud_only_text_no_comparison_has_degraded_reason(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx("cloud_only", local=False))
    assert result.report_mode == "cloud_only"
    assert "COMPARISON" not in result.text
    assert "⚠" in result.text or "degraded" in result.text.lower()
    assert result.degraded_reason is not None


# ─── E5-S04: file write ───────────────────────────────────────────────────────


def test_e5_s04_file_written_with_session_id_filename(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    ctx = _make_ctx()
    result = e5_generate_report(ctx)
    assert result.output_path is not None
    image_stem = Path(ctx.image_path).stem
    expected_file = tmp_path / f"{image_stem}_{ctx.session_id[:8]}.json"
    assert expected_file.exists()
    assert result.output_path == str(expected_file)


# ─── E5-S05: data JSON-serializable ──────────────────────────────────────────


def test_e5_s05_data_is_json_serializable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx())
    assert json.dumps(result.data)  # must not raise


# ─── E5-S06: text contains all 7 metric names ────────────────────────────────


def test_e5_s06_text_contains_all_seven_metric_names(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx())
    for metric in _7_METRICS:
        assert metric in result.text, f"Missing metric in text: {metric!r}"


# ─── E5-S07: invalid report_mode → ValueError ────────────────────────────────


def test_e5_s07_invalid_report_mode_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    ctx = PipelineContext.model_construct(
        session_id="test-session",
        image_path="data/test.png",
        prompt_label="short",
        n_runs=3,
        ground_truth=GroundTruth(counts={cat: 0 for cat in CANONICAL_CATEGORIES}),
        report_mode="invalid_mode",
        local_eval=_make_backend(),
        cloud_eval=_make_backend("cloud"),
    )
    with pytest.raises(ValueError):
        e5_generate_report(ctx)


# ─── E5-S08: output_dir created if missing ───────────────────────────────────


def test_e5_s08_output_dir_created_when_missing(tmp_path, monkeypatch) -> None:
    out_dir = tmp_path / "new_results"
    assert not out_dir.exists()
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", out_dir)
    result = e5_generate_report(_make_ctx())
    assert out_dir.exists()
    assert result.output_path is not None


# ─── E5-S09: file write failure → output_path=None, no raise ─────────────────


def test_e5_s09_file_write_failure_returns_none_output_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = e5_generate_report(_make_ctx())
    assert result.output_path is None
    assert result.text  # function completes normally


# ─── E5-S10: data top-level keys ─────────────────────────────────────────────


def test_e5_s10_data_contains_required_top_level_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx())
    for key in ("metadata", "metrics", "voting", "accuracy", "mode"):
        assert key in result.data, f"Missing required key in data: {key!r}"


# ─── E5-S11: degraded_reason in data ─────────────────────────────────────────


def test_e5_s11_degraded_reason_in_data_when_local_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx("local_only", cloud=False))
    assert "degraded_reason" in result.data
    assert result.data["degraded_reason"] is not None
    assert result.data["degraded_reason"] == result.degraded_reason


def test_e5_s11b_degraded_reason_none_in_data_for_full_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx("full"))
    assert result.data.get("degraded_reason") is None


# ─── E5-S12: write_status="success" on normal write ─────────────────────────


def test_e5_s12_write_status_success_on_normal_write(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    result = e5_generate_report(_make_ctx())
    assert result.write_status == "success"
    assert result.write_error is None


# ─── E5-S13: write_status="failed" + write_error set on OSError ───────────────


def test_e5_s13_write_status_failed_and_error_set_on_oserror(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path)
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = e5_generate_report(_make_ctx())
    assert result.write_status == "failed"
    assert result.write_error == "disk full"
