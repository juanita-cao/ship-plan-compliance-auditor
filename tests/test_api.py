"""API integration tests — API-S01 through API-S09.

Uses FastAPI TestClient; no DB, no external API calls (fixtures only).
"""
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


# ─── API-S01 ─────────────────────────────────────────────────────────────────

def test_api_s01_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── API-S02 ─────────────────────────────────────────────────────────────────

def test_api_s02_projects_list():
    r = client.get("/api/projects")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert "demo_ship_a" in ids
    assert "demo_ship_b" in ids


def test_api_s12_fleet_vessels_without_plans_are_projects():
    projects = {p["id"]: p for p in client.get("/api/projects").json()}
    assert len(projects) == 10
    assert projects["southern_cross"]["images"] == []
    assert projects["southern_cross"]["label"] == "Southern Cross"
    assert projects["demo_ship_a"]["images"]


def test_api_s02_projects_have_images_and_categories():
    r = client.get("/api/projects")
    for p in r.json():
        assert len(p["categories"]) > 0
        if p["id"] in ("demo_ship_a", "demo_ship_b"):
            assert len(p["images"]) > 0


# ─── API-S03 ─────────────────────────────────────────────────────────────────

def test_api_s03_detect_normal_path():
    r = client.post("/api/detect", json={"project_id": "demo_ship_a", "image_stem": "a_deck"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["instances"]) > 0
    assert body["compliance_result"] is not None
    assert body["project_id"] == "demo_ship_a"
    assert body["image_stem"] == "a_deck"


def test_api_s03_detect_total_by_category_has_all_categories():
    r = client.post("/api/detect", json={"project_id": "demo_ship_a", "image_stem": "a_deck"})
    body = r.json()
    expected_cats = {
        "extinguisher_CO2_5kg", "extinguisher_CO2_5kg_spare",
        "extinguisher_dry_powder_6kg", "extinguisher_dry_powder_6kg_spare",
        "extinguisher_foam_9L", "extinguisher_foam_9L_spare",
    }
    assert expected_cats == set(body["total_by_category"].keys())


# ─── API-S04 ─────────────────────────────────────────────────────────────────

def test_api_s04_detect_unknown_project():
    r = client.post("/api/detect", json={"project_id": "nonexistent", "image_stem": "a_deck"})
    assert r.status_code == 404


# ─── API-S05 ─────────────────────────────────────────────────────────────────

def test_api_s05_detect_unknown_image_stem():
    r = client.post("/api/detect", json={"project_id": "demo_ship_a", "image_stem": "nonexistent"})
    assert r.status_code == 404


# ─── API-S06 ─────────────────────────────────────────────────────────────────

def test_api_s06_spotlight_no_filter():
    r = client.get("/api/spotlight/demo_ship_a/a_deck")
    assert r.status_code == 200
    assert r.json()["data"].startswith("data:image/png;base64,")


# ─── API-S07 ─────────────────────────────────────────────────────────────────

def test_api_s07_spotlight_category_filter():
    r = client.get("/api/spotlight/demo_ship_a/a_deck?category=extinguisher_CO2_5kg")
    assert r.status_code == 200
    assert r.json()["data"].startswith("data:image/png;base64,")


# ─── API-S08 ─────────────────────────────────────────────────────────────────

def test_api_s08_image_normal():
    r = client.get("/api/image/demo_ship_a/a_deck")
    assert r.status_code == 200
    assert r.json()["data"].startswith("data:image/png;base64,")


# ─── API-S09 ─────────────────────────────────────────────────────────────────

def test_api_s09_image_not_found():
    r = client.get("/api/image/demo_ship_a/nonexistent")
    assert r.status_code == 404


# ─── demo_ship_b sanity ──────────────────────────────────────────────────────

def test_api_s03_detect_demo_ship_b():
    r = client.post("/api/detect", json={"project_id": "demo_ship_b", "image_stem": "below_main_deck_bow"})
    assert r.status_code == 200
    body = r.json()
    expected_cats = {
        "extinguisher_DCP_5kg", "extinguisher_CO2_5kg",
        "extinguisher_wheeld_foam_45L", "extinguisher_water_9L",
    }
    assert expected_cats == set(body["total_by_category"].keys())
