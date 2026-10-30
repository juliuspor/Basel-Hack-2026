"""Find my Bike Slot backend.

Cameras (real or simulated) POST JPEG frames to /ingest/{area_id}. Each frame
is analysed in memory and dropped; only per-slot occupancy is kept. The app
reads /areas and /areas/{id} and downloads 3D models from /models.

Run: .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
"""

import io
import json
import math
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image, ImageChops

from analyzers import make_analyzer

HERE = Path(__file__).parent
SCENE_OUT = Path(os.environ.get("SCENE_OUT", HERE.parent / "scene-generator" / "out"))
LAYOUTS = HERE.parent / "scene-generator" / "layouts"
# Largest grey-level change in an 80x60 thumbnail below which a frame counts as
# "nothing happened". One bike arriving changes some pixels by 90+.
CHANGE_THRESHOLD = float(os.environ.get("CHANGE_THRESHOLD", "40"))

app = FastAPI(title="Find my Bike Slot")
analyzer = make_analyzer()
lock = threading.Lock()


def footprint(center, heading_deg, length, depth):
    """Corner coordinates [lat, lon] of a length x depth rectangle around center."""
    lat, lon = center
    m_lat, m_lon = 1 / 111_320, 1 / (111_320 * math.cos(math.radians(lat)))
    h = math.radians(heading_deg)
    corners = []
    for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
        east, north = x * length / 2, y * depth / 2
        e = east * math.cos(h) + north * math.sin(h)
        n = -east * math.sin(h) + north * math.cos(h)
        corners.append([round(lat + n * m_lat, 7), round(lon + e * m_lon, 7)])
    return corners


def load_areas():
    areas = {}
    for entry in json.loads((HERE / "data" / "areas.json").read_text()):
        layout = json.loads((LAYOUTS / f"{entry['id']}.json").read_text())
        camera = json.loads((SCENE_OUT / "cameras" / entry["id"] / "camera.json").read_text())
        camera["reference_image"] = Image.open(
            SCENE_OUT / "cameras" / entry["id"] / camera["reference"]).convert("RGB")
        shelter = layout["shelter"]
        areas[entry["id"]] = {
            "id": entry["id"],
            "name": entry["name"],
            "kind": layout["kind"],
            "center": entry["center"],
            "polygon": footprint(entry["center"], entry["heading_deg"],
                                 shelter["length"], shelter["depth"]),
            "camera": camera,
            "slots": {key: False for key in camera["slots"]},
            "updated_at": None,
            "checked_at": None,
            "camera_time": None,
            "person_present": False,
            "frames_analyzed": 0,
            "frames_skipped": 0,
            "last_frame": None,
        }
    return areas


AREAS = load_areas()


def summary(area):
    capacity = len(area["slots"])
    occupied = sum(area["slots"].values())
    return {
        "id": area["id"],
        "name": area["name"],
        "kind": area["kind"],
        "center": area["center"],
        "polygon": area["polygon"],
        "capacity": capacity,
        "occupied": occupied,
        "free": capacity - occupied,
        "updated_at": area["updated_at"],
        "checked_at": area["checked_at"],
        "camera_time": area["camera_time"],
        "analyzer": analyzer.name,
        "model_url": f"/models/{area['id']}.usdz",
    }


@app.get("/health")
def health():
    return {"ok": True, "analyzer": analyzer.name, "areas": len(AREAS)}


@app.get("/areas")
def list_areas():
    return [summary(area) for area in AREAS.values()]


@app.get("/areas/{area_id}")
def get_area(area_id: str):
    area = AREAS.get(area_id) or _not_found(area_id)
    slots = [{"id": key, "label": area["camera"]["slots"][key]["label"], "occupied": taken}
             for key, taken in sorted(area["slots"].items())]
    return {**summary(area), "slots": slots, "person_present": area["person_present"],
            "frames_analyzed": area["frames_analyzed"], "frames_skipped": area["frames_skipped"]}


@app.post("/ingest/{area_id}")
async def ingest(area_id: str, request: Request, x_camera_time: str | None = Header(None)):
    """Accept one JPEG frame. The frame never leaves memory and is not stored."""
    area = AREAS.get(area_id) or _not_found(area_id)
    try:
        image = Image.open(io.BytesIO(await request.body())).convert("RGB")
    except Exception:
        raise HTTPException(400, "body must be a JPEG image")

    area["checked_at"] = time.time()
    small = image.convert("L").resize((80, 60))
    if area["last_frame"] is not None:
        change = ImageChops.difference(small, area["last_frame"]).getextrema()[1]
        if change < CHANGE_THRESHOLD:
            area["frames_skipped"] += 1
            area["camera_time"] = x_camera_time
            return {"analyzed": False, "change": round(change, 2)}

    started = time.time()
    result = analyzer.analyze(image, area["camera"])
    with lock:
        area["last_frame"] = small
        area["frames_analyzed"] += 1
        area["person_present"] = result.person_present
        area["camera_time"] = x_camera_time
        if not result.person_present:  # someone walking through hides slots; keep last state
            area["slots"] = {key: key in result.occupied for key in area["slots"]}
            area["updated_at"] = time.time()
    return {"analyzed": True, "seconds": round(time.time() - started, 2),
            "occupied": sorted(result.occupied), "person_present": result.person_present}


@app.get("/models/{name}")
def model(name: str):
    path = (SCENE_OUT / name).resolve()
    if path.parent != SCENE_OUT.resolve() or path.suffix != ".usdz" or not path.exists():
        _not_found(name)
    return FileResponse(path, media_type="model/vnd.usdz+zip")


def _not_found(what):
    raise HTTPException(404, f"unknown: {what}")
