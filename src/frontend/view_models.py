from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from src.backend import category_lookup
from src.backend.d_nodes import d2_check_compliance
from src.backend.e_nodes import e1b_refine_centers
from src.backend.schemas import (
    ComplianceInput,
    ComplianceResult,
    DetectedInstance,
    E3CountResult,
)


class ResultsViewModel(BaseModel):
    session_id: str
    image_path: str
    instances: list[DetectedInstance]
    total_by_category: dict[str, int]
    compliance_result: ComplianceResult | None = None
    raw_response: str | None = None


def build_results_viewmodel_from_report_data(
    report_data: dict,
    image_path: Path,
    session_id: str,
    project_id: str,
    raw_response: str | None = None,
) -> ResultsViewModel:
    """Build a ViewModel from an eval_runs.report_data JSONB row (run_id=0 only).

    Shared by the mock demo path and the real detection path (both now read
    through db_results) so there is exactly one place that turns a stored
    report into something the UI renders — no separate file-based vs
    in-memory rendering logic to keep in sync.

    E2 (free, local OpenCV) and compliance are recomputed here rather than
    stored, since the JSON report doesn't carry display_bbox or compliance.
    """
    raw = report_data["instance_table"]["cloud"] or []
    instances = [
        DetectedInstance(**{k: v for k, v in inst.items() if k not in ("run_id", "run_idx")})
        for inst in raw
        if inst.get("run_id", 0) == 0
    ]

    categories = category_lookup.get_canonical_categories(project_id)
    counts = Counter(inst.category for inst in instances)
    total_by_category = {cat: counts.get(cat, 0) for cat in categories}

    e3 = E3CountResult(total_by_category=total_by_category, run_id=0, instances=instances)
    refined = e1b_refine_centers(image_path, e3)

    compliance = d2_check_compliance(ComplianceInput(
        total_by_category=total_by_category,
        regulation_set="SOLAS 2020 + FSS Code 2015 (illustrative)",
        is_mock=True,
    ))

    return ResultsViewModel(
        session_id=session_id,
        image_path=str(image_path),
        instances=refined.instances,
        total_by_category=total_by_category,
        compliance_result=compliance,
        raw_response=raw_response,
    )
