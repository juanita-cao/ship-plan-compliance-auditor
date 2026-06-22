"""
Tests for build_results_viewmodel_from_report_data() — the shared builder used
by both the mock demo path (app_streamlit.py) and the real detection path
(pipeline_runner.py), both of which now read an eval_runs.report_data row
instead of building a ViewModel straight from a fresh PipelineContext.

F-VM-S01  counts only run_id=0 instances, ignores other runs
F-VM-S02  missing categories default to 0
F-VM-S03  compliance_result is populated (recomputed, not stored)
F-VM-S04  session_id / image_path pass through unchanged
F-VM-S05  empty instance_table.cloud → all-zero counts, no crash
F-VM-S06  raw_response passes through unchanged; defaults to None when omitted
"""

from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from src.frontend.view_models import ResultsViewModel, build_results_viewmodel_from_report_data

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/ship_plan_auditor"
)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)


def _inst(run_id, iid, category, cx=0.5, cy=0.5):
    return {
        "run_id": run_id,
        "instance_id": iid,
        "category": category,
        "nearby_text": "P 6",
        "location_desc": "test",
        "center": [cx, cy],
        "center_refined": False,
    }


def _gray_image(tmp_path):
    path = tmp_path / "img.png"
    img = np.full((200, 200, 3), 180, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def test_fvm_s01_counts_only_run0(tmp_path):
    image_path = _gray_image(tmp_path)
    report_data = {
        "instance_table": {
            "cloud": [
                _inst(0, "i1", "extinguisher_dry_powder_6kg"),
                _inst(0, "i2", "extinguisher_dry_powder_6kg"),
                _inst(1, "i3", "extinguisher_dry_powder_6kg"),  # different run — must be ignored
            ]
        }
    }
    vm = build_results_viewmodel_from_report_data(report_data, image_path, "sess-1", "demo_ship_a")
    assert isinstance(vm, ResultsViewModel)
    assert vm.total_by_category["extinguisher_dry_powder_6kg"] == 2
    assert len(vm.instances) == 2


def test_fvm_s02_missing_categories_default_zero(tmp_path):
    image_path = _gray_image(tmp_path)
    report_data = {
        "instance_table": {
            "cloud": [_inst(0, "i1", "extinguisher_CO2_5kg")],
        }
    }
    vm = build_results_viewmodel_from_report_data(report_data, image_path, "sess-2", "demo_ship_a")
    assert vm.total_by_category["extinguisher_CO2_5kg"] == 1
    assert vm.total_by_category["extinguisher_foam_9L"] == 0
    assert vm.total_by_category["extinguisher_dry_powder_6kg"] == 0


def test_fvm_s03_compliance_result_populated(tmp_path):
    image_path = _gray_image(tmp_path)
    report_data = {"instance_table": {"cloud": [_inst(0, "i1", "extinguisher_CO2_5kg")]}}
    vm = build_results_viewmodel_from_report_data(report_data, image_path, "sess-3", "demo_ship_a")
    assert vm.compliance_result is not None


def test_fvm_s04_session_and_path_passthrough(tmp_path):
    image_path = _gray_image(tmp_path)
    report_data = {"instance_table": {"cloud": []}}
    vm = build_results_viewmodel_from_report_data(report_data, image_path, "sess-4", "demo_ship_a")
    assert vm.session_id == "sess-4"
    assert vm.image_path == str(image_path)


def test_fvm_s05_empty_instances_all_zero(tmp_path):
    image_path = _gray_image(tmp_path)
    report_data = {"instance_table": {"cloud": []}}
    vm = build_results_viewmodel_from_report_data(report_data, image_path, "sess-5", "demo_ship_a")
    assert vm.instances == []
    assert all(v == 0 for v in vm.total_by_category.values())


def test_fvm_s06_raw_response_passthrough(tmp_path):
    image_path = _gray_image(tmp_path)
    report_data = {"instance_table": {"cloud": []}}
    vm = build_results_viewmodel_from_report_data(
        report_data, image_path, "sess-6", "demo_ship_a", raw_response="STEP1...\n[INSTANCES_JSON]..."
    )
    assert vm.raw_response == "STEP1...\n[INSTANCES_JSON]..."

    vm_default = build_results_viewmodel_from_report_data(report_data, image_path, "sess-6b", "demo_ship_a")
    assert vm_default.raw_response is None
