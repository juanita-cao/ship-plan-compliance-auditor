"""Plan upload, validation and deck segmentation (ADR-F30).

Storage layout (ephemeral, auto-deleted after 24 h):
    <upload_root>/<project_id>/<plan_id>/source.png      normalised upload (PDF pages stitched top to bottom)
    <upload_root>/<project_id>/<plan_id>/meta.json
    <upload_root>/<project_id>/<plan_id>/regions.json    result of segmentation
    <upload_root>/<project_id>/<plan_id>/decks/up_<plan8>_<n>.png + decks.json   after confirm

No model and no paid API is involved: segmentation is a classical XY-cut on whitespace gaps.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image

SERVICE_ROOT = Path(__file__).parent.parent.parent

# ── Upload specification (mirrors UPLOAD_SPEC in the frontend config) ─────────
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 10
MIN_LONG_EDGE = 2000
MAX_LONG_EDGE = 12000
MAX_PIXELS = 100_000_000
PDF_PAGE_LONG_EDGE = 2200
PDF_PAGE_GAP = 150

MAX_PLANS_PER_PROJECT = 5
TTL_SECONDS = 24 * 3600

MAX_REGIONS = 12
MIN_BOX_PX = 100  # smallest user-drawn deck box edge
MIN_REGION_AREA = 0.015  # fraction of the inked sheet area; favour recall, the user can delete extras
MAX_LABEL_LEN = 60

Image.MAX_IMAGE_PIXELS = MAX_PIXELS

_PLAN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_STEM_RE = re.compile(r"^up_([0-9a-f]{8})_(\d+)$")


class PlanError(Exception):
    def __init__(self, status: int, rule: str, message: str):
        super().__init__(message)
        self.status = status
        self.rule = rule
        self.message = message


def upload_root() -> Path:
    return Path(os.environ.get("PVCB_UPLOAD_DIR", SERVICE_ROOT / "data" / "uploads"))


# ── Validation ────────────────────────────────────────────────────────────────

def sniff_kind(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"%PDF-"):
        return "pdf"
    raise PlanError(415, "U1", "Unsupported file type. Use PNG, JPEG or PDF (DWG/DXF are not supported).")


def _flatten(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def _decode_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Image.DecompressionBombError:
        raise PlanError(422, "U3", "Image has too many pixels.")
    except Exception:
        raise PlanError(415, "U1", "The file could not be read as an image.")
    return _flatten(img)


def _rasterise_pdf(data: bytes) -> tuple[Image.Image, int]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
        n = len(pdf)
    except Exception:
        raise PlanError(415, "U1", "The PDF could not be read.")
    if n == 0 or n > MAX_PDF_PAGES:
        raise PlanError(413, "U2", f"PDF must have 1–{MAX_PDF_PAGES} pages (this one has {n}).")
    pages: list[Image.Image] = []
    for i in range(n):
        page = pdf[i]
        w, h = page.get_size()
        scale = PDF_PAGE_LONG_EDGE / max(w, h)
        pages.append(_flatten(page.render(scale=scale).to_pil()))
    width = max(p.width for p in pages)
    height = sum(p.height for p in pages) + PDF_PAGE_GAP * (n - 1)
    if width * height > MAX_PIXELS:
        raise PlanError(422, "U3", "PDF pages are too large to process.")
    sheet = Image.new("RGB", (width, height), (255, 255, 255))
    y = 0
    for p in pages:
        sheet.paste(p, (0, y))
        y += p.height + PDF_PAGE_GAP
    return sheet, n


def validate_and_decode(data: bytes) -> tuple[Image.Image, str, int]:
    kind = sniff_kind(data)
    limit = MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES
    if len(data) > limit:
        raise PlanError(413, "U2", f"File is too large (limit {limit // (1024 * 1024)} MB for {kind.upper()}).")
    if kind == "pdf":
        img, pages = _rasterise_pdf(data)
        return img, kind, pages
    img = _decode_image(data)
    long_edge = max(img.size)
    if long_edge < MIN_LONG_EDGE:
        raise PlanError(422, "U3", f"Resolution too low: long edge {long_edge}px, need at least {MIN_LONG_EDGE}px.")
    if long_edge > MAX_LONG_EDGE:
        raise PlanError(422, "U3", f"Resolution too high: long edge {long_edge}px, maximum is {MAX_LONG_EDGE}px.")
    return img, kind, 1


# ── Storage ───────────────────────────────────────────────────────────────────

def _safe_name(filename: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", Path(filename or "plan").name)[:80] or "plan"


def _plan_dirs(project_id: str | None = None) -> list[Path]:
    root = upload_root()
    if not root.exists():
        return []
    projects = [root / project_id] if project_id else [p for p in root.iterdir() if p.is_dir()]
    return [d for p in projects if p.exists() for d in p.iterdir() if d.is_dir() and _PLAN_ID_RE.match(d.name)]


def _read_meta(d: Path) -> dict | None:
    try:
        return json.loads((d / "meta.json").read_text())
    except Exception:
        return None


def cleanup_expired(now: float | None = None) -> int:
    now = now if now is not None else time.time()
    removed = 0
    for d in _plan_dirs():
        meta = _read_meta(d)
        if meta is None or now - meta.get("created_at", 0) > TTL_SECONDS:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed


def find_plan(plan_id: str) -> Path:
    if not _PLAN_ID_RE.match(plan_id):
        raise PlanError(404, "NF", "Plan not found.")
    for d in _plan_dirs():
        if d.name == plan_id:
            return d
    raise PlanError(404, "NF", "Plan not found.")


def create_plan(project_id: str, filename: str, data: bytes) -> dict:
    cleanup_expired()
    if len(_plan_dirs(project_id)) >= MAX_PLANS_PER_PROJECT:
        raise PlanError(429, "Q1", f"Upload limit reached ({MAX_PLANS_PER_PROJECT} plans per vessel). Delete one first.")
    img, kind, pages = validate_and_decode(data)
    plan_id = uuid.uuid4().hex
    d = upload_root() / project_id / plan_id
    d.mkdir(parents=True)
    img.save(d / "source.png")
    meta = {
        "plan_id": plan_id, "project_id": project_id, "filename": _safe_name(filename), "kind": kind,
        "width": img.width, "height": img.height, "size_bytes": len(data), "pages": pages,
        "created_at": time.time(), "confirmed": False,
    }
    (d / "meta.json").write_text(json.dumps(meta))
    return {k: v for k, v in meta.items() if k not in ("created_at", "confirmed")}


def delete_plan(plan_id: str) -> None:
    shutil.rmtree(find_plan(plan_id), ignore_errors=True)


# ── Segmentation (XY-cut on whitespace gaps) ──────────────────────────────────

@dataclass
class Region:
    id: str
    bbox: list[int]  # x0, y0, x1, y1 in source pixels
    label: str
    confidence: float


_ANALYSIS_EDGE = 1600
_INK_THRESHOLD = 235


def _ink_mask(img: Image.Image) -> tuple[np.ndarray, float]:
    scale = min(1.0, _ANALYSIS_EDGE / max(img.size))
    small = img if scale == 1.0 else img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.BILINEAR)
    arr = np.asarray(small)
    return arr.min(axis=2) < _INK_THRESHOLD, scale


def _best_gap(empty: np.ndarray, min_gap: int) -> tuple[int, int] | None:
    """Longest run of empty lines (not touching the ends) of at least min_gap; returns (start, length)."""
    best: tuple[int, int] | None = None
    n = len(empty)
    i = 0
    while i < n:
        if empty[i]:
            j = i
            while j < n and empty[j]:
                j += 1
            if i > 0 and j < n and (j - i) >= min_gap and (best is None or (j - i) > best[1]):
                best = (i, j - i)
            i = j
        else:
            i += 1
    return best


def _xy_cut(mask: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
    H, W = mask.shape
    out: list[tuple[tuple[int, int, int, int], float]] = []

    def trim(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int] | None:
        sub = mask[y0:y1, x0:x1]
        rows = np.where(sub.sum(axis=1) > max(2, 0.003 * sub.shape[1]))[0]
        cols = np.where(sub.sum(axis=0) > max(2, 0.003 * sub.shape[0]))[0]
        if len(rows) == 0 or len(cols) == 0:
            return None
        return x0 + int(cols[0]), y0 + int(rows[0]), x0 + int(cols[-1]) + 1, y0 + int(rows[-1]) + 1

    def rec(x0: int, y0: int, x1: int, y1: int, conf: float) -> None:
        box = trim(x0, y0, x1, y1)
        if box is None:
            return
        x0, y0, x1, y1 = box
        sub = mask[y0:y1, x0:x1]
        row_empty = sub.sum(axis=1) <= max(2, 0.003 * sub.shape[1])
        col_empty = sub.sum(axis=0) <= max(2, 0.003 * sub.shape[0])
        gy = _best_gap(row_empty, max(6, int(0.02 * H)))
        gx = _best_gap(col_empty, max(6, int(0.02 * W)))
        cand = []
        if gy:
            cand.append(("y", gy, gy[1] / H))
        if gx:
            cand.append(("x", gx, gx[1] / W))
        if not cand:
            out.append(((x0, y0, x1, y1), conf))
            return
        axis, (start, length), rel = max(cand, key=lambda c: c[2])
        c = min(conf, min(1.0, rel / 0.06))
        if axis == "y":
            rec(x0, y0, x1, y0 + start, c)
            rec(x0, y0 + start + length, x1, y1, c)
        else:
            rec(x0, y0, x0 + start, y1, c)
            rec(x0 + start + length, y0, x1, y1, c)

    rec(0, 0, W, H, 1.0)
    return out


def segment_image(img: Image.Image) -> list[Region]:
    mask, scale = _ink_mask(img)
    leaves = _xy_cut(mask)
    if not leaves:
        return [Region("r1", [0, 0, img.width, img.height], "Deck 1", 0.5)]

    H, W = mask.shape
    ink_x0 = min(b[0] for b, _ in leaves); ink_y0 = min(b[1] for b, _ in leaves)
    ink_x1 = max(b[2] for b, _ in leaves); ink_y1 = max(b[3] for b, _ in leaves)
    ink_area = max(1, (ink_x1 - ink_x0) * (ink_y1 - ink_y0))
    kept = [(b, c) for b, c in leaves if (b[2] - b[0]) * (b[3] - b[1]) / ink_area >= MIN_REGION_AREA]
    if not kept:
        kept = [((ink_x0, ink_y0, ink_x1, ink_y1), 0.5)]
    kept.sort(key=lambda bc: -(bc[0][2] - bc[0][0]) * (bc[0][3] - bc[0][1]))
    kept = kept[:MAX_REGIONS]
    if len(kept) == 1:
        kept = [(kept[0][0], 0.5)]
    bucket = max(1, int(0.2 * H))
    kept.sort(key=lambda bc: (bc[0][1] // bucket, bc[0][0]))

    pad_x, pad_y = max(2, int(0.01 * W)), max(2, int(0.01 * H))
    regions: list[Region] = []
    for i, ((x0, y0, x1, y1), conf) in enumerate(kept, start=1):
        bx0 = max(0, x0 - pad_x); by0 = max(0, y0 - pad_y)
        bx1 = min(W, x1 + pad_x); by1 = min(H, y1 + pad_y)
        box = [round(bx0 / scale), round(by0 / scale), min(img.width, round(bx1 / scale)), min(img.height, round(by1 / scale))]
        regions.append(Region(f"r{i}", box, f"Deck {i}", round(float(conf), 2)))
    return regions


def segment_plan(plan_id: str) -> dict:
    d = find_plan(plan_id)
    meta = _read_meta(d) or {}
    with Image.open(d / "source.png") as im:
        regions = segment_image(im.convert("RGB"))
    (d / "regions.json").write_text(json.dumps([asdict(r) for r in regions]))
    return {
        "plan_id": plan_id, "sheet_w": meta.get("width"), "sheet_h": meta.get("height"),
        "regions": [asdict(r) for r in regions], "method": "xy_cut",
    }


def sheet_preview(plan_id: str, max_edge: int = 1600) -> bytes:
    d = find_plan(plan_id)
    with Image.open(d / "source.png") as im:
        im = im.convert("RGB")
        s = min(1.0, max_edge / max(im.size))
        if s < 1.0:
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return buf.getvalue()


def confirm_plan(plan_id: str, decks: list[dict]) -> list[dict]:
    """decks: [{region_id, label}]. Empty list = whole sheet as one deck."""
    d = find_plan(plan_id)
    meta = _read_meta(d) or {}
    if meta.get("confirmed"):
        raise PlanError(409, "CF", "This plan has already been confirmed.")
    try:
        regions = {r["id"]: r for r in json.loads((d / "regions.json").read_text())}
    except Exception:
        raise PlanError(409, "SG", "Run segmentation before confirming.")

    with Image.open(d / "source.png") as src:
        src = src.convert("RGB")
        if not decks:
            selection = [("whole", [0, 0, src.width, src.height], f"{Path(meta.get('filename', 'Plan')).stem[:MAX_LABEL_LEN]}")]
        else:
            seen: set[str] = set()
            selection = []
            for dk in decks:
                rid = dk.get("region_id")
                label = (dk.get("label") or "").strip()
                custom = dk.get("bbox")
                if rid in seen or (custom is None and rid not in regions):
                    raise PlanError(422, "RG", "Unknown or duplicate region.")
                if not label or len(label) > MAX_LABEL_LEN:
                    raise PlanError(422, "LB", f"Each deck needs a name (1–{MAX_LABEL_LEN} characters).")
                if custom is not None:
                    if (len(custom) != 4 or not (0 <= custom[0] < custom[2] <= src.width and 0 <= custom[1] < custom[3] <= src.height)
                            or custom[2] - custom[0] < MIN_BOX_PX or custom[3] - custom[1] < MIN_BOX_PX):
                        raise PlanError(422, "RG", f"Deck box must lie inside the sheet and be at least {MIN_BOX_PX} px each way.")
                seen.add(rid)
                selection.append((rid, custom if custom is not None else regions[rid]["bbox"], label))

        plan8 = plan_id[:8]
        (d / "decks").mkdir(exist_ok=True)
        items = []
        for n, (_, bbox, label) in enumerate(selection, start=1):
            stem = f"up_{plan8}_{n}"
            src.crop(tuple(bbox)).save(d / "decks" / f"{stem}.png")
            items.append({"stem": stem, "label": label})

    (d / "decks.json").write_text(json.dumps(items))
    meta["confirmed"] = True
    (d / "meta.json").write_text(json.dumps(meta))
    return items


# ── Lookups used by the rest of the API ───────────────────────────────────────

def is_uploaded_stem(stem: str) -> bool:
    return bool(_STEM_RE.match(stem))


def uploaded_image_path(project_id: str, stem: str) -> Path | None:
    m = _STEM_RE.match(stem)
    if not m:
        return None
    for d in _plan_dirs(project_id):
        if d.name.startswith(m.group(1)):
            p = d / "decks" / f"{stem}.png"
            if p.exists():
                return p
    return None


def uploaded_decks(project_id: str) -> list[dict]:
    cleanup_expired()
    items: list[tuple[float, dict]] = []
    for d in _plan_dirs(project_id):
        meta = _read_meta(d)
        try:
            decks = json.loads((d / "decks.json").read_text())
        except Exception:
            continue
        for dk in decks:
            items.append((meta.get("created_at", 0) if meta else 0, {**dk, "uploaded": True}))
    return [it for _, it in sorted(items, key=lambda t: t[0])]
