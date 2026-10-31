"""Builds the FastAPI apps that the Lambda handlers and local.py serve."""

from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

import problems

if TYPE_CHECKING:
    from availability.mcp_server import McpEndpoint


def create_app(title: str, routers: Sequence[APIRouter], mcp: "McpEndpoint | None" = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            if mcp is not None:
                await stack.enter_async_context(mcp.running())
            yield

    app = FastAPI(title=title, version="1.0.0", lifespan=lifespan)
    problems.install(app)
    for router in routers:
        app.include_router(router)
    if mcp is not None:
        app.router.routes.extend(mcp.routes)
    return app
