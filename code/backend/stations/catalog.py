"""The bike stations and their slots, as bundled in data/stations.json."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

EARTH_RADIUS_M = 6_371_000


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float

    def distance_to(self, other: "Location") -> float:
        """Great-circle distance in metres (haversine formula)."""
        lat1, lat2 = math.radians(self.lat), math.radians(other.lat)
        dlat = lat2 - lat1
        dlon = math.radians(other.lon - self.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Slot:
    number: int
    location: Location


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    location: Location
    slots: tuple[Slot, ...]

    @property
    def capacity(self) -> int:
        return len(self.slots)


class CatalogError(ValueError):
    """stations.json is missing something the backend relies on."""


class StationCatalog:
    def __init__(self, stations: list[Station]) -> None:
        self._stations = {station.id: station for station in stations}
        if len(self._stations) != len(stations):
            raise CatalogError("station ids must be unique")
        for station in stations:
            numbers = [slot.number for slot in station.slots]
            if len(set(numbers)) != len(numbers):
                raise CatalogError(f"slot numbers repeat in station {station.id}")

    @classmethod
    def load(cls, path: Path) -> "StationCatalog":
        try:
            entries = json.loads(path.read_text())["stations"]
            return cls([_station(entry) for entry in entries])
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise CatalogError(f"{path}: {error}") from error

    def all(self) -> list[Station]:
        return list(self._stations.values())

    def get(self, station_id: str) -> Station | None:
        return self._stations.get(station_id)


def _location(entry: dict) -> Location:
    return Location(lat=float(entry["lat"]), lon=float(entry["lon"]))


def _station(entry: dict) -> Station:
    slots = tuple(Slot(number=int(slot["number"]), location=_location(slot["location"])) for slot in entry["slots"])
    return Station(id=entry["id"], name=entry["name"], location=_location(entry["location"]), slots=slots)
