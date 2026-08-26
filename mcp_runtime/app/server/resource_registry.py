from mcp_contracts import MCPManifest, MCPResource


class ResourceRegistry:
    def __init__(self, manifest: MCPManifest) -> None:
        self._resources = {resource.uri: resource for resource in manifest.resources}

    def list(self) -> tuple[MCPResource, ...]:
        return tuple(self._resources.values())

    def get(self, uri: str) -> MCPResource | None:
        return self._resources.get(uri)
