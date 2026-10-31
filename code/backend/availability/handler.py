"""Lambda entry point of the Availability function (handler: availability.handler.handler)."""

from typing import Any

from mangum import Mangum

import composition
import logs

logs.configure()
# Builds the service, its catalog and its DynamoDB table once per container,
# and fails at cold start when the configuration is broken.
composition.availability_service()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Mangum runs the ASGI lifespan on every invocation, and an MCP session
    # manager can start only once, so every invocation gets a fresh app around
    # the cached service.
    return Mangum(composition.availability_app(), lifespan="auto")(event, context)
