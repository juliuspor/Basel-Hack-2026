"""The camera's loop: change check, PII detection, pixelation, upload.

The frame stays in memory. Only the pixelated JPEG and the person boxes leave.
"""

import io
import logging
from datetime import datetime, timedelta

from PIL import Image

from change import ChangeDetector
from frame import Frame
from pii import PIIDetector
from pixelate import pixelate
from sources import FrameSource
from upload import FrameUploader

LOGGER = logging.getLogger("edge")
# Uploading at least this often keeps the backend from marking the camera's
# slots unknown, and catches changes too slow for the change check.
HEARTBEAT_INTERVAL = timedelta(minutes=5)
JPEG_QUALITY = 85


class EdgePipeline:
    def __init__(self, source: FrameSource, detector: PIIDetector, uploader: FrameUploader,
                 heartbeat: timedelta = HEARTBEAT_INTERVAL) -> None:
        self._source = source
        self._detector = detector
        self._uploader = uploader
        self._heartbeat = heartbeat
        self._changes: dict[str, ChangeDetector] = {}
        self._last_upload: dict[str, datetime] = {}

    def run(self) -> None:
        for frame in self._source.frames():
            self.process(frame)

    def process(self, frame: Frame) -> None:
        changes = self._changes.setdefault(frame.camera_id, ChangeDetector())
        last_upload = self._last_upload.get(frame.camera_id)
        heartbeat_due = last_upload is None or frame.captured_at - last_upload >= self._heartbeat
        if not changes.has_changed(frame.image) and not heartbeat_due:
            LOGGER.info("%s: no change, nothing sent", frame.camera_id)
            return
        detections = self._detector.detect(frame)
        pixelated = pixelate(frame.image, detections.pii_regions)
        if self._uploader.upload(frame, _jpeg(pixelated), detections.people):
            # Only an accepted frame becomes the new baseline, so a failed
            # upload is retried with the next frame that still shows the change.
            changes.accept(frame.image)
            self._last_upload[frame.camera_id] = frame.captured_at


def _jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()
