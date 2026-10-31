"""Reads slots with Jev through OpenRouter's Decisions API.

One request carries every slot of a frame: each slot crop is one image in the
state, and each gets one yes/no ("noul") question. Jev answers every question
with the probability that the statement is true.

Request format and image limits:
https://openrouter.ai/docs/guides/community/multimodal-decisions
"""

import base64
import io
import math
from collections.abc import Iterator, Sequence

import httpx
from PIL import Image

from cameras.camera import SlotView
from classification.classifier import ClassifierUnavailable, Reading

# Jev takes 256 to 1,568 pixels per side and at least 78,400 pixels in total.
# 280 x 280 meets both minimums.
MIN_SIDE = 280
MAX_SIDE = 1568
# TypeSafe limits each request to 32 MiB including base64, which grows the
# images by a third, so the raw JPEGs of one request stay below 20 MiB.
MAX_BATCH_BYTES = 20 * 1024 * 1024
JPEG_QUALITY = 90
PAD_COLOUR = (128, 128, 128)
STATEMENT = "A bicycle or another two-wheeler is parked in the slot shown in `{key}`."


class JevCropClassifier:
    def __init__(self, client: httpx.Client, api_key: str, model: str, url: str) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model
        self._url = url

    def classify(self, frame: Image.Image, slots: Sequence[SlotView]) -> dict[int, Reading]:
        readings = {}
        for batch in _batches(slots, frame):
            readings.update(self._ask(batch))
        return readings

    def _ask(self, crops: dict[int, bytes]) -> dict[int, Reading]:
        keys = {number: f"slot_{number}" for number in crops}
        request = {
            "model": self._model,
            "state": {keys[number]: _image_part(jpeg) for number, jpeg in crops.items()},
            "questions": {key: {"type": "noul", "instructions": STATEMENT.format(key=key)} for key in keys.values()},
        }
        try:
            response = self._client.post(self._url, json=request, headers={"Authorization": f"Bearer {self._api_key}"})
        except httpx.HTTPError as error:
            raise ClassifierUnavailable(f"Decisions API unreachable: {error}") from error
        if response.status_code != httpx.codes.OK:
            raise ClassifierUnavailable(f"Decisions API answered {response.status_code}: {response.text[:300]}")
        try:
            answers = response.json()["answers"]
            return {number: _reading(float(answers[key]["noul"])) for number, key in keys.items()}
        except (KeyError, TypeError, ValueError) as error:
            raise ClassifierUnavailable(f"Decisions API answer is incomplete: {error}") from error


def fit_for_jev(image: Image.Image) -> Image.Image:
    """Scales a crop into Jev's size limits, padding a very narrow crop instead of distorting it."""
    width, height = image.size
    scale = max(MIN_SIDE / width, MIN_SIDE / height, 1.0)
    scale = min(scale, MAX_SIDE / max(width, height))
    size = (max(1, math.ceil(width * scale)), max(1, math.ceil(height * scale)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    resized = resized.crop((0, 0, min(resized.width, MAX_SIDE), min(resized.height, MAX_SIDE)))
    if resized.width >= MIN_SIDE and resized.height >= MIN_SIDE:
        return resized
    canvas = Image.new("RGB", (max(resized.width, MIN_SIDE), max(resized.height, MIN_SIDE)), PAD_COLOUR)
    canvas.paste(resized, ((canvas.width - resized.width) // 2, (canvas.height - resized.height) // 2))
    return canvas


def _batches(slots: Sequence[SlotView], frame: Image.Image) -> Iterator[dict[int, bytes]]:
    batch: dict[int, bytes] = {}
    size = 0
    for slot in slots:
        jpeg = _jpeg(fit_for_jev(slot.crop(frame).convert("RGB")))
        if batch and size + len(jpeg) > MAX_BATCH_BYTES:
            yield batch
            batch, size = {}, 0
        batch[slot.number] = jpeg
        size += len(jpeg)
    if batch:
        yield batch


def _jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _image_part(jpeg: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}}


def _reading(probability: float) -> Reading:
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability {probability} is outside 0 to 1")
    return Reading(taken=probability >= 0.5, confidence=max(probability, 1.0 - probability))
