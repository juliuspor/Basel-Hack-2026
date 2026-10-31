"""Decides whether a frame differs enough from the last accepted one to be worth uploading."""

from PIL import Image, ImageChops

THUMBNAIL = (80, 60)
# A pixel counts as changed when its grey level moves by more than this...
PIXEL_THRESHOLD = 30
# ...and a frame counts as changed when more than this share of pixels did.
# Sensor noise moves single pixels, while a bike arriving moves a whole region.
CHANGED_SHARE = 0.005


class ChangeDetector:
    """Compares against the last frame the backend accepted, not the last one captured.

    A change that happens while uploads fail therefore stays visible until an
    upload succeeds.
    """

    def __init__(self) -> None:
        self._baseline: Image.Image | None = None

    def has_changed(self, image: Image.Image) -> bool:
        if self._baseline is None:
            return True
        difference = ImageChops.difference(_thumbnail(image), self._baseline)
        changed_pixels = sum(1 for level in difference.tobytes() if level > PIXEL_THRESHOLD)
        return changed_pixels > CHANGED_SHARE * THUMBNAIL[0] * THUMBNAIL[1]

    def accept(self, image: Image.Image) -> None:
        self._baseline = _thumbnail(image)


def _thumbnail(image: Image.Image) -> Image.Image:
    return image.convert("L").resize(THUMBNAIL, Image.Resampling.BOX)
