"""Where the backend keeps live state and reads its static assets.

Both are small interfaces so the cloud versions (e.g. DynamoDB for state, S3 for
assets) can be added as new classes without touching app.py. The local
versions below need no account and are what runs on a laptop.
"""

import copy
import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from PIL import Image

HERE = Path(__file__).parent


@dataclass
class AreaState:
    """What the backend knows about one area right now. No images, no people."""

    slots: dict[str, bool] = field(default_factory=dict)  # slot id -> occupied
    updated_at: float | None = None
    checked_at: float | None = None
    camera_time: str | None = None
    person_present: bool = False
    frames_analyzed: int = 0
    frames_skipped: int = 0


class StateStore(Protocol):
    def get(self, area_id: str) -> AreaState | None: ...

    def put(self, area_id: str, state: AreaState) -> None: ...


class MemoryStateStore:
    """Keeps state in this process; it is lost on restart."""

    def __init__(self):
        self._states: dict[str, AreaState] = {}
        self._lock = threading.Lock()

    def get(self, area_id):
        with self._lock:
            state = self._states.get(area_id)
            return copy.deepcopy(state) if state else None

    def put(self, area_id, state):
        with self._lock:
            self._states[area_id] = copy.deepcopy(state)


class AssetStore(Protocol):
    """Site configuration plus the scene generator's per-area bundle.

    A bundle is `<id>.json` (layout), `cameras/<id>/camera.json` with its
    reference frame (calibration) and `<id>.usdz` (3D model).
    """

    def areas(self) -> list[dict]: ...  # entries of data/areas.json: id, name, center, heading_deg

    def layout(self, area_id: str) -> dict: ...

    def camera(self, area_id: str) -> dict: ...  # calibration with `reference_image` loaded

    def model_url(self, name: str) -> str: ...  # what the app downloads, e.g. /models/<name>.usdz

    def model_file(self, name: str) -> Path | None: ...  # local file to serve, if any


class LocalAssetStore:
    def __init__(self, data=HERE / "data", layouts=HERE.parent / "scene-generator" / "layouts",
                 scene_out=None):
        self.data = Path(data)
        self.layouts = Path(layouts)
        self.scene_out = Path(scene_out or os.environ.get(
            "SCENE_OUT", HERE.parent / "scene-generator" / "out"))

    def areas(self):
        return json.loads((self.data / "areas.json").read_text())

    def layout(self, area_id):
        return json.loads((self.layouts / f"{area_id}.json").read_text())

    def camera(self, area_id):
        folder = self.scene_out / "cameras" / area_id
        camera = json.loads((folder / "camera.json").read_text())
        camera["reference_image"] = Image.open(folder / camera["reference"]).convert("RGB")
        return camera

    def model_url(self, name):
        return f"/models/{name}.usdz"

    def model_file(self, name):
        path = (self.scene_out / name).resolve()
        if path.parent != self.scene_out.resolve() or path.suffix != ".usdz" or not path.exists():
            return None
        return path


def make_stores() -> tuple[StateStore, AssetStore]:
    """STATE_STORE / ASSET_STORE pick the implementations; only `local` exists so far."""
    state, assets = os.environ.get("STATE_STORE", "local"), os.environ.get("ASSET_STORE", "local")
    if state != "local" or assets != "local":
        raise ValueError(f"unknown store: STATE_STORE={state}, ASSET_STORE={assets}")
    return MemoryStateStore(), LocalAssetStore()
