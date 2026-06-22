"""ADR-007 amendment — Postgres-backed eval run results.

Persists the same report data run_eval.py used to only write to
experiments/results/*.json, plus the cloud raw_response text. Both the mock
demo path (app_streamlit.py) and the real detection path
(pipeline_runner.py) read through this module, so neither depends on flat
files or in-process memory for "what was the last result for this image".
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg

from .schemas import PipelineContext


def _connect() -> psycopg.Connection:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg.connect(database_url)


def save_eval_run(
    ctx: PipelineContext,
    target_short: int | None,
    spotlight_png_path: str | None = None,
) -> None:
    """Insert one row for this pipeline run. session_id is unique — re-saving
    the same ctx twice raises (each run produces a fresh session_id)."""
    if ctx.report is None:
        raise ValueError("ctx.report is None — call this after e5_generate_report has run")

    raw_response = None
    if ctx.cloud_eval is not None and ctx.cloud_eval.runs:
        raw_response = ctx.cloud_eval.runs[0].counts.raw_response

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO eval_runs
                (session_id, project_id, image_stem, target_short, prompt_label,
                 report_data, raw_response_cloud, spotlight_png_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ctx.session_id,
                ctx.project_id,
                Path(ctx.image_path).stem,
                target_short,
                ctx.prompt_label,
                json.dumps(ctx.report.data, default=str),
                raw_response,
                spotlight_png_path,
            ),
        )


def get_latest_eval_run(image_stem: str, project_id: str) -> dict | None:
    """Most recent row for this (project_id, image_stem), or None if no run exists yet."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT session_id, report_data, raw_response_cloud, spotlight_png_path, created_at
            FROM eval_runs
            WHERE project_id = %s AND image_stem = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id, image_stem),
        ).fetchone()

    if row is None:
        return None
    return {
        "session_id": row[0],
        "report_data": row[1],
        "raw_response_cloud": row[2],
        "spotlight_png_path": row[3],
        "created_at": row[4],
    }


def list_validated_image_stems(project_id: str) -> list[str]:
    """Image stems that have at least one eval_runs row for this project.

    Used by the frontend to filter the deck dropdown to images with a real,
    accuracy-checked result on file (same "verified only" spirit as ADR-F11),
    without requiring unvalidated images to be deleted from disk.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT image_stem FROM eval_runs WHERE project_id = %s",
            (project_id,),
        ).fetchall()
    return sorted(r[0] for r in rows)


def get_eval_run_by_session(session_id: str) -> dict | None:
    """One specific row by session_id — used right after a live run to read back what was saved."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT session_id, report_data, raw_response_cloud, spotlight_png_path, created_at
            FROM eval_runs
            WHERE session_id = %s
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None
    return {
        "session_id": row[0],
        "report_data": row[1],
        "raw_response_cloud": row[2],
        "spotlight_png_path": row[3],
        "created_at": row[4],
    }
