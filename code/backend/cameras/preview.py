"""Draws a camera's slot boxes on one of its frames, to check a calibration by eye.

Run from code/backend:
    .venv/bin/python -m cameras.preview data/cameras/<camera_id>.json <frame.jpg> <preview.png>
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cameras.camera import load_camera

BOX_COLOUR = (255, 220, 0)


def draw(calibration: Path, frame: Path) -> Image.Image:
    camera = load_camera(calibration)
    image = Image.open(frame).convert("RGB")
    if image.size != camera.frame_size:
        raise SystemExit(f"{frame} is {image.size[0]}x{image.size[1]}, calibration expects "
                         f"{camera.frame_size[0]}x{camera.frame_size[1]}")
    canvas = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    for slot in camera.slots:
        canvas.rectangle(slot.box, outline=BOX_COLOUR, width=3)
        canvas.text((slot.box[0] + 6, slot.box[1] + 4), str(slot.number), fill=BOX_COLOUR, font=font,
                    stroke_width=2, stroke_fill=(0, 0, 0))
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("frame", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(args.calibration, args.frame).save(args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
