"""Find my Bike Slot backend.

Cameras (real or simulated) POST JPEG frames to /ingest/{area_id}. Each frame
is masked to the parking area, analysed by a vision provider in memory and
dropped; only per-slot occupancy is kept. The app reads /areas and
/areas/{id} and downloads 3D models from /models.

The pieces are swappable (see documentation/architecture.md):
- schemas.py: the API contract the app relies on
- providers/: vision models, picked with VISION_PROVIDER
- storage.py: where state and assets live, picked with STATE_STORE / ASSET_STORE

Run: .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
"""

import functools
import io
import math
import os
import threading
import time

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image, ImageChops

from providers import make_provider, privacy_mask
from schemas import AreaDetail, AreaSummary, Health, IngestResult, Slot
from storage import AreaState, make_stores

# Largest grey-level change in an 80x60 thumbnail below which a frame counts as
# "nothing happened". One bike arriving changes some pixels by 90+.
CHANGE_THRESHOLD = float(os.environ.get("CHANGE_THRESHOLD", "40"))

app = FastAPI(title="Find my Bike Slot", version="1.0.0")
provider = make_provider()
states, assets = make_stores()
lock = threading.Lock()
last_frames = {}  # area id -> thumbnail of the last analysed frame, for the change check


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


@functools.cache
def site():
    """Static description of every area, loaded on first use."""
    areas = {}
    for entry in assets.areas():
        layout = assets.layout(entry["id"])
        shelter = layout["shelter"]
        areas[entry["id"]] = {
            "id": entry["id"],
            "name": entry["name"],
            "kind": layout["kind"],
            "center": entry["center"],
            "polygon": footprint(entry["center"], entry["heading_deg"],
                                 shelter["length"], shelter["depth"]),
            "camera": assets.camera(entry["id"]),
        }
    return areas


def area_or_404(area_id):
    area = site().get(area_id)
    if area is None:
        raise HTTPException(404, f"unknown area: {area_id}")
    return area


def state_of(area):
    return states.get(area["id"]) or AreaState(slots={key: False for key in area["camera"]["slots"]})


def summary(area, state):
    capacity = len(state.slots)
    occupied = sum(state.slots.values())
    return AreaSummary(
        id=area["id"], name=area["name"], kind=area["kind"], center=area["center"],
        polygon=area["polygon"], capacity=capacity, occupied=occupied, free=capacity - occupied,
        updated_at=state.updated_at, checked_at=state.checked_at, camera_time=state.camera_time,
        analyzer=provider.name, model_url=assets.model_url(area["id"]),
    )


@app.get("/health")
def health() -> Health:
    return Health(ok=True, analyzer=provider.name, areas=len(site()))


@app.get("/areas")
def list_areas() -> list[AreaSummary]:
    return [summary(area, state_of(area)) for area in site().values()]


@app.get("/areas/{area_id}")
def get_area(area_id: str) -> AreaDetail:
    area = area_or_404(area_id)
    state = state_of(area)
    slots = [Slot(id=key, label=area["camera"]["slots"][key]["label"], occupied=taken)
             for key, taken in sorted(state.slots.items())]
    return AreaDetail(**summary(area, state).model_dump(), slots=slots,
                      person_present=state.person_present, frames_analyzed=state.frames_analyzed,
                      frames_skipped=state.frames_skipped)


@app.post("/ingest/{area_id}")
async def ingest(area_id: str, request: Request,
                 x_camera_time: str | None = Header(None)) -> IngestResult:
    """Accept one JPEG frame. The frame never leaves memory and is not stored."""
    area = area_or_404(area_id)
    try:
        image = Image.open(io.BytesIO(await request.body())).convert("RGB")
    except Exception:
        raise HTTPException(400, "body must be a JPEG image")

    small = image.convert("L").resize((80, 60))
    previous = last_frames.get(area_id)
    if previous is not None:
        change = ImageChops.difference(small, previous).getextrema()[1]
        if change < CHANGE_THRESHOLD:
            with lock:
                state = state_of(area)
                state.checked_at, state.camera_time = time.time(), x_camera_time
                state.frames_skipped += 1
                states.put(area_id, state)
            return IngestResult(analyzed=False, change=round(change, 2))

    started = time.time()
    result = provider.analyze(privacy_mask(image, area["camera"]["area_roi"]), area["camera"])
    with lock:
        last_frames[area_id] = small
        state = state_of(area)
        state.checked_at, state.camera_time = time.time(), x_camera_time
        state.frames_analyzed += 1
        state.person_present = result.person_present
        if not result.person_present:  # someone walking through hides slots; keep last state
            state.slots = {key: key in result.occupied for key in state.slots}
            state.updated_at = time.time()
        states.put(area_id, state)
    return IngestResult(analyzed=True, seconds=round(time.time() - started, 2),
                        occupied=sorted(result.occupied), person_present=result.person_present)


@app.get("/models/{name}", response_class=FileResponse)
def model(name: str):
    path = assets.model_file(name)
    if path is None:
        raise HTTPException(404, f"unknown model: {name}")
    return FileResponse(path, media_type="model/vnd.usdz+zip")
