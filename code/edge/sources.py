"""Where frames come from: a camera, or recorded frames on disk."""

import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageOps

from frame import Frame


class FrameSource(Protocol):
    def frames(self) -> Iterator[Frame]: ...


class FolderFrameSource:
    """Replays recorded JPEGs, one subfolder per camera, each folder's frames in name order and looped.

    Every round yields one frame per camera, then waits `interval` seconds.
    """

    def __init__(self, root: Path, interval: float, rounds: int | None = None) -> None:
        folders = [folder for folder in sorted(root.iterdir()) if folder.is_dir()]
        self._cameras = {folder.name: sorted(folder.glob("*.jpg")) for folder in folders if any(folder.glob("*.jpg"))}
        if not self._cameras:
            raise ValueError(f"{root} has no camera folders with .jpg frames")
        self._interval = interval
        self._rounds = rounds

    @property
    def camera_ids(self) -> list[str]:
        return list(self._cameras)

    def frames(self) -> Iterator[Frame]:
        round_number = 0
        while self._rounds is None or round_number < self._rounds:
            if round_number:
                time.sleep(self._interval)
            for camera_id, photos in self._cameras.items():
                path = photos[round_number % len(photos)]
                image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                yield Frame(camera_id=camera_id, image=image, captured_at=datetime.now(UTC), path=path)
            round_number += 1


class WebcamFrameSource:
    """Captures from a camera attached to this computer, like a board's camera does."""

    def __init__(self, camera_id: str, device: int, size: tuple[int, int], interval: float) -> None:
        self._camera_id = camera_id
        self._device = device
        self._size = size
        self._interval = interval

    def frames(self) -> Iterator[Frame]:
        # OpenCV is an optional dependency (requirements-camera.txt), only needed here.
        import cv2

        capture = cv2.VideoCapture(self._device)
        if not capture.isOpened():
            raise RuntimeError(f"cannot open camera device {self._device}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._size[0])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._size[1])
        try:
            while True:
                captured, bgr = capture.read()
                if not captured:
                    raise RuntimeError(f"camera device {self._device} returned no frame")
                image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                if image.size != self._size:
                    image = image.resize(self._size, Image.Resampling.LANCZOS)
                yield Frame(camera_id=self._camera_id, image=image, captured_at=datetime.now(UTC))
                time.sleep(self._interval)
        finally:
            capture.release()
