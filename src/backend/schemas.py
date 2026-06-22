from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.backend import category_lookup

# ─── Constants ────────────────────────────────────────────────────────────────

# ADR-006: canonical categories are now looked up per project_id from Postgres
# (see category_lookup.py). This tuple is kept only as a stable reference for
# demo_ship_a — the original dataset and the default project_id — e.g. for
# building fixture counts dicts in tests. It no longer drives validation.
CANONICAL_CATEGORIES: tuple[str, ...] = (
    "extinguisher_CO2_5kg",
    "extinguisher_CO2_5kg_spare",
    "extinguisher_dry_powder_6kg",
    "extinguisher_dry_powder_6kg_spare",
    "extinguisher_foam_9L",
    "extinguisher_foam_9L_spare",
)
CANONICAL_CATEGORY_SET: frozenset[str] = frozenset(CANONICAL_CATEGORIES)

VOTE_THRESHOLD_ACCEPT: float = 0.75
VOTE_THRESHOLD_WARN: float = 0.50

# ─── Input Models ─────────────────────────────────────────────────────────────


class GroundTruth(BaseModel):
    project_id: str = "demo_ship_a"
    counts: dict[str, int]
    image_id: str | None = None

    @model_validator(mode="after")
    def _validate_canonical_categories(self) -> GroundTruth:
        provided = set(self.counts.keys())
        expected = category_lookup.get_canonical_categories(self.project_id)
        if provided == expected:
            return self
        missing = expected - provided
        extra = provided - expected
        raise ValueError(
            f"GroundTruth for project_id={self.project_id!r} must contain exactly "
            f"its canonical categories. Missing: {missing!r}. Extra: {extra!r}."
        )


# ─── E1 / E3 (counts + instances) ────────────────────────────────────────────


class DetectedInstance(BaseModel):
    instance_id: str
    category: str
    nearby_text: str
    location_desc: str
    # LLM-provided center of the extinguisher cylinder symbol, normalized 0–1
    center: list[float] | None = None  # [cx, cy]
    center_refined: bool = False  # reserved; currently unused (E2 uses display_bbox instead)
    # E2 output: union of qualifying red blob bounding boxes near the LLM center
    display_bbox: list[float] | None = None  # [x1, y1, x2, y2] normalized 0–1
    display_bbox_method: str | None = None   # e.g. "union_red_blobs_near_llm_center"

    @field_validator("center")
    @classmethod
    def _validate_center(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != 2:
            raise ValueError(f"center must have exactly 2 elements [cx, cy], got {len(v)}")
        cx, cy = v
        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
            raise ValueError(f"center must satisfy 0<=cx<=1 and 0<=cy<=1, got {v}")
        return v


class E3CountResult(BaseModel):
    total_by_category: dict[str, int]
    run_id: int
    instances: list[DetectedInstance] = Field(default_factory=list)
    # (w, h) of the image actually sent to the model (after resize); center coords are relative to this
    input_image_size: tuple[int, int] | None = None
    # Full raw text response from the model (STEP1-4 reasoning trace + final JSON).
    # None for local/Ollama runs that don't capture it, or when not requested.
    raw_response: str | None = None


# ─── E4 ───────────────────────────────────────────────────────────────────────


class CategoryVote(BaseModel):
    category: str
    voted_count: int | None  # None when is_tie=True
    all_counts: list[int]
    majority_freq: int
    n_runs: int
    ratio: float
    is_tie: bool
    tied_candidates: list[int] | None = None
    vote_mode: Literal["voting", "single_run"] = "voting"
    status: Literal["ACCEPTED", "ACCEPTED_WITH_WARNING", "MANUAL_REVIEW_REQUIRED"]
    threshold_accept: float = VOTE_THRESHOLD_ACCEPT
    threshold_warn: float = VOTE_THRESHOLD_WARN


class E4VotingResult(BaseModel):
    votes: dict[str, CategoryVote]


# ─── D1 ───────────────────────────────────────────────────────────────────────


class CategoryAccuracy(BaseModel):
    category: str
    ground_truth: int
    voted_count: int | None
    correct: bool
    vote_status: str


class D1AccuracyDecision(BaseModel):
    per_category: list[CategoryAccuracy]
    n_correct: int
    n_total: int
    majority_vote_accuracy_pct: float
    single_run_accuracy_avg_pct: float
    accuracy_gain_pct: float
    image_level_exact_match: bool
    auto_accept_rate: float
    accuracy_on_auto_accepted_pct: float
    manual_review_rate: float
    decision: Literal["PASS", "FAIL", "PARTIAL"]
    reason: str
    rule_triggered: str
    inputs_snapshot: dict[str, Any]


# ─── E5 ───────────────────────────────────────────────────────────────────────


class E5Report(BaseModel):
    text: str
    data: dict[str, Any]
    output_path: str | None = None
    report_mode: Literal["full", "local_only", "cloud_only"]
    degraded_reason: str | None = None
    write_status: Literal["success", "failed"]
    write_error: str | None = None


# ─── Pipeline State ───────────────────────────────────────────────────────────


class SingleRunResult(BaseModel):
    run_id: int
    counts: E3CountResult


class BackendEvalResult(BaseModel):
    backend: Literal["local", "cloud"]
    api_model_id: str
    status: Literal["success", "failed"]
    error_message: str | None = None
    runs: list[SingleRunResult] = Field(default_factory=list)
    voting: E4VotingResult | None = None
    accuracy: D1AccuracyDecision | None = None


class PipelineContext(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    image_path: str
    prompt_label: str
    n_runs: int
    # Lives on ctx (not just on GroundTruth) because production/detection mode
    # has no GroundTruth but still needs a category set for E1/E4 (ADR-006).
    project_id: str = "demo_ship_a"
    ground_truth: GroundTruth | None = None  # None in production/detection mode; required for eval
    local_eval: BackendEvalResult | None = None
    cloud_eval: BackendEvalResult | None = None
    report_mode: Literal["full", "local_only", "cloud_only"] = "full"
    compliance_result: ComplianceResult | None = None
    report: E5Report | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    node_timings: dict[str, float] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


# ─── D2 · Compliance ─────────────────────────────────────────────────────────


class ComplianceInput(BaseModel):
    total_by_category: dict[str, int]
    regulation_set: str
    is_mock: bool
    space_type: Literal["accommodation"] | None = None


class ComplianceCheck(BaseModel):
    rule_id: str
    article: str
    description: str
    status: Literal["pass", "fail", "warning", "not_applicable"]
    required: str | None
    found: str | None
    verdict: Literal["GO", "NO_GO", "CONDITIONAL", "N/A"]
    is_mock_rule: bool


class ComplianceResult(BaseModel):
    overall_verdict: Literal["GO", "NO_GO", "CONDITIONAL"]
    checks: list[ComplianceCheck]
    regulation_set: str
    is_mock: bool
    counts_snapshot: dict[str, int]


# ─── V&V ─────────────────────────────────────────────────────────────────────


class V1Report(BaseModel):
    is_clean: bool
    missing_nodes: list[str]
    warnings: list[str]


class V2Trace(BaseModel):
    session_id: str
    output_path: str
