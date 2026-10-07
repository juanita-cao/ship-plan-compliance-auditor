"""Pydantic response schemas for the FastAPI layer."""
from __future__ import annotations

from pydantic import BaseModel


class CategoryMeta(BaseModel):
    id: str
    label: str
    color: str


class ImageInfo(BaseModel):
    stem: str
    label: str
    uploaded: bool = False


class ProjectInfo(BaseModel):
    id: str
    label: str
    images: list[ImageInfo]
    categories: list[CategoryMeta]


class ImageResponse(BaseModel):
    data: str  # data:image/png;base64,...


class DetectRequest(BaseModel):
    project_id: str
    image_stem: str


class DetectedInstance(BaseModel):
    id: str
    category: str
    cx: float
    cy: float
    display_bbox: list[float] | None = None  # [x1, y1, x2, y2]
    location_desc: str | None = None
    nearby_text: str | None = None


class ComplianceCheck(BaseModel):
    rule_id: str
    article: str
    description: str
    required: str | None   # e.g. "≥1"
    found: str | None      # e.g. "4"
    status: str            # pass | fail | warning | not_applicable
    verdict: str           # GO | NO_GO | CONDITIONAL | N/A


class ComplianceResult(BaseModel):
    verdict: str           # GO | NO_GO | CONDITIONAL  (mapped from overall_verdict)
    is_mock: bool
    regulation_set: str
    checks: list[ComplianceCheck]


class DetectResult(BaseModel):
    session_id: str
    project_id: str
    image_stem: str
    instances: list[DetectedInstance]
    total_by_category: dict[str, int]
    compliance_result: ComplianceResult | None = None
    raw_response: str | None = None
    is_sample: bool = False
    sample_label: str | None = None


class HealthResponse(BaseModel):
    status: str


class PlanUpload(BaseModel):
    plan_id: str
    project_id: str
    filename: str
    kind: str
    width: int
    height: int
    size_bytes: int
    pages: int


class RegionModel(BaseModel):
    id: str
    bbox: list[int]
    label: str
    confidence: float


class SegmentResult(BaseModel):
    plan_id: str
    sheet_w: int
    sheet_h: int
    regions: list[RegionModel]
    method: str


class DeckSelection(BaseModel):
    region_id: str
    label: str
    bbox: list[int] | None = None  # user-adjusted box on the sheet (ADR-F34); overrides the detected one


class ConfirmRequest(BaseModel):
    decks: list[DeckSelection] = []


class ConfirmResponse(BaseModel):
    images: list[ImageInfo]
