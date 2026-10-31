"""Where station occupancy is kept: the interface and the in-memory version for a laptop."""

import threading
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

from occupancy.model import StationOccupancy


class ConcurrentUpdate(Exception):
    """Another writer saved the station after it was read."""


class OccupancyRepository(Protocol):
    def get(self, station_id: str) -> StationOccupancy | None: ...

    def get_many(self, station_ids: Sequence[str]) -> list[StationOccupancy]: ...

    def save(self, occupancy: StationOccupancy) -> None:
        """Stores the occupancy as the next version, or raises ConcurrentUpdate."""


class InMemoryOccupancyRepository:
    """Lost when the process ends, which is enough for a laptop."""

    def __init__(self) -> None:
        self._stations: dict[str, StationOccupancy] = {}
        self._lock = threading.Lock()

    def get(self, station_id: str) -> StationOccupancy | None:
        with self._lock:
            return self._stations.get(station_id)

    def get_many(self, station_ids: Sequence[str]) -> list[StationOccupancy]:
        with self._lock:
            return [self._stations[station_id] for station_id in station_ids if station_id in self._stations]

    def save(self, occupancy: StationOccupancy) -> None:
        with self._lock:
            stored = self._stations.get(occupancy.station_id)
            if occupancy.version != (stored.version if stored else 0):
                raise ConcurrentUpdate(occupancy.station_id)
            self._stations[occupancy.station_id] = replace(occupancy, version=occupancy.version + 1)
