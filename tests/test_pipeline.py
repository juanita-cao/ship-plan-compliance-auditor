"""
T9 Integration tests for run_pipeline().

Verifies that run_pipeline orchestrates all nodes correctly:
- Full mode: both backends succeed (S01).
- Degraded cloud_only: local backend fails (S02).
- Degraded local_only: cloud backend fails (S03).
- Both fail: RuntimeError raised (S04).
- completed_nodes order (S05).
- V2 trace file written (S06).
- api_model_id populated from env (S07).

All LLM calls (E1) are mocked; E4, D1, V1, V2 run their actual code.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import src.backend.e_nodes as e_nodes_mod
import src.backend.vv as vv_mod
from src.backend.pipeline import run_pipeline
from src.backend.schemas import CANONICAL_CATEGORIES, E3CountResult, GroundTruth

_GT = GroundTruth(counts={cat: 0 for cat in CANONICAL_CATEGORIES})
_IMAGE = Path("data/test.png")
_PROMPT = "Detect fire extinguishers."
_ZERO_COUNTS = {cat: 0 for cat in CANONICAL_CATEGORIES}


def _e1_ok(
    image_path: Path, prompt: str, backend: str, run_id: int, project_id: str = "demo_ship_a"
) -> E3CountResult:
    return E3CountResult(total_by_category=dict(_ZERO_COUNTS), run_id=run_id)


def _e1_local_fail(
    image_path: Path, prompt: str, backend: str, run_id: int, project_id: str = "demo_ship_a"
) -> E3CountResult:
    if backend == "local":
        raise RuntimeError("local backend unavailable")
    return _e1_ok(image_path, prompt, backend, run_id, project_id)


def _e1_cloud_fail(
    image_path: Path, prompt: str, backend: str, run_id: int, project_id: str = "demo_ship_a"
) -> E3CountResult:
    if backend == "cloud":
        raise RuntimeError("cloud backend unavailable")
    return _e1_ok(image_path, prompt, backend, run_id, project_id)


@pytest.fixture(autouse=True)
def _patch_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "cloud-model-v1")
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "local-model-v1")
    monkeypatch.setattr(e_nodes_mod, "_REPORT_OUTPUT_DIR", tmp_path / "results")
    monkeypatch.setattr(vv_mod, "_TRACE_OUTPUT_DIR", tmp_path / "logs")


# ─── S01: full mode ───────────────────────────────────────────────────────────


def test_pipeline_s01_full_mode_both_backends_succeed() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    assert ctx.report_mode == "full"
    assert ctx.local_eval is not None and ctx.local_eval.status == "success"
    assert ctx.cloud_eval is not None and ctx.cloud_eval.status == "success"
    for node in ["E4_local", "D1_local", "E4_cloud", "D1_cloud", "E5"]:
        assert node in ctx.completed_nodes
    assert ctx.report is not None


# ─── S02: local fails → cloud_only ───────────────────────────────────────────


def test_pipeline_s02_local_fails_cloud_only_mode() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_local_fail):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    assert ctx.report_mode == "cloud_only"
    assert ctx.local_eval is not None and ctx.local_eval.status == "failed"
    assert ctx.local_eval.error_message is not None
    assert ctx.cloud_eval is not None and ctx.cloud_eval.status == "success"
    assert ctx.errors


# ─── S03: cloud fails → local_only ───────────────────────────────────────────


def test_pipeline_s03_cloud_fails_local_only_mode() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_cloud_fail):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    assert ctx.report_mode == "local_only"
    assert ctx.local_eval is not None and ctx.local_eval.status == "success"
    assert ctx.cloud_eval is not None and ctx.cloud_eval.status == "failed"


# ─── S04: both fail → RuntimeError ───────────────────────────────────────────


def test_pipeline_s04_both_fail_raises_runtime_error() -> None:
    with patch(
        "src.backend.pipeline.e1_extract_counts",
        side_effect=RuntimeError("both backends down"),
    ):
        with pytest.raises(RuntimeError, match="Both backends failed"):
            run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)


# ─── S05: completed_nodes order ──────────────────────────────────────────────


def test_pipeline_s05_completed_nodes_correct_order_e5_last() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    nodes = ctx.completed_nodes
    assert nodes.index("D1_local") > nodes.index("E4_local")
    assert nodes.index("D1_cloud") > nodes.index("E4_cloud")
    assert nodes[-1] == "E5"


# ─── S06: V2 trace file written ──────────────────────────────────────────────


def test_pipeline_s06_v2_trace_file_written(tmp_path: Path) -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    trace_file = tmp_path / "logs" / f"{ctx.session_id}_trace.json"
    assert trace_file.exists()
    data = json.loads(trace_file.read_text())
    assert data["session_id"] == ctx.session_id
    assert data["report_mode"] == "full"


# ─── S08: trace contains total_ms ────────────────────────────────────────────


def test_pipeline_s08_trace_contains_total_ms(tmp_path: Path) -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    trace_file = tmp_path / "logs" / f"{ctx.session_id}_trace.json"
    data = json.loads(trace_file.read_text())
    assert "total_ms" in data["node_timings"]
    assert data["node_timings"]["total_ms"] > 0


# ─── S07: api_model_id from env ──────────────────────────────────────────────


def test_pipeline_s07_api_model_id_populated_from_env() -> None:
    with patch("src.backend.pipeline.e1_extract_counts", side_effect=_e1_ok):
        ctx = run_pipeline(_IMAGE, _PROMPT, _GT, n_runs=3)

    assert ctx.local_eval is not None
    assert ctx.local_eval.api_model_id == "local-model-v1"
    assert ctx.cloud_eval is not None
    assert ctx.cloud_eval.api_model_id == "cloud-model-v1"
