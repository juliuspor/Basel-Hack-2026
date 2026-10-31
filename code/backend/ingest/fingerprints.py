"""Where each camera's slot fingerprints are kept, so unchanged slots skip the classifier.

They belong to a camera's view, not to a station's occupancy, and losing them
costs one extra round of classification and nothing else.
"""

import threading
from typing import Protocol


class FingerprintStore(Protocol):
    def get(self, camera_id: str) -> dict[int, int]: ...

    def put(self, camera_id: str, fingerprints: dict[int, int]) -> None: ...


class InMemoryFingerprintStore:
    def __init__(self) -> None:
        self._cameras: dict[str, dict[int, int]] = {}
        self._lock = threading.Lock()

    def get(self, camera_id: str) -> dict[int, int]:
        with self._lock:
            return dict(self._cameras.get(camera_id, {}))

    def put(self, camera_id: str, fingerprints: dict[int, int]) -> None:
        with self._lock:
            self._cameras[camera_id] = dict(fingerprints)
