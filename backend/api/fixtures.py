"""File-based fixture data (ADR-F18) — no DB required.

Fixture JSONs: data/fixtures/{project_id}/{image_stem}.json (git tracked).
Categories hardcoded here; no category_lookup DB calls needed.
"""
from __future__ import annotations

import json
from pathlib import Path

SERVICE_ROOT = Path(__file__).parent.parent.parent

_FIXTURES_DIR = SERVICE_ROOT / "data" / "fixtures"
_IMAGES_DIR = SERVICE_ROOT / "data" / "images"

_CATEGORY_META: dict[str, dict] = {
    "extinguisher_CO2_5kg":              {"label": "CO₂ 5kg",               "color": "#0FC6C2"},
    "extinguisher_CO2_5kg_spare":        {"label": "CO₂ 5kg (spare)",       "color": "#0FC6C2"},
    "extinguisher_dry_powder_6kg":       {"label": "Dry Powder 6kg",        "color": "#FF7D00"},
    "extinguisher_dry_powder_6kg_spare": {"label": "Dry Powder 6kg (spare)", "color": "#FF7D00"},
    "extinguisher_foam_9L":              {"label": "Foam 9L",               "color": "#1664FF"},
    "extinguisher_foam_9L_spare":        {"label": "Foam 9L (spare)",       "color": "#1664FF"},
    "extinguisher_DCP_5kg":              {"label": "DCP 5kg",               "color": "#FF7D00"},
    "extinguisher_wheeld_foam_45L":      {"label": "Wheeled Foam 45L",      "color": "#1664FF"},
    "extinguisher_water_9L":             {"label": "Water 9L",              "color": "#7B61FF"},
}
_FALLBACK_COLOR = "#F5A623"

_PROJECT_CATEGORIES: dict[str, list[str]] = {
    "demo_ship_a": [
        "extinguisher_CO2_5kg",
        "extinguisher_CO2_5kg_spare",
        "extinguisher_dry_powder_6kg",
        "extinguisher_dry_powder_6kg_spare",
        "extinguisher_foam_9L",
        "extinguisher_foam_9L_spare",
    ],
    "demo_ship_b": [
        "extinguisher_DCP_5kg",
        "extinguisher_CO2_5kg",
        "extinguisher_wheeld_foam_45L",
        "extinguisher_water_9L",
    ],
}

_STANDARD_CATEGORIES = [
    "extinguisher_CO2_5kg",
    "extinguisher_dry_powder_6kg",
    "extinguisher_foam_9L",
]

_PROJECT_LABELS: dict[str, str] = {
    "demo_ship_a": "Demo Ship A",
    "demo_ship_b": "Demo Ship B",
    "eastern_pioneer": "Eastern Pioneer",
    "southern_cross": "Southern Cross",
    "northern_star": "Northern Star",
    "pacific_trader": "Pacific Trader",
    "asian_spirit": "Asian Spirit",
    "ocean_pioneer": "Ocean Pioneer",
    "pacific_eagle": "Pacific Eagle",
    "eastern_wind": "Eastern Wind",
}

# Fleet vessels without bundled plans: listed with no images (ADR-F33).
for _pid in _PROJECT_LABELS:
    _PROJECT_CATEGORIES.setdefault(_pid, list(_STANDARD_CATEGORIES))


def _stem_label(stem: str) -> str:
    return stem.replace("_", " ").title()


def _fixture_stems(project_id: str) -> list[str]:
    d = _FIXTURES_DIR / project_id
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json") if not p.name.startswith("._"))


def project_exists(project_id: str) -> bool:
    return project_id in _PROJECT_LABELS


def list_projects() -> list[dict]:
    from backend.api import plans

    result = []
    for project_id, cats in _PROJECT_CATEGORIES.items():
        result.append({
            "id": project_id,
            "label": _PROJECT_LABELS.get(project_id, project_id),
            "images": [{"stem": s, "label": _stem_label(s)} for s in _fixture_stems(project_id)] + plans.uploaded_decks(project_id),
            "categories": [
                {
                    "id": c,
                    "label": _CATEGORY_META.get(c, {}).get("label", c),
                    "color": _CATEGORY_META.get(c, {}).get("color", _FALLBACK_COLOR),
                }
                for c in cats
            ],
        })
    return result


def load_fixture(project_id: str, image_stem: str) -> dict:
    path = _FIXTURES_DIR / project_id / f"{image_stem}.json"
    if not path.exists():
        raise FileNotFoundError(f"No fixture for {project_id!r}/{image_stem!r}")
    return json.loads(path.read_text())


def image_path(project_id: str, image_stem: str) -> Path:
    from backend.api import plans

    if plans.is_uploaded_stem(image_stem):
        return plans.uploaded_image_path(project_id, image_stem) or (_IMAGES_DIR / "__missing__.png")
    return _IMAGES_DIR / project_id / f"{image_stem}.png"


def categories_for(project_id: str) -> list[str]:
    return _PROJECT_CATEGORIES.get(project_id, [])


def load_trace(project_id: str, image_stem: str) -> str | None:
    path = _FIXTURES_DIR / project_id / f"{image_stem}_trace.txt"
    if not path.exists():
        return None
    return path.read_text()
