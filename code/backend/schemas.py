"""The app-facing API contract.

These models define every response the iOS app reads. FastAPI turns them into
the OpenAPI spec (`/openapi.json`, exported to documentation/api/openapi.json).
Changing a field here changes the contract: update the spec and the app's demo
data in the same pull request (see documentation/architecture.md).
"""

from pydantic import BaseModel, Field


class AreaSummary(BaseModel):
    id: str = Field(description="Stable area id, e.g. curved-shelter-a")
    name: str = Field(description="Display name")
    kind: str = Field(description="Parking type, e.g. curved-shelter")
    center: list[float] = Field(description="[latitude, longitude] of the area centre", min_length=2,
                                max_length=2)
    polygon: list[list[float]] = Field(description="Outline corners as [latitude, longitude]")
    capacity: int = Field(description="Number of slots")
    occupied: int = Field(description="Slots holding a bike")
    free: int = Field(description="capacity - occupied")
    updated_at: float | None = Field(description="Unix time the slot states last changed; null "
                                     "until a camera frame was analysed")
    checked_at: float | None = Field(description="Unix time the camera last sent a frame")
    camera_time: str | None = Field(description="Camera clock of the last frame, e.g. 08:15")
    analyzer: str = Field(description="Vision provider that produced the states")
    model_url: str = Field(description="3D model of the area: a path on this server "
                           "(/models/<id>.usdz) or an absolute URL")


class Slot(BaseModel):
    id: str = Field(description="Slot id, matches the slot_<id> node in the 3D model")
    label: int = Field(description="Number painted on the ground marker")
    occupied: bool


class AreaDetail(AreaSummary):
    slots: list[Slot]
    person_present: bool = Field(description="A person is in view; slot states are kept from "
                                 "the previous frame")
    frames_analyzed: int
    frames_skipped: int = Field(description="Frames dropped by the change check")


class Health(BaseModel):
    ok: bool
    analyzer: str
    areas: int


class IngestResult(BaseModel):
    analyzed: bool = Field(description="False when the frame barely changed and was skipped")
    change: float | None = None
    seconds: float | None = None
    occupied: list[str] | None = None
    person_present: bool | None = None
