"""A camera's calibration: which station it watches and where each slot sits in its frame.

Calibration files live in data/cameras/<camera_id>.json:

    {"station_id": "cmr-south-02", "frame_size": [1280, 960],
     "slots": {"1": [x0, y0, x1, y1], ...}}

Boxes are pixel coordinates in the camera's frame, with x1 and y1 exclusive.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from stations.catalog import StationCatalog

Box = tuple[int, int, int, int]


class CalibrationError(ValueError):
    """A calibration file is malformed or does not match the station catalog."""


@dataclass(frozen=True)
class SlotView:
    """One slot as one camera sees it."""

    station_id: str
    number: int
    box: Box

    def crop(self, frame: Image.Image) -> Image.Image:
        return frame.crop(self.box)

    def overlaps(self, other: Box) -> bool:
        x0, y0, x1, y1 = self.box
        ox0, oy0, ox1, oy1 = other
        return x0 < ox1 and ox0 < x1 and y0 < oy1 and oy0 < y1


@dataclass(frozen=True)
class Camera:
    id: str
    station_id: str
    frame_size: tuple[int, int]
    slots: tuple[SlotView, ...]


def load_camera(path: Path) -> Camera:
    """Reads one calibration file. The camera id is the file name without .json."""
    try:
        entry = json.loads(path.read_text())
        width, height = (int(side) for side in entry["frame_size"])
        station_id = str(entry["station_id"])
        slots = tuple(
            SlotView(station_id=station_id, number=int(number), box=_box(coordinates, width, height))
            for number, coordinates in entry["slots"].items()
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise CalibrationError(f"{path}: {error}") from error
    if not slots:
        raise CalibrationError(f"{path}: lists no slots")
    return Camera(id=path.stem, station_id=station_id, frame_size=(width, height), slots=slots)


def load_cameras(directory: Path) -> dict[str, Camera]:
    return {path.stem: load_camera(path) for path in sorted(directory.glob("*.json"))}


def check_against(cameras: dict[str, Camera], catalog: StationCatalog) -> None:
    """Fails unless every camera watches a known station and only that station's slots."""
    for camera in cameras.values():
        station = catalog.get(camera.station_id)
        if station is None:
            raise CalibrationError(f"camera {camera.id} watches unknown station {camera.station_id}")
        unknown = {slot.number for slot in camera.slots} - {slot.number for slot in station.slots}
        if unknown:
            raise CalibrationError(f"camera {camera.id} lists slots {sorted(unknown)} that {station.id} does not have")


def _box(coordinates: list, width: int, height: int) -> Box:
    x0, y0, x1, y1 = (int(value) for value in coordinates)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError(f"box {coordinates} does not fit a {width}x{height} frame")
    return x0, y0, x1, y1
