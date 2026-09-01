from dataclasses import dataclass

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from mcp_contracts import MCPTool, ResponseDefinition

from app.clients.api_client import UpstreamResult
from app.executor.errors import RuntimeConfigurationError, UpstreamResponseContractError


@dataclass(frozen=True, slots=True)
class CompiledResponseDefinition:
    definition: ResponseDefinition
    validator: Draft202012Validator | None


def compile_response_contract(tool: MCPTool) -> tuple[CompiledResponseDefinition, ...]:
    compiled: list[CompiledResponseDefinition] = []
    identities: set[tuple[str, str | None]] = set()
    for definition in tool.responses:
        identity = (definition.status_code, definition.media_type)
        if identity in identities:
            raise RuntimeConfigurationError(
                f"Tool {tool.name!r} has duplicate response dispatch definitions"
            )
        identities.add(identity)
        validator: Draft202012Validator | None = None
        if definition.schema_ is not None:
            try:
                Draft202012Validator.check_schema(definition.schema_)
            except SchemaError as exc:
                raise RuntimeConfigurationError(
                    f"Tool {tool.name!r} has an invalid response schema"
                ) from exc
            validator = Draft202012Validator(definition.schema_)
        compiled.append(CompiledResponseDefinition(definition, validator))
    return tuple(compiled)


def validate_upstream_response(
    contract: tuple[CompiledResponseDefinition, ...],
    result: UpstreamResult,
) -> None:
    if result.is_error:
        return
    status = str(result.status_code)
    status_class = f"{status[0]}XX"
    for status_key in (status, status_class, "default"):
        candidates = [item for item in contract if item.definition.status_code == status_key]
        if not candidates:
            continue
        # Status specificity is resolved before media. An explicit response
        # cannot be bypassed through a range/default with a different media type.
        selected = _select_media(candidates, result.content_type, result.data)
        if selected is None:
            raise UpstreamResponseContractError()
        if selected.validator is not None:
            try:
                selected.validator.validate(  # pyright: ignore[reportUnknownMemberType]
                    result.data
                )
            except JSONSchemaValidationError as exc:
                raise UpstreamResponseContractError() from exc
        elif selected.definition.media_type is None and result.data is not None:
            raise UpstreamResponseContractError()
        return
    raise UpstreamResponseContractError()


def _select_media(
    candidates: list[CompiledResponseDefinition],
    actual: str,
    data: object,
) -> CompiledResponseDefinition | None:
    if data is None:
        without_media = [item for item in candidates if item.definition.media_type is None]
        if without_media:
            return without_media[0]
    scored = [
        (_media_specificity(item.definition.media_type, actual), item)
        for item in candidates
        if item.definition.media_type is not None
    ]
    matched = [item for score, item in scored if score >= 0]
    if not matched:
        return None
    return max(scored, key=lambda value: value[0])[1]


def _media_specificity(expected: str | None, actual: str) -> int:
    if expected is None:
        return -1
    if expected == actual:
        return 4
    expected_type, _, expected_subtype = expected.partition("/")
    actual_type, _, actual_subtype = actual.partition("/")
    if expected == "*/*":
        return 1
    if expected_type == actual_type and expected_subtype == "*":
        return 2
    if (
        expected_type == actual_type
        and expected_subtype.startswith("*+")
        and actual_subtype.endswith(expected_subtype[1:])
    ):
        return 3
    return -1
