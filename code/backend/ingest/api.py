"""POST /v1/frames: cameras upload pixelated frames here.

The router authenticates the camera, so the service never sees the token.
"""

import json
import time
from datetime import datetime
from http import HTTPStatus

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from cameras.camera import Box, Camera
from cameras.registry import CameraRegistry
from classification.classifier import ClassifierUnavailable
from ingest.frame import NotAJpeg
from ingest.service import FrameSizeMismatch, IngestService
from logs import log_event
from problems import Problem

MAX_FRAME_BYTES = 1_000_000


class IngestResponse(BaseModel):
    camera_id: str
    station_id: str
    slots_checked: int
    slots_changed: int


def create_router(service: IngestService, registry: CameraRegistry) -> APIRouter:
    router = APIRouter(tags=["ingest"])

    @router.post(
        "/v1/frames",
        response_model=IngestResponse,
        summary="Upload one pixelated camera frame",
        openapi_extra={"requestBody": {
            "required": True,
            "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
        }},
        responses={code: {"description": text} for code, text in [
            (401, "Unknown camera token"), (413, "Frame larger than 1 MB"), (415, "Body is not a JPEG"),
            (422, "Invalid headers, or a frame of the wrong size"), (502, "Classifier unavailable, retry later"),
        ]},
    )
    async def upload_frame(
        request: Request,
        authorization: str | None = Header(None),
        x_captured_at: str | None = Header(None, description="Board time of capture, ISO 8601"),
        x_person_boxes: str = Header("[]", description="JSON list of [x0, y0, x1, y1] pixel boxes"),
    ) -> IngestResponse:
        camera = _authenticate(registry, authorization)
        if request.headers.get("content-type", "").split(";")[0].strip() != "image/jpeg":
            raise Problem(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be image/jpeg")
        captured_at = _captured_at(x_captured_at)
        person_boxes = _person_boxes(x_person_boxes)
        body = await request.body()
        if len(body) > MAX_FRAME_BYTES:
            raise Problem(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, f"frame is {len(body)} bytes, at most {MAX_FRAME_BYTES}")
        started = time.monotonic()
        try:
            result = await run_in_threadpool(service.ingest, camera, body, person_boxes)
        except NotAJpeg as error:
            raise Problem(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, str(error)) from error
        except FrameSizeMismatch as error:
            raise Problem(HTTPStatus.UNPROCESSABLE_CONTENT, str(error)) from error
        except ClassifierUnavailable as error:
            log_event("frame_failed", camera_id=camera.id, reason=str(error))
            raise Problem(HTTPStatus.BAD_GATEWAY,
                          "the classifier is unavailable, send the frame again later") from error
        log_event("frame_ingested", camera_id=result.camera_id, station_id=result.station_id,
                  captured_at=captured_at.isoformat(), slots_checked=result.slots_checked,
                  slots_changed=result.slots_changed, seconds=round(time.monotonic() - started, 3))
        return IngestResponse(camera_id=result.camera_id, station_id=result.station_id,
                              slots_checked=result.slots_checked, slots_changed=result.slots_changed)

    return router


def _authenticate(registry: CameraRegistry, authorization: str | None) -> Camera:
    scheme, _, token = (authorization or "").partition(" ")
    camera = registry.camera_for_token(token.strip()) if scheme.lower() == "bearer" and token.strip() else None
    if camera is None:
        raise Problem(HTTPStatus.UNAUTHORIZED, "unknown camera token", headers={"WWW-Authenticate": "Bearer"})
    return camera


def _captured_at(value: str | None) -> datetime:
    if value is None:
        raise Problem(HTTPStatus.UNPROCESSABLE_CONTENT, "X-Captured-At header is required")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise Problem(HTTPStatus.UNPROCESSABLE_CONTENT, "X-Captured-At must be an ISO 8601 time") from error


def _person_boxes(value: str) -> list[Box]:
    try:
        boxes = json.loads(value)
        if not isinstance(boxes, list):
            raise TypeError("not a list")
        return [_box(entry) for entry in boxes]
    except (TypeError, ValueError) as error:
        raise Problem(HTTPStatus.UNPROCESSABLE_CONTENT,
                      "X-Person-Boxes must be a JSON list of [x0, y0, x1, y1] boxes") from error


def _box(entry: object) -> Box:
    numbers = isinstance(entry, list) and all(
        isinstance(value, int | float) and not isinstance(value, bool) for value in entry)
    if not (numbers and len(entry) == 4):
        raise ValueError(f"{entry!r} is not a box")
    x0, y0, x1, y1 = (int(value) for value in entry)
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"{entry!r} is empty")
    return x0, y0, x1, y1
