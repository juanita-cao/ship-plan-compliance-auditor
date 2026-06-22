"""Image visualisation utilities for ship_plan_auditor."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .backend.schemas import DetectedInstance

# Overlay darkness: 0 = transparent, 255 = fully black. 160 ≈ 63% opacity.
_DIM_ALPHA = 160
_DIM_COLOR = (30, 30, 30, _DIM_ALPHA)

# Border drawn around each highlighted box (pixels in output image space).
_BORDER_WIDTH = 3

# Fixed half-size of the spotlight box around each instance center.
# hw/hh are fractions of image width/height; calibrated on poop_deck.
_BOX_HW = 0.030
_BOX_HH = 0.045

_CATEGORY_COLORS: dict[str, str] = {
    # demo_ship_a (6 categories incl. spares)
    "extinguisher_CO2_5kg": "#0FC6C2",
    "extinguisher_CO2_5kg_spare": "#0FC6C2",
    "extinguisher_dry_powder_6kg": "#FF7D00",
    "extinguisher_dry_powder_6kg_spare": "#FF7D00",
    "extinguisher_foam_9L": "#1664FF",
    "extinguisher_foam_9L_spare": "#1664FF",
    # demo_ship_b (4 categories, no spares) — extinguisher_CO2_5kg shared with demo_ship_a above
    "extinguisher_DCP_5kg": "#FF7D00",
    "extinguisher_wheeld_foam_45L": "#1664FF",
    "extinguisher_water_9L": "#7B61FF",
}
_FALLBACK_COLOR = "#F5A623"


def _hex_to_rgba(hex_color: str) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255


def render_spotlight(
    image_path: Path,
    instances: list[DetectedInstance],
    *,
    selected_category: str | None = None,
    selected_instance_id: str | None = None,
) -> Image.Image:
    """Return a PIL image with a spotlight effect.

    Highlighted instances appear at full brightness; everything else is covered
    by a semi-transparent dark overlay.

    Selection priority:
    - selected_instance_id → highlight that one instance only
    - selected_category    → highlight all instances of that category
    - both None            → highlight all instances that have a center
    """
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    if selected_instance_id is not None:
        highlighted = [i for i in instances if i.instance_id == selected_instance_id and i.center]
    elif selected_category is not None:
        highlighted = [i for i in instances if i.category == selected_category and i.center]
    else:
        highlighted = [i for i in instances if i.center]

    # Dim the full image
    overlay = Image.new("RGBA", (w, h), _DIM_COLOR)
    dimmed = Image.alpha_composite(img, overlay)

    def _box_px(inst: DetectedInstance) -> tuple[int, int, int, int]:
        if inst.display_bbox is not None:
            x1n, y1n, x2n, y2n = inst.display_bbox
            return (max(0, int(x1n * w)), max(0, int(y1n * h)),
                    min(w, int(x2n * w)), min(h, int(y2n * h)))
        assert inst.center is not None
        cx, cy = inst.center
        return (
            max(0, int((cx - _BOX_HW) * w)),
            max(0, int((cy - _BOX_HH) * h)),
            min(w, int((cx + _BOX_HW) * w)),
            min(h, int((cy + _BOX_HH) * h)),
        )

    # Restore original pixels inside each highlighted box
    for inst in highlighted:
        px1, py1, px2, py2 = _box_px(inst)
        if px2 <= px1 or py2 <= py1:
            continue
        dimmed.paste(img.crop((px1, py1, px2, py2)), (px1, py1))

    # Draw colored border around each box
    draw = ImageDraw.Draw(dimmed)
    for inst in highlighted:
        px1, py1, px2, py2 = _box_px(inst)
        color = _hex_to_rgba(_CATEGORY_COLORS.get(inst.category, _FALLBACK_COLOR))
        draw.rectangle([px1, py1, px2, py2], outline=color, width=_BORDER_WIDTH)

    return dimmed.convert("RGB")


def save_run_artifacts(ctx, output_dir: Path) -> Path | None:
    """Write spotlight PNG(s) + raw_response.txt(s) for a finished pipeline run.

    Shared by run_eval.py (--save-viz) and the live frontend's real-detection
    path, so both produce the same on-disk artifacts alongside their eval_runs
    DB row. Returns the cloud spotlight PNG path if one was written, else None.
    """
    image_path = Path(ctx.image_path)
    image_stem = image_path.stem
    prefix = f"{image_stem}_{ctx.session_id[:8]}"
    cloud_png_path: Path | None = None

    for backend, eval_result in [("cloud", ctx.cloud_eval), ("local", ctx.local_eval)]:
        if eval_result is None or eval_result.status != "success" or not eval_result.runs:
            continue
        counts = eval_result.runs[0].counts
        raw_response = counts.raw_response
        if raw_response:
            txt_path = output_dir / f"{prefix}_{backend}_raw_response.txt"
            txt_path.write_text(raw_response)
        instances = counts.instances
        if not instances:
            continue
        img = render_spotlight(image_path, instances)
        out_path = output_dir / f"{prefix}_{backend}_spotlight.png"
        img.save(out_path)
        if backend == "cloud":
            cloud_png_path = out_path

    return cloud_png_path
