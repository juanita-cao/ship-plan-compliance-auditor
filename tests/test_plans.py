"""Plan upload + segmentation tests (ADR-F30, UP-S01..S13). No DB, no paid API."""
from __future__ import annotations

import io
import json
import random
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.api import plans
from backend.api.main import app

client = TestClient(app)
PID = "southern_cross"


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PVCB_UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _drawing(draw: ImageDraw.ImageDraw, box, seed=0):
    rnd = random.Random(seed)
    x0, y0, x1, y1 = box
    draw.rectangle(box, outline=(0, 0, 0), width=4)
    for _ in range(60):
        a = (rnd.randint(x0, x1), rnd.randint(y0, y1))
        b = (rnd.randint(x0, x1), rnd.randint(y0, y1))
        draw.line([a, b], fill=(20, 20, 20), width=3)


def sheet(decks: int = 3, w: int = 2400, h: int = 2400) -> Image.Image:
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    band = h // decks
    for i in range(decks):
        _drawing(d, (200, i * band + 120, w - 200, (i + 1) * band - 120), seed=i)
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def upload(data: bytes, name="plan.png", project=PID):
    return client.post(f"/api/projects/{project}/plans", files={"file": (name, data, "application/octet-stream")})


def test_up_s01_valid_png_upload():
    r = upload(png_bytes(sheet()))
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "png" and body["width"] == 2400 and body["pages"] == 1
    assert len(body["plan_id"]) == 32


def test_up_s02_unsupported_format():
    r = upload(b"AC1015" + b"\x00" * 100, "ship.dwg")
    assert r.status_code == 415 and r.json()["detail"]["rule"] == "U1"
    r = upload(b"MZ\x90\x00" + b"\x00" * 100, "evil.png")  # exe disguised as png
    assert r.status_code == 415 and r.json()["detail"]["rule"] == "U1"


def test_up_s03_too_large():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (plans.MAX_IMAGE_BYTES + 10)
    r = upload(big)
    assert r.status_code == 413 and r.json()["detail"]["rule"] == "U2"


def test_up_s04_low_resolution():
    r = upload(png_bytes(sheet(1, 1200, 1000)))
    assert r.status_code == 422 and r.json()["detail"]["rule"] == "U3"


def test_up_s13_decompression_bomb():
    bomb = Image.new("1", (20000, 20000), 1)
    r = upload(png_bytes(bomb))
    assert r.status_code == 422 and r.json()["detail"]["rule"] == "U3"


def test_up_s06_segments_three_decks_top_to_bottom():
    pid = upload(png_bytes(sheet(3))).json()["plan_id"]
    r = client.post(f"/api/plans/{pid}/segment")
    assert r.status_code == 200
    regions = r.json()["regions"]
    assert [x["label"] for x in regions] == ["Deck 1", "Deck 2", "Deck 3"]
    ys = [x["bbox"][1] for x in regions]
    assert ys == sorted(ys)
    assert r.json()["method"] == "xy_cut"


def test_up_s07_single_deck_is_one_region():
    pid = upload(png_bytes(sheet(1))).json()["plan_id"]
    regions = client.post(f"/api/plans/{pid}/segment").json()["regions"]
    assert len(regions) == 1 and regions[0]["confidence"] == 0.5


def test_side_by_side_decks_are_split_left_to_right():
    img = Image.new("RGB", (3000, 1600), (255, 255, 255))
    d = ImageDraw.Draw(img)
    _drawing(d, (100, 100, 1400, 1500), 1)
    _drawing(d, (1600, 100, 2900, 1500), 2)
    pid = upload(png_bytes(img)).json()["plan_id"]
    xs = [r["bbox"][0] for r in client.post(f"/api/plans/{pid}/segment").json()["regions"]]
    assert len(xs) == 2 and xs == sorted(xs)


