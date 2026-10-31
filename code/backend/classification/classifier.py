"""What every occupancy classifier takes and returns.

A classifier gets the whole frame and the slots to read, and decides itself
how to look at them. It answers for every slot it was given, or raises
ClassifierUnavailable so the frame is not used at all.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from cameras.camera import SlotView


@dataclass(frozen=True)
class Reading:
    taken: bool
    confidence: float  # 0.5 (a guess) to 1.0 (certain)


class ClassifierUnavailable(Exception):
    """The classifier could not read the slots, for example because its API failed."""


class OccupancyClassifier(Protocol):
    def classify(self, frame: Image.Image, slots: Sequence[SlotView]) -> dict[int, Reading]: ...
