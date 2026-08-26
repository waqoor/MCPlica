from mcp_contracts import (
    MCPTool,
    ParameterMapping,
    RequestMapping,
    ServerDefinition,
)
from mcp_contracts.manifest import HttpMethod, ParameterTarget

from app.auth.upstream import AuthInjection
from app.executor.request_builder import build_request


def test_path_and_query_mapping_is_deterministic() -> None:
    tool = MCPTool(
        name="get_product",
        title="Get product",
        description="Get product",
        input_schema={"type": "object"},
        operation_key="op_1",
        request_mapping=RequestMapping(
            server_ref="main",
            method=HttpMethod.GET,
            path="/products/{product_id}",
            parameters=[
                ParameterMapping(tool_field="product_id", source_name="product_id", target=ParameterTarget.PATH, required=True),
                ParameterMapping(tool_field="include", source_name="include", target=ParameterTarget.QUERY),
            ],
        ),
    )
    request = build_request(
        tool,
        {"product_id": "a/b", "include": "stock"},
        ServerDefinition(id="main", url="https://api.example.com"),
        AuthInjection(),
    )
    assert request.url == "https://api.example.com/products/a%2Fb"
    assert request.query == {"include": "stock"}
