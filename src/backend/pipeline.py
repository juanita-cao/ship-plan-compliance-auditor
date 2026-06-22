from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .configs.feature_flags import COMPLIANCE_MODE
from .d_nodes import d1_evaluate_accuracy, d2_check_compliance
from .e_nodes import (
    e1_extract_counts,
    e1b_refine_centers,
    e4_vote_per_category,
    e5_generate_report,
)
from .schemas import (
    BackendEvalResult,
    ComplianceInput,
    GroundTruth,
    PipelineContext,
    SingleRunResult,
)
from .vv import v1_sequence_check, v2_trace_output

logger = logging.getLogger(__name__)


def _run_backend(
    ctx: PipelineContext,
    backend: str,
    prompt: str,
) -> BackendEvalResult:
    image_path = Path(ctx.image_path)
    api_model_id = os.environ.get(
        "OPENAI_VISION_MODEL" if backend == "cloud" else "OLLAMA_VISION_MODEL",
        "unknown",
    )

    def _one_run(run_id: int) -> SingleRunResult:
        counts = e1_extract_counts(image_path, prompt, backend, run_id, ctx.project_id)
        counts = e1b_refine_centers(image_path, counts)
        return SingleRunResult(run_id=run_id, counts=counts)

    runs: list[SingleRunResult] = []
    with ThreadPoolExecutor(max_workers=ctx.n_runs) as pool:
        futures = {pool.submit(_one_run, run_id): run_id for run_id in range(ctx.n_runs)}
        for future in as_completed(futures):
            runs.append(future.result())  # re-raises on E1 hard fail
    runs.sort(key=lambda r: r.run_id)

    e3_results = [r.counts for r in runs]
    voting = e4_vote_per_category(e3_results, ctx.n_runs, ctx.project_id)
    accuracy = (
        d1_evaluate_accuracy(voting, ctx.ground_truth)
        if ctx.ground_truth is not None
        else None
    )

    return BackendEvalResult(
        backend=backend,
        api_model_id=api_model_id,
        status="success",
        runs=runs,
        voting=voting,
        accuracy=accuracy,
    )


def run_pipeline(
    image_path: Path,
    prompt: str,
    ground_truth: GroundTruth,
    n_runs: int,
    prompt_label: str = "default",
    backends: list[str] | None = None,
    project_id: str = "demo_ship_a",
) -> PipelineContext:
    if backends is None:
        backends = ["local", "cloud"]
    if ground_truth is not None and ground_truth.project_id != project_id:
        raise ValueError(
            f"project_id mismatch: run_pipeline got project_id={project_id!r} but "
            f"ground_truth.project_id={ground_truth.project_id!r}."
        )

    pipeline_start = time.time()

    ctx = PipelineContext(
        image_path=str(image_path),
        prompt_label=prompt_label,
        n_runs=n_runs,
        project_id=project_id,
        ground_truth=ground_truth,
    )

    for backend in backends:
        t = time.time()
        try:
            result = _run_backend(ctx, backend, prompt)
            if backend == "local":
                ctx.local_eval = result
            else:
                ctx.cloud_eval = result
            nodes = [f"E4_{backend}"]
            if ctx.ground_truth is not None:
                nodes.append(f"D1_{backend}")
            ctx.completed_nodes.extend(nodes)
            ctx.node_timings[f"{backend}_backend_ms"] = round((time.time() - t) * 1000)
        except Exception as e:
            logger.error({"pipeline": f"{backend}_backend_failed", "error": str(e)})
            failed = BackendEvalResult(
                backend=backend, api_model_id="unknown", status="failed", error_message=str(e)
            )
            if backend == "local":
                ctx.local_eval = failed
            else:
                ctx.cloud_eval = failed
            ctx.errors.append(f"{backend} backend: {e}")

    # ── Determine report_mode ─────────────────────────────────────────────────
    local_ok = ctx.local_eval is not None and ctx.local_eval.status == "success"
    cloud_ok = ctx.cloud_eval is not None and ctx.cloud_eval.status == "success"
    local_skipped = "local" not in backends
    cloud_skipped = "cloud" not in backends

    if local_ok and cloud_ok:
        ctx.report_mode = "full"
    elif local_ok and cloud_skipped:
        ctx.report_mode = "local_only"
    elif cloud_ok and local_skipped:
        ctx.report_mode = "cloud_only"
    elif local_ok:
        ctx.report_mode = "local_only"
    elif cloud_ok:
        ctx.report_mode = "cloud_only"
    else:
        raise RuntimeError("Both backends failed — no report can be generated.")

    # ── D2 · Compliance ───────────────────────────────────────────────────────
    if COMPLIANCE_MODE != "off":
        primary = ctx.cloud_eval if ctx.cloud_eval and ctx.cloud_eval.status == "success" else ctx.local_eval
        if primary and primary.voting:
            total_by_category = {
                cat: (v.voted_count or 0)
                for cat, v in primary.voting.votes.items()
            }
            try:
                ctx.compliance_result = d2_check_compliance(ComplianceInput(
                    total_by_category=total_by_category,
                    regulation_set="SOLAS 2020 + FSS Code 2015 (illustrative)",
                    is_mock=(COMPLIANCE_MODE == "mock"),
                ))
                ctx.completed_nodes.append("D2")
            except Exception as exc:
                logger.warning({"node": "D2", "status": "skipped", "reason": str(exc)})

    # ── E5 ────────────────────────────────────────────────────────────────────
    ctx.report = e5_generate_report(ctx)
    ctx.completed_nodes.append("E5")

    # ── V&V ───────────────────────────────────────────────────────────────────
    ctx.node_timings["total_ms"] = round((time.time() - pipeline_start) * 1000)
    v1_report = v1_sequence_check(ctx)
    v2_trace_output(ctx, v1_report)
    logger.info(
        {
            "pipeline": "run_pipeline",
            "status": "success",
            "report_mode": ctx.report_mode,
            "session_id": ctx.session_id,
            "duration_ms": ctx.node_timings["total_ms"],
        }
    )
    return ctx


def run_detection(
    image_path: Path,
    prompt: str,
    n_runs: int = 5,
    prompt_label: str = "default",
    backends: list[str] | None = None,
    project_id: str = "demo_ship_a",
) -> PipelineContext:
    """Production entry point: no ground truth, D1 skipped. For frontend use."""
    if backends is None:
        backends = ["cloud"]
    return run_pipeline(
        image_path=image_path,
        prompt=prompt,
        ground_truth=None,
        n_runs=n_runs,
        prompt_label=prompt_label,
        backends=backends,
        project_id=project_id,
    )
