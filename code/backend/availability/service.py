"""Station availability for riders: the station catalog joined with the current occupancy.

The Availability API and the MCP server both answer from here.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from occupancy.model import SlotState, StationOccupancy
from occupancy.repository import OccupancyRepository
from stations.catalog import Location, Station, StationCatalog


@dataclass(frozen=True)
class SlotStatus:
    number: int
    state: SlotState
    location: Location
    changed_at: datetime | None


@dataclass(frozen=True)
class StationStatus:
    station: Station
    slots: tuple[SlotStatus, ...]
    updated_at: datetime | None

    def count(self, state: SlotState) -> int:
        return sum(1 for slot in self.slots if slot.state is state)


class AvailabilityService:
    def __init__(self, catalog: StationCatalog, occupancy: OccupancyRepository, stale_after: timedelta,
                 models_dir: Path) -> None:
        self._catalog = catalog
        self._occupancy = occupancy
        self._stale_after = stale_after
        self._models_dir = models_dir

    def stations(self, min_free: int = 0) -> list[StationStatus]:
        stations = self._catalog.all()
        stored = {entry.station_id: entry for entry in self._occupancy.get_many([s.id for s in stations])}
        now = datetime.now(UTC)
        statuses = [self._status(station, stored.get(station.id), now) for station in stations]
        return [status for status in statuses if status.count(SlotState.FREE) >= min_free]

    def station(self, station_id: str) -> StationStatus | None:
        station = self._catalog.get(station_id)
        if station is None:
            return None
        return self._status(station, self._occupancy.get(station_id), datetime.now(UTC))

    def nearest_with_free_slots(self, origin: Location, min_free: int) -> list[tuple[StationStatus, float]]:
        """Stations with at least min_free free slots, nearest first, with their straight-line distance in metres."""
        distances = [(status, origin.distance_to(status.station.location)) for status in self.stations(min_free)]
        return sorted(distances, key=lambda entry: entry[1])

    def model_file(self, station_id: str) -> Path | None:
        path = self._models_dir / f"{station_id}.usdz"
        return path if self._catalog.get(station_id) and path.is_file() else None

    def _status(self, station: Station, occupancy: StationOccupancy | None, now: datetime) -> StationStatus:
        occupancy = occupancy or StationOccupancy(station.id)
        slots = []
        for slot in station.slots:
            stored = occupancy.slot(slot.number)
            slots.append(SlotStatus(number=slot.number, state=stored.current_state(now, self._stale_after),
                                    location=slot.location, changed_at=stored.changed_at))
        return StationStatus(station=station, slots=tuple(slots), updated_at=occupancy.last_report())
