"""Finds the camera behind a bearer token.

Only SHA-256 hashes of tokens are kept. Locally they are computed from the
development tokens in data/local-cameras.json. On AWS they come from an SSM
parameter, so the real tokens exist only on the boards.
"""

import hashlib
import hmac
import json
from pathlib import Path

from cameras.camera import CalibrationError, Camera


class TokenError(ValueError):
    """A token file or parameter is not a JSON object of camera id to token or hash."""


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class CameraRegistry:
    def __init__(self, cameras: dict[str, Camera], token_hashes: dict[str, str]) -> None:
        uncalibrated = sorted(set(token_hashes) - set(cameras))
        if uncalibrated:
            raise CalibrationError(f"tokens for cameras without calibration: {', '.join(uncalibrated)}")
        self._cameras_by_hash = [(digest, cameras[camera_id]) for camera_id, digest in token_hashes.items()]

    def camera_for_token(self, token: str) -> Camera | None:
        digest = token_hash(token)
        for known, camera in self._cameras_by_hash:
            if hmac.compare_digest(known, digest):
                return camera
        return None


def token_hashes_from_tokens(tokens: dict[str, str]) -> dict[str, str]:
    """Hashes a mapping of camera id to plain token."""
    return {camera_id: token_hash(token) for camera_id, token in tokens.items()}


def read_token_file(path: Path) -> dict[str, str]:
    """Reads a JSON object of camera id to plain development token."""
    return _string_mapping(json.loads(path.read_text()), str(path))


def parse_token_hashes(text: str, source: str) -> dict[str, str]:
    """Parses a JSON object of camera id to SHA-256 hex digest of its token."""
    hashes = _string_mapping(json.loads(text), source)
    malformed = sorted(camera for camera, digest in hashes.items() if not _is_sha256_hex(digest))
    if malformed:
        raise TokenError(f"{source}: not a SHA-256 hex digest for {', '.join(malformed)}")
    return hashes


def _is_sha256_hex(digest: str) -> bool:
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest.lower())


def _string_mapping(value: object, source: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise TokenError(f"{source}: expected a JSON object of camera id to string")
    return value
