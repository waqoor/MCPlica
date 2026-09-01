import pytest
from pydantic import ValidationError

from app.schemas.build import OperationExclusionCreate


@pytest.mark.parametrize("field", ["operation_key", "reason"])
@pytest.mark.parametrize("value", [None, 42, True, [], {}])
def test_exclusions_reject_non_string_json_with_validation_errors(
    field: str, value: object
) -> None:
    data: dict[str, object] = {"operation_key": "GET /records", "reason": "Read-only integration"}
    data[field] = value
    with pytest.raises(ValidationError) as exc:
        OperationExclusionCreate.model_validate(data)
    assert exc.value.errors()[0]["loc"] == (field,)


def test_exclusion_length_is_checked_after_normalization() -> None:
    valid = OperationExclusionCreate(operation_key=" GET /records ", reason=" Not required ")
    assert valid.operation_key == "GET /records"
    assert valid.reason == "Not required"
    with pytest.raises(ValidationError):
        OperationExclusionCreate(operation_key="GET /records", reason="   no   ")
