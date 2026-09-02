import base64

import pytest
from mcp_contracts import (
    MCPTool,
    MultipartFileMapping,
    ParameterMapping,
    RequestBodyMapping,
    RequestMapping,
    ServerDefinition,
)
from mcp_contracts.manifest import HttpMethod, ParameterTarget
from pydantic import AnyHttpUrl

from app.auth.upstream import AuthInjection
from app.executor.errors import ArgumentValidationError
from app.executor.request_builder import QueryParameter, build_request
from app.security.url_policy import UpstreamUrlPolicy


def _policy() -> UpstreamUrlPolicy:
    return UpstreamUrlPolicy([ServerDefinition(id="main", url=AnyHttpUrl("https://8.8.8.8/api"))])


def test_path_query_header_and_auth_mapping_is_deterministic() -> None:
    tool = MCPTool(
        name="get_product",
        title="Get product",
        description="Get product",
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "trace": {"type": "string"},
            },
            "required": ["product_id"],
            "additionalProperties": False,
        },
        operation_key="op_1",
        request_mapping=RequestMapping(
            server_ref="main",
            method=HttpMethod.GET,
            path="/products/{product_id}",
            parameters=[
                ParameterMapping(
                    tool_field="product_id",
                    source_name="product_id",
                    target=ParameterTarget.PATH,
                    required=True,
                ),
                ParameterMapping(
                    tool_field="tags",
                    source_name="tag",
                    target=ParameterTarget.QUERY,
                    style="form",
                    explode=True,
                ),
                ParameterMapping(
                    tool_field="trace",
                    source_name="X-Trace",
                    target=ParameterTarget.HEADER,
                ),
            ],
        ),
    )
    request = build_request(
        tool,
        {"product_id": "a/b", "tags": ["one", "two"], "trace": "trace-1"},
        _policy(),
        AuthInjection(headers=(("Authorization", "Bearer secret"),)),
    )

    assert request.url == "https://8.8.8.8/api/products/a%2Fb"
    assert request.query == (
        QueryParameter("tag", "one"),
        QueryParameter("tag", "two"),
    )
    assert request.headers[-1] == ("Authorization", "Bearer secret")

    with pytest.raises(ArgumentValidationError, match="Undeclared"):
        build_request(tool, {"product_id": "1", "host": "evil"}, _policy(), AuthInjection())


def test_embedded_and_multiple_path_parameters_are_substituted_exactly() -> None:
    tool = MCPTool(
        name="coordinate_file",
        title="Coordinate file",
        description="Read one coordinate file",
        input_schema={
            "type": "object",
            "properties": {
                "latitude": {"type": "string"},
                "longitude": {"type": "string"},
                "format": {"type": "string"},
            },
            "required": ["latitude", "longitude", "format"],
            "additionalProperties": False,
        },
        operation_key="op_coordinates",
        request_mapping=RequestMapping(
            server_ref="main",
            method=HttpMethod.GET,
            path="/coordinates/{lat},{lon}.{format}",
            parameters=[
                ParameterMapping(
                    tool_field="latitude",
                    source_name="lat",
                    target=ParameterTarget.PATH,
                    required=True,
                ),
                ParameterMapping(
                    tool_field="longitude",
                    source_name="lon",
                    target=ParameterTarget.PATH,
                    required=True,
                ),
                ParameterMapping(
                    tool_field="format",
                    source_name="format",
                    target=ParameterTarget.PATH,
                    required=True,
                ),
            ],
        ),
    )
    request = build_request(
        tool,
        {"latitude": "1/2", "longitude": "3,4", "format": "json"},
        _policy(),
        AuthInjection(),
    )
    assert request.url == "https://8.8.8.8/api/coordinates/1%2F2,3%2C4.json"


def test_multipart_mapping_decodes_only_declared_file_fields() -> None:
    tool = MCPTool(
        name="upload_document",
        title="Upload",
        description="Upload",
        input_schema={
            "type": "object",
            "properties": {"body": {"type": "object"}},
            "required": ["body"],
            "additionalProperties": False,
        },
        operation_key="op_upload",
        request_mapping=RequestMapping(
            server_ref="main",
            method=HttpMethod.POST,
            path="/documents",
            body=RequestBodyMapping(
                media_type="multipart/form-data",
                required=True,
                multipart_files=[
                    MultipartFileMapping(
                        part_name="file",
                        content_field="content_base64",
                        filename_field="filename",
                        required=True,
                    )
                ],
            ),
        ),
    )
    request = build_request(
        tool,
        {
            "body": {
                "content_base64": base64.b64encode(b"hello").decode("ascii"),
                "filename": "hello.txt",
                "label": "documentation",
            }
        },
        _policy(),
        AuthInjection(),
    )

    assert request.multipart_body is not None
    assert request.multipart_body[0].content == b"hello"
    assert request.multipart_body[0].filename == "hello.txt"
    assert request.multipart_body[1].content == b"documentation"
