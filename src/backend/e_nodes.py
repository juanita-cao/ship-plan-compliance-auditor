from __future__ import annotations

import base64
import csv
import dataclasses
import io
import json
import logging
import math
import os
import time
from collections import Counter
from pathlib import Path

import cv2
import httpx
import numpy as np
import openai
from PIL import Image

from . import category_lookup
from .schemas import (
    VOTE_THRESHOLD_ACCEPT,
    VOTE_THRESHOLD_WARN,
    CategoryVote,
    D1AccuracyDecision,
    DetectedInstance,
    E3CountResult,
    E4VotingResult,
    E5Report,
    PipelineContext,
)

_RESULTS_ROOT = Path("experiments") / "results"  # fixed — never mutated; subfolders computed from this
_REPORT_OUTPUT_DIR = _RESULTS_ROOT  # current write target — callers may override per run (see experiment_dir)
_E1_TARGET_SHORT: int | None = 800  # normalize short side to this px; None = send at original size


def experiment_dir(image_path: Path, target_short: int) -> Path:
    """One subfolder per (image, resolution) experiment: results/{image_stem}_t{target_short}/."""
    return _RESULTS_ROOT / f"{Path(image_path).stem}_t{target_short}"

logger = logging.getLogger(__name__)


# ─── E1 · Detect · Visual Count Extractor ────────────────────────────────────

_MIME_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def e1_extract_counts(
    image_path: Path,
    prompt: str,
    backend: str,
    run_id: int,
    project_id: str = "demo_ship_a",
) -> E3CountResult:
    if backend not in ("cloud", "local"):
        raise ValueError(f"Unknown backend: {backend!r}. Must be 'cloud' or 'local'.")
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if image_path.is_dir():
        raise ValueError(f"image_path is a directory: {image_path}")

    image_b64, input_size = _e1_upscale_b64(image_path)

    if backend == "cloud":
        model_id = os.environ["OPENAI_VISION_MODEL"]
        mime_type = _MIME_TYPES.get(image_path.suffix.lower(), "image/png")
        return _e1_retry(
            _e1_cloud, image_b64, mime_type, prompt, model_id, run_id, input_size, project_id
        )
    else:
        model_id = os.environ["OLLAMA_VISION_MODEL"]
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return _e1_retry(
            _e1_local, image_b64, prompt, model_id, base_url, run_id, input_size, project_id
        )


def _e1_upscale_b64(image_path: Path) -> tuple[str, tuple[int, int]]:
    img = Image.open(image_path).convert("RGB")
    if _E1_TARGET_SHORT is not None:
        short = min(img.width, img.height)
        if short != _E1_TARGET_SHORT:
            scale = _E1_TARGET_SHORT / short
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode(), (img.width, img.height)


def _e1_retry(fn, *args, max_attempts: int = 3) -> E3CountResult:
    last_exc: BaseException = RuntimeError("unreachable")
    for attempt in range(max_attempts):
        try:
            return fn(*args)
        except Exception as exc:
            last_exc = exc
            logger.warning("E1 attempt %d/%d failed: %s", attempt + 1, max_attempts, exc)
            if attempt < max_attempts - 1:
                time.sleep(min(2**attempt, 10))
    raise RuntimeError(f"E1 failed after {max_attempts} attempts") from last_exc


def _e1_image_detail(model_id: str) -> str:
    if any(v in model_id for v in ("5.5", "5.4")):
        return "original"
    return "high"


def _e1_cloud(
    image_b64: str,
    mime_type: str,
    prompt: str,
    model_id: str,
    run_id: int,
    input_size: tuple[int, int],
    project_id: str,
) -> E3CountResult:
    client = openai.OpenAI(timeout=120.0)
    response = client.responses.create(
        model=model_id,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_b64}",
                        "detail": _e1_image_detail(model_id),
                    },
                ],
            }
        ],
    )
    raw: str = response.output_text
    return _e1_parse_counts(raw, run_id, project_id, input_size)


