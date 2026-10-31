"""Structured logs: one JSON object per line.

Log lines carry ids, counts and timings only, never request bodies or images.
"""

import json
import logging

LOGGER = logging.getLogger("easyhitch")


def configure() -> None:
    # Lambda installs a root handler. On a laptop nothing does, so add one.
    if not logging.getLogger().handlers:
        logging.basicConfig(format="%(message)s")
    LOGGER.setLevel(logging.INFO)


def log_event(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, default=str))
