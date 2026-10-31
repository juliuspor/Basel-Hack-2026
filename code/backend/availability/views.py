"""The JSON shapes riders' clients get, shared by the Availability API and the MCP server."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from availability.service import AvailabilityService, StationStatus
from occupancy.model import SlotState
from stations.catalog import Location


class LocationView(BaseModel):
    lat: float
    lon: float


class StationSummary(BaseModel):
    id: str = Field(description="Stable station id, e.g. cmr-north-01")
    name: str = Field(description="Display name")
    location: LocationView
    capacity: int = Field(description="Number of slots")
    free: int
    taken: int
    unknown: int = Field(description="Slots no camera has reported recently")
    updated_at: datetime | None = Field(description="Latest camera report at this station, null before the first")
    distance_m: float | None = Field(None, description="Straight-line distance from `near`, when it was given")


class StationList(BaseModel):
    stations: list[StationSummary]


class SlotDetail(BaseModel):
    number: int = Field(description="Matches the node slot_<number> in the station's 3D model")
    state: Literal["free", "taken", "unknown"]
    location: LocationView
    changed_at: datetime | None = Field(description="When the slot last changed state")


class StationDetail(BaseModel):
    id: str
    name: str
    location: LocationView
    capacity: int
    free: int
    taken: int
    unknown: int
    updated_at: datetime | None
    model_url: str | None = Field(description="Path of the station's 3D model on this server, null when there is none")
    slots: list[SlotDetail]


def model_url(service: AvailabilityService, station_id: str) -> str | None:
    return f"/v1/stations/{station_id}/model.usdz" if service.model_file(station_id) else None


def location_view(location: Location) -> LocationView:
    return LocationView(lat=location.lat, lon=location.lon)


def station_summary(status: StationStatus, distance_m: float | None = None) -> StationSummary:
    return StationSummary(
        id=status.station.id,
        name=status.station.name,
        location=location_view(status.station.location),
        capacity=status.station.capacity,
        free=status.count(SlotState.FREE),
        taken=status.count(SlotState.TAKEN),
        unknown=status.count(SlotState.UNKNOWN),
        updated_at=status.updated_at,
        distance_m=None if distance_m is None else round(distance_m, 1),
    )


def station_detail(status: StationStatus, model_url: str | None) -> StationDetail:
    summary = station_summary(status)
    return StationDetail(
        **summary.model_dump(exclude={"distance_m"}),
        model_url=model_url,
        slots=[
            SlotDetail(number=slot.number, state=slot.state.value, location=location_view(slot.location),
                       changed_at=slot.changed_at)
            for slot in status.slots
        ],
    )
