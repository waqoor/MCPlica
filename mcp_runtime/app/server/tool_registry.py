from mcp_contracts import MCPManifest, MCPTool


class ToolRegistry:
    def __init__(self, manifest: MCPManifest) -> None:
        self._tools = {tool.name: tool for tool in manifest.enabled_tools()}

    def list(self) -> tuple[MCPTool, ...]:
        return tuple(self._tools.values())

    def get(self, name: str) -> MCPTool | None:
        return self._tools.get(name)
