import pytest
from pydantic import ValidationError

from app.schemas.build import OperationExclusionCreate
from app.validators.build import coverage_percent, validate_runtime_manifest_size


def test_coverage_requires_all_expected_operations() -> None:
    assert coverage_percent(expected_operations=96, generated_tools=96) == 100.0
    assert coverage_percent(expected_operations=96, generated_tools=95) == 98.96
    assert coverage_percent(expected_operations=0, generated_tools=0) == 100.0


def test_operation_exclusion_requires_meaningful_normalized_reason() -> None:
    exclusion = OperationExclusionCreate(operation_key="  get_products  ", reason="  duplicate  ")
    assert exclusion.operation_key == "get_products"
    assert exclusion.reason == "duplicate"
    with pytest.raises(ValidationError):
        OperationExclusionCreate(operation_key="get_products", reason="   no  ")


def test_runtime_manifest_limit_uses_inclusive_exact_byte_boundary() -> None:
    payload = b"x" * 1_025

    assert validate_runtime_manifest_size(payload, maximum_bytes=len(payload)) == []
    finding = validate_runtime_manifest_size(
        payload,
        maximum_bytes=len(payload) - 1,
    )[0]
    assert finding.code == "MANIFEST_RUNTIME_SIZE_LIMIT_EXCEEDED"
    assert finding.details == {
        "actual_bytes": 1_025,
        "maximum_bytes": 1_024,
        "excess_bytes": 1,
    }
