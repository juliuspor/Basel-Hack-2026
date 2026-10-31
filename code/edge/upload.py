"""Sends a pixelated frame to the backend's Ingest API, or reports what would be sent."""

import json
import logging
import time
from collections.abc import Sequence
from typing import Protocol

import httpx

from frame import Box, Frame

LOGGER = logging.getLogger("edge")
RETRY_STATUSES = {502, 503, 504}  # the backend or its classifier is briefly unavailable


class FrameUploader(Protocol):
    def upload(self, frame: Frame, jpeg: bytes, people: Sequence[Box]) -> bool:
        """Returns True once the backend accepted the frame."""


class IngestClient:
    """POSTs to /v1/frames with the camera's token, retrying briefly when the backend is unavailable."""

    def __init__(self, client: httpx.Client, base_url: str, tokens: dict[str, str], attempts: int = 3,
                 backoff_seconds: float = 1.0) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/v1/frames"
        self._tokens = tokens
        self._attempts = attempts
        self._backoff = backoff_seconds

    def upload(self, frame: Frame, jpeg: bytes, people: Sequence[Box]) -> bool:
        token = self._tokens.get(frame.camera_id)
        if token is None:
            raise KeyError(f"no token for camera {frame.camera_id} in the tokens file")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/jpeg",
            "X-Captured-At": frame.captured_at.isoformat(),
            "X-Person-Boxes": json.dumps([list(box) for box in people]),
        }
        for attempt in range(1, self._attempts + 1):
            try:
                response = self._client.post(self._url, content=jpeg, headers=headers)
            except httpx.HTTPError as error:
                LOGGER.warning("%s: upload attempt %d failed: %s", frame.camera_id, attempt, error)
            else:
                if response.status_code == httpx.codes.OK:
                    LOGGER.info("%s: accepted, %s", frame.camera_id, response.json())
                    return True
                if response.status_code not in RETRY_STATUSES:
                    LOGGER.error("%s: rejected with %d: %s", frame.camera_id, response.status_code, response.text)
                    return False
                LOGGER.warning("%s: upload attempt %d answered %d", frame.camera_id, attempt, response.status_code)
            if attempt < self._attempts:
                time.sleep(self._backoff * 2 ** (attempt - 1))
        return False


class DryRunUploader:
    """Logs what would be uploaded and keeps nothing, so the pipeline runs without a backend."""

    def upload(self, frame: Frame, jpeg: bytes, people: Sequence[Box]) -> bool:
        LOGGER.info("%s: would upload %d bytes, %dx%d, %d people", frame.camera_id, len(jpeg),
                    frame.image.width, frame.image.height, len(people))
        return True
