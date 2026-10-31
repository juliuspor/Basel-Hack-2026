from PIL import ImageChops, ImageStat

from .base import Result


class DiffProvider:
    """Compares each slot's wheel-holder region with a frame of the empty area.

    Needs no network or API key. Works on fixed cameras with stable light, so it
    is the offline fallback and a baseline for the vision models.
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
