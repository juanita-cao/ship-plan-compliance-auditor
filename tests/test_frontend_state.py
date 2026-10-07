"""
Tests for F-State node: resolve_next_state()

F-State-S01  IDLE + analyze_clicked + image_path valid → RUNNING
F-State-S02  IDLE + analyze_clicked + image_path=None  → IDLE (guard blocks)
F-State-S03  RUNNING + pipeline_complete               → RESULTS, results_vm set, selected_*=None
F-State-S04  RUNNING + pipeline_error                  → IDLE, last_error set
F-State-S05  RESULTS + new_analysis_clicked            → IDLE, all fields cleared
F-State-S06  RESULTS + category_clicked                → RESULTS, selected_category set
F-State-S07  unknown (state, event)                    → HARD FAIL raises ValueError
"""

from __future__ import annotations

import pytest

from src.backend.schemas import CANONICAL_CATEGORIES
from src.frontend.state import StateTransitionResult, resolve_next_state
from src.frontend.view_models import ResultsViewModel

# ─── Fixtures ─────────────────────────────────────────────────────────────────

_MOCK_VM = ResultsViewModel(
    session_id="mock-0001",
    image_path="data/test.png",
    instances=[],
    total_by_category={cat: 0 for cat in CANONICAL_CATEGORIES},
)


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_fstate_s01_idle_analyze_with_image_goes_running() -> None:
    result = resolve_next_state(
        current_state="IDLE",
        event="analyze_clicked",
        guard_result={"image_path": "data/test.png"},
    )
    assert isinstance(result, StateTransitionResult)
    assert result.next_state == "RUNNING"
    assert result.session_state_patch["stage"] == "RUNNING"
    assert result.session_state_patch["job_status"] == "running"
    assert result.session_state_patch.get("last_error") is None


def test_fstate_s02_idle_analyze_without_image_stays_idle() -> None:
    result = resolve_next_state(
        current_state="IDLE",
        event="analyze_clicked",
        guard_result={"image_path": None},
    )
    assert result.next_state == "IDLE"
    # no stage transition in the patch
    assert result.session_state_patch.get("stage", "IDLE") == "IDLE"


def test_fstate_s03_running_pipeline_complete_goes_results() -> None:
    result = resolve_next_state(
        current_state="RUNNING",
        event="pipeline_complete",
        guard_result={"results_vm": _MOCK_VM},
    )
    assert result.next_state == "RESULTS"
    assert result.session_state_patch["stage"] == "RESULTS"
    assert result.session_state_patch["results_vm"] is _MOCK_VM
    assert result.session_state_patch["selected_category"] is None
    assert result.session_state_patch["selected_instance_id"] is None


def test_fstate_s04_running_pipeline_error_goes_idle() -> None:
    result = resolve_next_state(
        current_state="RUNNING",
        event="pipeline_error",
        guard_result={"error_msg": "timeout"},
    )
    assert result.next_state == "IDLE"
    assert result.session_state_patch["stage"] == "IDLE"
    assert result.session_state_patch["last_error"] == "timeout"
    assert result.session_state_patch.get("results_vm") is None


def test_fstate_s05_results_new_analysis_clears_all() -> None:
    result = resolve_next_state(
        current_state="RESULTS",
        event="new_analysis_clicked",
        guard_result={},
    )
    assert result.next_state == "IDLE"
    patch = result.session_state_patch
    assert patch["stage"] == "IDLE"
    assert patch["job_status"] == "none"
    assert patch["results_vm"] is None
    assert patch["selected_category"] is None
    assert patch["selected_instance_id"] is None
    assert patch["last_error"] is None


def test_fstate_s06_results_category_clicked_sets_selected() -> None:
    result = resolve_next_state(
        current_state="RESULTS",
        event="category_clicked",
        guard_result={"category": "extinguisher_CO2_5kg"},
    )
    assert result.next_state == "RESULTS"
    assert result.session_state_patch["selected_category"] == "extinguisher_CO2_5kg"
    assert result.session_state_patch["selected_instance_id"] is None


def test_fstate_s07_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        resolve_next_state(
            current_state="IDLE",
            event="nonexistent_event",
            guard_result={},
        )

    with pytest.raises(ValueError):
        resolve_next_state(
            current_state="RUNNING",
            event="category_clicked",
            guard_result={},
        )
