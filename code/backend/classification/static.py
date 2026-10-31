"""Answers with fixed readings from data/static-readings.json, without looking at the frame.

It lets the whole backend run without network access or an OpenRouter key.
The file holds one state per slot that a camera sees:

    {"cmr-south-02": {"1": "taken", "2": "free"}}
"""

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from PIL import Image

from cameras.camera import Camera, SlotView
from classification.classifier import Reading

STATES = {"taken": True, "free": False}


class StaticReadingsError(ValueError):
    """The readings file is malformed or misses a slot that a camera sees."""


class StaticClassifier:
    def __init__(self, taken: dict[tuple[str, int], bool]) -> None:
        self._taken = taken

    @classmethod
    def load(cls, path: Path) -> "StaticClassifier":
        try:
            entries = json.loads(path.read_text())
            taken = {
                (station_id, int(number)): STATES[state]
                for station_id, slots in entries.items()
                for number, state in slots.items()
            }
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise StaticReadingsError(f"{path}: {error}") from error
        return cls(taken)

    def check_covers(self, cameras: Iterable[Camera]) -> None:
        """Fails unless the file has a reading for every slot a camera sees."""
        missing = sorted(
            f"{slot.station_id}/{slot.number}"
            for camera in cameras
            for slot in camera.slots
            if (slot.station_id, slot.number) not in self._taken
        )
        if missing:
            raise StaticReadingsError(f"static readings have no state for {', '.join(missing)}")

    def classify(self, frame: Image.Image, slots: Sequence[SlotView]) -> dict[int, Reading]:
        return {
            slot.number: Reading(taken=self._taken[(slot.station_id, slot.number)], confidence=1.0)
            for slot in slots
        }
