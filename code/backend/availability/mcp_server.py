"""The MCP server: the Availability API's answers as tools for AI agents.

Every tool calls AvailabilityService and returns the same shapes as the API.
It serves Streamable HTTP in stateless mode with plain JSON responses, so each
request stands alone, as on Lambda.
"""

from contextlib import AbstractAsyncContextManager
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.routing import BaseRoute

from availability.service import AvailabilityService
from availability.views import StationDetail, StationList, model_url, station_detail, station_summary
from stations.catalog import Location

MCP_PATH = "/mcp"
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
INSTRUCTIONS = (
    "Live bike parking at the Endress+Hauser site on Christoph-Merian-Ring in Reinach, Switzerland. "
    "Slots are free, taken, or unknown when no camera reported them in the last minutes. "
    "Use find_free_stations to answer where a rider can park near a place."
)


def build_server(service: AvailabilityService) -> MCPServer:
    server = MCPServer(name="Easy+Hitch", version="1.0.0", instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def list_stations() -> StationList:
        """Lists every bike station with its location and its free, taken and unknown slot counts."""
        return StationList(stations=[station_summary(status) for status in service.stations()])

    @server.tool(annotations=READ_ONLY)
    def get_station(station_id: Annotated[str, Field(description="Station id, e.g. cmr-north-01")]) -> StationDetail:
        """Returns one station with the number, state and location of every slot."""
        status = service.station(station_id)
        if status is None:
            known = ", ".join(entry.station.id for entry in service.stations())
            raise ToolError(f"Unknown station {station_id}. Known stations: {known}")
        return station_detail(status, model_url(service, station_id))

    @server.tool(annotations=READ_ONLY)
    def find_free_stations(
        lat: Annotated[float, Field(ge=-90, le=90, description="Latitude of the place to park near")],
        lon: Annotated[float, Field(ge=-180, le=180, description="Longitude of the place to park near")],
        min_free: Annotated[int, Field(ge=1, description="Free slots the rider needs")] = 1,
    ) -> StationList:
        """Finds stations with free slots near a place, nearest first, with the distance in metres."""
        nearest = service.nearest_with_free_slots(Location(lat=lat, lon=lon), min_free)
        return StationList(stations=[station_summary(status, distance) for status, distance in nearest])

    return server


class McpEndpoint:
    """The MCP server's HTTP route, and the session manager that has to run while the route serves."""

    def __init__(self, server: MCPServer) -> None:
        # The data is public and read-only and the server sets no cookies, so
        # the DNS rebinding check would only reject the Lambda URL's host.
        app = server.streamable_http_app(
            streamable_http_path=MCP_PATH,
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
        self.routes: list[BaseRoute] = list(app.routes)
        # Each streamable_http_app() call makes a new session manager. Keep the one behind these routes.
        self._session_manager = server.session_manager

    def running(self) -> AbstractAsyncContextManager[None]:
        return self._session_manager.run()
