#!/usr/bin/env python3
"""Visual smoke test for render_spotlight() using pre-generated a_deck JSON.

Loads instances from experiments/results/a_deck_963c2d26.json (no API calls),
renders three spotlight variants, and saves PNGs to experiments/results/.

Exit 0 on pass, 1 on any failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.backend.e_nodes import e1b_refine_centers
from src.backend.schemas import DetectedInstance, E3CountResult
from src.viz import render_spotlight

_JSON = Path("experiments/results/a_deck_963c2d26.json")
_IMAGE = Path("data/images/a_deck.png")
_OUT_DIR = Path("experiments/results")

_CASES: list[tuple[str, dict]] = [
    ("a_deck_viz_all",      {}),
    ("a_deck_viz_cat_dp",   {"selected_category": "extinguisher_dry_powder_6kg"}),
    ("a_deck_viz_inst_co2", {"selected_instance_id": "instance_2"}),
]


def _load_instances(json_path: Path) -> list[DetectedInstance]:
    data = json.loads(json_path.read_text())
    rows = data["instance_table"]["cloud"] or []
    instances: list[DetectedInstance] = []
    for row in rows:
        instances.append(DetectedInstance(
            instance_id=row["instance_id"],
            category=row["category"],
            nearby_text=row["nearby_text"],
            location_desc=row["location_desc"],
            center=row.get("center"),
            center_refined=row.get("center_refined", False),
        ))
    return instances


def main() -> None:
    errors: list[str] = []

    if not _JSON.exists():
        print(f"FAIL  source JSON not found: {_JSON}", file=sys.stderr)
        sys.exit(1)
    if not _IMAGE.exists():
        print(f"FAIL  image not found: {_IMAGE}", file=sys.stderr)
        sys.exit(1)

    raw_instances = _load_instances(_JSON)

    # apply e2 refinement on the raw LLM centers (no API call needed)
    e3 = E3CountResult(total_by_category={}, run_id=0, instances=raw_instances)
    e3_refined = e1b_refine_centers(_IMAGE, e3)
    instances = e3_refined.instances

    print(f"Loaded {len(raw_instances)} instances from {_JSON.name}, e2 applied:")
    for inst in instances:
        ctr = f"[{inst.center[0]:.3f},{inst.center[1]:.3f}]" if inst.center else "—"
        if inst.display_bbox is not None:
            x1, y1, x2, y2 = inst.display_bbox
            bbox_str = f"[{x1:.3f},{y1:.3f},{x2:.3f},{y2:.3f}]"
        else:
            bbox_str = "—"
        print(f"  {inst.instance_id:<12}  center={ctr}  display_bbox={bbox_str}")

    print()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    for stem, kwargs in _CASES:
        out_path = _OUT_DIR / f"{stem}.png"
        try:
            img = render_spotlight(_IMAGE, instances, **kwargs)
            img.save(out_path)
            w, h = img.size
            print(f"PASS  {stem:<30}  {w}×{h}  → {out_path}")
        except Exception as exc:
            errors.append(f"{stem}: {exc}")
            print(f"FAIL  {stem:<30}  {exc}", file=sys.stderr)

    print()
    if errors:
        print(f"{len(errors)} failure(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    print(f"All {len(_CASES)} smoke tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
