"""Finds readable text, licence plates among it, so that a live camera pixelates it before upload.

Plate detectors trained on car plates miss plates that are common at a bike shelter, such as the
small yellow e-bike plates or a tilted motorbike plate. A text detector finds them by their
characters, and any other readable text, such as a name on a bag, with them.
"""

import hashlib
from pathlib import Path

import httpx

from frame import Box, Frame
from pii import Detections

# PP-OCRv5's mobile text detector (Apache-2.0), pinned to one commit and checked before every load,
# as a swapped model could let plates through.
MODEL_URL = ("https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx/resolve/"
             "e6f4fa85f00e168c862bc462aebca69eef9b3d3d/inference.onnx")
MODEL_SHA256 = "a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d"
MODEL_PATH = Path(__file__).with_name("ppocrv5-mobile-det.onnx")
# PaddleOCR's input: a BGR frame less ImageNet's channel means, over a standard deviation of about 0.226.
MEAN = (123.675, 116.28, 103.53)
SCALE = 1 / (0.226 * 255)
TEXT_THRESHOLD = 0.2  # text probability above which a pixel belongs to the core of a text line
# The detector marks a shrunken core of each text line. Growing it by two of its heights on every
# side covers the whole line and the lines above and below it, as a plate stacks two or three lines
# and the detector may find only one of them.
GROWTH = 2


class TextPIIDetector:
    """Finds readable text with PP-OCRv5, at the frame's full resolution so that small plates count too."""

    def __init__(self) -> None:
        # OpenCV is an optional dependency (requirements-camera.txt), only needed here.
        import cv2

        self._net = cv2.dnn.readNetFromONNX(str(_pinned_model()))

    def detect(self, frame: Frame) -> Detections:
        import cv2
        import numpy as np

        width, height = frame.image.size
        size = (max(32, width // 32 * 32), max(32, height // 32 * 32))  # the network takes multiples of 32
        bgr = cv2.cvtColor(np.asarray(frame.image), cv2.COLOR_RGB2BGR)
        self._net.setInput(cv2.dnn.blobFromImage(bgr, SCALE, size, MEAN, swapRB=False))
        cores = (self._net.forward()[0, 0] > TEXT_THRESHOLD).astype(np.uint8)
        contours, _ = cv2.findContours(cores, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return Detections(pii_regions=tuple(
            _grown(cv2.boundingRect(contour), width / size[0], height / size[1], frame) for contour in contours))


def _grown(core: tuple[int, int, int, int], x_scale: float, y_scale: float, frame: Frame) -> Box:
    """Grows a text core by GROWTH of its heights and maps it from the network's input onto the frame."""
    x, y, core_width, core_height = core
    grow = GROWTH * core_height
    x0, y0 = round((x - grow) * x_scale), round((y - grow) * y_scale)
    x1, y1 = round((x + core_width + grow) * x_scale), round((y + core_height + grow) * y_scale)
    return max(0, x0), max(0, y0), min(frame.image.width, x1), min(frame.image.height, y1)


def _pinned_model() -> Path:
    """Downloads the model on first use, and refuses a file that is not the pinned one."""
    if not MODEL_PATH.is_file():
        MODEL_PATH.write_bytes(httpx.get(MODEL_URL, follow_redirects=True, timeout=60).raise_for_status().content)
    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != MODEL_SHA256:
        raise ValueError(f"{MODEL_PATH} is not the pinned PP-OCRv5 model. Delete it to download it again")
    return MODEL_PATH
