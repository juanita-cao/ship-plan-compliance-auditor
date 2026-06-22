#!/usr/bin/env python3
"""Mock smoke test — full pipeline without real LLM calls.

Verifies end-to-end plumbing (E2→E3→E4→D1→E5→V1→V2) using synthetic E1 output.
Run this before T2 (real E1) to confirm the pipeline produces correct output.

Expected result with a_deck ground truth (CO2_5kg=1, dry_powder_6kg=4):
  - majority_vote: CO2_5kg=1 (3/3 ACCEPTED), dry_powder_6kg=4 (2/3 ACCEPTED_WITH_WARNING)
  - D1 decision: PASS (both match GT)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import patch

from src.backend.pipeline import run_pipeline
from src.backend.schemas import (
    ClassificationConfig,
    E1DetectionResult,
    GroundTruth,
    RawInstance,
)

_CONFIG_PATH = Path("src/backend/configs/classification_rules.json")
_IMAGE = Path("data/images/a_deck.png")
_GT_CSV = Path("data/ground_truth/a_deck.csv")
_N_RUNS = 3

# ─── Mock E1 instances ────────────────────────────────────────────────────────
# Run 0 & 1: CO2_5kg=1, dry_powder_6kg=4  (exact GT match)
# Run 2:     CO2_5kg=1, dry_powder_6kg=3  (one dry_powder boundary_cut → excluded)
# → E4 majority vote: CO2=1 (3/3), dry_powder=4 (2/3) → both match GT → D1 PASS

_R0_R1 = [
    RawInstance(
        instance_id="FE_001",
        nearby_text="CO2 5KG",
        visual_features="red cylinder",
        location_desc="port wall",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_002",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="aft bulkhead",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_003",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="starboard",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_004",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="forward",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_005",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="center",
        boundary_status="clear",
    ),
]

_R2 = [
    RawInstance(
        instance_id="FE_001",
        nearby_text="CO2 5KG",
        visual_features="red cylinder",
        location_desc="port wall",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_002",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="aft bulkhead",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_003",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="starboard",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_004",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="forward",
        boundary_status="clear",
    ),
    RawInstance(
        instance_id="FE_005",
        nearby_text="DRY POWDER 6KG",
        visual_features="blue cylinder",
        location_desc="center",
        boundary_status="boundary_cut",  # excluded by E3 → dry_powder count = 3 this run
    ),
]

_RUNS = [_R0_R1, _R0_R1, _R2]


def _mock_e1(
    image_path: Path,
    prompt: str,
    backend: str,
    run_id: int,
) -> E1DetectionResult:
    return E1DetectionResult(
        instances=_RUNS[run_id % len(_RUNS)],
        run_id=run_id,
        backend=backend,
        api_model_id=f"mock-{backend}-v0",
        prompt_label="mock",
        raw_response='{"mock": true}',
    )


def _load_ground_truth(csv_path: Path) -> GroundTruth:
    counts: dict[str, int] = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            counts[row["category"]] = int(row["count"])
    return GroundTruth(counts=counts)


def main() -> None:
    ground_truth = _load_ground_truth(_GT_CSV)
    config = ClassificationConfig.from_json_file(_CONFIG_PATH)

    print(f"Running mock smoke test  image={_IMAGE}  n_runs={_N_RUNS}")
    print("─" * 60)

    with patch("src.backend.pipeline.e1_extract_instances", side_effect=_mock_e1):
        ctx = run_pipeline(
            image_path=_IMAGE,
            prompt="[mock prompt]",
            ground_truth=ground_truth,
            n_runs=_N_RUNS,
            config=config,
            prompt_label="mock",
        )

    print(ctx.report.text)

    if ctx.report.output_path:
        print(f"Report JSON: {ctx.report.output_path}")

    trace_dir = Path("logs")
    trace_file = trace_dir / f"{ctx.session_id}_trace.json"
    if trace_file.exists():
        print(f"Trace JSON:  {trace_file}")

    if ctx.errors:
        print(f"\nPipeline errors: {ctx.errors}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
