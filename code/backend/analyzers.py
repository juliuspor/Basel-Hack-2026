"""Turn one camera frame into per-slot occupancy.

Both analyzers use the camera's calibration (camera.json): every slot has a
numbered label point and a pixel region around the rack's wheel holder.
"""

import base64
import io
import json
import os
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


@dataclass
class Result:
    occupied: set
    person_present: bool = False
    detail: dict = field(default_factory=dict)


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


class DiffAnalyzer:
    """Compares each slot's wheel-holder region with a frame of the empty area.

    Needs no network or API key. Works on fixed cameras with stable light, so it
    is the offline fallback and a baseline for the vision model.
    """

    name = "reference-diff"

    def __init__(self, threshold=0.29):
        self.threshold = threshold

    def analyze(self, image, camera):
        reference = camera["reference_image"]
        diff = ImageChops.difference(image.convert("L"), reference.convert("L"))
        changed = diff.point(lambda v: 255 if v > 28 else 0)
        occupied, scores = set(), {}
        for key, slot in camera["slots"].items():
            box = tuple(round(v) for v in slot["roi"])
            share = ImageStat.Stat(changed.crop(box)).mean[0] / 255
            scores[key] = round(share, 3)
            if share > self.threshold:
                occupied.add(key)
        return Result(occupied, detail={"scores": scores})


class ClaudeAnalyzer:
    """Asks a small vision model which numbered slots hold a bike."""

    name = "claude"

    def __init__(self, model=None):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
        self.name = self.model

    def analyze(self, image, camera):
        slots = camera["slots"]
        prepared = draw_labels(privacy_mask(image, camera["area_roi"]), slots)
        buffer = io.BytesIO()
        prepared.save(buffer, "JPEG", quality=85)
        labels = sorted(slot["label"] for slot in slots.values())
        prompt = (
            "This is a fixed camera looking at a bicycle shelter with a front-wheel rack. "
            f"Yellow tags numbered {labels[0]}-{labels[-1]} sit on the ground in front of each "
            "rack slot; each slot's wheel holder is directly behind its tag. List the numbers of "
            "the slots that hold a bicycle or anything else that blocks the slot. Also say whether "
            "a person is visible near the rack."
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "occupied": {"type": "array", "items": {"type": "integer", "enum": labels}},
                            "person_present": {"type": "boolean"},
                        },
                        "required": ["occupied", "person_present"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(buffer.getvalue()).decode()}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        if response.stop_reason != "end_turn":
            raise RuntimeError(f"model stopped with {response.stop_reason}")
        data = json.loads(next(b.text for b in response.content if b.type == "text"))
        by_label = {slot["label"]: key for key, slot in slots.items()}
        return Result({by_label[n] for n in data["occupied"]}, data["person_present"],
                      {"usage": {"input": response.usage.input_tokens,
                                 "output": response.usage.output_tokens}})


def make_analyzer():
    """Claude when credentials exist (or ANALYZER=claude), otherwise the offline diff."""
    choice = os.environ.get("ANALYZER", "auto")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if choice == "claude" or (choice == "auto" and has_key):
        return ClaudeAnalyzer()
    return DiffAnalyzer()
