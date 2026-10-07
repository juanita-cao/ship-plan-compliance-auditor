"""Export the API's own responses for the bundled demo decks as static JSON (ADR-F36).

    PYTHONPATH=. python scripts/export_static_demo.py

Writes frontend/public/demo-data/ in the same shapes the FastAPI endpoints return, so the
frontend's static adapter can serve them without a backend. Deterministic and re-runnable.
Only the two bundled demo ships are exported; uploaded decks are never included.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from backend.api import fixtures
from backend.api.routers import auditor
from backend.api.schemas import DetectRequest

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "demo-data"
DEMO_SHIPS = ("demo_ship_a", "demo_ship_b")
SIZE_GATE_MB = 30


def safe(name: str) -> str:
    """Same rule as `safeName` in frontend/src/api/staticAdapter.ts."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def write(rel: str, payload) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    projects = []
    for p in fixtures.list_projects():
        if p["id"] in DEMO_SHIPS:
            p = {**p, "images": [i for i in p["images"] if not i.get("uploaded")]}
        else:
            p = {**p, "images": []}
        projects.append(p)
    write("projects.json", projects)

    n_files = 0
    for p in projects:
        for im in p["images"]:
            pid, stem = p["id"], im["stem"]
            write(f"image/{pid}/{safe(stem)}.json", {"data": auditor.get_image(pid, stem).data})
            result = auditor.detect(DetectRequest(project_id=pid, image_stem=stem))
            write(f"detect/{pid}/{safe(stem)}.json", result.model_dump(mode="json"))
            base = f"spotlight/{pid}/{safe(stem)}"
            write(f"{base}/all.json", {"data": auditor.get_spotlight(pid, stem, None, None).data})
            for cat in result.total_by_category:
                write(f"{base}/cat-{safe(cat)}.json", {"data": auditor.get_spotlight(pid, stem, cat, None).data})
            for inst in result.instances:
                write(f"{base}/inst-{safe(inst.id)}.json", {"data": auditor.get_spotlight(pid, stem, None, inst.id).data})
            n_files += 3 + len(result.total_by_category) + len(result.instances)

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"{n_files + 1} files, {total / 1e6:.1f} MB → {OUT}")
    if total > SIZE_GATE_MB * 1e6:
        print(f"ERROR: over the {SIZE_GATE_MB} MB gate", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
