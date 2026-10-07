"""All route handlers for the compliance auditor API."""
from __future__ import annotations

import base64
import io
import logging
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.api import fixtures, plans
from backend.api.schemas import (
    ComplianceCheck,
    ComplianceResult,
    DetectedInstance,
    DetectRequest,
    DetectResult,
    HealthResponse,
    ImageResponse,
    ProjectInfo,
)
from src.backend.d_nodes import d2_check_compliance
from src.backend.e_nodes import e1b_refine_centers
from src.backend.schemas import (
    ComplianceInput,
    E3CountResult,
)
from src.backend.schemas import (
    DetectedInstance as CoreDetectedInstance,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _image_to_base64(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:image/png;base64,{b64}"


def _pil_to_base64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _build_detect_result(project_id: str, image_stem: str) -> DetectResult:
    data = fixtures.load_fixture(project_id, image_stem)
    categories = fixtures.categories_for(project_id)
    img_path = fixtures.image_path(project_id, image_stem)

    raw = data.get("instance_table", {}).get("cloud") or []
    core_instances = [
        CoreDetectedInstance(**{k: v for k, v in inst.items() if k not in ("run_id", "run_idx")})
        for inst in raw
        if inst.get("run_id", 0) == 0
    ]

    counts = Counter(inst.category for inst in core_instances)
    total_by_category = {cat: counts.get(cat, 0) for cat in categories}

    e3 = E3CountResult(total_by_category=total_by_category, run_id=0, instances=core_instances)
    refined = e1b_refine_centers(img_path, e3)

    compliance_core = d2_check_compliance(ComplianceInput(
        total_by_category=total_by_category,
        regulation_set="SOLAS 2020 + FSS Code 2015 (illustrative)",
        is_mock=True,
    ))

    api_instances = [
        DetectedInstance(
            id=inst.instance_id,
            category=inst.category,
            cx=inst.center[0] if inst.center else 0.0,
            cy=inst.center[1] if inst.center else 0.0,
            display_bbox=list(inst.display_bbox) if inst.display_bbox else None,
            location_desc=inst.location_desc,
            nearby_text=inst.nearby_text,
        )
        for inst in refined.instances
    ]

    compliance = None
    if compliance_core is not None:
        compliance = ComplianceResult(
            verdict=compliance_core.overall_verdict,
            is_mock=compliance_core.is_mock,
            regulation_set=compliance_core.regulation_set,
            checks=[
                ComplianceCheck(
                    rule_id=c.rule_id,
                    article=c.article,
                    description=c.description,
                    required=c.required,
                    found=c.found,
                    status=c.status,
                    verdict=c.verdict,
                )
                for c in compliance_core.checks
            ],
        )

    session_id = data.get("metadata", {}).get("session_id", f"fixture-{project_id}-{image_stem}")
    raw_response = fixtures.load_trace(project_id, image_stem)
    return DetectResult(
        session_id=session_id,
        project_id=project_id,
        image_stem=image_stem,
        instances=api_instances,
        total_by_category=total_by_category,
        compliance_result=compliance,
        raw_response=raw_response,
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.get("/projects", response_model=list[ProjectInfo])
def get_projects():
    return [ProjectInfo(**p) for p in fixtures.list_projects()]


@router.get("/image/{project_id}/{image_stem}", response_model=ImageResponse)
def get_image(project_id: str, image_stem: str):
    path = fixtures.image_path(project_id, image_stem)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {project_id}/{image_stem}")
    return ImageResponse(data=_image_to_base64(path))


_SAMPLE = ("demo_ship_a", "a_deck")
_SAMPLE_LABEL = "Demo Ship A · A Deck"


def _sample_result_for(project_id: str, image_stem: str) -> DetectResult:
    """Uploaded decks get a clearly labelled sample result: no model is connected in the demo."""
    if not fixtures.image_path(project_id, image_stem).exists():
        raise FileNotFoundError(f"No uploaded deck {project_id!r}/{image_stem!r}")
    base = _build_detect_result(*_SAMPLE)
    return base.model_copy(update={
        "project_id": project_id,
        "image_stem": image_stem,
        "session_id": f"sample-{image_stem}",
        "raw_response": None,
        "is_sample": True,
        "sample_label": _SAMPLE_LABEL,
    })


@router.post("/detect", response_model=DetectResult)
def detect(req: DetectRequest):
    try:
        if plans.is_uploaded_stem(req.image_stem):
            return _sample_result_for(req.project_id, req.image_stem)
        return _build_detect_result(req.project_id, req.image_stem)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("detect failed: %s/%s", req.project_id, req.image_stem)
        raise HTTPException(status_code=500, detail="Detection failed")


@router.get("/spotlight/{project_id}/{image_stem}", response_model=ImageResponse)
def get_spotlight(
    project_id: str,
    image_stem: str,
    category: str | None = None,
    instance_id: str | None = None,
):
    from src.frontend.spotlight import render_spotlight_node
    from src.frontend.view_models import ResultsViewModel

    sample_mode = plans.is_uploaded_stem(image_stem)
    if sample_mode and not fixtures.image_path(project_id, image_stem).exists():
        raise HTTPException(status_code=404, detail="Uploaded deck not found")
    try:
        result = _build_detect_result(*_SAMPLE) if sample_mode else _build_detect_result(project_id, image_stem)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Build a minimal ResultsViewModel for the spotlight renderer
    core_instances = [
        CoreDetectedInstance(
            instance_id=inst.id,
            category=inst.category,
            center=[inst.cx, inst.cy],
            display_bbox=inst.display_bbox,
            nearby_text=inst.nearby_text or "",
            location_desc=inst.location_desc or "",
        )
        for inst in result.instances
    ]
    img_path = str(fixtures.image_path(*_SAMPLE) if sample_mode else fixtures.image_path(project_id, image_stem))
    vm = ResultsViewModel(
        session_id=result.session_id,
        image_path=img_path,
        instances=core_instances,
        total_by_category=result.total_by_category,
    )

    img = render_spotlight_node(vm, selected_category=category, selected_instance_id=instance_id)
    return ImageResponse(data=_pil_to_base64(img))
