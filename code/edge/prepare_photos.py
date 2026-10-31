"""Turns photos into recorded frames for one camera: upright, at the camera's frame size.

Run from code/edge:
    .venv/bin/python prepare_photos.py cam-south-a ../../assets/challenge-site-photos/IMG_20261029_083909.jpg \\
        --output ../../assets/camera-frames

Each frame needs a sidecar JSON file next to it listing people and the regions
to pixelate. prepare_photos.py writes an empty one, to be filled in by hand.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps

from frame import parse_size

JPEG_QUALITY = 90


def prepare(camera_id: str, photos: list[Path], output: Path, frame_size: tuple[int, int]) -> None:
    folder = output / camera_id
    folder.mkdir(parents=True, exist_ok=True)
    for photo in photos:
        image = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
        image = image.resize(frame_size, Image.Resampling.LANCZOS)
        target = folder / f"{photo.stem}.jpg"
        image.save(target, quality=JPEG_QUALITY)
        sidecar = target.with_suffix(".json")
        if not sidecar.exists():
            sidecar.write_text(json.dumps({"people": [], "pii_regions": []}, indent=2) + "\n")
        print(f"wrote {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("camera_id")
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="folder with one subfolder per camera")
    parser.add_argument("--size", type=parse_size, default=(1280, 960), help="frame size (default 1280x960)")
    args = parser.parse_args()
    prepare(args.camera_id, args.photos, args.output, args.size)


if __name__ == "__main__":
    main()
