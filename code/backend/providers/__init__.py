"""Vision providers: one module per model or method, picked with VISION_PROVIDER.

To add one (e.g. OpenAI or a model on AWS Bedrock), write a class with a `name`
and `analyze(image, camera) -> Result` in its own module, reusing the helpers
in base.py, and register it in PROVIDERS below.
"""

import os

from .base import Result, VisionProvider, privacy_mask


def _diff():
    from .diff import DiffProvider
    return DiffProvider()


def _claude():
    from .claude import ClaudeProvider
    return ClaudeProvider()


# Imported lazily, so a provider's SDK is only needed when it is used.
PROVIDERS = {
    "diff": _diff,
    "claude": _claude,
}


def make_provider(name=None):
    """VISION_PROVIDER picks one; `auto` uses Claude when its credentials exist, else diff."""
    name = name or os.environ.get("VISION_PROVIDER") or os.environ.get("ANALYZER", "auto")
    if name == "auto":
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        name = "claude" if has_key else "diff"
    if name not in PROVIDERS:
        raise ValueError(f"unknown VISION_PROVIDER {name!r}; choose from {', '.join(PROVIDERS)}")
    return PROVIDERS[name]()


__all__ = ["PROVIDERS", "Result", "VisionProvider", "make_provider", "privacy_mask"]
