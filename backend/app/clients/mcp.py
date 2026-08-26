from typing import Any

from mcp import Client

from app.clients.base import AsyncClient


class MCPValidationClient(AsyncClient):
    async def health(self) -> bool:
        return True

    async def inspect(self, endpoint: str) -> dict[str, Any]:
        async with Client(endpoint) as client:
            tools = await client.list_tools()
            return {
                "protocol_version": client.protocol_version,
                "tool_count": len(tools.tools),
                "tools": [tool.name for tool in tools.tools],
            }
