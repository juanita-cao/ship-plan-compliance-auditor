"""
L2 Node Unit Tests for v1_sequence_check and v2_trace_output (V&V layer).

Contract Test Scenario List: V1-S01 through V1-S08, V2-S01 through V2-S08
(design_backend.md §7.10).

V1 verifies that v1_sequence_check:
- Returns is_clean=True when all required nodes are present in correct order (V1-S01).
- Detects missing required nodes (V1-S02, V1-S03).
- Allows legal absent nodes in degraded modes (V1-S04, V1-S05).
- Warns on unknown nodes without failing is_clean (V1-S06).
- Fails is_clean on order violations (V1-S07).
- Warns on duplicate nodes without failing is_clean (V1-S08).

V2 verifies that v2_trace_output:
- Writes file with correct filename and path (V2-S01, V2-S08).
- Writes valid JSON (V2-S02).
- Records session_id correctly (V2-S03).
- Includes minimum schema fields in trace (V2-S04).
- Includes V1 verification result in trace (V2-S05).
- Creates logs/ dir when missing (V2-S06).
- Raises OSError on write failure — HARD FAIL (V2-S07).

Out of scope:
- Does not test E1–E5 or D1 logic.
- Does not test pipeline orchestration.
- PII/secret safety: out of scope for Phase 0.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import src.backend.vv as vv_mod
from src.backend.schemas import CANONICAL_CATEGORIES, GroundTruth, PipelineContext, V1Report
from src.backend.vv import v1_sequence_check, v2_trace_output

_FULL_NODES = ["E4_local", "D1_local", "E4_cloud", "D1_cloud", "E5"]
_LOCAL_ONLY_NODES = ["E4_local", "D1_local", "E5"]
_CLOUD_ONLY_NODES = ["E4_cloud", "D1_cloud", "E5"]


def _ctx(report_mode: str = "full", completed_nodes: list[str] | None = None) -> PipelineContext:
    return PipelineContext(
        image_path="data/test.png",
        prompt_label="short",
        n_runs=3,
        ground_truth=GroundTruth(counts={cat: 0 for cat in CANONICAL_CATEGORIES}),
        report_mode=report_mode,
        completed_nodes=completed_nodes if completed_nodes is not None else [],
    )


def _v1(
    is_clean: bool = True,
    missing: list[str] | None = None,
    warnings: list[str] | None = None,
) -> V1Report:
    return V1Report(is_clean=is_clean, missing_nodes=missing or [], warnings=warnings or [])


# ─── V1-S01 to V1-S05: required nodes and degraded modes ─────────────────────


def test_v1_s01_full_mode_all_nodes_correct_order_is_clean() -> None:
    result = v1_sequence_check(_ctx("full", _FULL_NODES))
    assert result.is_clean is True
    assert result.missing_nodes == []
    assert result.warnings == []


def test_v1_s02_e5_missing_not_clean() -> None:
    result = v1_sequence_check(_ctx("full", [n for n in _FULL_NODES if n != "E5"]))
    assert result.is_clean is False
    assert "E5" in result.missing_nodes


def test_v1_s03_d1_local_missing_full_mode_not_clean() -> None:
    result = v1_sequence_check(_ctx("full", [n for n in _FULL_NODES if n != "D1_local"]))
    assert result.is_clean is False
    assert "D1_local" in result.missing_nodes


def test_v1_s04_local_only_cloud_nodes_absent_is_clean() -> None:
    result = v1_sequence_check(_ctx("local_only", _LOCAL_ONLY_NODES))
    assert result.is_clean is True
    assert result.warnings  # degraded explanation present


def test_v1_s05_cloud_only_local_nodes_absent_is_clean() -> None:
    result = v1_sequence_check(_ctx("cloud_only", _CLOUD_ONLY_NODES))
    assert result.is_clean is True
    assert result.warnings  # degraded explanation present


# ─── V1-S06: unknown node — warning only ──────────────────────────────────────


def test_v1_s06_unknown_node_sets_not_clean() -> None:
    result = v1_sequence_check(_ctx("full", _FULL_NODES + ["X_unknown"]))
    assert result.is_clean is False
    assert any("X_unknown" in w or "unknown" in w.lower() for w in result.warnings)


# ─── V1-S07: order violation — is_clean=False ────────────────────────────────


def test_v1_s07_order_violation_not_clean() -> None:
    # D1_local before E4_local violates dependency
    nodes = ["D1_local", "E4_local", "E4_cloud", "D1_cloud", "E5"]
    result = v1_sequence_check(_ctx("full", nodes))
    assert result.is_clean is False
    assert any("D1_local" in w or "order" in w.lower() for w in result.warnings)


# ─── V1-S08: duplicate node — warning only ───────────────────────────────────


def test_v1_s08_duplicate_node_warning_only_no_clean_impact() -> None:
    result = v1_sequence_check(_ctx("full", _FULL_NODES + ["E5"]))
    assert result.is_clean is True
    assert any("duplicate" in w.lower() or "E5" in w for w in result.warnings)


# ─── V1-S09: invalid report_mode → ValueError ────────────────────────────────


def test_v1_s09_invalid_report_mode_raises_value_error() -> None:
    ctx = PipelineContext.model_construct(
        report_mode="invalid_mode",
        completed_nodes=[],
        image_path="data/test.png",
        prompt_label="short",
        n_runs=3,
        ground_truth=GroundTruth(counts={cat: 0 for cat in CANONICAL_CATEGORIES}),
    )
    with pytest.raises(ValueError):
        v1_sequence_check(ctx)


# ─── V2-S01 to V2-S03: basic file write ──────────────────────────────────────


def test_v2_s01_normal_write_output_path_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    ctx = _ctx()
    result = v2_trace_output(ctx, _v1())
    assert result.output_path is not None
    assert Path(result.output_path).exists()


def test_v2_s02_written_file_is_valid_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    result = v2_trace_output(_ctx(), _v1())
    data = json.loads(Path(result.output_path).read_text())
    assert isinstance(data, dict)


def test_v2_s03_session_id_matches_ctx(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    ctx = _ctx()
    result = v2_trace_output(ctx, _v1())
    assert result.session_id == ctx.session_id


# ─── V2-S04: minimum schema fields ───────────────────────────────────────────


def test_v2_s04_trace_contains_minimum_schema_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    result = v2_trace_output(_ctx(), _v1())
    data = json.loads(Path(result.output_path).read_text())
    _MIN_KEYS = (
        "session_id",
        "timestamp",
        "completed_nodes",
        "node_timings",
        "errors",
        "report_mode",
    )
    for key in _MIN_KEYS:
        assert key in data, f"Missing key in trace: {key!r}"


# ─── V2-S05: V1 verification result in trace ─────────────────────────────────


def test_v2_s05_trace_contains_verification_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    v1 = V1Report(is_clean=False, missing_nodes=["E5"], warnings=["degraded"])
    result = v2_trace_output(_ctx(), v1)
    data = json.loads(Path(result.output_path).read_text())
    assert "verification" in data
    assert data["verification"]["is_clean"] is False
    assert "E5" in data["verification"]["missing_nodes"]


# ─── V2-S06: logs/ auto-created ──────────────────────────────────────────────


def test_v2_s06_logs_dir_created_when_missing(tmp_path, monkeypatch) -> None:
    out_dir = tmp_path / "new_logs"
    assert not out_dir.exists()
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", out_dir)
    v2_trace_output(_ctx(), _v1())
    assert out_dir.exists()


# ─── V2-S07: write failure → HARD FAIL ───────────────────────────────────────


def test_v2_s07_write_failure_raises_oserror(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    with patch.object(Path, "write_text", side_effect=OSError("no space")):
        with pytest.raises(OSError):
            v2_trace_output(_ctx(), _v1())


# ─── V2-S08: filename format ─────────────────────────────────────────────────


def test_v2_s08_filename_is_session_id_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path)
    ctx = _ctx()
    result = v2_trace_output(ctx, _v1())
    assert Path(result.output_path).name == f"{ctx.session_id}_trace.json"
