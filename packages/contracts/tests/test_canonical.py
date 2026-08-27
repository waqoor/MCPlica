import json
from pathlib import Path

import pytest
from mcp_contracts import CanonicalApi
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]


def _canonical_fixture() -> dict[str, object]:
    return json.loads(
        ROOT.joinpath(
            "tests",
            "fixtures",
            "canonical",
            "schema-dialect-3.0-json.json",
        ).read_text(encoding="utf-8")
    )


def test_legacy_v1_operation_restores_its_selected_server_as_the_candidate() -> None:
    document = _canonical_fixture()
    operations = document["operations"]
    assert isinstance(operations, list)
    first = operations[0]
    assert isinstance(first, dict)
    expected = first["server_ref"]
    first.pop("server_candidates")

    canonical = CanonicalApi.model_validate(document)

    assert canonical.operations[0].server_candidates == [expected]


def test_legacy_v1_operation_without_any_server_evidence_fails_closed() -> None:
    document = _canonical_fixture()
    operations = document["operations"]
    assert isinstance(operations, list)
    first = operations[0]
    assert isinstance(first, dict)
    first.pop("server_candidates")
    first["server_ref"] = None

    with pytest.raises(ValidationError, match="require server_ref"):
        CanonicalApi.model_validate(document)
