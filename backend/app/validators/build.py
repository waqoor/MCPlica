from collections import Counter
from collections.abc import Mapping
from typing import cast
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, SchemaError
from mcp_contracts import CanonicalApi, MCPManifest
from mcp_contracts.json_types import JsonObject, JsonValue
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from app.domain.validation import FindingSeverity, ValidationFinding


def coverage_percent(*, expected_operations: int, generated_tools: int) -> float:
    if expected_operations < 0 or generated_tools < 0:
        raise ValueError("Coverage counts cannot be negative")
    if expected_operations == 0:
        return 100.0 if generated_tools == 0 else 0.0
    return round(generated_tools / expected_operations * 100, 2)


def validate_build(
    canonical: CanonicalApi,
    manifest: MCPManifest,
    *,
    excluded_operation_keys: frozenset[str],
    canonical_sha256: str,
    runtime_version: str,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    operations = {operation.key: operation for operation in canonical.operations}
    unknown_exclusions = excluded_operation_keys - set(operations)
    for operation_key in sorted(unknown_exclusions):
        findings.append(
            _finding(
                "EXCLUSION_UNKNOWN_OPERATION",
                FindingSeverity.ERROR,
                "coverage",
                f"Exclusion references unknown operation {operation_key}",
                operation_key=operation_key,
            )
        )
    expected = set(operations) - excluded_operation_keys
    generated = [tool.operation_key for tool in manifest.tools if tool.enabled]
    counts = Counter(generated)
    for operation_key, count in sorted(counts.items()):
        if count > 1:
            findings.append(
                _finding(
                    "DUPLICATE_OPERATION_MAPPING",
                    FindingSeverity.ERROR,
                    "coverage",
                    f"Operation maps to {count} generated tools",
                    operation_key=operation_key,
                )
            )
    generated_set = set(generated)
    for operation_key in sorted(expected - generated_set):
        findings.append(
            _finding(
                "EXPECTED_OPERATION_MISSING",
                FindingSeverity.ERROR,
                "coverage",
                "Expected source operation has no generated MCP tool",
                operation_key=operation_key,
                source_ref=operations[operation_key].provenance.operation,
            )
        )
    for operation_key in sorted(generated_set - expected):
        findings.append(
            _finding(
                "UNEXPECTED_TOOL_OPERATION",
                FindingSeverity.ERROR,
                "coverage",
                "Generated tool maps to an excluded or unknown operation",
                operation_key=operation_key,
            )
        )
    tool_names = [tool.name for tool in manifest.tools]
    duplicates = [name for name, count in Counter(tool_names).items() if count > 1]
    if duplicates:
        duplicate_names = [cast(JsonValue, name) for name in sorted(duplicates)]
        findings.append(
            _finding(
                "DUPLICATE_TOOL_NAME",
                FindingSeverity.ERROR,
                "manifest",
                "Manifest tool names are not unique",
                details={"tool_names": duplicate_names},
            )
        )

    server_ids = {server.id for server in manifest.servers}
    profile_ids = {profile.id for profile in manifest.auth_profiles}
    for tool in manifest.tools:
        operation = operations.get(tool.operation_key)
        if operation is None:
            continue
        if tool.request_mapping.method != operation.method:
            findings.append(_mapping_finding(operation, "METHOD_CHANGED", "HTTP method changed"))
        if tool.request_mapping.path != operation.path_template:
            findings.append(_mapping_finding(operation, "PATH_CHANGED", "Path template changed"))
        if tool.request_mapping.server_ref != operation.server_ref:
            findings.append(
                _mapping_finding(operation, "SERVER_CHANGED", "Upstream server mapping changed")
            )
        if tool.request_mapping.server_ref not in server_ids:
            findings.append(
                _mapping_finding(operation, "SERVER_UNKNOWN", "Tool references unknown server")
            )
        if tool.security_profile_ref and tool.security_profile_ref not in profile_ids:
            findings.append(
                _mapping_finding(
                    operation,
                    "AUTH_PROFILE_UNKNOWN",
                    "Tool references unknown authentication profile",
                )
            )
        source_required = {
            (parameter.location.value, parameter.name)
            for parameter in operation.parameters
            if parameter.required and parameter.location.value != "cookie"
        }
        mapped_required = {
            (mapping.target.value, mapping.source_name)
            for mapping in tool.request_mapping.parameters
            if mapping.required
        }
        if not source_required.issubset(mapped_required):
            missing_parameters: list[JsonValue] = [
                f"{location}:{name}" for location, name in sorted(source_required - mapped_required)
            ]
            findings.append(
                _mapping_finding(
                    operation,
                    "REQUIRED_PARAMETER_DROPPED",
                    "One or more required parameters were dropped",
                    details={"missing": missing_parameters},
                )
            )
        if (
            operation.request_body is not None
            and operation.request_body.required
            and (tool.request_mapping.body is None or not tool.request_mapping.body.required)
        ):
            findings.append(
                _mapping_finding(
                    operation,
                    "REQUIRED_BODY_DROPPED",
                    "Required request body became optional or absent",
                )
            )
        _check_schema(tool.input_schema, tool.operation_key, "input", findings)
        if tool.output_schema is not None:
            _check_schema(tool.output_schema, tool.operation_key, "output", findings)
        if not operation.description and not operation.summary:
            findings.append(
                _finding(
                    "SPARSE_SOURCE_DESCRIPTION",
                    FindingSeverity.WARNING,
                    "semantic",
                    "Source operation has no summary or description",
                    operation_key=operation.key,
                    source_ref=operation.provenance.operation,
                )
            )

    manifest_hosts = {_server_hostname(str(server.url)) for server in manifest.servers}
    if set(manifest.security.allowed_upstream_hosts) != manifest_hosts:
        findings.append(
            _finding(
                "UPSTREAM_ALLOWLIST_MISMATCH",
                FindingSeverity.ERROR,
                "security",
                "Runtime upstream host allowlist does not exactly match manifest servers",
            )
        )
    if manifest.build.canonical_sha256 != canonical_sha256:
        findings.append(
            _finding(
                "CANONICAL_HASH_MISMATCH",
                FindingSeverity.ERROR,
                "manifest",
                "Manifest canonical hash does not match the immutable snapshot",
            )
        )
    if set(manifest.build.source_version_ids) != {
        str(value) for value in canonical.provenance.source_version_ids
    }:
        findings.append(
            _finding(
                "SOURCE_BINDING_MISMATCH",
                FindingSeverity.ERROR,
                "manifest",
                "Manifest source versions do not match the canonical snapshot",
            )
        )
    try:
        compatible = Version(runtime_version) in SpecifierSet(manifest.runtime_compatibility)
    except (InvalidSpecifier, InvalidVersion):
        compatible = False
    if not compatible:
        findings.append(
            _finding(
                "RUNTIME_INCOMPATIBLE",
                FindingSeverity.ERROR,
                "protocol",
                "Configured generic runtime version is outside manifest compatibility",
                details={"runtime_version": runtime_version},
            )
        )
    expected_count = len(expected)
    generated_count = len(generated)
    if (
        coverage_percent(
            expected_operations=expected_count,
            generated_tools=generated_count,
        )
        != 100.0
    ):
        findings.append(
            _finding(
                "COVERAGE_INCOMPLETE",
                FindingSeverity.ERROR,
                "coverage",
                "Expected operation coverage is not 100 percent",
                details={
                    "expected_operations": expected_count,
                    "generated_tools": generated_count,
                },
            )
        )
    return findings


def _check_schema(
    schema: Mapping[str, object],
    operation_key: str,
    direction: str,
    findings: list[ValidationFinding],
) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        findings.append(
            _finding(
                "INVALID_JSON_SCHEMA",
                FindingSeverity.ERROR,
                "manifest",
                f"Generated {direction} JSON Schema is invalid: {exc.message}",
                operation_key=operation_key,
            )
        )


def _mapping_finding(
    operation: object,
    code: str,
    message: str,
    *,
    details: JsonObject | None = None,
) -> ValidationFinding:
    from mcp_contracts import CanonicalOperation

    assert isinstance(operation, CanonicalOperation)
    return _finding(
        code,
        FindingSeverity.ERROR,
        "compiler",
        message,
        operation_key=operation.key,
        source_ref=operation.provenance.operation,
        details=details,
    )


def _finding(
    code: str,
    severity: FindingSeverity,
    stage: str,
    message: str,
    *,
    operation_key: str | None = None,
    source_ref: object | None = None,
    details: JsonObject | None = None,
) -> ValidationFinding:
    from mcp_contracts import SourceRef

    return ValidationFinding(
        code=code,
        severity=severity,
        stage=stage,
        operation_key=operation_key,
        source_ref=source_ref if isinstance(source_ref, SourceRef) else None,
        message=message,
        details=details or {},
    )


def _server_hostname(url: str) -> str:
    hostname = urlsplit(url).hostname
    if hostname is None:
        raise ValueError("Validated manifest server URL has no hostname")
    return hostname.casefold()
