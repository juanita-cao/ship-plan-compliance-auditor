"""Plan upload + segmentation endpoints (ADR-F30)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, UploadFile

from backend.api import fixtures, plans
from backend.api.schemas import ConfirmRequest, ConfirmResponse, ImageInfo, ImageResponse, PlanUpload, SegmentResult

router = APIRouter()


def _raise(e: plans.PlanError):
    raise HTTPException(status_code=e.status, detail={"rule": e.rule, "message": e.message})


@router.post("/projects/{project_id}/plans", response_model=PlanUpload)
async def upload_plan(project_id: str, file: UploadFile):
    if not fixtures.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Unknown project")
    data = await file.read(plans.MAX_PDF_BYTES + 1)
    try:
        return plans.create_plan(project_id, file.filename or "plan", data)
    except plans.PlanError as e:
        _raise(e)


@router.post("/plans/{plan_id}/segment", response_model=SegmentResult)
def segment(plan_id: str):
    try:
        return plans.segment_plan(plan_id)
    except plans.PlanError as e:
        _raise(e)


@router.get("/plans/{plan_id}/sheet", response_model=ImageResponse)
def sheet(plan_id: str):
    try:
        raw = plans.sheet_preview(plan_id)
    except plans.PlanError as e:
        _raise(e)
    return ImageResponse(data="data:image/jpeg;base64," + base64.b64encode(raw).decode())


@router.post("/plans/{plan_id}/confirm", response_model=ConfirmResponse)
def confirm(plan_id: str, req: ConfirmRequest):
    try:
        items = plans.confirm_plan(plan_id, [d.model_dump() for d in req.decks])
    except plans.PlanError as e:
        _raise(e)
    return ConfirmResponse(images=[ImageInfo(stem=i["stem"], label=i["label"], uploaded=True) for i in items])


@router.delete("/plans/{plan_id}", status_code=204)
def delete(plan_id: str):
    try:
        plans.delete_plan(plan_id)
    except plans.PlanError as e:
        _raise(e)
