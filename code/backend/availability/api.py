"""The Availability API for the iOS app: stations, their slots and 3D models.

Station responses carry an ETag, so a polling client gets 304 Not Modified
while nothing changed.
"""

import hashlib
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from availability.service import AvailabilityService
from availability.views import StationDetail, StationList, model_url, station_detail, station_summary
from problems import Problem
from stations.catalog import Location

USDZ = "model/vnd.usdz+zip"
NOT_MODIFIED = {304: {"description": "Not modified since the ETag in If-None-Match"}}
NOT_FOUND = {404: {"description": "Unknown station, or no model for it"}}


class Health(BaseModel):
    status: Literal["ok"]


def create_router(service: AvailabilityService) -> APIRouter:
    router = APIRouter(tags=["availability"])

    @router.get("/v1/stations", response_model=StationList, responses=NOT_MODIFIED,
                summary="All stations with their free, taken and unknown slots")
    def list_stations(
        request: Request,
        near: str | None = Query(None, description="lat,lon: sort by distance from here and add distance_m",
                                 examples=["47.4875,7.6001"]),
        min_free: int = Query(0, ge=0, description="Only stations with at least this many free slots"),
    ) -> Response:
        if near is None:
            stations = [station_summary(status) for status in service.stations(min_free)]
        else:
            stations = [station_summary(status, distance)
                        for status, distance in service.nearest_with_free_slots(_location(near), min_free)]
        return _json_with_etag(request, StationList(stations=stations))

    @router.get("/v1/stations/{station_id}", response_model=StationDetail, responses={**NOT_MODIFIED, **NOT_FOUND},
                summary="One station with the state of every slot")
    def get_station(request: Request, station_id: str) -> Response:
        status = service.station(station_id)
        if status is None:
            raise Problem(HTTPStatus.NOT_FOUND, f"unknown station {station_id}")
        return _json_with_etag(request, station_detail(status, model_url(service, station_id)))

    @router.get("/v1/stations/{station_id}/model.usdz", response_class=FileResponse,
                responses={200: {"content": {USDZ: {}}}, **NOT_FOUND}, summary="The station's 3D model")
    def get_model(station_id: str) -> FileResponse:
        path = service.model_file(station_id)
        if path is None:
            raise Problem(HTTPStatus.NOT_FOUND, f"no 3D model for station {station_id}")
        return FileResponse(path, media_type=USDZ)

    @router.get("/v1/health", response_model=Health)
    def health() -> Health:
        return Health(status="ok")

    return router


def _location(near: str) -> Location:
    try:
        lat, lon = (float(part) for part in near.split(","))
    except ValueError as error:
        raise Problem(HTTPStatus.UNPROCESSABLE_CONTENT, "near must be lat,lon, e.g. 47.4875,7.6001") from error
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise Problem(HTTPStatus.UNPROCESSABLE_CONTENT, "near is outside valid latitudes and longitudes")
    return Location(lat=lat, lon=lon)


def _json_with_etag(request: Request, body: BaseModel) -> Response:
    content = body.model_dump_json().encode()
    etag = '"' + hashlib.sha256(content).hexdigest()[:32] + '"'
    sent = {tag.strip().removeprefix("W/") for tag in request.headers.get("if-none-match", "").split(",")}
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if etag in sent or "*" in sent:
        return Response(status_code=HTTPStatus.NOT_MODIFIED, headers=headers)
    return Response(content=content, media_type="application/json", headers=headers)