def test_small_title_block_is_dropped():
    img = sheet(2)
    d = ImageDraw.Draw(img)
    d.rectangle((200, 2330, 700, 2380), outline=(0, 0, 0), width=3)  # tiny legend at the bottom
    pid = upload(png_bytes(img)).json()["plan_id"]
    assert len(client.post(f"/api/plans/{pid}/segment").json()["regions"]) == 2


def test_up_s08_confirm_rename_and_delete_region():
    pid = upload(png_bytes(sheet(3))).json()["plan_id"]
    regions = client.post(f"/api/plans/{pid}/segment").json()["regions"]
    r = client.post(f"/api/plans/{pid}/confirm", json={"decks": [
        {"region_id": regions[0]["id"], "label": "Main Deck"},
        {"region_id": regions[2]["id"], "label": "Bridge"},
    ]})
    assert r.status_code == 200
    images = r.json()["images"]
    assert [i["label"] for i in images] == ["Main Deck", "Bridge"]
    assert all(i["uploaded"] and i["stem"].startswith("up_") for i in images)
    # appears in the project list and the image is served
    proj = next(p for p in client.get("/api/projects").json() if p["id"] == PID)
    assert [i["label"] for i in proj["images"]] == ["Main Deck", "Bridge"]
    img = client.get(f"/api/image/{PID}/{images[0]['stem']}")
    assert img.status_code == 200 and img.json()["data"].startswith("data:image/png")
    # a second confirm is rejected
    assert client.post(f"/api/plans/{pid}/confirm", json={"decks": []}).status_code == 409


def test_up_s09_invalid_confirm_requests():
    pid = upload(png_bytes(sheet(2))).json()["plan_id"]
    regions = client.post(f"/api/plans/{pid}/segment").json()["regions"]
    rid = regions[0]["id"]
    assert client.post(f"/api/plans/{pid}/confirm", json={"decks": [{"region_id": rid, "label": "  "}]}).status_code == 422
    assert client.post(f"/api/plans/{pid}/confirm", json={"decks": [{"region_id": "nope", "label": "X"}]}).status_code == 422
    twice = {"decks": [{"region_id": rid, "label": "A"}, {"region_id": rid, "label": "B"}]}
    assert client.post(f"/api/plans/{pid}/confirm", json=twice).status_code == 422
    # whole sheet as one deck (empty selection) is allowed
    r = client.post(f"/api/plans/{pid}/confirm", json={"decks": []})
    assert r.status_code == 200 and len(r.json()["images"]) == 1


def test_confirm_requires_segmentation():
    pid = upload(png_bytes(sheet(2))).json()["plan_id"]
    assert client.post(f"/api/plans/{pid}/confirm", json={"decks": []}).status_code == 409


def test_up_s10_quota_per_project():
    data = png_bytes(sheet(1))
    for _ in range(plans.MAX_PLANS_PER_PROJECT):
        assert upload(data).status_code == 200
    r = upload(data)
    assert r.status_code == 429 and r.json()["detail"]["rule"] == "Q1"
    assert upload(data, project="asian_spirit").status_code == 200  # other vessels unaffected


def test_up_s11_detect_on_uploaded_deck_is_labelled_sample():
    pid = upload(png_bytes(sheet(2))).json()["plan_id"]
    client.post(f"/api/plans/{pid}/segment")
    stem = client.post(f"/api/plans/{pid}/confirm", json={"decks": []}).json()["images"][0]["stem"]
    r = client.post("/api/detect", json={"project_id": PID, "image_stem": stem})
    assert r.status_code == 200
    body = r.json()
    assert body["is_sample"] is True and "Demo Ship A" in body["sample_label"]
    assert body["image_stem"] == stem and body["project_id"] == PID
    assert body["raw_response"] is None
    # fixture decks are never marked as samples
    real = client.post("/api/detect", json={"project_id": "demo_ship_a", "image_stem": "a_deck"}).json()
    assert real["is_sample"] is False
    # spotlight works for the uploaded deck
    assert client.get(f"/api/spotlight/{PID}/{stem}").status_code == 200


