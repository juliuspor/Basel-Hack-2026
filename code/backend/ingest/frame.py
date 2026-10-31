"""Decodes uploaded frames and fingerprints their slots, in memory only."""

import io

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

from cameras.camera import Box

# A slot's fingerprint packs two measures into one integer:
# - a 64-bit difference hash (each bit: is a pixel brighter than its right
#   neighbour?), which catches shapes such as a bike arriving or leaving,
# - the average grey level above those bits, which catches a slot turning
#   darker or brighter as a whole, which the hash alone cannot see.
HASH_SIZE = 8
HASH_BITS = HASH_SIZE * HASH_SIZE
# Light and sensor noise flip a few hash bits and nudge the brightness.
# A bike that arrives or leaves changes far more.
HASH_TOLERANCE = 6
BRIGHTNESS_TOLERANCE = 20


class NotAJpeg(ValueError):
    """The request body is not a JPEG image."""


def decode_jpeg(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        if image.format != "JPEG":
            raise NotAJpeg(f"body is {image.format}, not JPEG")
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise NotAJpeg("body is not a readable JPEG") from error
    return ImageOps.exif_transpose(image).convert("RGB")


def fingerprint(frame: Image.Image, box: Box) -> int:
    grey = frame.crop(box).convert("L")
    small = grey.resize((HASH_SIZE + 1, HASH_SIZE), Image.Resampling.BOX)
    pixels = small.tobytes()  # one byte per pixel, row by row
    bits = 0
    for row in range(HASH_SIZE):
        for column in range(HASH_SIZE):
            left = pixels[row * (HASH_SIZE + 1) + column]
            right = pixels[row * (HASH_SIZE + 1) + column + 1]
            bits = (bits << 1) | (left > right)
    brightness = round(ImageStat.Stat(grey).mean[0])
    return (brightness << HASH_BITS) | bits


def has_changed(previous: int | None, current: int) -> bool:
    if previous is None:
        return True
    hash_mask = (1 << HASH_BITS) - 1
    flipped_bits = ((previous ^ current) & hash_mask).bit_count()
    brightness_shift = abs((previous >> HASH_BITS) - (current >> HASH_BITS))
    return flipped_bits > HASH_TOLERANCE or brightness_shift > BRIGHTNESS_TOLERANCE
