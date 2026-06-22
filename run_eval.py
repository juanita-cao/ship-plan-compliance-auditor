#!/usr/bin/env python3
"""Fire equipment evaluation harness — CLI entry point."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from src.backend.pipeline import run_pipeline
from src.backend.schemas import GroundTruth

_DEFAULT_PROMPT = Path("data/prompts/prompt_cot_counts_demo_ship_a.txt")


def _parse_ground_truth(csv_path: Path, project_id: str) -> GroundTruth:
    counts: dict[str, int] = {}
    try:
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            if not {"category", "count"}.issubset(fieldnames):
                raise ValueError(
                    f"ground truth {csv_path}: CSV must contain columns"
                    f" 'category' and 'count', got: {sorted(fieldnames)!r}"
                )
            for row in reader:
                cat = row["category"]
                raw = row["count"]
                try:
                    counts[cat] = int(raw)
                except ValueError as e:
                    raise ValueError(
                        f"ground truth {csv_path}: non-integer count for category {cat!r}: {raw!r}"
                    ) from e
    except OSError as e:
        raise ValueError(f"ground truth {csv_path}: {e}") from e
    return GroundTruth(counts=counts, project_id=project_id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate fire equipment detection prompts against ground truth."
    )
    parser.add_argument("--image", required=True, type=Path, help="Path to image file.")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=_DEFAULT_PROMPT,
        dest="prompt_file",
        help=f"Path to prompt text file (default: {_DEFAULT_PROMPT}).",
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        type=Path,
        dest="ground_truth",
        help="Path to ground truth CSV (columns: category,count).",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        default=5,
        dest="n_runs",
        help="Number of runs per backend (default: 5).",
    )
    parser.add_argument(
        "--cloud-only",
        action="store_true",
        dest="cloud_only",
        help="Skip local backend (Ollama); run cloud only.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        dest="model",
        help="Override OPENAI_VISION_MODEL env var for this run.",
    )
    parser.add_argument(
        "--target-short",
        type=int,
        default=None,
        dest="target_short",
        help="Override _E1_TARGET_SHORT (short-side px to normalize to; 0 = no resize).",
    )
    parser.add_argument(
        "--save-viz",
        action="store_true",
        dest="save_viz",
        help="Save spotlight PNG(s) to experiments/results/ alongside JSON/CSV.",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        dest="project_id",
        help=(
            "Category set to validate against (ADR-006). Default: inferred from "
            "--ground-truth's parent directory name, e.g. .../demo_ship_b/x.csv -> 'demo_ship_b'."
        ),
    )
    args = parser.parse_args()

    for flag, path in [
        ("--image", args.image),
        ("--prompt-file", args.prompt_file),
        ("--ground-truth", args.ground_truth),
    ]:
        if not path.is_file():
            parser.error(f"{flag}: file not found: {path}")

    if args.n_runs <= 0:
        parser.error(f"--n-runs must be > 0, got {args.n_runs}")

    if args.model:
        os.environ["OPENAI_VISION_MODEL"] = args.model

    import src.backend.e_nodes as _en

    if args.target_short is not None:
        _en._E1_TARGET_SHORT = args.target_short
    target_short = _en._E1_TARGET_SHORT if _en._E1_TARGET_SHORT is not None else 0

    exp_dir = _en.experiment_dir(args.image, target_short)
    exp_dir.mkdir(parents=True, exist_ok=True)
    _en._REPORT_OUTPUT_DIR = exp_dir

    project_id = args.project_id or args.ground_truth.parent.name

    try:
        prompt = args.prompt_file.read_text().strip()
        ground_truth = _parse_ground_truth(args.ground_truth, project_id)
        ctx = run_pipeline(
            image_path=args.image,
            prompt=prompt,
            ground_truth=ground_truth,
            n_runs=args.n_runs,
            prompt_label=args.prompt_file.stem,
            backends=["cloud"] if args.cloud_only else None,
            project_id=project_id,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(ctx.report.text)
    if ctx.report.output_path:
        print(f"Report saved: {ctx.report.output_path}")

    png_path = None
    if args.save_viz:
        from src.viz import save_run_artifacts

        png_path = save_run_artifacts(ctx, exp_dir)
        if png_path:
            print(f"Viz saved:    {png_path}")

    from src.backend.db_results import save_eval_run

    try:
        save_eval_run(
            ctx, target_short, spotlight_png_path=str(png_path) if png_path else None
        )
        print(f"DB row saved: eval_runs.session_id={ctx.session_id}")
    except Exception as e:
        print(f"WARNING: failed to save eval_runs row: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