def _e1_local(
    image_b64: str,
    prompt: str,
    model_id: str,
    base_url: str,
    run_id: int,
    input_size: tuple[int, int],
    project_id: str,
) -> E3CountResult:
    resp = httpx.post(
        f"{base_url}/api/generate",
        json={
            "model": model_id,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    raw: str = resp.json()["response"]
    return _e1_parse_counts(raw, run_id, project_id, input_size)


_INSTANCES_MARKER = "[INSTANCES_JSON]"


def _e1_parse_instances(raw: str, counts_start: int) -> list[DetectedInstance]:
    marker_idx = raw.find(_INSTANCES_MARKER)
    if marker_idx == -1:
        return []
    text = raw[marker_idx + len(_INSTANCES_MARKER) : counts_start].strip()
    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start == -1 or arr_end == -1:
        logger.warning("E1: [INSTANCES_JSON] marker found but no JSON array detected")
        return []
    try:
        raw_list = json.loads(text[arr_start : arr_end + 1])
    except json.JSONDecodeError as exc:
        logger.warning("E1: [INSTANCES_JSON] parse failed: %s", exc)
        return []
    result: list[DetectedInstance] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        center = item.get("center") if isinstance(item.get("center"), list) else None
        try:
            result.append(
                DetectedInstance(
                    instance_id=str(item.get("instance_id", "")),
                    category=str(item.get("category", "unknown")),
                    nearby_text=str(item.get("nearby_text", "")),
                    location_desc=str(item.get("location_desc", "")),
                    center=center,
                )
            )
        except ValueError as exc:
            logger.warning(
                "E1: invalid center skipped for instance %r: %s", item.get("instance_id"), exc
            )
    return result


def _e1_parse_counts(
    raw: str, run_id: int, project_id: str, input_size: tuple[int, int] | None = None
) -> E3CountResult:
    idx = raw.rfind("{")
    if idx == -1:
        raise ValueError("E1: no JSON object found in model response")
    data = json.loads(raw[idx : raw.rfind("}") + 1])
    total: dict[str, int] = {}
    for cat in category_lookup.get_canonical_categories(project_id):
        if cat not in data:
            raise KeyError(f"E1: missing category {cat!r} in model response")
        total[cat] = int(data[cat])
    instances = _e1_parse_instances(raw, idx)
    return E3CountResult(
        total_by_category=total,
        run_id=run_id,
        instances=instances,
        input_image_size=input_size,
        raw_response=raw,
    )


# ─── E2 · Detect · OpenCV Center Refiner ────────────────────────────────────

_BOX_HW: float = 0.030
_BOX_HH: float = 0.045
_SEARCH_HALF_W: float = 3.0 * _BOX_HW
_SEARCH_HALF_H: float = 3.0 * _BOX_HH
_MIN_BLOB_AREA_PX: int = 10
# Distance gate as a fraction of the search-window half-size, not a fixed pixel count —
# a fixed px value (the original calibration was 35px on a_deck, 838x775) silently became
# far too tight on much larger/wider images (e.g. main_deck, 2400x702), where 35px is <1.5%
# of the search window and rejected almost every real blob. 0.464 reproduces the original
# 35px gate exactly on a_deck (35 / (3*_BOX_HW*838)) while scaling correctly elsewhere.
_MAX_DIST_FRAC_OF_WINDOW: float = 0.464
_MAX_BLOB_AREA_FRAC: float = 0.25
_MAX_ASPECT_RATIO: float = 4.0      # reject blobs whose bbox is more elongated than this
_DISPLAY_PAD_PX: int = 5            # padding added around union bbox to include nearby text

_HSV_LOW1 = np.array([0,   80,  80],  dtype=np.uint8)
_HSV_HIGH1 = np.array([10,  255, 255], dtype=np.uint8)
_HSV_LOW2 = np.array([170, 80,  80],  dtype=np.uint8)
_HSV_HIGH2 = np.array([180, 255, 255], dtype=np.uint8)


@dataclasses.dataclass(frozen=True)
class _BlobCandidate:
    area: int
    abs_cx: float
    abs_cy: float
    dist: float
    bbox_w: int
    bbox_h: int
    bbox_abs_x1: int = 0  # absolute pixel coord of blob bbox top-left (for union computation)
    bbox_abs_y1: int = 0


def _e1b_build_red_mask(img_bgr: np.ndarray) -> np.ndarray:
    """E1b-1 Transform: build combined red-channel HSV mask."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    return cv2.bitwise_or(
        cv2.inRange(hsv, _HSV_LOW1, _HSV_HIGH1),
        cv2.inRange(hsv, _HSV_LOW2, _HSV_HIGH2),
    )


def _e1b_find_blobs_in_window(
    red_mask: np.ndarray,
    cx_px: int,
    cy_px: int,
    hw_px: int,
    hh_px: int,
) -> tuple[list[_BlobCandidate], tuple[int, int, int, int]]:
    """E1b-2 Detect: connected components inside the local search window.

    Returns (candidates, (x1, y1, x2, y2)); caller uses window bounds to
    derive max_area from window size.
    """
    h, w = red_mask.shape[:2]
    x1 = max(0, cx_px - hw_px)
    y1 = max(0, cy_px - hh_px)
    x2 = min(w, cx_px + hw_px)
    y2 = min(h, cy_px + hh_px)

    window = red_mask[y1:y2, x1:x2]
    num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(window)

    candidates: list[_BlobCandidate] = []
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        bcx, bcy = centroids[label]
        abs_cx = x1 + bcx
        abs_cy = y1 + bcy
        dist = ((abs_cx - cx_px) ** 2 + (abs_cy - cy_px) ** 2) ** 0.5
        bbox_w = int(stats[label, cv2.CC_STAT_WIDTH])
        bbox_h = int(stats[label, cv2.CC_STAT_HEIGHT])
        bbox_abs_x1 = x1 + int(stats[label, cv2.CC_STAT_LEFT])
        bbox_abs_y1 = y1 + int(stats[label, cv2.CC_STAT_TOP])
        candidates.append(_BlobCandidate(
            area=area, abs_cx=abs_cx, abs_cy=abs_cy,
            dist=dist, bbox_w=bbox_w, bbox_h=bbox_h,
            bbox_abs_x1=bbox_abs_x1, bbox_abs_y1=bbox_abs_y1,
        ))

    return candidates, (x1, y1, x2, y2)


def _e1b_filter_candidates(
    candidates: list[_BlobCandidate],
    max_area: int,
    max_dist_px: float,
    other_centers_px: list[tuple[float, float]] | None = None,
) -> list[_BlobCandidate]:
    """E1b-3 Transform: apply area, distance, shape, and ownership gates.

    other_centers_px (if given) are the pixel centers of every OTHER instance
    in the same image. A candidate blob is rejected if it sits closer to one
    of those other centers than to this instance's own center — this stops
    two nearby instances (e.g. two extinguishers side by side) from both
    unioning in each other's blob and ending up with identical/merged boxes.
    """
    result: list[_BlobCandidate] = []
    for c in candidates:
        if c.area < _MIN_BLOB_AREA_PX or c.area > max_area:
            continue
        if c.dist > max_dist_px:
            continue
        if c.bbox_w > 0 and c.bbox_h > 0:
            if max(c.bbox_w, c.bbox_h) / min(c.bbox_w, c.bbox_h) > _MAX_ASPECT_RATIO:
                continue
        if other_centers_px:
            min_other_dist = min(
                math.hypot(c.abs_cx - ocx, c.abs_cy - ocy)
                for ocx, ocy in other_centers_px
            )
            if min_other_dist < c.dist:
                continue
        result.append(c)
    return result


def _e1b_compute_display_bbox(
    passing: list[_BlobCandidate],
    w_orig: int,
    h_orig: int,
) -> list[float] | None:
    """E1b-4 Transform: union all passing blob bboxes + padding → normalized display_bbox.

    Returns [x1, y1, x2, y2] normalized to [0, 1], or None if no passing blobs.
    Padding (_DISPLAY_PAD_PX) expands the box to include nearby label text.
    """
    if not passing:
        return None
    abs_x1 = min(c.bbox_abs_x1 for c in passing)
    abs_y1 = min(c.bbox_abs_y1 for c in passing)
    abs_x2 = max(c.bbox_abs_x1 + c.bbox_w for c in passing)
    abs_y2 = max(c.bbox_abs_y1 + c.bbox_h for c in passing)
    abs_x1 = max(0, abs_x1 - _DISPLAY_PAD_PX)
    abs_y1 = max(0, abs_y1 - _DISPLAY_PAD_PX)
    abs_x2 = min(w_orig, abs_x2 + _DISPLAY_PAD_PX)
    abs_y2 = min(h_orig, abs_y2 + _DISPLAY_PAD_PX)
    return [
        round(abs_x1 / w_orig, 4),
        round(abs_y1 / h_orig, 4),
        round(abs_x2 / w_orig, 4),
        round(abs_y2 / h_orig, 4),
    ]


def _e1b_standardize_bboxes(
    instances: list[DetectedInstance],
) -> list[DetectedInstance]:
    """E1b-5 Post-process: resize all display_bboxes to the same (max) dimensions.

    Finds the widest and tallest display_bbox across all instances, then
    recenters every instance's box at that size.  Instances that had no
    qualifying blobs (display_bbox=None) also receive a standardized box
    centered on their LLM center, so every instance is displayed consistently.
    Instances with center=None are left unchanged.
    """
    max_w = max_h = 0.0
    for inst in instances:
        if inst.display_bbox is not None:
            x1, y1, x2, y2 = inst.display_bbox
            max_w = max(max_w, x2 - x1)
            max_h = max(max_h, y2 - y1)

    if max_w == 0.0:
        return instances  # no blobs found for any instance — nothing to standardize

    # Never go below the fallback fixed-box size so small blobs stay visible
    hw = max(max_w / 2, _BOX_HW)
    hh = max(max_h / 2, _BOX_HH)
    result: list[DetectedInstance] = []
    for inst in instances:
        if inst.display_bbox is not None:
            x1, y1, x2, y2 = inst.display_bbox
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            method = inst.display_bbox_method
        elif inst.center is not None:
            cx, cy = inst.center
            method = "standardized_no_blobs_found"
        else:
            result.append(inst)
            continue
        result.append(inst.model_copy(update={
            "display_bbox": [
                round(max(0.0, cx - hw), 4),
                round(max(0.0, cy - hh), 4),
                round(min(1.0, cx + hw), 4),
                round(min(1.0, cy + hh), 4),
            ],
            "display_bbox_method": method,
        }))
    return result


def e1b_refine_centers(image_path: Path, result: E3CountResult) -> E3CountResult:
    if not any(inst.center for inst in result.instances):
        return result

    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        logger.warning("E2: could not read image %s — skipping refinement", image_path)
        return result

    h_orig, w_orig = img_bgr.shape[:2]
    red_mask = _e1b_build_red_mask(img_bgr)

    hw_px = int(_SEARCH_HALF_W * w_orig)
    hh_px = int(_SEARCH_HALF_H * h_orig)

    # Pixel centers of every instance with a valid center, keyed by instance_id —
    # used so two nearby instances don't both union in each other's red blob
    # (see _e1b_filter_candidates' other_centers_px gate).
    all_centers_px: dict[str, tuple[float, float]] = {}
    for inst in result.instances:
        if inst.center is None:
            continue
        cx, cy = inst.center
        if 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0:
            all_centers_px[inst.instance_id] = (cx * w_orig, cy * h_orig)

    refined: list[DetectedInstance] = []
    for inst in result.instances:
        if inst.center is None:
            refined.append(inst)
            continue

        cx, cy = inst.center
        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
            logger.warning(
                "E2: instance %r has out-of-range center %s — keeping original",
                inst.instance_id,
                inst.center,
            )
            refined.append(inst)
            continue

        cx_px = int(cx * w_orig)
        cy_px = int(cy * h_orig)
        other_centers_px = [
            c for iid, c in all_centers_px.items() if iid != inst.instance_id
        ]

        candidates, (x1, y1, x2, y2) = _e1b_find_blobs_in_window(
            red_mask, cx_px, cy_px, hw_px, hh_px
        )
        window_area = (x2 - x1) * (y2 - y1)
        max_area = int(_MAX_BLOB_AREA_FRAC * window_area) if window_area > 0 else 0
        max_dist_px = _MAX_DIST_FRAC_OF_WINDOW * min(hw_px, hh_px)

        passing = _e1b_filter_candidates(candidates, max_area, max_dist_px, other_centers_px)
        display_bbox = _e1b_compute_display_bbox(passing, w_orig, h_orig)
        method = "union_red_blobs_near_llm_center" if display_bbox is not None else None
        if display_bbox is None:
            logger.warning(
                "E2: no qualifying red blobs for instance %r (center=%s) — display_bbox unset",
                inst.instance_id,
                inst.center,
            )
        refined.append(inst.model_copy(update={
            "display_bbox": display_bbox,
            "display_bbox_method": method,
        }))

    standardized = _e1b_standardize_bboxes(refined)
    return result.model_copy(update={"instances": standardized})


# ─── E4 · Select · Per-category Majority Voter ───────────────────────────────


def e4_vote_per_category(
    runs: list[E3CountResult],
    n_runs: int,
    project_id: str = "demo_ship_a",
) -> E4VotingResult:
    start = time.time()

    expected = category_lookup.get_canonical_categories(project_id)

    if n_runs <= 0:
        raise ValueError(f"n_runs must be positive, got {n_runs}")
    if len(runs) != n_runs:
        raise ValueError(f"Expected {n_runs} runs but got {len(runs)}")
    for run in runs:
        provided = set(run.total_by_category.keys())
        if provided != expected:
            missing = expected - provided
            extra = provided - expected
            raise ValueError(
                f"Run {run.run_id} total_by_category has invalid keys. "
                f"Missing: {missing!r}. Extra: {extra!r}."
            )

    try:
        votes: dict[str, CategoryVote] = {}

        for category in expected:
            all_counts = [run.total_by_category[category] for run in runs]

            if n_runs == 1:
                votes[category] = CategoryVote(
                    category=category,
                    voted_count=all_counts[0],
                    all_counts=all_counts,
                    majority_freq=1,
                    n_runs=1,
                    ratio=1.0,
                    is_tie=False,
                    tied_candidates=None,
                    vote_mode="single_run",
                    status="ACCEPTED_WITH_WARNING",
                    threshold_accept=VOTE_THRESHOLD_ACCEPT,
                    threshold_warn=VOTE_THRESHOLD_WARN,
                )
                continue

            counter = Counter(all_counts)
            top_two = counter.most_common(2)
            top_count, top_freq = top_two[0]

            is_tie = len(top_two) >= 2 and top_two[0][1] == top_two[1][1]
            ratio = top_freq / n_runs

            if is_tie:
                tied_freq = top_two[0][1]
                tied_candidates = sorted(c for c, f in counter.most_common() if f == tied_freq)
                votes[category] = CategoryVote(
                    category=category,
                    voted_count=None,
                    all_counts=all_counts,
                    majority_freq=tied_freq,
                    n_runs=n_runs,
                    ratio=ratio,
                    is_tie=True,
                    tied_candidates=tied_candidates,
                    vote_mode="voting",
                    status="MANUAL_REVIEW_REQUIRED",
                    threshold_accept=VOTE_THRESHOLD_ACCEPT,
                    threshold_warn=VOTE_THRESHOLD_WARN,
                )
            else:
                if ratio >= VOTE_THRESHOLD_ACCEPT:
                    status = "ACCEPTED"
                elif ratio >= VOTE_THRESHOLD_WARN:
                    status = "ACCEPTED_WITH_WARNING"
                else:
                    status = "MANUAL_REVIEW_REQUIRED"

                votes[category] = CategoryVote(
                    category=category,
                    voted_count=top_count,
                    all_counts=all_counts,
                    majority_freq=top_freq,
                    n_runs=n_runs,
                    ratio=ratio,
                    is_tie=False,
                    tied_candidates=None,
                    vote_mode="voting",
                    status=status,
                    threshold_accept=VOTE_THRESHOLD_ACCEPT,
                    threshold_warn=VOTE_THRESHOLD_WARN,
                )

        result = E4VotingResult(votes=votes)
        logger.info(
            {
                "node": "E4",
                "n_runs": n_runs,
                "accepted": sum(1 for v in votes.values() if v.status == "ACCEPTED"),
                "warning": sum(1 for v in votes.values() if v.status == "ACCEPTED_WITH_WARNING"),
                "manual": sum(1 for v in votes.values() if v.status == "MANUAL_REVIEW_REQUIRED"),
                "ties": sum(1 for v in votes.values() if v.is_tie),
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        return result
    except Exception as e:
        logger.error(
            {
                "node": "E4",
                "status": "error",
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        raise


# ─── E5 · Execute · Report Generator ─────────────────────────────────────────

_VALID_MODES = {"full", "local_only", "cloud_only"}
_7_METRICS = [
    "majority_vote_accuracy_pct",
    "single_run_accuracy_avg_pct",
    "accuracy_gain_pct",
    "image_level_exact_match",
    "auto_accept_rate",
    "accuracy_on_auto_accepted_pct",
    "manual_review_rate",
]


_CAT_SHORT = {
    "extinguisher_CO2_5kg": "CO2_5kg",
    "extinguisher_CO2_5kg_spare": "CO2_5kg_sp",
    "extinguisher_dry_powder_6kg": "DP_6kg",
    "extinguisher_dry_powder_6kg_spare": "DP_6kg_sp",
    "extinguisher_foam_9L": "Foam_9L",
    "extinguisher_foam_9L_spare": "Foam_9L_sp",
}


def _format_summary_table(
    label: str, eval_result, gt: dict[str, int], categories: frozenset[str]
) -> str:
    if eval_result is None or eval_result.voting is None or eval_result.accuracy is None:
        return f"=== SUMMARY TABLE ({label}) ===\n  (no data)\n"

    votes = eval_result.voting.votes
    acc = eval_result.accuracy
    n_runs = len(next(iter(votes.values())).all_counts)
    run_headers = "  ".join(f"R{i + 1:>2}" for i in range(n_runs))
    header = f"{'Category':<32} {'GT':>4}  {run_headers}  {'Voted':>5}  {'Status':<26} {'OK?':>4}"
    sep = "─" * len(header)
    lines = [f"=== SUMMARY TABLE ({label}) ===", header, sep]

    for cat in categories:
        vote = votes[cat]
        per_run = "  ".join(f"{c:>4}" for c in vote.all_counts)
        voted = str(vote.voted_count) if vote.voted_count is not None else "TIE"
        cat_acc = next(a for a in acc.per_category if a.category == cat)
        ok = "✓" if cat_acc.correct else "✗"
        short = _CAT_SHORT.get(cat, cat)
        lines.append(
            f"{short:<32} {gt[cat]:>4}  {per_run}  {voted:>5}  {vote.status:<26} {ok:>4}"
        )

    lines.append(sep)
    lines.append(
        f"Accuracy: {acc.n_correct}/{acc.n_total} ({acc.majority_vote_accuracy_pct:.1f}%)"
        f" | Exact match: {'YES' if acc.image_level_exact_match else 'NO'}"
        f" | Voting gain: {acc.accuracy_gain_pct:+.1f}%"
    )
    lines.append("")
    return "\n".join(lines)


def _format_instance_table(label: str, eval_result) -> str:
    if eval_result is None or not eval_result.runs:
        return f"=== INSTANCE TABLE ({label}) ===\n  (no data)\n"

    all_instances = [
        (r.counts.run_id, inst) for r in eval_result.runs for inst in r.counts.instances
    ]
    if not all_instances:
        return f"=== INSTANCE TABLE ({label}) ===\n  (no instance data — model did not output [INSTANCES_JSON])\n"

    header = f"{'Run':>4}  {'Instance':<10}  {'Category':<30}  {'Nearby Text':<14}  {'Location':<35}  BBox"
    sep = "─" * 115
    lines = [f"=== INSTANCE TABLE ({label}) ===", header, sep]
    for run_id, inst in all_instances:
        center_str = f"[{inst.center[0]:.3f},{inst.center[1]:.3f}]" if inst.center else "—"
        lines.append(
            f"{run_id + 1:>4}  {inst.instance_id:<10}  {_CAT_SHORT.get(inst.category, inst.category):<30}"
            f"  {inst.nearby_text[:14]:<14}  {inst.location_desc[:35]:<35}  {center_str}"
        )
    lines.append("")
    return "\n".join(lines)


def _format_metrics_block(label: str, acc: D1AccuracyDecision | None) -> str:
    if acc is None:
        return f"=== {label} ===\n  (no data)\n"
    lines = [f"=== {label} ==="]
    for m in _7_METRICS:
        lines.append(f"  {m}: {getattr(acc, m)}")
    lines.append("")
    return "\n".join(lines)


def _format_text(ctx: PipelineContext) -> str:
    parts: list[str] = []

    if ctx.report_mode != "full":
        reason = (
            "Cloud backend unavailable."
            if ctx.report_mode == "local_only"
            else "Local backend unavailable."
        )
        parts.append(f"⚠ DEGRADED MODE: {ctx.report_mode} — {reason}\n")

    gt = ctx.ground_truth.counts if ctx.ground_truth is not None else {}
    categories = category_lookup.get_canonical_categories(ctx.project_id)
    local_acc = ctx.local_eval.accuracy if ctx.local_eval else None
    cloud_acc = ctx.cloud_eval.accuracy if ctx.cloud_eval else None

    if ctx.report_mode in ("full", "local_only"):
        parts.append(_format_summary_table("LOCAL", ctx.local_eval, gt, categories))
        parts.append(_format_instance_table("LOCAL", ctx.local_eval))
        parts.append(_format_metrics_block("LOCAL BACKEND METRICS", local_acc))
    if ctx.report_mode in ("full", "cloud_only"):
        parts.append(_format_summary_table("CLOUD", ctx.cloud_eval, gt, categories))
        parts.append(_format_instance_table("CLOUD", ctx.cloud_eval))
        parts.append(_format_metrics_block("CLOUD BACKEND METRICS", cloud_acc))

    if ctx.report_mode == "full" and local_acc and cloud_acc:
        gain_diff = local_acc.accuracy_gain_pct - cloud_acc.accuracy_gain_pct
        parts.append("=== COMPARISON ===")
        parts.append(f"  local majority_vote_accuracy_pct:  {local_acc.majority_vote_accuracy_pct}")
        parts.append(f"  cloud majority_vote_accuracy_pct:  {cloud_acc.majority_vote_accuracy_pct}")
        parts.append(f"  accuracy_gain_pct delta (local-cloud): {gain_diff:.2f}")
        parts.append("")

    return "\n".join(parts)


def _build_summary_table(
    eval_result, gt: dict[str, int], categories: frozenset[str]
) -> list[dict] | None:
    if eval_result is None or eval_result.voting is None or eval_result.accuracy is None:
        return None
    votes = eval_result.voting.votes
    acc_map = {a.category: a for a in eval_result.accuracy.per_category}
    rows = []
    for cat in categories:
        vote = votes[cat]
        rows.append(
            {
                "category": cat,
                "ground_truth": gt[cat],
                "per_run_counts": vote.all_counts,
                "voted": vote.voted_count,
                "ratio": vote.ratio,
                "status": vote.status,
                "correct": acc_map[cat].correct,
            }
        )
    return rows


def _build_instance_table(eval_result) -> list[dict] | None:
    if eval_result is None or not eval_result.runs:
        return None
    rows = []
    for run in eval_result.runs:
        for inst in run.counts.instances:
            rows.append(
                {
                    "run_id": run.counts.run_id,
                    "instance_id": inst.instance_id,
                    "category": inst.category,
                    "nearby_text": inst.nearby_text,
                    "location_desc": inst.location_desc,
                    "center": inst.center,
                    "center_refined": inst.center_refined,
                }
            )
    return rows


def _build_data(ctx: PipelineContext, degraded_reason: str | None) -> dict:
    def _acc_metrics(acc: D1AccuracyDecision | None) -> dict | None:
        if acc is None:
            return None
        return {m: getattr(acc, m) for m in _7_METRICS}

    def _voting_dump(eval_result) -> dict | None:
        if eval_result is None or eval_result.voting is None:
            return None
        return eval_result.voting.model_dump()

    def _accuracy_dump(eval_result) -> dict | None:
        if eval_result is None or eval_result.accuracy is None:
            return None
        return eval_result.accuracy.model_dump()

    gt = ctx.ground_truth.counts if ctx.ground_truth is not None else {}
    categories = category_lookup.get_canonical_categories(ctx.project_id)
    return {
        "metadata": {
            "session_id": ctx.session_id,
            "timestamp": str(ctx.timestamp),
            "image_path": ctx.image_path,
            "prompt_label": ctx.prompt_label,
            "n_runs": ctx.n_runs,
        },
        "summary_table": {
            "local": _build_summary_table(ctx.local_eval, gt, categories),
            "cloud": _build_summary_table(ctx.cloud_eval, gt, categories),
        },
        "instance_table": {
            "local": _build_instance_table(ctx.local_eval),
            "cloud": _build_instance_table(ctx.cloud_eval),
        },
        "metrics": {
            "local": _acc_metrics(ctx.local_eval.accuracy if ctx.local_eval else None),
            "cloud": _acc_metrics(ctx.cloud_eval.accuracy if ctx.cloud_eval else None),
        },
        "voting": {
            "local": _voting_dump(ctx.local_eval),
            "cloud": _voting_dump(ctx.cloud_eval),
        },
        "accuracy": {
            "local": _accuracy_dump(ctx.local_eval),
            "cloud": _accuracy_dump(ctx.cloud_eval),
        },
        "mode": ctx.report_mode,
        "degraded_reason": degraded_reason,
    }


def _write_csvs(ctx: PipelineContext, data: dict) -> list[str]:
    image_stem = Path(ctx.image_path).stem
    prefix = f"{image_stem}_{ctx.session_id[:8]}"
    written: list[str] = []

    for backend in ("local", "cloud"):
        summary_rows = data["summary_table"].get(backend)
        instance_rows = data["instance_table"].get(backend)

        if summary_rows:
            n_runs = len(summary_rows[0]["per_run_counts"])
            run_cols = [f"run_{i + 1}" for i in range(n_runs)]
            fieldnames = [
                "image",
                "backend",
                "category",
                "ground_truth",
                *run_cols,
                "voted",
                "ratio",
                "status",
                "correct",
            ]
            path = _REPORT_OUTPUT_DIR / f"{prefix}_{backend}_summary.csv"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in summary_rows:
                    flat: dict = {"image": image_stem, "backend": backend}
                    flat["category"] = row["category"]
                    flat["ground_truth"] = row["ground_truth"]
                    for i, c in enumerate(row["per_run_counts"]):
                        flat[f"run_{i + 1}"] = c
                    flat["voted"] = row["voted"]
                    flat["ratio"] = round(row["ratio"], 3)
                    flat["status"] = row["status"]
                    flat["correct"] = row["correct"]
                    writer.writerow(flat)
            written.append(str(path))

        if instance_rows:
            fieldnames = [
                "image",
                "backend",
                "run",
                "instance_id",
                "category",
                "nearby_text",
                "location_desc",
                "center_x",
                "center_y",
                "center_refined",
            ]
            path = _REPORT_OUTPUT_DIR / f"{prefix}_{backend}_instances.csv"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in instance_rows:
                    center = row["center"] or []
                    writer.writerow(
                        {
                            "image": image_stem,
                            "backend": backend,
                            "run": row["run_id"] + 1,
                            "instance_id": row["instance_id"],
                            "category": row["category"],
                            "nearby_text": row["nearby_text"],
                            "location_desc": row["location_desc"],
                            "center_x": center[0] if len(center) > 0 else "",
                            "center_y": center[1] if len(center) > 1 else "",
                            "center_refined": row.get("center_refined", False),
                        }
                    )
            written.append(str(path))

    return written


def e5_generate_report(ctx: PipelineContext) -> E5Report:
    start = time.time()

    try:
        if ctx.report_mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid report_mode: {ctx.report_mode!r}. Must be one of {_VALID_MODES}."
            )

        degraded_reason: str | None = None
        if ctx.report_mode == "local_only":
            degraded_reason = "Cloud backend unavailable."
        elif ctx.report_mode == "cloud_only":
            degraded_reason = "Local backend unavailable."

        text = _format_text(ctx)
        data = _build_data(ctx, degraded_reason)

        output_path: str | None = None
        write_status: str = "failed"
        write_error: str | None = None
        csv_paths: list[str] = []
        try:
            _REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            image_stem = Path(ctx.image_path).stem
            file_path = _REPORT_OUTPUT_DIR / f"{image_stem}_{ctx.session_id[:8]}.json"
            file_path.write_text(json.dumps(data, indent=2, default=str))
            output_path = str(file_path)
            csv_paths = _write_csvs(ctx, data)
            write_status = "success"
        except OSError as e:
            write_error = str(e)
            logger.error(
                {
                    "node": "E5",
                    "status": "file_write_error",
                    "error": write_error,
                    "duration_ms": round((time.time() - start) * 1000),
                }
            )

        if csv_paths:
            text += "CSV exports:\n" + "\n".join(f"  {p}" for p in csv_paths) + "\n"

        result = E5Report(
            text=text,
            data=data,
            output_path=output_path,
            report_mode=ctx.report_mode,
            degraded_reason=degraded_reason,
            write_status=write_status,
            write_error=write_error,
        )
        logger.info(
            {
                "node": "E5",
                "status": "success",
                "report_mode": ctx.report_mode,
                "write_status": write_status,
                "output_path": output_path,
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        return result

    except Exception as e:
        logger.error(
            {
                "node": "E5",
                "status": "error",
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        raise
