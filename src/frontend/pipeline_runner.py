"""
Background thread wrapper for run_detection().

Results are stored in module-level _job_results[session_id]; the app layer
polls on each Streamlit rerun. No queue needed — only done/error signals matter.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from src.backend import e_nodes
from src.backend.db_results import get_eval_run_by_session, save_eval_run
from src.backend.pipeline import run_detection
from src.frontend.view_models import build_results_viewmodel_from_report_data
from src.viz import save_run_artifacts

logger = logging.getLogger(__name__)

_TIMEOUT_S = 300  # seconds before a running job is considered hung

# session_id → {"status": "running"|"success"|"error", "vm": ..., "error": ..., "started_at": float}
_job_results: dict[str, dict] = {}
_lock = threading.Lock()


def start_detection(
    session_id: str,
    image_path: Path,
    prompt: str,
    prompt_label: str = "default",
    project_id: str = "demo_ship_a",
) -> None:
    with _lock:
        _job_results[session_id] = {"status": "running", "vm": None, "error": None, "started_at": time.time()}

    def _run() -> None:
        try:
            # Same {image_stem}_t{resolution}/ subfolder convention as run_eval.py,
            # so real frontend runs and CLI eval runs land in the same place.
            # NOTE: _REPORT_OUTPUT_DIR is a shared module global — two detections
            # running concurrently in different threads could race on this. Not
            # a concern for today's single-user manual testing; would need a
            # real fix (pass output_dir through run_pipeline explicitly) before
            # this app serves concurrent users.
            target_short = e_nodes._E1_TARGET_SHORT or 0
            exp_dir = e_nodes.experiment_dir(image_path, target_short)
            exp_dir.mkdir(parents=True, exist_ok=True)
            e_nodes._REPORT_OUTPUT_DIR = exp_dir

            ctx = run_detection(
                image_path=image_path,
                prompt=prompt,
                prompt_label=prompt_label,
                n_runs=1,
                project_id=project_id,
            )
            # Same artifacts run_eval.py --save-viz produces (spotlight PNG +
            # raw_response.txt), so a real frontend run leaves the same files
            # behind as a CLI eval run.
            png_path = save_run_artifacts(ctx, exp_dir)

            # Persist to Postgres, then read the row back rather than building
            # the ViewModel straight from ctx — mock mode and real mode go
            # through the exact same "fetch from DB → render" code path.
            save_eval_run(ctx, target_short, spotlight_png_path=str(png_path) if png_path else None)
            row = get_eval_run_by_session(ctx.session_id)
            if row is None:
                raise RuntimeError(f"eval_runs row missing right after save for {ctx.session_id!r}")
            vm = build_results_viewmodel_from_report_data(
                row["report_data"], image_path, row["session_id"], project_id,
                raw_response=row["raw_response_cloud"],
            )
            with _lock:
                _job_results[session_id] = {"status": "success", "vm": vm, "error": None}
        except Exception as exc:
            logger.warning("pipeline_runner: detection failed for %s: %s", session_id, exc)
            with _lock:
                _job_results[session_id] = {"status": "error", "vm": None, "error": str(exc)}

    threading.Thread(target=_run, daemon=True).start()


def poll_job(session_id: str) -> dict | None:
    with _lock:
        return _job_results.get(session_id)


def clear_job(session_id: str) -> None:
    with _lock:
        _job_results.pop(session_id, None)
