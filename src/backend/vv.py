from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .schemas import PipelineContext, V1Report, V2Trace

logger = logging.getLogger(__name__)

_TRACE_OUTPUT_DIR = Path("logs")

_REQUIRED_NODES: dict[str, list[str]] = {
    "full": ["E4_local", "D1_local", "E4_cloud", "D1_cloud", "E5"],
    "local_only": ["E4_local", "D1_local", "E5"],
    "cloud_only": ["E4_cloud", "D1_cloud", "E5"],
}

_KNOWN_NODES: frozenset[str] = frozenset({"E4_local", "D1_local", "E4_cloud", "D1_cloud", "E5"})

_ORDER_CONSTRAINTS: list[tuple[str, str]] = [
    ("E4_local", "D1_local"),
    ("E4_cloud", "D1_cloud"),
]


# ─── V1 · Detect · Sequence Verifier ─────────────────────────────────────────


def v1_sequence_check(ctx: PipelineContext) -> V1Report:
    start = time.time()

    if ctx.report_mode not in _REQUIRED_NODES:
        raise ValueError(
            f"Invalid report_mode: {ctx.report_mode!r}. Must be one of {set(_REQUIRED_NODES)}."
        )

    completed = ctx.completed_nodes
    required = _REQUIRED_NODES[ctx.report_mode]
    completed_set = set(completed)

    missing_nodes: list[str] = []
    warnings: list[str] = []
    is_clean = True

    for node in required:
        if node not in completed_set:
            missing_nodes.append(node)
            is_clean = False

    for dep, dependent in _ORDER_CONSTRAINTS:
        if dep in completed_set and dependent in completed_set:
            dep_idx = next(i for i, n in enumerate(completed) if n == dep)
            dependent_idx = next(i for i, n in enumerate(completed) if n == dependent)
            if dependent_idx < dep_idx:
                is_clean = False
                warnings.append(
                    f"Order violation: {dependent!r} appears before {dep!r} in completed_nodes."
                )

    seen: set[str] = set()
    for node in completed:
        if node not in _KNOWN_NODES:
            is_clean = False
            warnings.append(f"Unknown node in completed_nodes: {node!r}.")
        if node in seen:
            warnings.append(f"Duplicate node in completed_nodes: {node!r}.")
        else:
            seen.add(node)

    if ctx.report_mode == "local_only":
        warnings.append("Degraded mode (local_only): E4_cloud and D1_cloud were not run.")
    elif ctx.report_mode == "cloud_only":
        warnings.append("Degraded mode (cloud_only): E4_local and D1_local were not run.")

    result = V1Report(is_clean=is_clean, missing_nodes=missing_nodes, warnings=warnings)
    logger.info(
        {
            "node": "V1",
            "status": "success",
            "is_clean": is_clean,
            "missing": len(missing_nodes),
            "warnings": len(warnings),
            "duration_ms": round((time.time() - start) * 1000),
        }
    )
    return result


# ─── V2 · Transform · Trace Output ───────────────────────────────────────────


def v2_trace_output(ctx: PipelineContext, v1_report: V1Report) -> V2Trace:
    start = time.time()

    try:
        trace = {
            "session_id": ctx.session_id,
            "timestamp": str(ctx.timestamp),
            "completed_nodes": ctx.completed_nodes,
            "node_timings": ctx.node_timings,
            "errors": ctx.errors,
            "report_mode": ctx.report_mode,
            "verification": {
                "is_clean": v1_report.is_clean,
                "missing_nodes": v1_report.missing_nodes,
                "warnings": v1_report.warnings,
            },
        }

        _TRACE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        file_path = _TRACE_OUTPUT_DIR / f"{ctx.session_id}_trace.json"
        file_path.write_text(json.dumps(trace, indent=2, default=str))

        result = V2Trace(session_id=ctx.session_id, output_path=str(file_path))
        logger.info(
            {
                "node": "V2",
                "status": "success",
                "output_path": str(file_path),
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        return result

    except Exception as e:
        logger.error(
            {
                "node": "V2",
                "status": "error",
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        raise
