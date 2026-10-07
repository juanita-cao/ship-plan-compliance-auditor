"""Static demo export (ADR-F36): ST-S07, ST-S08. Run `scripts/export_static_demo.py` first."""
import json
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "demo-data"
pytestmark = pytest.mark.skipif(not OUT.exists(), reason="demo-data not exported yet")


def _load(rel):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def test_st_s07_every_deck_has_every_spotlight_combination():
    projects = _load("projects.json")
    decks = [(p["id"], i["stem"]) for p in projects for i in p["images"]]
    assert len(decks) == 6
    for pid, stem in decks:
        assert _load(f"image/{pid}/{stem}.json")["data"].startswith("data:image/png;base64,")
        result = _load(f"detect/{pid}/{stem}.json")
        base = f"spotlight/{pid}/{stem}"
        assert _load(f"{base}/all.json")["data"].startswith("data:image/png")
        for cat in result["total_by_category"]:
            assert (OUT / f"{base}/cat-{cat}.json").exists(), (pid, stem, cat)
        for inst in result["instances"]:
            assert (OUT / f"{base}/inst-{inst['id']}.json").exists(), (pid, stem, inst["id"])


def test_st_s08_only_demo_ships_are_exported_and_size_is_within_gate():
    projects = _load("projects.json")
    assert len(projects) == 10
    with_plans = {p["id"] for p in projects if p["images"]}
    assert with_plans == {"demo_ship_a", "demo_ship_b"}
    assert not any(i.get("uploaded") for p in projects for i in p["images"])
    assert not (OUT / "uploads").exists()
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    assert total <= 30e6