def test_detect_unknown_uploaded_stem_is_404():
    assert client.post("/api/detect", json={"project_id": PID, "image_stem": "up_deadbeef_1"}).status_code == 404


def test_up_s12_delete_removes_everything():
    pid = upload(png_bytes(sheet(1))).json()["plan_id"]
    assert client.delete(f"/api/plans/{pid}").status_code == 204
    assert client.post(f"/api/plans/{pid}/segment").status_code == 404
    assert client.delete(f"/api/plans/{pid}").status_code == 404


def test_unknown_project_and_bad_plan_id():
    assert upload(png_bytes(sheet(1)), project="nope").status_code == 404
    assert client.post("/api/plans/../../etc/passwd/segment").status_code in (404, 405)
    assert client.get("/api/plans/not-a-hex-id/sheet").status_code == 404


def test_expired_plans_are_cleaned_up(upload_dir):
    pid = upload(png_bytes(sheet(1))).json()["plan_id"]
    meta_path = next(upload_dir.rglob("meta.json"))
    meta = json.loads(meta_path.read_text())
    meta["created_at"] = time.time() - plans.TTL_SECONDS - 10
    meta_path.write_text(json.dumps(meta))
    assert plans.cleanup_expired() == 1
    assert client.post(f"/api/plans/{pid}/segment").status_code == 404


def test_filename_is_sanitised_and_never_used_on_disk(upload_dir):
    r = upload(png_bytes(sheet(1)), name="../../evil name<script>.png")
    assert r.status_code == 200
    assert "/" not in r.json()["filename"] and "<" not in r.json()["filename"]
    assert not any(p.name.startswith("evil") for p in upload_dir.rglob("*"))


def test_pdf_pages_are_stitched_and_split():
    pages = [sheet(1, 2000, 1400), sheet(1, 2000, 1400)]
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
    r = upload(buf.getvalue(), "plan.pdf")
    assert r.status_code == 200 and r.json()["kind"] == "pdf" and r.json()["pages"] == 2
    regions = client.post(f"/api/plans/{r.json()['plan_id']}/segment").json()["regions"]
    assert len(regions) == 2


def test_pdf_with_too_many_pages_is_rejected():
    pages = [Image.new("RGB", (400, 300), (255, 255, 255)) for _ in range(plans.MAX_PDF_PAGES + 1)]
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
    r = upload(buf.getvalue(), "plan.pdf")
    assert r.status_code == 413 and r.json()["detail"]["rule"] == "U2"


def test_up_s13_confirm_with_adjusted_and_added_boxes():
    pid = upload(png_bytes(sheet(2))).json()["plan_id"]
    seg = client.post(f"/api/plans/{pid}/segment").json()
    w, h = seg["sheet_w"], seg["sheet_h"]
    rid = seg["regions"][0]["id"]
    ok = client.post(f"/api/plans/{pid}/confirm", json={"decks": [
        {"region_id": rid, "label": "Adjusted", "bbox": [10, 10, 900, 700]},
        {"region_id": "new_1", "label": "Drawn", "bbox": [0, 0, w, h]},
    ]})
    assert ok.status_code == 200 and [i["label"] for i in ok.json()["images"]] == ["Adjusted", "Drawn"]


def test_up_s14_invalid_boxes_rejected():
    pid = upload(png_bytes(sheet(2))).json()["plan_id"]
    seg = client.post(f"/api/plans/{pid}/segment").json()
    rid = seg["regions"][0]["id"]
    for bad in ([0, 0, 50, 50], [-5, 0, 500, 500], [0, 0, seg["sheet_w"] + 1, 500], [500, 500, 100, 100], [1, 2, 3]):
        r = client.post(f"/api/plans/{pid}/confirm", json={"decks": [{"region_id": rid, "label": "X", "bbox": bad}]})
        assert r.status_code == 422, bad
    # unknown region id without a box is still rejected
    assert client.post(f"/api/plans/{pid}/confirm", json={"decks": [{"region_id": "new_1", "label": "X"}]}).status_code == 422
