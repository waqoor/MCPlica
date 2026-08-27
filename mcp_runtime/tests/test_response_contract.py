import pytest
from mcp_contracts import MCPTool, RequestMapping, ResponseDefinition
from mcp_contracts.manifest import HttpMethod

from app.clients.api_client import UpstreamResult
from app.executor.errors import RuntimeConfigurationError, UpstreamResponseContractError
from app.executor.response_contract import (
    compile_response_contract,
    validate_upstream_response,
)


def _tool(responses: list[ResponseDefinition]) -> MCPTool:
    return MCPTool(
        name="response_matrix",
        title="Response matrix",
        description="Exercises response dispatch",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={
            "type": "object",
            "required": ["status", "contentType", "body"],
        },
        responses=responses,
        operation_key="GET /matrix",
        request_mapping=RequestMapping(
            server_ref="main",
            method=HttpMethod.GET,
            path="/matrix",
        ),
    )


def test_dispatches_exact_class_and_default_contracts_with_media_precedence() -> None:
    contract = compile_response_contract(
        _tool(
            [
                ResponseDefinition(
                    status_code="200",
                    media_type="application/json",
                    schema={
                        "type": "object",
                        "required": ["kind"],
                        "properties": {"kind": {"const": "exact"}},
                        "additionalProperties": False,
                    },
                ),
                ResponseDefinition(
                    status_code="2XX",
                    media_type="application/*+json",
                    schema={"type": "array", "items": {"type": "integer"}},
                ),
                ResponseDefinition(
                    status_code="default",
                    media_type="text/plain",
                    schema={"type": "string", "minLength": 1},
                ),
            ]
        )
    )

    validate_upstream_response(
        contract,
        UpstreamResult(200, "application/json", {"kind": "exact"}),
    )
    validate_upstream_response(
        contract,
        UpstreamResult(201, "application/vnd.example+json", [1, 2]),
    )
    validate_upstream_response(contract, UpstreamResult(204, "text/plain", "ok"))

    with pytest.raises(UpstreamResponseContractError):
        validate_upstream_response(
            contract,
            UpstreamResult(200, "application/json", {"kind": "wrong"}),
        )
    with pytest.raises(UpstreamResponseContractError):
        validate_upstream_response(
            contract,
            UpstreamResult(201, "application/vnd.example+json", ["wrong"]),
        )


@pytest.mark.parametrize(
    ("schema", "data"),
    [
        ({"type": "object"}, {"id": "one"}),
        ({"type": "array", "items": {"type": "string"}}, ["one"]),
        ({"type": "integer"}, 7),
    ],
)
def test_accepts_object_array_and_scalar_json_bodies(
    schema: dict[str, object], data: object
) -> None:
    contract = compile_response_contract(
        _tool(
            [
                ResponseDefinition(
                    status_code="200",
                    media_type="application/json",
                    schema=schema,
                )
            ]
        )
    )
    validate_upstream_response(contract, UpstreamResult(200, "application/json", data))


def test_rejects_unadvertised_binary_media_and_nonempty_no_content_response() -> None:
    json_contract = compile_response_contract(
        _tool([ResponseDefinition(status_code="200", media_type="application/json")])
    )
    with pytest.raises(UpstreamResponseContractError):
        validate_upstream_response(
            json_contract,
            UpstreamResult(200, "application/pdf", b"pdf"),
        )

    empty_contract = compile_response_contract(_tool([ResponseDefinition(status_code="204")]))
    validate_upstream_response(empty_contract, UpstreamResult(204, "text/plain", None))
    with pytest.raises(UpstreamResponseContractError):
        validate_upstream_response(empty_contract, UpstreamResult(204, "text/plain", "body"))


def test_invalid_or_duplicate_dispatch_contract_fails_during_runtime_load() -> None:
    with pytest.raises(RuntimeConfigurationError, match="invalid response schema"):
        compile_response_contract(
            _tool(
                [
                    ResponseDefinition(
                        status_code="200",
                        media_type="application/json",
                        schema={"type": "not-a-json-schema-type"},
                    )
                ]
            )
        )
    with pytest.raises(RuntimeConfigurationError, match="duplicate response"):
        compile_response_contract(
            _tool(
                [
                    ResponseDefinition(status_code="200", media_type="application/json"),
                    ResponseDefinition(status_code="200", media_type="application/json"),
                ]
            )
        )
