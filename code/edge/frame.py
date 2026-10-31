"""One captured frame, as it moves through the pipeline. It lives in memory only."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

Box = tuple[int, int, int, int]  # x0, y0, x1, y1 in frame pixels, x1 and y1 exclusive


@dataclass(frozen=True)
class Frame:
    camera_id: str
    image: Image.Image
    captured_at: datetime
    # Where a recorded frame was read from, so its sidecar file can be found.
    path: Path | None = None


def parse_size(text: str) -> tuple[int, int]:
    """Parses a frame size such as 1280x960."""
    width, separator, height = text.partition("x")
    if not (separator and width.isdigit() and height.isdigit() and int(width) > 0 and int(height) > 0):
        raise ValueError(f"{text!r} is not a size like 1280x960")
    return int(width), int(height)
