"""What every vision provider gets and returns.

The backend masks each frame to the parking area *before* calling a provider,
so a provider never sees anything outside it. A provider turns that masked
frame plus the camera calibration into a Result.

Calibration (`camera`, from the area's camera.json):
- `slots`: {slot_id: {"label": int, "label_px": [x, y], "roi": [x0, y0, x1, y1]}}
- `area_roi`: [x0, y0, x1, y1] of the parking area in the image
- `reference_image`: PIL image of the empty area

Model-based providers should reuse `tagged_jpeg`, `PROMPT` and `result_schema`
so every model gets the same input and is compared fairly.
"""

import io
from dataclasses import dataclass, field
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont


@dataclass
class Result:
    occupied: set  # slot ids that hold a bike or are otherwise blocked
    person_present: bool = False
    detail: dict = field(default_factory=dict)  # free-form, e.g. scores or token usage


class VisionProvider(Protocol):
    name: str

    def analyze(self, image: Image.Image, camera: dict) -> Result: ...


def privacy_mask(image, area_roi):
    """Black out everything outside the parking area before it goes anywhere."""
    masked = Image.new("RGB", image.size)
    box = tuple(round(v) for v in area_roi)
    masked.paste(image.crop(box), box[:2])
    return masked


def draw_labels(image, slots):
    """Numbered tags on the ground in front of each slot (set-of-mark prompting)."""
    image = image.copy()
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    for slot in slots.values():
        x, y = slot["label_px"]
        text = str(slot["label"])
        draw.rounded_rectangle((x - 13, y - 11, x + 13, y + 11), radius=5, fill=(255, 220, 0),
                               outline=(0, 0, 0))
        draw.text((x, y), text, fill=(0, 0, 0), font=font, anchor="mm")
    return image


def tagged_jpeg(image, camera):
    """The frame with numbered slot tags, as JPEG bytes for a vision model."""
    buffer = io.BytesIO()
    draw_labels(image, camera["slots"]).save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def labels(camera):
    return sorted(slot["label"] for slot in camera["slots"].values())


def prompt(camera):
    numbers = labels(camera)
    return (
        "This is a fixed camera looking at a bicycle shelter with a front-wheel rack. "
        f"Yellow tags numbered {numbers[0]}-{numbers[-1]} sit on the ground in front of each "
        "rack slot; each slot's wheel holder is directly behind its tag. List the numbers of "
        "the slots that hold a bicycle or anything else that blocks the slot. Also say whether "
        "a person is visible near the rack."
    )


def result_schema(camera):
    """JSON schema of the model's answer: {"occupied": [tag numbers], "person_present": bool}."""
    return {
        "type": "object",
        "properties": {
            "occupied": {"type": "array", "items": {"type": "integer", "enum": labels(camera)}},
            "person_present": {"type": "boolean"},
        },
        "required": ["occupied", "person_present"],
        "additionalProperties": False,
    }


def from_answer(answer, camera, detail=None):
    """Turn a model answer that matches `result_schema` into a Result."""
    by_label = {slot["label"]: key for key, slot in camera["slots"].items()}
    return Result({by_label[n] for n in answer["occupied"] if n in by_label},
                  bool(answer["person_present"]), detail or {})
