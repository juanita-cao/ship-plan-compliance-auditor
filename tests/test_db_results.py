"""
Tests for db_results.py — Postgres-backed eval_runs persistence (ADR-007 amendment).

Integration tests against the real local Postgres instance, same convention
as test_category_lookup.py. Each test uses a unique session_id and cleans up
its own row afterward.

DBR-S01  save then get_latest_eval_run round-trips report_data + raw_response
DBR-S02  get_latest_eval_run returns the most recent of several rows
DBR-S03  get_eval_run_by_session finds the exact row
DBR-S04  get_latest_eval_run / get_eval_run_by_session return None when no match
DBR-S05  saving twice with the same session_id raises (UNIQUE constraint)
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from src.backend import db_results
from src.backend.schemas import (
    BackendEvalResult,
    DetectedInstance,
    E3CountResult,
    E5Report,
    PipelineContext,
    SingleRunResult,
)

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/ship_plan_auditor"
)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)


@pytest.fixture
def cleanup_sessions():
    created: list[str] = []
    yield created
    if created:
        with psycopg.connect(_TEST_DATABASE_URL) as conn:
            conn.execute("DELETE FROM eval_runs WHERE session_id = ANY(%s)", (created,))


def _make_ctx(session_id: str, image_stem: str, raw_response: str | None = "STEP1...") -> PipelineContext:
    instance = DetectedInstance(
        instance_id="i1", category="extinguisher_CO2_5kg",
        nearby_text="CO2", location_desc="test", center=[0.5, 0.5],
    )
    counts = E3CountResult(
        total_by_category={"extinguisher_CO2_5kg": 1},
        run_id=0,
        instances=[instance],
        raw_response=raw_response,
    )
    cloud_eval = BackendEvalResult(
        backend="cloud", api_model_id="test-model", status="success",
        runs=[SingleRunResult(run_id=0, counts=counts)],
    )
    ctx = PipelineContext(
        session_id=session_id,
        image_path=f"data/images/demo_ship_a/{image_stem}.png",
        prompt_label="test",
        n_runs=1,
        project_id="demo_ship_a",
        cloud_eval=cloud_eval,
    )
    ctx.report = E5Report(
        text="report text",
        data={"instance_table": {"cloud": [{"run_id": 0, "instance_id": "i1"}]}},
        report_mode="cloud_only",
        write_status="success",
    )
    return ctx


def test_dbr_s01_save_and_get_latest_roundtrip(cleanup_sessions):
    session_id = f"test-{uuid.uuid4()}"
    cleanup_sessions.append(session_id)
    image_stem = f"test_image_{uuid.uuid4().hex[:8]}"
    ctx = _make_ctx(session_id, image_stem, raw_response="STEP1: detected...")

    db_results.save_eval_run(ctx, target_short=800, spotlight_png_path="/tmp/x.png")
    row = db_results.get_latest_eval_run(image_stem, "demo_ship_a")

    assert row is not None
    assert row["session_id"] == session_id
    assert row["report_data"]["instance_table"]["cloud"][0]["instance_id"] == "i1"
    assert row["raw_response_cloud"] == "STEP1: detected..."
    assert row["spotlight_png_path"] == "/tmp/x.png"


def test_dbr_s02_get_latest_returns_most_recent(cleanup_sessions):
    image_stem = f"test_image_{uuid.uuid4().hex[:8]}"
    session_old = f"test-{uuid.uuid4()}"
    session_new = f"test-{uuid.uuid4()}"
    cleanup_sessions.extend([session_old, session_new])

    db_results.save_eval_run(_make_ctx(session_old, image_stem), target_short=800)
    db_results.save_eval_run(_make_ctx(session_new, image_stem), target_short=1200)

    row = db_results.get_latest_eval_run(image_stem, "demo_ship_a")
    assert row["session_id"] == session_new


def test_dbr_s03_get_by_session_finds_exact_row(cleanup_sessions):
    session_id = f"test-{uuid.uuid4()}"
    cleanup_sessions.append(session_id)
    image_stem = f"test_image_{uuid.uuid4().hex[:8]}"

    db_results.save_eval_run(_make_ctx(session_id, image_stem), target_short=800)
    row = db_results.get_eval_run_by_session(session_id)

    assert row is not None
    assert row["session_id"] == session_id


def test_dbr_s04_no_match_returns_none():
    missing_stem = f"nonexistent_{uuid.uuid4().hex}"
    assert db_results.get_latest_eval_run(missing_stem, "demo_ship_a") is None
    assert db_results.get_eval_run_by_session(f"nonexistent-{uuid.uuid4()}") is None


def test_dbr_s05_duplicate_session_id_raises(cleanup_sessions):
    session_id = f"test-{uuid.uuid4()}"
    cleanup_sessions.append(session_id)
    image_stem = f"test_image_{uuid.uuid4().hex[:8]}"
    ctx = _make_ctx(session_id, image_stem)

    db_results.save_eval_run(ctx, target_short=800)
    with pytest.raises(psycopg.errors.UniqueViolation):
        db_results.save_eval_run(ctx, target_short=800)
